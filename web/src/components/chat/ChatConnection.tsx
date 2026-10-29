import { useState } from 'react';
import type { ConnectionAnswer, ConnectionRequestPayload } from '@sci/shared';

interface ChatConnectionProps { operation: ConnectionRequestPayload; onAnswer: (answer: ConnectionAnswer) => Promise<void> }
export function ChatConnection({ operation, onAnswer }: ChatConnectionProps) {
  const [values, setValues] = useState<Record<string, Record<string, string>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function answer(result: ConnectionAnswer) {
    setBusy(true); setError('');
    try { await onAnswer(result); setValues({}); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }
  return <section className="chat-request" aria-label="Connection setup">
    <h3>Review service access</h3>
    {operation.targets.map(target => <form key={target.name} onSubmit={e => {
      e.preventDefault();
      const defaults = Object.fromEntries((target.required_env || []).filter(field => !field.secret).map(field => [field.name, field.default]));
      void answer({ targets: [{ name: target.name, status: 'approved', env: { ...defaults, ...values[target.name] } }] });
    }}>
      <h4>{target.display || target.name} · {target.action}</h4>
      <p>{target.description || target.detail || target.instructions}</p>
      {target.repo && <p>Source: {target.repo}</p>}
      {target.requirements?.length ? <p>Requirements: {target.requirements.join(', ')}</p> : null}
      {target.tools?.length ? <details><summary>Requested tools ({target.tools.length})</summary><p>{target.tools.join(', ')}</p></details> : null}
      {target.scan && <p>Scan: {target.scan.status} — {target.scan.summary}</p>}
      {target.required_env?.map(field => <label key={field.name}>{field.prompt || field.name}<input
        type={field.secret ? 'password' : 'text'} autoComplete="off" required={field.required}
        value={values[target.name]?.[field.name] ?? (field.secret ? '' : field.default)}
        onChange={e => setValues(prev => ({ ...prev, [target.name]: { ...prev[target.name], [field.name]: e.target.value } }))} /></label>)}
      {target.connect_url && /^https?:\/\//i.test(target.connect_url) && <a href={target.connect_url} target="_blank" rel="noreferrer">Open authorization page ↗</a>}
      <p>Status: {target.state}{target.discovery_error ? ` — ${target.discovery_error}` : ''}</p>
      {['pending', 'not_connected'].includes(target.state) && <div className="chat-request-actions"><button type="submit" disabled={busy}>Approve {target.action}</button><button type="button" disabled={busy} onClick={() => void answer({ targets: [{ name: target.name, status: 'skipped' }] })}>Skip</button></div>}
    </form>)}
    {error && <p className="chat-error" role="alert">{error}</p>}
    <div className="chat-request-actions"><button disabled={busy} onClick={() => void answer({ settled_by: 'continue' })}>Continue with current connections</button></div>
  </section>;
}
