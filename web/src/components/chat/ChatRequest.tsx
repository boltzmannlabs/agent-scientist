import { useState } from 'react';
import type { ServerRequest, ClarifyQuestion, ApprovalChoice } from '@sci/shared';

interface ChatRequestProps { request: ServerRequest; onAnswer: (result: Record<string, unknown>) => void }
const choiceLabels: Record<ApprovalChoice, string> = { once: 'Allow once', session: 'Allow for this session', always: 'Always allow', deny: 'Deny' };

export function ChatRequest({ request, onAnswer }: ChatRequestProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [secret, setSecret] = useState('');
  const [identifier, setIdentifier] = useState('');
  const p = request.params;
  if (request.method === 'approval') {
    const choices = Array.isArray(p.choices) ? p.choices as ApprovalChoice[] : ['once', 'deny'] as ApprovalChoice[];
    return <section className="chat-request" aria-label="Approval required">
      <h3>Permission needed</h3><p>{String(p.description || 'Review this action before continuing.')}</p>
      {p.command ? <pre>{String(p.command)}</pre> : null}
      <div className="chat-request-actions">{choices.filter(c => c in choiceLabels).map(c => <button key={c} onClick={() => onAnswer({ choice: c })}>{choiceLabels[c]}</button>)}</div>
    </section>;
  }
  if (request.method === 'clarify') {
    const questions = (p.questions || []) as ClarifyQuestion[];
    return <form className="chat-request" onSubmit={e => { e.preventDefault(); onAnswer({ answers }); }}>
      <h3>A little more information</h3>
      {questions.map(q => <fieldset key={q.qid}><legend>{q.question}</legend>
        {q.choices?.length ? <div className="chat-request-actions">{q.choices.map(choice => <button type="button" key={choice} aria-pressed={(answers[q.qid] || '').split('\n').includes(choice)} onClick={() => setAnswers(prev => {
          const selected = (prev[q.qid] || '').split('\n').filter(Boolean);
          return { ...prev, [q.qid]: q.multi_select ? (selected.includes(choice) ? selected.filter(c => c !== choice) : [...selected, choice]).join('\n') : choice };
        })}>{choice}</button>)}</div> : null}
        <textarea aria-label={q.question} placeholder="Type your answer…" value={answers[q.qid] || ''} onChange={e => setAnswers({ ...answers, [q.qid]: e.target.value })} required />
      </fieldset>)}
      <div className="chat-request-actions"><button type="submit">Continue</button><button type="button" onClick={() => onAnswer({})}>Cancel</button></div>
    </form>;
  }
  return <form className="chat-request" onSubmit={e => { e.preventDefault(); onAnswer({ value: request.method === 'vault.save_login' ? JSON.stringify({ identifier, password: secret }) : secret }); setSecret(''); }}>
    <h3>{request.method === 'sudo' ? 'Administrator permission requested' : 'Secure input required'}</h3>
    <p>{String(p.prompt || p.command || p.display_name || p.site || 'Enter the requested secret to continue.')}</p>
    {request.method === 'vault.save_login' && <input type="text" autoComplete="off" aria-label="Login identifier" placeholder="Username or email" value={identifier} onChange={e => setIdentifier(e.target.value)} required />}
    <input type="password" autoComplete="off" aria-label="Secret value" value={secret} onChange={e => setSecret(e.target.value)} required />
    <div className="chat-request-actions"><button type="submit">Submit securely</button><button type="button" onClick={() => { setSecret(''); onAnswer({ value: '' }); }}>Cancel</button></div>
  </form>;
}
