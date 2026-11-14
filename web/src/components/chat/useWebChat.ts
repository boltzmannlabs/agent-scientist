import { useEffect, useReducer, useRef, useState } from 'react';
import { looksLikeSlashCommand, parseSlashCommand, parseCommandDispatch, JsonRpcGatewayError, type ServerRequest, type SessionResumeResult, type SessionLiveInfo, type SlashExecResult, type GatewayEvent, type ConnectionRequestPayload, type ConnectionAnswer, type ConnectionRespondResult, type SessionControlReadResult, type SessionControlSnapshot, type CommandsCatalogResult, type ConfigSetResult } from '@sci/shared';
import { GatewayClient } from '@/lib/gatewayClient';
import { chatReducer, emptyChat } from '@/lib/web-chat-state';

const messageOf = (error: unknown) => error instanceof Error ? error.message : String(error);
const secretMethods = new Set(['sudo', 'secret', 'vault.unlock_prompt', 'vault.code', 'vault.save_login']);
const WEB_SLASH_SUGGESTIONS = new Set(['/side', '/compact', '/goal']);
export const chatStorageKey = (profile: string) => `sci-web-chat:${profile || 'default'}`;
export function readChatSession(profile: string): string {
  try { return sessionStorage.getItem(chatStorageKey(profile)) || ''; } catch { return ''; }
}
function rememberSession(profile: string, id: string) {
  try { sessionStorage.setItem(chatStorageKey(profile), id); } catch { /* Private browsing can disable storage. */ }
}
interface WebChatOptions { profile: string; resume: string; cwd: string; storageKey?: string; parentSessionId?: string }

