import { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router';
import { MessageSquarePlus, PanelLeftOpen, RefreshCw, X, ShieldCheck, Target } from 'lucide-react';
import { ChatSessionList } from '@/components/ChatSessionList';
import { ModelPickerDialog } from '@/components/ModelPickerDialog';
import { ChatComposer } from '@/components/chat/ChatComposer';
import { ChatTranscript } from '@/components/chat/ChatTranscript';
import { ChatConnection } from '@/components/chat/ChatConnection';
import { ChatRequest } from '@/components/chat/ChatRequest';
import { readChatSession, useWebChat } from '@/components/chat/useWebChat';
import { useProfileScope } from '@/contexts/useProfileScope';
import { usePageHeader } from '@/contexts/usePageHeader';
import { api } from '@/lib/api';
import { readStoredWorkspace } from '@/lib/chat-workspaces';
import '@/components/chat/chat.css';

interface ChatPageProps { isActive?: boolean }
export default function ChatPage({ isActive = true }: ChatPageProps) {
  const { profile } = useProfileScope();
  const [scope, setScope] = useState(profile);
  const [, setParams] = useSearchParams();
  useEffect(() => {
    if (scope !== profile) {
      setParams(p => { const next = new URLSearchParams(p); next.delete('resume'); return next; }, { replace: true });
      setScope(profile);
    }
  }, [profile, scope, setParams]);
  if (scope !== profile) return <p role="status">Opening profile…</p>;
  return <ProfileChat key={profile} profile={profile} isActive={isActive} />;
}
interface ProfileChatProps { profile: string; isActive: boolean }
function ProfileChat({ profile, isActive }: ProfileChatProps) {
  const [params, setParams] = useSearchParams();
  const requested = params.get('resume') || '';
  const previous = useRef(requested);
  const [target, setTarget] = useState(() => requested || readChatSession(profile));
  const [version, setVersion] = useState(0);
  const [workspace] = useState(() => readStoredWorkspace(profile));
  const { setTitle } = usePageHeader();
  useEffect(() => {
    if (isActive) { setTitle('Chat'); return () => setTitle(null); }
  }, [isActive, setTitle]);
  useEffect(() => {
    if (isActive && previous.current !== requested) {
      previous.current = requested; setTarget(requested); setVersion(v => v + 1);
    }
  }, [isActive, requested]);
  function newChat() {
    previous.current = '';
    setParams(p => { const next = new URLSearchParams(p); next.delete('resume'); return next; });
    setTarget(''); setVersion(v => v + 1);
  }
  return <ChatConversation key={`${target}:${version}`} active={isActive} profile={profile} resume={target} workspace={workspace} onNew={newChat} />;
}
interface ChatConversationProps { active: boolean; profile: string; resume: string; workspace: string; onNew: () => void }
function ChatConversation({ active, profile, resume, workspace, onNew }: ChatConversationProps) {
  const [cwd] = useState(workspace);
  const chat = useWebChat({ profile, resume, cwd });
  const [historyOpen, setHistoryOpen] = useState(false);
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [modelLabel, setModelLabel] = useState('');
  const [modelNotice, setModelNotice] = useState('');
  const [controlsOpen, setControlsOpen] = useState(false);
  const [statusOpen, setStatusOpen] = useState(false);
  const [sideOpen, setSideOpen] = useState(false);
  const [sideVersion, setSideVersion] = useState(0);
  const activeRequest = chat.requests[0];
  const promptToolbar = <>
    <div className="chat-prompt-toolbar">
      <div className="chat-prompt-toolbar-group">
        <button type="button" className="chat-prompt-tool" aria-label={historyOpen ? 'Close chat history' : 'Open chat history'} title="Chat history" aria-expanded={historyOpen} onClick={() => setHistoryOpen(value => !value)}>{historyOpen ? <X size={16} /> : <PanelLeftOpen size={16} />}</button>
        <button type="button" className="chat-prompt-tool" aria-label="New chat" title="New chat" onClick={onNew}><MessageSquarePlus size={16} /></button>
      </div>
      <div className="chat-prompt-toolbar-spacer" />
      <button type="button" className={`chat-prompt-tool ${chat.info.yolo ? 'is-active' : ''}`} aria-label="Permissions" title="Permissions" aria-expanded={controlsOpen} onClick={() => { setStatusOpen(false); setControlsOpen(value => !value); }}><ShieldCheck size={16} /><span>Permissions</span></button>
      <button type="button" className="chat-prompt-tool" aria-label="Status" title="Session status" aria-expanded={statusOpen} onClick={() => { setControlsOpen(false); setStatusOpen(value => !value); }}><Target size={16} /><span>Status</span></button>
    </div>
    {controlsOpen && <div className="chat-control-popover" role="dialog" aria-label="Permissions and model controls">
      <strong>Permissions</strong>
      <p>YOLO skips approval prompts for guarded actions in this session.</p>
      <button type="button" className="chat-control-choice" onClick={() => { void chat.setControl('yolo', chat.info.yolo ? 'off' : 'on'); }}><ShieldCheck size={16} />{chat.info.yolo ? 'Turn YOLO off' : 'Enable YOLO for this session'}</button>
      <label>Fast mode<select value={chat.info.fast ? 'fast' : 'normal'} onChange={event => void chat.setControl('fast', event.target.value)}><option value="normal">Normal</option><option value="fast">Fast</option></select></label>
      <label>Reasoning<select value={chat.info.reasoning_effort || 'medium'} onChange={event => void chat.setControl('reasoning', event.target.value)}>{['none','minimal','low','medium','high','xhigh','max','ultra'].map(value => <option key={value} value={value}>{value}</option>)}</select></label>
    </div>}
    {statusOpen && <div className="chat-control-popover chat-status-popover" role="status">
      <strong>Session status</strong><p>{chat.state.busy ? chat.state.status || 'Working…' : 'Ready'} · {chat.info.model || 'Model unknown'}</p>
      {chat.info.usage?.context_percent != null && <p>Context {Math.round(chat.info.usage.context_percent)}% used{chat.info.usage.context_estimated ? ' (estimated)' : ''}</p>}
      <p>Goal: {chat.control.goal?.title || 'No active goal'}</p>
      {chat.control.goal && <button type="button" className="chat-control-choice" onClick={() => void chat.controlAction(chat.control.goal?.status === 'paused' ? 'goal.resume' : 'goal.pause')}>
        {chat.control.goal.status === 'paused' ? 'Resume goal' : 'Pause goal'}
      </button>}
    </div>}
  </>;
  return <div className={`native-chat ${historyOpen ? 'native-chat--history-open' : ''}`}>
    {historyOpen && <button className="chat-history-backdrop" aria-label="Close chat history" onClick={() => setHistoryOpen(false)} />}
    <aside id="chat-history-panel" className="chat-history" aria-label="Chat history" aria-hidden={!historyOpen}><ChatSessionList refreshKey={chat.state.busy ? undefined : chat.state.messages.length} activeSessionId={chat.storedId} profile={profile} onNewChat={onNew} onPicked={() => setHistoryOpen(false)} /></aside>
    <section className="chat-main" aria-label="Chat with Agent Scientist">
      {(!chat.online || chat.loading) && <div className="chat-connection" role="status"><span>{chat.loading ? 'Connecting to your workspace…' : 'Chat disconnected. Reconnect to check the latest state.'}</span>{!chat.loading && <button onClick={() => void chat.reconnect()}><RefreshCw size={14} />Reconnect</button>}</div>}
      {sideOpen ? <div className="chat-side-surface">
        <SideConversation key={sideVersion} profile={profile} cwd={cwd} parentSessionId={chat.storedId} onClose={() => setSideOpen(false)} />
      </div> : <>
      <ChatTranscript state={chat.state} onSuggestion={chat.setPrefill} active={active} sessionId={chat.storedId || undefined}>
        {chat.connection && chat.online && <ChatConnection key={chat.connection.op_id} operation={chat.connection} onAnswer={chat.answerConnection} />}
        {activeRequest && chat.online && <ChatRequest key={activeRequest.id} request={activeRequest} onAnswer={result => chat.answer(activeRequest, result)} />}
      </ChatTranscript>
      <ChatComposer disabled={!chat.online || chat.loading} busy={chat.state.busy} prefill={chat.prefill}
        contextPercent={chat.info.usage?.context_percent ?? null}
        contextEstimated={Boolean(chat.info.usage?.context_estimated)}
        onCompact={() => void chat.send('/compact')}
        onQueue={text => chat.send(text, [], true)}
        onSteer={text => chat.steer(text)}
        commands={chat.commands}
        toolbar={promptToolbar}
        modelLabel={modelLabel || chat.info.model || 'Choose model'} onChooseModel={() => { setModelNotice(''); setModelPickerOpen(true); }} onSend={async (text, files) => {
        if (/^\/(new|reset)\s*$/i.test(text)) { onNew(); return true; }
        if (/^\/side\s*$/i.test(text)) { setHistoryOpen(false); setSideVersion(value => value + 1); setSideOpen(true); return true; }
        return chat.send(text, files);
      }} onStop={chat.stop} />
      {modelNotice && <div className="chat-model-notice" role="status">{modelNotice}</div>}
      </>}
      {modelPickerOpen && <ModelPickerDialog
        loader={() => api.getModelOptions(profile)}
        title="Choose model"
        onApply={async ({ provider, model, confirmExpensiveModel, persistGlobal }) => {
          const result = persistGlobal
            ? await api.setModelAssignment({ confirm_expensive_model: confirmExpensiveModel, scope: 'main', provider, model }, profile)
            : await chat.setModel(provider, model, confirmExpensiveModel);
          if (!result.confirm_required && persistGlobal) {
            setModelNotice(`${model} saved as the default for new conversations.`);
          } else if (!result.confirm_required) {
            setModelLabel(model);
            setModelNotice('deferred' in result && result.deferred ? `${model} will be used after the current response.` : `${model} is now active in this conversation.`);
          }
          return result;
        }}
        onClose={() => setModelPickerOpen(false)}
      />}
    </section>
  </div>;
}

function SideConversation({ profile, cwd, parentSessionId, onClose }: { profile: string; cwd: string; parentSessionId: string; onClose: () => void }) {
  const chat = useWebChat({ profile, resume: '', cwd, storageKey: `${profile}:side`, parentSessionId });
  const [modelPickerOpen, setModelPickerOpen] = useState(false);
  const [modelLabel, setModelLabel] = useState('');
  const [modelNotice, setModelNotice] = useState('');
  const toolbar = <div className="chat-prompt-toolbar">
    <span className="chat-side-label">SIDE CONVERSATION</span>
    <span className="chat-prompt-toolbar-spacer" />
    <button type="button" className="chat-prompt-tool chat-prompt-close" aria-label="Close side conversation" title="Close side conversation" onClick={onClose}><X size={17} /></button>
  </div>;
  return <>
    <ChatTranscript state={chat.state} onSuggestion={chat.setPrefill} active sessionId={chat.storedId || undefined} />
    {modelNotice && <div className="chat-model-notice" role="status">{modelNotice}</div>}
    <ChatComposer disabled={!chat.online || chat.loading} busy={chat.state.busy} prefill={chat.prefill}
      contextPercent={chat.info.usage?.context_percent ?? null} contextEstimated={Boolean(chat.info.usage?.context_estimated)}
      onCompact={() => void chat.send('/compact')} onQueue={text => chat.send(text, [], true)} onSteer={text => chat.steer(text)}
      commands={chat.commands}
      toolbar={toolbar}
      modelLabel={modelLabel || chat.info.model || 'Choose model'}
      onChooseModel={() => { setModelNotice(''); setModelPickerOpen(true); }}
      onSend={(text, files) => chat.send(text, files)} onStop={chat.stop} />
    {modelPickerOpen && <ModelPickerDialog loader={() => api.getModelOptions(profile)} title="Choose model"
      onApply={async ({ provider, model, confirmExpensiveModel, persistGlobal }) => {
        const result = persistGlobal
          ? await api.setModelAssignment({ confirm_expensive_model: confirmExpensiveModel, scope: 'main', provider, model }, profile)
          : await chat.setModel(provider, model, confirmExpensiveModel);
        if (!result.confirm_required && persistGlobal) setModelNotice(`${model} saved as the default for new conversations.`);
        else if (!result.confirm_required) { setModelLabel(model); setModelNotice('deferred' in result && result.deferred ? `${model} will be used after the current response.` : `${model} is now active in this conversation.`); }
        return result;
      }} onClose={() => setModelPickerOpen(false)} />}
  </>;
}
