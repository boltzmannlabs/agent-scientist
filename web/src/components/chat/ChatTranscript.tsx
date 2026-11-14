import { useEffect, useMemo, useRef, useState } from 'react';
import { Check, ChevronDown, Copy, LoaderCircle } from 'lucide-react';
import { BoltzmannParticleLogo } from '@/components/BoltzmannParticleLogo';
import { Markdown } from '@/components/Markdown';
import { copyTextToClipboard } from '@/lib/clipboard';
import type { WebChatState } from '@/lib/web-chat-state';
import type { ReactNode } from 'react';
import { useProfileScope } from '@/contexts/useProfileScope';
import { OutputFileContext } from '@/components/files/output-file-context';
import { OutputFile } from '@/components/files/OutputFile';
import { outputFilesInResult, type OutputFileScope } from '@/lib/output-files';

interface ChatTranscriptProps { state: WebChatState; children?: ReactNode; onSuggestion: (text: string) => void; active?: boolean; sessionId?: string }
export function ChatTranscript({ state, children, onSuggestion, active = true, sessionId }: ChatTranscriptProps) {
  const { profile, currentProfile } = useProfileScope();
  const fileScope = useMemo(() => ({ profile: profile || currentProfile, sessionId }), [profile, currentProfile, sessionId]);
  const scroll = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [copied, setCopied] = useState('');
  const [copyError, setCopyError] = useState('');
  useEffect(() => {
    if (!scroll.current) return;
    // Empty-chat connection updates must not scroll the welcome logo out of view.
    if (state.messages.length === 0 && !state.stream) scroll.current.scrollTop = 0;
    else if (pinned.current) scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [state.messages, state.stream, state.status, children]);
  async function copy(id: string, text: string) {
    try { if (!await copyTextToClipboard(text)) throw new Error('Clipboard unavailable'); setCopied(id); setCopyError(''); }
    catch { setCopyError('Could not copy. Select the response text and copy it manually.'); }
  }
  return <OutputFileContext.Provider value={fileScope}><div className="chat-scroll" ref={scroll} onScroll={() => {
    const e = scroll.current; if (e) pinned.current = e.scrollHeight - e.scrollTop - e.clientHeight < 100;
  }}>
    <div className="chat-transcript" role="log" aria-label="Conversation" aria-live="off">
      {state.messages.length === 0 && !state.stream && <div className="chat-welcome">
        <BoltzmannParticleLogo active={active && !state.busy} />
        <p className="chat-eyebrow">YOUR SCIENTIFIC WORKSPACE</p>
        <h1>What would you like to explore?</h1>
        <p>Ask a question, explore your research, or work through an idea together.</p>
        <div className="chat-suggestions">{[
          ['Explore the literature', 'Help me review the literature on '],
          ['Understand your data', 'Help me understand my dataset. Start by asking what data and files I have.'],
          ['Plan your next step', 'Help me plan my research. Ask about my objective and available resources first.'],
        ].map(([label, prompt]) => <button key={label} onClick={() => onSuggestion(prompt)}>{label}</button>)}</div>
      </div>}
      {state.messages.map(message => message.role === 'tool' ? <div key={message.id}><details className="chat-tool">
        <summary>{message.running ? <LoaderCircle size={15} className="chat-spinning" /> : <Check size={15} />}<span>{message.name || 'Tool activity'}</span><ChevronDown size={14} /></summary>
        <pre>{message.text || (message.running ? 'Running…' : 'Finished. No text output returned.')}</pre>
      </details>{!message.running && <ToolFiles text={message.text} scope={fileScope} />}</div> : <article className={`chat-message chat-message--${message.role}`} key={message.id} aria-label={message.role === 'user' ? 'You' : 'Agent Scientist'}>
        {message.role === 'assistant' && <div className="chat-speaker">Agent Scientist</div>}
        <div className="chat-message-content">{message.role === 'user' ? <p>{message.text}</p> : <Markdown content={message.text} />}</div>
        {message.role === 'assistant' && <button className="chat-copy" aria-label="Copy response" onClick={() => void copy(message.id, message.text)}>{copied === message.id ? <Check size={14} /> : <Copy size={14} />}{copied === message.id ? 'Copied' : 'Copy'}</button>}
      </article>)}
      {state.stream && <article className="chat-message chat-message--assistant" aria-label="Agent Scientist reply"><div className="chat-speaker">Agent Scientist</div><Markdown content={state.stream} streaming={state.busy} /></article>}
      {state.busy && <p role="status" className="chat-progress"><LoaderCircle size={15} className="chat-spinning" />{state.status || 'Working…'}</p>}
      {children}
      {(state.error || copyError) && <div className="chat-error" role="alert">{state.error || copyError}</div>}
    </div>
  </div></OutputFileContext.Provider>;
}

function ToolFiles({ text, scope }: { text: string; scope: OutputFileScope }) {
  const files = useMemo(() => outputFilesInResult(text), [text]);
  return files.length ? <div aria-label="Files referenced by tool result" className="flex flex-wrap gap-2 py-2">
    {files.map(file => <OutputFile key={file.path} file={file} scope={scope} />)}
    {files.length === 20 && <small>Up to 20 references shown. Use Show in Files to browse the complete folder.</small>}
  </div> : null;
}
