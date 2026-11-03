import { useEffect, useRef, useState } from 'react';
import { fetchJSON } from '@/lib/api';
import { errorMessage } from '@/lib/api-error';
import { useProfileScope } from '@/contexts/useProfileScope';
import type { StructureSource } from '@/lib/structure-source';

interface RuntimeStatus {
  installed: boolean;
  installing: boolean;
  package: string;
  desktops: { id: string; label: string }[];
}
interface LaunchResult { pid: number; desktop: string; atoms: number; version: string }

export function PyMOLDesktop({ source }: { source: StructureSource }) {
  const { profile } = useProfileScope();
  const [runtime, setRuntime] = useState<RuntimeStatus | null>(null);
  const [desktop, setDesktop] = useState('');
  const [result, setResult] = useState<LaunchResult | null>(null);
  const [busy, setBusy] = useState('');
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState('');
  const controller = useRef<AbortController | null>(null);
  const scope = `?profile=${encodeURIComponent(profile || 'current')}`;
  const endpoint = '/api/structures/pymol';

  useEffect(() => {
    const abort = new AbortController();
    const refresh = () => void fetchJSON<RuntimeStatus>(endpoint + scope, { signal: abort.signal })
      .then(setRuntime).catch(e => { if (!abort.signal.aborted) setError(errorMessage(e)); });
    refresh();
    const timer = setInterval(refresh, 5000);
    return () => { abort.abort(); controller.current?.abort(); clearInterval(timer); };
  }, [scope]);

  useEffect(() => {
    if (!busy) return;
    const start = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [busy]);

  const selectedDesktop = desktop || (runtime?.desktops.length === 1 ? runtime.desktops[0].id : '');
  async function perform(install: boolean) {
    const abort = new AbortController(); controller.current = abort;
    setError(''); setElapsed(0); setBusy(install ? 'Installing PyMOL Desktop' : 'Opening PyMOL on the server desktop');
    if (!install) setResult(null);
    try {
      if (install) {
        setRuntime(await fetchJSON<RuntimeStatus>(endpoint + '/install' + scope, { method: 'POST', signal: abort.signal }));
      } else {
        setResult(await fetchJSON<LaunchResult>(endpoint + '/launch' + scope, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ path: source.path, desktop_id: selectedDesktop }), signal: abort.signal,
        }));
      }
    } catch (e) { if (!abort.signal.aborted) setError(errorMessage(e)); }
    finally { if (!abort.signal.aborted) setBusy(''); }
  }

  return <div className="pymol-panel">
    <p>This opens a separate PyMOL window on the <strong>SCI server’s desktop</strong>. View it on the server’s screen or through your remote-desktop connection; SSH port forwarding only displays the web dashboard.</p>
    <p>PyMOL opens a temporary copy of this structure. Your original file is unchanged. Once opened, the window stays open until you close it in PyMOL.</p>
    {!runtime && !error && <p role="status">Checking PyMOL and desktop availability…</p>}
    {runtime && !runtime.installed && <div>
      <p>Install PyMOL Desktop for this profile? This downloads community-built Open-Source PyMOL wheels ({runtime.package}), Qt and NumPy into a separate managed environment. Installation may continue if you close this panel; reopen it to check.</p>
      <button type="button" className="structure-open" disabled={Boolean(busy) || runtime.installing} onClick={() => void perform(true)}>Install PyMOL Desktop</button>
    </div>}
    {runtime?.installing && !busy && <p role="status">PyMOL installation is in progress on the server…</p>}
    {runtime && runtime.desktops.length === 0 && <p role="alert">No accessible server desktop was found. Sign in to the server’s graphical desktop as the SCI user. If needed, start the dashboard from a terminal in that desktop session.</p>}
    {runtime?.installed && runtime.desktops.length > 0 && <div className="pymol-actions">
      <label>Desktop <select aria-label="PyMOL server desktop" value={selectedDesktop} disabled={Boolean(busy)} onChange={e => setDesktop(e.target.value)}>
        <option value="" disabled>Select a desktop</option>
        {runtime.desktops.map(item => <option key={item.id} value={item.id}>{item.label}</option>)}
      </select></label>
      <button className="structure-open" type="button" disabled={Boolean(busy) || !selectedDesktop} onClick={() => void perform(false)}>{result ? 'Open another PyMOL window' : 'Open PyMOL on server desktop'}</button>
    </div>}
    {busy && <p role="status">{busy} · {elapsed}s elapsed</p>}
    {error && <p role="alert" className="structure-error">{error}</p>}
    {result && <p role="status">Opened PyMOL {result.version} on {result.desktop}. Loaded {result.atoms.toLocaleString()} atoms. Process {result.pid}.</p>}
  </div>;
}
