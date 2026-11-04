import { Component, lazy, Suspense, useState, type ReactNode } from 'react';
import { Atom, FileUp } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@sci/ui/ui/components/dialog';
import { useProfileScope } from '@/contexts/useProfileScope';
import { SCI_BASE_PATH } from '@/lib/api';
import { structureSourceFromLink, type StructureSource } from '@/lib/structure-source';
import './structure-preview.css';
import { PyMOLDesktop } from './PyMOLDesktop';

const StructureViewport = lazy(() => import('./StructureViewport'));

class ViewerBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed
      ? <p role="alert" className="structure-notice">The structure viewer could not load. Close this panel and try again, or refresh the dashboard.</p>
      : this.props.children;
  }
}

function StructureDialog({ source, close }: { source: StructureSource; close: () => void }) {
  const [desktopMode, setDesktopMode] = useState(false);
  return <Dialog open onOpenChange={open => { if (!open) close(); }}>
    <DialogContent className="structure-dialog">
      <DialogHeader>
        <DialogTitle className="structure-heading"><Atom size={20} />{source.name}</DialogTitle>
        <DialogDescription>
          Interactive structure · rotate, zoom, select residues, measure, and export an image.
          {source.file ? ' This file stays in your browser.' : ' Read through SCI’s file access controls.'}
        </DialogDescription>
      </DialogHeader>
      {source.path && <div className="pymol-actions" aria-label="Structure viewer mode">
        <button className="structure-open" type="button" aria-pressed={!desktopMode} onClick={() => setDesktopMode(false)}>Interactive 3D</button>
        <button className="structure-open" type="button" aria-pressed={desktopMode} onClick={() => setDesktopMode(true)}>PyMOL Desktop</button>
      </div>}
      {desktopMode ? <PyMOLDesktop source={source} /> : <ViewerBoundary><Suspense fallback={<p role="status" className="structure-notice">Loading 3D viewer…</p>}>
        <StructureViewport source={source} />
      </Suspense></ViewerBoundary>}
      <p className="structure-caption">Powered by <a href={`${SCI_BASE_PATH}/molstar-LICENSE.txt`} target="_blank" rel="noreferrer">Mol*</a> · Viewing a structure does not validate its scientific accuracy.</p>
    </DialogContent>
  </Dialog>;
}

export function StructureButton({ source, label = 'View structure' }: { source: StructureSource; label?: string }) {
  const { profile } = useProfileScope();
  const [opened, setOpened] = useState<{ source: StructureSource; profile: string } | null>(null);
  if (opened && opened.profile !== profile) setOpened(null);
  return <>
    <button type="button" className="structure-open" aria-label={`View structure ${source.name}`} onClick={() => setOpened({ source, profile })}>
      <Atom size={15} aria-hidden="true" />{label}
    </button>
    {opened && opened.profile === profile && <StructureDialog source={opened.source} close={() => setOpened(null)} />}
  </>;
}

export function StructureLink({ href, children }: { href: string; children: ReactNode }) {
  const source = structureSourceFromLink(href, typeof window === 'undefined' ? undefined : window.location.origin);
  if (!source) return null;
  return <StructureButton source={source} label={typeof children === 'string' ? `${children} · View structure` : 'View structure'} />;
}

export function OpenLocalStructure() {
  const [source, setSource] = useState<StructureSource | null>(null);
  return <>
    <label className="structure-open structure-local"><FileUp size={16} />Open local structure
      <input type="file" accept=".pdb,.cif,.mmcif" aria-label="Open local structure" onChange={event => {
        const file = event.currentTarget.files?.[0];
        if (file) setSource({ name: file.name, file });
        event.currentTarget.value = '';
      }} />
    </label>
    {source && <StructureDialog source={source} close={() => setSource(null)} />}
  </>;
}
