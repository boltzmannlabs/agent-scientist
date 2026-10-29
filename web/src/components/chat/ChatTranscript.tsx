import { useEffect, useRef, useState } from 'react';
import { Check, ChevronDown, Copy, FlaskConical, LoaderCircle } from 'lucide-react';
import { Markdown } from '@/components/Markdown';
import { copyTextToClipboard } from '@/lib/clipboard';
import type { WebChatState } from '@/lib/web-chat-state';
import type { ReactNode } from 'react';

interface ChatTranscriptProps { state: WebChatState; children?: ReactNode; onSuggestion: (text: string) => void }
export function ChatTranscript({ state, children, onSuggestion }: ChatTranscriptProps) {
  const scroll = useRef<HTMLDivElement>(null);
  const pinned = useRef(true);
  const [copied, setCopied] = useState('');
  const [copyError, setCopyError] = useState('');
  useEffect(() => {
    if (pinned.current && scroll.current) scroll.current.scrollTop = scroll.current.scrollHeight;
  }, [state.messages, state.stream, state.status, children]);
  async function copy(id: string, text: string) {
    try { if (!await copyTextToClipboard(text)) throw new Error('Clipboard unavailable'); setCopied(id); setCopyError(''); }
    catch { setCopyError('Could not copy. Select the response text and copy it manually.'); }
  }
  return <div className="chat-scroll" ref={scroll} onScroll={() => {
    const e = scroll.current; if (e) pinned.current = e.scrollHeight - e.scrollTop - e.clientHeight < 100;
  }}>
    <div className="chat-transcript" role="log" aria-label="Conversation" aria-live="off">
      {state.messages.length === 0 && !state.stream && <div className="chat-welcome">
        <span className="chat-welcome-icon"><FlaskConical size={30} strokeWidth={1.4} /></span>
        <p className="chat-eyebrow">YOUR SCIENTIFIC WORKSPACE</p>
        <h1>What would you like to explore?</h1>
        <p>Ask a question, explore your research, or work through an idea together.</p>
        <div className="chat-suggestions">{[
          ['Explore the literature', 'Help me review the literature on '],
          ['Understand your data', 'Help me understand my dataset. Start by asking what data and files I have.'],
          ['Plan your next step', 'Help me plan my research. Ask about my objective and available resources first.'],
        ].map(([label, prompt]) => <button key={label} onClick={() => onSuggestion(prompt)}>{label}</button>)}</div>
      </div>}
      {state.messages.map(message => message.role === 'tool' ? <details className="chat-tool" key={message.id}>
        <summary>{message.running ? <LoaderCircle size={15} className="chat-spinning" /> : <Check size={15} />}<span>{message.name || 'Tool activity'}</span><ChevronDown size={14} /></summary>
        <pre>{message.text || (message.running ? 'Running…' : 'Finished. No text output returned.')}</pre>
      </details> : <article className={`chat-message chat-message--${message.role}`} key={message.id} aria-label={message.role === 'user' ? 'You' : 'Agent Scientist'}>
        {message.role === 'assistant' && <div className="chat-speaker">Agent Scientist</div>}
        <div className="chat-message-content">{message.role === 'user' ? <p>{message.text}</p> : <Markdown content={message.text} />}</div>
        {message.role === 'assistant' && <button className="chat-copy" aria-label="Copy response" onClick={() => void copy(message.id, message.text)}>{copied === message.id ? <Check size={14} /> : <Copy size={14} />}{copied === message.id ? 'Copied' : 'Copy'}</button>}
      </article>)}
      {state.stream && <article className="chat-message chat-message--assistant" aria-label="Agent Scientist reply"><div className="chat-speaker">Agent Scientist</div><Markdown content={state.stream} streaming={state.busy} /></article>}
      {state.busy && <p role="status" className="chat-progress"><LoaderCircle size={15} className="chat-spinning" />{state.status || 'Working…'}</p>}
      {children}
      {(state.error || copyError) && <div className="chat-error" role="alert">{state.error || copyError}</div>}
    </div>
  </div>;
}
