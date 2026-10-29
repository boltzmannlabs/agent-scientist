import { useEffect, useRef, useState } from 'react';
import { ArrowUp, Paperclip, Square, X } from 'lucide-react';

interface ChatComposerProps {
  disabled: boolean;
  busy: boolean;
  prefill: string;
  onSend: (text: string, images: File[]) => Promise<boolean>;
  onStop: () => Promise<void>;
}
export function ChatComposer({ disabled, busy, prefill, onSend, onStop }: ChatComposerProps) {
  const [text, setText] = useState('');
  const [images, setImages] = useState<File[]>([]);
  const [error, setError] = useState('');
  const [sending, setSending] = useState(false);
  const field = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  useEffect(() => { if (prefill) { setText(prefill); field.current?.focus(); } }, [prefill]);
  useEffect(() => {
    if (field.current) { field.current.style.height = 'auto'; field.current.style.height = `${Math.min(field.current.scrollHeight, 200)}px`; }
  }, [text]);
  function addFiles(files: File[]) {
    const valid = files.filter(f => ['image/png', 'image/jpeg', 'image/gif', 'image/webp', 'image/bmp'].includes(f.type) && f.size <= 25 * 1024 * 1024);
    setError(valid.length !== files.length ? 'Choose a PNG, JPEG, GIF, WebP, or BMP image up to 25 MB.' : '');
    setImages(prev => [...prev, ...valid]);
  }
  async function submit() {
    if (!text.trim() || disabled || busy || sending) return;
    if (images.length && text.startsWith('/')) { setError('Send images with a normal message, rather than a slash command.'); return; }
    setSending(true); setError('');
    const sentText = text;
    const ok = await onSend(sentText.trim(), images);
    if (ok) { setText(current => current === sentText ? '' : current); setImages([]); }
    setSending(false); field.current?.focus();
  }
  return <div className="chat-composer-area">
    {error && <p role="alert" className="chat-error">{error}</p>}
    <form className="chat-composer" onSubmit={e => { e.preventDefault(); void submit(); }}>
      {images.length > 0 && <div className="chat-attachments">{images.map((file, index) => <span key={`${file.name}-${index}`}>{file.name}<button type="button" aria-label={`Remove ${file.name}`} onClick={() => setImages(prev => prev.filter((_, i) => i !== index))}><X size={14} /></button></span>)}</div>}
      <textarea ref={field} aria-label="Message Agent Scientist" placeholder="Message Agent Scientist…" rows={2} value={text} disabled={disabled}
        onChange={e => setText(e.target.value)}
        onPaste={e => { const files = Array.from(e.clipboardData.files); if (files.length) { e.preventDefault(); addFiles(files); } }}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) { e.preventDefault(); void submit(); } }} />
      <div className="chat-composer-actions">
        <input ref={picker} hidden type="file" multiple accept="image/png,image/jpeg,image/gif,image/webp,image/bmp" onChange={e => { addFiles(Array.from(e.target.files || [])); e.target.value = ''; }} />
        <button type="button" className="chat-icon-button" disabled={disabled || busy} aria-label="Attach images" title="Attach images" onClick={() => picker.current?.click()}><Paperclip size={20} /></button>
        <span className="chat-keyboard-hint">Enter to send · Shift + Enter for a new line</span>
        {busy ? <button type="button" className="chat-send" aria-label="Stop response" disabled={disabled} onClick={() => void onStop()}><Square size={17} fill="currentColor" /></button>
          : <button className="chat-send" type="submit" aria-label="Send message" disabled={disabled || !text.trim() || sending}><ArrowUp size={22} /></button>}
      </div>
    </form>
    <p className="chat-footnote">Agent Scientist can make mistakes. Check important results and sources.</p>
  </div>;
}
