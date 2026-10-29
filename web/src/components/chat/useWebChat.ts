import { useEffect, useReducer, useRef, useState } from 'react';
import { looksLikeSlashCommand, parseSlashCommand, parseCommandDispatch, JsonRpcGatewayError, type ServerRequest, type SessionResumeResult, type SessionLiveInfo, type SlashExecResult, type GatewayEvent, type ConnectionRequestPayload, type ConnectionAnswer, type ConnectionRespondResult } from '@sci/shared';
import { GatewayClient } from '@/lib/gatewayClient';
import { chatReducer, emptyChat } from '@/lib/web-chat-state';

const messageOf = (error: unknown) => error instanceof Error ? error.message : String(error);
const secretMethods = new Set(['sudo', 'secret', 'vault.unlock_prompt', 'vault.code', 'vault.save_login']);
export const chatStorageKey = (profile: string) => `sci-web-chat:${profile || 'default'}`;
export function readChatSession(profile: string): string {
  try { return sessionStorage.getItem(chatStorageKey(profile)) || ''; } catch { return ''; }
}
function rememberSession(profile: string, id: string) {
  try { sessionStorage.setItem(chatStorageKey(profile), id); } catch { /* Private browsing can disable storage. */ }
}
interface WebChatOptions { profile: string; resume: string; cwd: string }

export function useWebChat({ profile, resume, cwd }: WebChatOptions) {
  const [state, dispatch] = useReducer(chatReducer, emptyChat);
  const [online, setOnline] = useState(false);
  const [loading, setLoading] = useState(true);
  const [storedId, setStoredId] = useState(resume);
  const [info, setInfo] = useState<SessionLiveInfo>({});
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
        const result = await gw.request<SessionResumeResult>(resuming ? 'session.resume' : 'session.create', {
          profile, source: 'web', close_on_disconnect: false,
          ...(stored.current ? { session_id: stored.current } : cwd ? { cwd } : {}),
        });
        if (cancelled) { gw.close(); return; }
        runtime.current = result.session_id;
        stored.current = result.stored_session_id || result.session_key || stored.current;
        setStoredId(stored.current);
        // Empty drafts have no durable DB row; do not restore one after a server restart.
        rememberSession(profile, resuming ? stored.current : '');
        setInfo(result.info);
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
  }, [profile, resume, cwd]);

  async function send(text: string, images: File[] = []): Promise<boolean> {
    const gw = gateway.current;
    if (!gw || !online || locked.current || !runtime.current) return false;
    locked.current = true;
    setPrefill('');
    dispatch({ type: 'user', text });
    const params = { session_id: runtime.current, profile };
    try {
      let prompt = text;
      if (looksLikeSlashCommand(text)) {
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
      rememberSession(profile, stored.current);
      await gw.request('prompt.submit', { ...params, text: prompt, surface: 'web' });
      return true;
    } catch (error) {
      if (alive.current) {
        setOnline(false);
        dispatch({ type: 'error', text: `${messageOf(error)} Reconnect to verify the conversation before sending again. No automatic retry was attempted.` });
      }
      return false;
    }
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
  return { connection, answerConnection, setPrefill, state, online, loading, storedId, info, requests, prefill, send, stop, answer, reconnect: () => reconnect.current() };
}
