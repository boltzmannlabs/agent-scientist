import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router';
import { MessageSquarePlus, PanelLeftClose, PanelLeftOpen, RefreshCw } from 'lucide-react';
import { ChatSessionList } from '@/components/ChatSessionList';
import { ChatComposer } from '@/components/chat/ChatComposer';
import { ChatTranscript } from '@/components/chat/ChatTranscript';
import { ChatConnection } from '@/components/chat/ChatConnection';
import { ChatRequest } from '@/components/chat/ChatRequest';
import { readChatSession, useWebChat } from '@/components/chat/useWebChat';
import { useProfileScope } from '@/contexts/useProfileScope';
import { usePageHeader } from '@/contexts/usePageHeader';
import { readStoredWorkspace, writeStoredWorkspace } from '@/lib/chat-workspaces';
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
  const [workspace, setWorkspace] = useState(() => readStoredWorkspace(profile));
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
  return <ChatConversation key={`${target}:${version}`} profile={profile} resume={target} workspace={workspace} onWorkspace={cwd => { setWorkspace(cwd); writeStoredWorkspace(profile, cwd); }} onNew={newChat} />;
}
interface ChatConversationProps { profile: string; resume: string; workspace: string; onWorkspace: (cwd: string) => void; onNew: () => void }
function ChatConversation({ profile, resume, workspace, onWorkspace, onNew }: ChatConversationProps) {
  const [cwd] = useState(workspace);
  const chat = useWebChat({ profile, resume, cwd });
  const [historyOpen, setHistoryOpen] = useState(false);
  const activeRequest = chat.requests[0];
  return <div className={`native-chat ${historyOpen ? 'native-chat--history-open' : ''}`}>
    <aside className="chat-history" aria-label="Chat history"><ChatSessionList refreshKey={chat.state.busy ? undefined : chat.state.messages.length} activeSessionId={chat.storedId} profile={profile} onNewChat={onNew} onPicked={() => setHistoryOpen(false)} workspaceCwd={workspace} onWorkspaceChange={onWorkspace} /></aside>
    <section className="chat-main" aria-label="Chat with Agent Scientist">
      <header className="chat-toolbar">
        <button className="chat-icon-button chat-history-toggle" aria-label="Toggle chat history" aria-expanded={historyOpen} onClick={() => setHistoryOpen(v => !v)}>{historyOpen ? <PanelLeftClose size={20} /> : <PanelLeftOpen size={20} />}</button>
        <div><strong>Agent Scientist</strong><span className="chat-model">{chat.info.model || 'Your configured model'}{profile ? ` · ${profile}` : ''}</span></div>
        <Link className="chat-model-settings" to="/models">Model settings</Link>
        <button className="chat-icon-button" aria-label="New chat" title="New chat" onClick={onNew}><MessageSquarePlus size={21} /></button>
      </header>
      {(!chat.online || chat.loading) && <div className="chat-connection" role="status"><span>{chat.loading ? 'Connecting to your workspace…' : 'Chat disconnected. Reconnect to check the latest state.'}</span>{!chat.loading && <button onClick={() => void chat.reconnect()}><RefreshCw size={14} />Reconnect</button>}</div>}
      <ChatTranscript state={chat.state} onSuggestion={chat.setPrefill}>
        {chat.connection && chat.online && <ChatConnection key={chat.connection.op_id} operation={chat.connection} onAnswer={chat.answerConnection} />}
        {activeRequest && chat.online && <ChatRequest key={activeRequest.id} request={activeRequest} onAnswer={result => chat.answer(activeRequest, result)} />}
      </ChatTranscript>
      <ChatComposer disabled={!chat.online || chat.loading} busy={chat.state.busy} prefill={chat.prefill} onSend={async (text, files) => {
        if (/^\/(new|reset)\s*$/i.test(text)) { onNew(); return true; }
        return chat.send(text, files);
      }} onStop={chat.stop} />
    </section>
  </div>;
}
