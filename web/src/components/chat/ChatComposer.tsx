import { useEffect, useRef, useState, type KeyboardEvent, type ReactNode } from 'react';
import { ArrowUp, ChevronDown, Paperclip, Square, X, Gauge, Trash2 } from 'lucide-react';

interface ChatComposerProps {
  disabled: boolean;
  busy: boolean;
  prefill: string;
  onSend: (text: string, images: File[]) => Promise<boolean>;
  onStop: () => Promise<void>;
  modelLabel: string;
  onChooseModel?: () => void;
  contextPercent: number | null;
  contextEstimated: boolean;
  onCompact: () => void;
  onQueue: (text: string) => Promise<boolean>;
  onSteer: (text: string) => Promise<boolean>;
  commands: Array<[string, string]>;
  toolbar?: ReactNode;
}
export function ChatComposer({ disabled, busy, prefill, onSend, onStop, modelLabel, onChooseModel, contextPercent, contextEstimated, onCompact, onQueue, onSteer, commands, toolbar }: ChatComposerProps) {
  const [text, setText] = useState('');
  const [images, setImages] = useState<File[]>([]);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const [busyMode, setBusyMode] = useState<'queue' | 'steer'>('queue');
  const field = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const [selectedCommand, setSelectedCommand] = useState(0);
  useEffect(() => { if (!busy) setBusyMode('queue'); }, [busy]);
  useEffect(() => { if (prefill) { setText(prefill); field.current?.focus(); } }, [prefill]);
  useEffect(() => {
    if (field.current) { field.current.style.height = 'auto'; field.current.style.height = `${Math.min(field.current.scrollHeight, 200)}px`; }
    setSelectedCommand(0);
  }, [text]);
  function addFiles(files: File[]) {
    const valid = files.filter(f => ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'].includes(f.type) && f.size <= 25 * 1024 * 1024);
    setError(valid.length !== files.length ? 'Choose a PNG, JPEG, GIF, WebP, or BMP image up to 25 MB.' : '');
    setImages(prev => [...prev, ...valid]);
  }
  async function submit() {
    if (!text.trim() || disabled || sending || (busy && !['queue', 'steer'].includes(busyMode))) return;
    if (images.length && text.startsWith('/')) { setError('Send images with a normal message, rather than a slash command.'); return; }
    setSending(true); setError('');
    const sentText = text;
    const ok = busy ? await (busyMode === 'queue' ? onQueue(sentText.trim()) : onSteer(sentText.trim())) : await onSend(sentText.trim(), images);
    if (ok) { setText(current => current === sentText ? '' : current); setImages([]); }
    setSending(false); field.current?.focus();
  }
  const commandQuery = text.startsWith('/') && !/\s/.test(text);
  const commandMatches = commandQuery ? commands.filter(([name]) => name.toLowerCase().startsWith(text.toLowerCase())).slice(0, 9) : [];
  function chooseCommand(name: string) {
    setText(`${name} `); setError(''); field.current?.focus();
  }
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (commandMatches.length && event.key === 'ArrowDown') { event.preventDefault(); setSelectedCommand(index => (index + 1) % commandMatches.length); return; }
    if (commandMatches.length && event.key === 'ArrowUp') { event.preventDefault(); setSelectedCommand(index => (index - 1 + commandMatches.length) % commandMatches.length); return; }
    if (commandMatches.length && event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); chooseCommand(commandMatches[selectedCommand]?.[0] || commandMatches[0][0]); return; }
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void submit(); }
  }
  return <div className="chat-composer-area">
    {contextPercent != null && <div className="chat-context-wrap" title={`Context window ${Math.round(contextPercent)}% used${contextEstimated ? ' (estimated)' : ''}`}>
      <div className="chat-context-meter" role="progressbar" aria-label="Context window usage" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.max(0, Math.min(100, contextPercent))}>
        <Gauge size={14} /><span className="chat-context-track"><i style={{ width: `${Math.max(0, Math.min(100, contextPercent))}%` }} /></span><span>{Math.round(contextPercent)}%{contextEstimated ? ' est.' : ''}</span>
      </div>
      <button type="button" className="chat-context-compact" disabled={disabled || busy} onClick={onCompact}>Compact</button>
    </div>}
    {error && <p role="alert" className="chat-error">{error}</p>}
    {commandMatches.length > 0 && <div className="chat-command-suggestions" role="listbox" aria-label="Slash commands">
      {commandMatches.map(([name, description], index) => <button type="button" role="option" aria-selected={index === selectedCommand} key={name} onMouseDown={event => event.preventDefault()} onClick={() => chooseCommand(name)}>
        <span>{name}</span><small>{description}</small>
      </button>)}
    </div>}
    <form className="chat-composer" onSubmit={e => { e.preventDefault(); void submit(); }}>
      {toolbar}
      {images.length > 0 && <div className="chat-attachments">{images.map((file, index) => <span key={`${file.name}-${index}`}>{file.name}<button type="button" aria-label={`Remove ${file.name}`} onClick={() => setImages(prev => prev.filter((_, i) => i !== index))}><X size={14} /></button></span>)}</div>}
      <textarea ref={field} aria-label="Message Agent Scientist" placeholder="Message Agent Scientist…" rows={2} value={text} disabled={disabled}
        onChange={e => setText(e.target.value)}
        onPaste={e => { const files = Array.from(e.clipboardData.files); if (files.length) { e.preventDefault(); addFiles(files); } }}
        onKeyDown={handleKeyDown} />
      <div className="chat-composer-actions">
        <input ref={picker} hidden type="file" multiple accept="image/png,image/jpeg,image/gif,image/webp,image/bmp" onChange={e => { addFiles(Array.from(e.target.files || [])); e.target.value = ''; }} />
        <button type="button" className="chat-icon-button" disabled={disabled || busy} aria-label="Attach images" title="Attach images" onClick={() => picker.current?.click()}><Paperclip size={20} /></button>
        {onChooseModel && <button type="button" className="chat-model-picker" onClick={onChooseModel} aria-label={`Choose model. Current model: ${modelLabel}`} title={modelLabel ? `Model: ${modelLabel}` : 'Choose model'}>
          <span>{modelLabel}</span><ChevronDown size={14} />
        </button>}
        {busy && <div className="chat-busy-mode" role="group" aria-label="While response is running">
          <button type="button" aria-pressed={busyMode === 'queue'} onClick={() => setBusyMode('queue')}>Queue</button>
          <button type="button" aria-pressed={busyMode === 'steer'} onClick={() => setBusyMode('steer')}>Steer</button>
          {busyMode === 'steer' && text && <button type="button" aria-label="Delete steer draft" title="Delete steer draft" onClick={() => setText('')}><Trash2 size={13} /></button>}
        </div>}
        <span className="chat-keyboard-hint">{busy ? (busyMode === 'queue' ? 'Send next' : 'Steer reply') : 'Enter to send · Shift + Enter for a new line'}</span>
        {busy ? <button type="button" className="chat-stop" aria-label="Stop response" disabled={disabled} onClick={() => void onStop()}><Square size={14} fill="currentColor" /></button>
          : null}
        {(!busy || text.trim()) && <button className={`chat-send ${busy ? 'chat-send--busy' : ''}`} type="submit" aria-label={busy ? (busyMode === 'queue' ? 'Queue message' : 'Steer response') : 'Send message'} disabled={disabled || !text.trim() || sending}><ArrowUp size={22} /></button>}
      </div>
    </form>
    <p className="chat-footnote">Agent Scientist can make mistakes. Check important results and sources.</p>
  </div>;
}
