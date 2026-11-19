import { useEffect, useRef, useState } from 'react';
import { KeyRound, Library, Activity, ArrowUpRight, Search, LoaderCircle } from 'lucide-react';
import { fetchJSON } from '@/lib/api';
import { useProfileScope } from '@/contexts/useProfileScope';
import { BoltzmannMark } from '@/components/BoltzmannMark';
import './boltzmann.css';

interface Account { authorized: boolean; verified: boolean; message: string; email?: string; credits?: number | null; frozen_credits?: number | null }
interface Tool { name: string; module: string; section: string; status: string; description: string }
interface Catalog { tools: Tool[]; notice: string }

export default function BoltzmannPage() {
  const { profile, currentProfile } = useProfileScope();
  // Remount profile-owned forms to clear secrets and ignore stale requests.
  return <BoltzmannWorkspace key={profile || currentProfile} profile={profile || currentProfile} />;
}

function BoltzmannWorkspace({ profile }: { profile: string }) {
  const [account, setAccount] = useState<Account | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [panel, setPanel] = useState<'login' | 'tools' | 'status' | null>(null);
  const [key, setKey] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [receipt, setReceipt] = useState('');
  const [connected, setConnected] = useState(false);
  const [alreadyConnected, setAlreadyConnected] = useState(false);
  const [query, setQuery] = useState('');
  const [section, setSection] = useState('All');
  const [selected, setSelected] = useState<Tool | null>(null);
  const alive = useRef(true);
  const scope = `profile=${encodeURIComponent(profile)}`;
  useEffect(() => {
    alive.current = true;
    void fetchJSON<Account>(`/api/boltzmann/status?${scope}`).then(value => { if (alive.current) setAccount(value); }).catch(e => { if (alive.current) setError(String(e)); });
    return () => { alive.current = false; };
  }, [scope]);
  async function action(work: () => Promise<void>) {
    setBusy(true); setError(''); setReceipt(''); setConnected(false); setAlreadyConnected(false);
    try { await work(); } catch (e) { if (alive.current) setError(e instanceof Error ? e.message : String(e)); }
    finally { if (alive.current) setBusy(false); }
  }
  function browse() {
    setPanel('tools');
    void action(async () => {
      const value = await fetchJSON<Catalog>(`/api/boltzmann/tools?${scope}`);
      if (alive.current) setCatalog(value);
    });
  }
  function refresh() {
    setPanel('status');
    void action(async () => {
      const value = await fetchJSON<Account>(`/api/boltzmann/status?${scope}&verify=true`);
      if (alive.current) setAccount(value);
    });
  }
  const rows = (catalog?.tools || []).filter(t => (section === 'All' || t.section === section) && `${t.name} ${t.module}`.toLowerCase().includes(query.toLowerCase()));
  const credits = (value?: number | null) => value == null ? 'Not provided' : value.toLocaleString(undefined, { maximumFractionDigits: 2 });
  return <main className="boltz-page">
    <header className="boltz-hero"><BoltzmannMark className="boltz-brand" /><div><span className="boltz-eyebrow">YOUR SCIENTIFIC TOOLKIT</span><h1>Boltzmann</h1><p>One connection. A world of scientific possibilities.</p></div><span className="boltz-profile">Profile · {profile}</span></header>
    <div className="boltz-cards">
      <article><KeyRound /><span className="boltz-step">01 / CONNECT</span><h2>Your account</h2><p>Securely connect your API key to unlock Boltzmann workflows in this profile.</p><span className="boltz-badge">{account?.authorized ? 'Connected locally' : 'Connection required'}</span><button disabled={busy} onClick={() => { setPanel('login'); setError(''); setReceipt(''); }}>{account?.authorized ? 'Update connection' : 'Connect account'}<ArrowUpRight size={17} /></button></article>
      <article><Library /><span className="boltz-step">02 / DISCOVER</span><h2>Scientific tools</h2><p>Explore tools across protein engineering, molecular design, chemistry and more.</p><span className="boltz-badge">Browse by research area</span><button disabled={busy} onClick={browse}>Explore tools<ArrowUpRight size={17} /></button></article>
      <article><Activity /><span className="boltz-step">03 / MONITOR</span><h2>Account status</h2><p>Verify your connection and check available and frozen credits directly with Boltzmann.</p><span className="boltz-badge">Refresh on demand</span><button disabled={busy} onClick={refresh}>Check status<ArrowUpRight size={17} /></button></article>
    </div>
    {busy && <p className="boltz-feedback" role="status"><LoaderCircle className="animate-spin" size={18} /> Working…</p>}
    {error && <p className="boltz-error" role="alert">{error}</p>}
    {receipt && <section className={`boltz-receipt ${connected ? 'boltz-success' : ''}`} role="status">{connected && <><span className="boltz-eyebrow">✓ CONNECTION COMPLETE</span><h2>{alreadyConnected ? 'Account already connected' : 'Welcome to Boltzmann'}</h2></>}<p>{receipt}</p>{connected && account?.verified && <dl className="boltz-stats"><div><dt>Signed in as</dt><dd>{account.email || 'Verified account'}</dd></div><div><dt>Available credits</dt><dd>{credits(account.credits)}</dd></div><div><dt>Frozen credits</dt><dd>{credits(account.frozen_credits)}</dd></div></dl>}</section>}
    {panel === 'login' && <section className="boltz-panel"><h2>Connect to Boltzmann</h2><p>Your key is stored securely for <strong>{profile}</strong>. New tools become available in a new conversation.</p><a href="https://app.boltzmann.co/user-profile" target="_blank" rel="noreferrer">Get your API key <ArrowUpRight size={15} /></a><form onSubmit={e => { e.preventDefault(); const secret = key; setKey(''); void action(async () => {
      const result = await fetchJSON<{ ok: boolean; message: string; already_connected?: boolean }>(`/api/boltzmann/login?${scope}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ api_key: secret }) });
      if (!alive.current) return;
      setReceipt(result.message); setConnected(result.ok); setAlreadyConnected(!!result.already_connected);
      if (result.ok && result.already_connected) { setPanel(null); return; }
      if (result.ok) { setPanel(null); setAccount(null); const value = await fetchJSON<Account>(`/api/boltzmann/status?${scope}&verify=true`); if (alive.current) setAccount(value); }
    }); }}><label htmlFor="boltz-key">Boltzmann API key</label><div className="boltz-key-row"><input id="boltz-key" type="password" autoComplete="off" spellCheck={false} value={key} onChange={e => setKey(e.target.value)} placeholder="Enter your API key" required disabled={busy} /><button disabled={busy || !key.trim()} type="submit">Verify & connect</button></div></form></section>}
    {panel === 'status' && account && <section className="boltz-panel"><h2>{account.verified ? 'Account verified' : 'Connection status'}</h2><p>{account.message}</p>{account.verified && <dl className="boltz-stats"><div><dt>Account</dt><dd>{account.email || 'Not provided'}</dd></div><div><dt>Available credits</dt><dd>{credits(account.credits)}</dd></div><div><dt>Frozen credits</dt><dd>{credits(account.frozen_credits)}</dd></div></dl>}<p className="boltz-note">Account verification does not submit a scientific job. Credits reflect the latest check.</p></section>}
    {panel === 'tools' && catalog && <section className="boltz-panel"><div className="boltz-catalog-head"><h2>Explore the catalog</h2><span>{rows.length} tools</span></div><div className="boltz-filters"><label><Search size={18} /><input aria-label="Search tools" value={query} placeholder="Search tools or modules…" onChange={e => setQuery(e.target.value)} /></label><select aria-label="Research area" value={section} onChange={e => setSection(e.target.value)}>{['All', ...new Set(catalog.tools.map(t => t.section))].map(s => <option key={s}>{s}</option>)}</select></div><p className="boltz-note">Browse freely. Selecting a tool shows its details; run a workflow from Chat after connecting.</p>{selected && <aside className="boltz-detail"><button aria-label="Close tool details" onClick={() => setSelected(null)}>×</button><h3>{selected.name}</h3><p className="boltz-definition">{selected.description}</p><p>{selected.section} · {selected.module}</p><p>Catalog status: {selected.status}</p></aside>}<div className="boltz-tool-grid">{rows.map((t, i) => <button key={`${t.module}-${t.name}-${i}`} onClick={() => setSelected(t)}><span>{t.section}</span><strong>{t.name}</strong><small>{t.module} · {t.status}</small></button>)}</div>{!rows.length && <p>No matching tools. Try another name or research area.</p>}<p className="boltz-note">{catalog.notice}</p></section>}
  </main>;
}