export function useWebChat({ profile, resume, cwd, storageKey = profile, parentSessionId }: WebChatOptions) {
  const [state, dispatch] = useReducer(chatReducer, emptyChat);
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [storedId, setStoredId] = useState(resume);
  const [info, setInfo] = useState<SessionLiveInfo>({});
  const [control, setSessionControl] = useState<SessionControlSnapshot>({ goal: null, loop: null, heartbeat: null, revision: '', updated_at: 0 });
  const [commands, setCommands] = useState<Array<[string, string]>>([]);
  const [requests, setRequests] = useState<ServerRequest[]>([]);
  const [prefill, setPrefill] = useState('');
  const [connection, setConnection] = useState<ConnectionRequestPayload | null>(null);
  const gateway = useRef<GatewayClient | null>(null);
  const runtime = useRef('');
  const stored = useRef(resume);
  const locked = useRef(false);
  const alive = useRef(true);
  const reconnect = useRef<() => Promise<void>>(async () => {});

  useEffect(() => {
    alive.current = true;
    const gw = new GatewayClient(); gateway.current = gw;
    let cancelled = false;
    let hydrating = true;
    const buffered: GatewayEvent[] = [];
    function event(ev: GatewayEvent) {
      if (hydrating) { buffered.push(ev); return; }
      if (ev.session_id !== runtime.current) return;
      const p = (ev.payload || {}) as Record<string, unknown>;
      const text = typeof p.text === 'string' ? p.text : '';
      const handlers: Record<string, () => void> = {
        'message.delta': () => dispatch({ type: 'delta', text }),
        'message.interim': () => dispatch({ type: 'interim', text }),
        'message.complete': () => { locked.current = false; dispatch({ type: 'complete', text, status: String(p.status || ''), error: String(p.error || p.failure_reason || p.warning || '') }); },
        'tool.start': () => dispatch({ type: 'tool', id: String(p.tool_id), name: String(p.name), text: String(p.preview || p.context || ''), running: true }),
        'tool.complete': () => dispatch({ type: 'tool', id: String(p.tool_id), name: String(p.name), text: String(p.summary || p.result_text || ''), running: false }),
        'tool.generating': () => dispatch({ type: 'status', text: `Preparing ${String(p.name)}…` }),
        'status.update': () => dispatch({ type: 'status', text }),
        'session.info': () => setInfo(prev => ({ ...prev, ...p })),
        'session.control.update': () => { if (p.control && typeof p.control === 'object') setSessionControl(p.control as SessionControlSnapshot); },
        'error': () => { locked.current = false; dispatch({ type: 'error', text: String(p.message || 'The request failed.') }); },
        'notice': () => dispatch({ type: 'notice', text: String(p.message || '') }),
        'connection.request': () => setConnection(p as unknown as ConnectionRequestPayload),
        'connection.update': () => setConnection(prev => p.settled ? null : prev ? { ...prev, ...p } : null),
        'request.cancel': () => setRequests(prev => prev.filter(r => r.id !== p.id && r.id !== p.request_id)),
      };
      handlers[ev.type]?.();
    }
    const subscriptions = [
      gw.onAny(event),
      gw.onState(connection => {
        if (cancelled) return;
        if (connection === 'closed' || connection === 'error') {
          setOnline(false); setLoading(false);
          dispatch({ type: 'notice', text: 'Connection lost. Work may still be running. Reconnect to check its status; your message will not be resent.' });
          setRequests([]);
        }
      }),
      gw.onRequest(request => {
        if (cancelled || (!hydrating && request.params.session_id !== runtime.current)) return false;
        if (!['approval', 'clarify'].includes(request.method) && !secretMethods.has(request.method)) {
          request.fail(-32601, `This browser does not support the ${request.method} interaction.`);
          dispatch({ type: 'notice', text: `The ${request.method} interaction is unavailable in this browser. No approval was granted.` });
          return true;
        }
        setRequests(prev => [...prev.filter(r => r.id !== request.id), request]);
        return true;
      }),
    ];
    async function connect() {
      if (cancelled) return;
      setLoading(true); setOnline(false); hydrating = true;
      try {
        await gw.connect();
        if (cancelled) { gw.close(); return; }
        const resuming = Boolean(stored.current);
        const method = resuming ? 'session.resume' : parentSessionId ? 'session.branch_stored' : 'session.create';
        const result = await gw.request<SessionResumeResult>(method, {
          profile, source: 'web', close_on_disconnect: false,
          ...(parentSessionId && !resuming ? { parent_session_id: parentSessionId } : {}),
          ...(stored.current ? { session_id: stored.current } : cwd ? { cwd } : {}),
        });
        if (cancelled) { gw.close(); return; }
        runtime.current = result.session_id;
        stored.current = result.stored_session_id || result.session_key || stored.current;
        setStoredId(stored.current);
        // Empty drafts have no durable DB row; do not restore one after a server restart.
        rememberSession(storageKey, resuming ? stored.current : '');
        setInfo(result.info);
        void gw.request<SessionControlReadResult>('session.control.read', { profile, session_id: runtime.current }).then(snapshot => setSessionControl(snapshot.control)).catch(() => {});
        void gw.request<CommandsCatalogResult>('commands.catalog', { profile, session_id: runtime.current }).then(catalog => {
          const pairs = (catalog.pairs || []).filter(pair => pair.length >= 1);
          const suggestions = pairs
            .filter(pair => WEB_SLASH_SUGGESTIONS.has(String(pair[0]).toLowerCase()))
            .map(pair => [pair[0], pair[1] || ''] as [string, string]);
          // The command registry exposes /compact as an alias of /compress, so
          // add the requested web-facing alias while preserving its native dispatch.
          const compress = pairs.find(pair => String(pair[0]).toLowerCase() === '/compress');
          if (compress && !suggestions.some(([name]) => name.toLowerCase() === '/compact')) {
            suggestions.push(['/compact', compress[1] || '']);
          }
          setCommands(suggestions.sort(([left], [right]) => left.localeCompare(right)));
        }).catch(() => {});
        setConnection(result.pending_connection || null);
        setRequests(prev => prev.filter(r => r.params.session_id === runtime.current));
        locked.current = Boolean(result.running || result.inflight?.streaming);
        dispatch({ type: 'hydrate', messages: result.messages || [], stream: result.inflight?.assistant,
          busy: locked.current, error: result.inflight?.error || result.info.credential_warning || '' });
        hydrating = false;
        // Resume's transcript/inflight snapshot supersedes replayed token chunks.
        // Full completion events still settle a turn that finished during hydration.
        buffered.splice(0).filter(ev => !ev.replayed && !['message.delta', 'message.interim'].includes(ev.type)).forEach(event);
        setOnline(true);
      } catch (error) {
        if (!cancelled) dispatch({ type: 'error', text: `Chat could not connect: ${messageOf(error)}` });
      } finally { if (!cancelled) setLoading(false); }
    }
    reconnect.current = connect;
    void connect();
    return () => {
      cancelled = true; alive.current = false;
      subscriptions.forEach(unsubscribe => unsubscribe());
      gw.close(); gateway.current = null;
    };
    // A keyed ChatConversation owns exactly one profile and initial resume target.
  }, [profile, resume, cwd, storageKey, parentSessionId]);

  async function send(text: string, images: File[] = [], queued = false): Promise<boolean> {
    const gw = gateway.current;
    if (!gw || !online || (locked.current && !queued) || !runtime.current) return false;
    if (!queued) locked.current = true;
    setPrefill('');
    if (!queued) dispatch({ type: 'user', text });
    const params = { session_id: runtime.current, profile };
    try {
      let prompt = text;
      if (looksLikeSlashCommand(text)) {
        if (queued) throw new Error('Slash commands cannot be queued. Send the command after the current response.');
        let response: SlashExecResult;
        try { response = await gw.request<SlashExecResult>('slash.exec', { ...params, command: text }); }
        catch (error) {
          if (!(error instanceof JsonRpcGatewayError) || error.code !== 4018) throw error;
          response = await gw.request<SlashExecResult>('command.dispatch', { ...params, ...parseSlashCommand(text) });
        }
        if (!alive.current) return false;
        const action = parseCommandDispatch(response);
        if (action?.type === 'prefill') {
          setPrefill(action.message); locked.current = false;
          dispatch({ type: 'complete', text: action.notice || 'Complete the request below, then send it.' }); return true;
        }
        if (action?.type === 'send' || action?.type === 'skill') prompt = action.message || text;
        else {
          locked.current = false;
          dispatch({ type: 'complete', text: response.output || response.message || response.notice || response.warning || (action?.type === 'alias' ? `Use ${action.target} to continue.` : 'Command completed.') });
          return true;
        }
      }
      for (const file of images) {
        const encoded = await new Promise<string>((resolve, reject) => {
          const reader = new FileReader(); reader.onload = () => resolve(String(reader.result).split(',')[1]);
          reader.onerror = () => reject(new Error(`Could not read ${file.name}`)); reader.readAsDataURL(file);
        });
        if (!alive.current) return false;
        await gw.request('image.attach_bytes', { ...params, filename: file.name, content_base64: encoded });
      }
      if (!alive.current) return false;
      // Persist the target before delivery so refresh during a pending request
      // resumes this conversation instead of silently creating another one.
      rememberSession(storageKey, stored.current);
      await gw.request('prompt.submit', { ...params, text: prompt, surface: 'web', ...(queued ? { queued: true } : {}) });
      if (queued) dispatch({ type: 'queued', text: prompt });
      return true;
    } catch (error) {
      if (alive.current) {
        if (queued) dispatch({ type: 'notice', text: `Message was not queued: ${messageOf(error)}. The active response is still running.` });
        else {
          setOnline(false);
          dispatch({ type: 'error', text: `${messageOf(error)} Reconnect to verify the conversation before sending again. No automatic retry was attempted.` });
        }
      }
      return false;
    }
  }
  async function steer(text: string): Promise<boolean> {
    const gw = gateway.current;
    if (!gw || !online || !runtime.current || !locked.current) return false;
    try {
      const result = await gw.request<{ status: string }>('session.steer', { session_id: runtime.current, profile, text });
      if (result.status === 'rejected') { dispatch({ type: 'notice', text: 'The active response could not be steered. Your message was not applied.' }); return false; }
      dispatch({ type: 'queued', text: `/steer ${text}` });
      return true;
    } catch (error) { dispatch({ type: 'notice', text: `Steer failed: ${messageOf(error)}` }); return false; }
  }
  async function setChatControl(key: 'yolo' | 'fast' | 'reasoning', value: string) {
    const gw = gateway.current;
    if (!gw || !online || !runtime.current) return;
    try {
      const result = await gw.request<{ info?: SessionLiveInfo }>('config.set', { profile, session_id: runtime.current, key, value, scope: 'session' });
      if (result.info) setInfo(prev => ({ ...prev, ...result.info }));
      if (key === 'yolo') setInfo(prev => ({ ...prev, yolo: value !== 'off' }));
      if (key === 'fast') setInfo(prev => ({ ...prev, fast: value === 'fast' }));
      if (key === 'reasoning') setInfo(prev => ({ ...prev, reasoning_effort: value }));
    } catch (error) { dispatch({ type: 'notice', text: `${key} setting was not changed: ${messageOf(error)}` }); }
  }
  async function setModel(provider: string, model: string, confirmExpensiveModel = false): Promise<ConfigSetResult> {
    const gw = gateway.current;
    if (!gw || !online || !runtime.current) throw new Error('Chat is not connected. Reconnect before changing the model.');
    const result = await gw.request<ConfigSetResult>('config.set', {
      profile, session_id: runtime.current, key: 'model',
      value: `${model} --provider ${provider}`, confirm_expensive_model: confirmExpensiveModel,
    });
    if (!result.confirm_required) setInfo(prev => ({ ...prev, model, provider }));
    return result;
  }
  async function controlAction(action: string) {
    const gw = gateway.current;
    if (!gw || !online || !runtime.current) return;
    try { const result = await gw.request<{ control: SessionControlSnapshot }>('session.control', { profile, session_id: runtime.current, action }); setSessionControl(result.control); }
    catch (error) { dispatch({ type: 'notice', text: `Control action failed: ${messageOf(error)}` }); }
  }
  async function stop() {
    try {
      dispatch({ type: 'status', text: 'Stopping…' });
      const result = await gateway.current?.request<{ status: string }>('session.interrupt', { session_id: runtime.current, profile });
      if (result?.status === 'not_interrupted') {
        locked.current = false;
        dispatch({ type: 'complete' });
        dispatch({ type: 'notice', text: 'There is no active response to stop.' });
      }
    } catch (error) {
      dispatch({ type: 'status', text: 'Stop not confirmed' });
      dispatch({ type: 'notice', text: `Could not confirm stopping: ${messageOf(error)}` });
    }
  }
  function answer(request: ServerRequest, result: Record<string, unknown>) {
    if (!online) return;
    request.respond(result);
    setRequests(prev => prev.filter(r => r.id !== request.id));
  }
  async function answerConnection(result: ConnectionAnswer) {
    if (!online || !connection) throw new Error('Reconnect before answering.');
    const response = await gateway.current!.request<ConnectionRespondResult>('connection.respond', {
      profile, owner: { type: 'session', session_id: runtime.current }, op_id: connection.op_id, result,
    });
    if (response.settled) setConnection(null);
  }
  return { connection, answerConnection, setPrefill, state, online, loading, storedId, info, control, commands, requests, prefill, send, steer, setControl: setChatControl, setModel, controlAction, stop, answer, reconnect: () => reconnect.current() };
}
