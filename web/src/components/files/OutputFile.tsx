import { lazy, Suspense, useEffect, useState } from 'react';
import { Link } from 'react-router';
import { Download, FileIcon, FolderOpen } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@sci/ui/ui/components/dialog';
import { api } from '@/lib/api';
import { errorMessage } from '@/lib/api-error';
import { downloadOutputFile, outputFilesLink, type OutputFileReference, type OutputFileScope } from '@/lib/output-files';
import { structureFormat } from '@/lib/structure-source';

const StructureViewport = lazy(() => import('@/components/structure/StructureViewport'));
const MAX_PREVIEW_BYTES = 20 * 1024 * 1024;

function FilePreview({ file, scope }: { file: OutputFileReference; scope: OutputFileScope }) {
  const { profile, sessionId } = scope;
  const [preview, setPreview] = useState<{ text?: string; url?: string; kind?: string; error?: string } | null>(null);
  useEffect(() => {
    if (structureFormat(file.name)) return;
    const abort = new AbortController();
    let url = '';
    void api.readFile(file.path, abort.signal, { profile, sessionId }, MAX_PREVIEW_BYTES).then(value => {
      if (abort.signal.aborted) return;
      const data = value.data_url.slice(value.data_url.indexOf(',') + 1);
      const bytes = Uint8Array.from(atob(data), char => char.charCodeAt(0));
      const mime = value.mime_type;
      const kind = /^(?:image\/(?:png|jpeg|gif|webp|bmp|avif)|audio\/|video\/)/.test(mime) ? mime.split('/')[0]
        : mime === 'application/pdf' ? 'pdf' : 'text';
      if (kind !== 'text') {
        url = URL.createObjectURL(new Blob([bytes], { type: mime }));
        setPreview({ url, kind });
      } else {
        const text = new TextDecoder('utf-8', { fatal: true }).decode(bytes);
        if (text.includes('\0')) throw new Error('This format has no browser preview. Use Download to open it with a suitable application.');
        setPreview({ text: text.slice(0, 64000) + (text.length > 64000 ? '\n… Preview truncated. Download for the complete file.' : '') });
      }
    }).catch(error => { if (!abort.signal.aborted) setPreview({ error: errorMessage(error) }); });
    return () => { abort.abort(); if (url) URL.revokeObjectURL(url); };
  }, [file.name, file.path, profile, sessionId]);
  if (structureFormat(file.name)) return <Suspense fallback={<p>Loading structure…</p>}>
    <StructureViewport source={{ name: file.name, path: file.path, profile: scope.profile, sessionId: scope.sessionId }} />
  </Suspense>;
  if (!preview) return <p role="status">Loading preview…</p>;
  if (preview.error) return <p role="alert">Preview unavailable: {preview.error} You can still use Download.</p>;
  if (preview.kind === 'image') return <img src={preview.url} alt={file.name} className="max-h-[65vh] max-w-full object-contain" />;
  if (preview.kind === 'audio') return <audio src={preview.url} controls />;
  if (preview.kind === 'video') return <video src={preview.url} controls className="max-h-[65vh] max-w-full" />;
  if (preview.kind === 'pdf') return <iframe src={preview.url} title={file.name} sandbox="" className="h-[65vh] w-full" />;
  return <pre className="max-h-[65vh] overflow-auto whitespace-pre-wrap break-words text-xs">{preview.text}</pre>;
}

export function OutputFile({ file, scope }: { file: OutputFileReference; scope: OutputFileScope }) {
  return <FileActions key={`${scope.profile}:${scope.sessionId || ''}:${file.path}`} file={file} scope={scope} />;
}

function FileActions({ file, scope }: { file: OutputFileReference; scope: OutputFileScope }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function download() {
    setBusy(true); setError('');
    try { await downloadOutputFile(file, scope); } catch (cause) { setError(errorMessage(cause)); }
    finally { setBusy(false); }
  }
  return <span className="inline-flex max-w-full flex-wrap items-center gap-2 rounded border border-border bg-secondary/40 px-2 py-1 align-middle" title={file.path}>
    <FileIcon size={14} aria-hidden="true" />
    <button type="button" className="break-all text-primary underline" onClick={() => void download()} disabled={busy}>{file.name}</button>
    <button type="button" className="text-xs underline" onClick={() => setOpen(true)}>Preview</button>
    <button type="button" className="inline-flex items-center gap-1 text-xs underline" aria-label={`Download ${file.name}`} onClick={() => void download()} disabled={busy}><Download size={12} />{busy ? 'Checking…' : 'Download'}</button>
    <Link className="inline-flex items-center gap-1 text-xs underline" to={outputFilesLink(file, scope)}><FolderOpen size={12} />Show in Files</Link>
    {error && <span role="alert" className="text-destructive">{error}</span>}
    {open && <Dialog open onOpenChange={setOpen}><DialogContent className="max-w-5xl">
      <DialogHeader><DialogTitle>{file.name}</DialogTitle><DialogDescription>{file.path}</DialogDescription></DialogHeader>
      <FilePreview file={file} scope={scope} />
      <button type="button" onClick={() => void download()} disabled={busy}>Download complete file</button>
    </DialogContent></Dialog>}
  </span>;
}
