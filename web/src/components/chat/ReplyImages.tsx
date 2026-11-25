import { useEffect, useState } from 'react';
import { authedFetch } from '@/lib/api';
import { outputFileQuery, type OutputFileScope } from '@/lib/output-files';

function ReplyImage({ path, scope }: { path: string; scope: OutputFileScope }) {
  const [url, setUrl] = useState('');
  const { profile, sessionId } = scope;
  useEffect(() => {
    const abort = new AbortController();
    let objectUrl = '';
    async function load() {
      const response = await authedFetch('/api/files/download?' + outputFileQuery(path, { profile, sessionId }), { signal: abort.signal });
      if (!response.ok || Number(response.headers.get('content-length')) > 8_000_000) return;
      const blob = await response.blob();
      if (abort.signal.aborted || blob.size > 8_000_000) return;
      objectUrl = URL.createObjectURL(blob);
      setUrl(objectUrl);
    }
    void load().catch(() => {}); // Existing file actions remain available on a read failure.
    return () => { abort.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [path, profile, sessionId]);
  return url ? <img src={url} alt={`Generated figure: ${path.split(/[\\/]/).pop()}`} style={{maxWidth: '100%', height: 'auto'}} /> : null;
}

export function ReplyImages({ text, scope }: { text: string; scope: OutputFileScope }) {
  const paths = new Set<string>();
  for (const line of text.replace(/```[\s\S]*?```/g, '').split('\n')) {
    const path = line.trim().match(/^(?:MEDIA:\s*|(?:[-*]\s+)?Figure:\s+)["'`]?((?:\/(?!\/)|[a-z]:[\\/]).+?\.(?:png|jpe?g|webp|gif|bmp))["'`]?(?:\s+\(also [^()]*\))?$/i)?.[1];
    if (path) paths.add(path);
  }
  return <>{[...paths].map(path => <ReplyImage key={JSON.stringify([scope.profile, scope.sessionId, path])} path={path} scope={scope} />)}</>;
}
