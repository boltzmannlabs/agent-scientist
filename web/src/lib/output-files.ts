import { authedFetch, SCI_BASE_PATH } from './api';

export interface OutputFileScope { profile: string; sessionId?: string }
export interface OutputFileReference { path: string; name: string }

/** File references are candidates; only the authenticated server can authorize/read them. */
export function outputFileReference(value: string, origin?: string, allowRelative = false): OutputFileReference | null {
  let path = value.trim();
  try {
    if (/^https?:/i.test(path) || path.startsWith('/api/files/')) {
      if (!origin) return null;
      const url = new URL(path, origin);
      if (url.origin !== origin || !/\/api\/files\/(?:read|download)$/.test(url.pathname)) return null;
      path = url.searchParams.get('path') || '';
    } else if (/^file:/i.test(path)) {
      const url = new URL(path);
      if (url.hostname && url.hostname !== 'localhost') return null;
      path = decodeURIComponent(url.pathname).replace(/^\/([a-z]:\/)/i, '$1');
    } else if (path.startsWith('sandbox:')) path = decodeURIComponent(path.slice(8));
  } catch { return null; }
  if (/[\0\r\n]/.test(path) || path.startsWith('//') || path.startsWith('\\\\')) return null;
  const absolute = path.startsWith('/') || /^[a-z]:[\\/]/i.test(path);
  if (!absolute && (!allowRelative || !path || /^[a-z][a-z0-9+.-]*:|[<>{}()=;*?"|]/i.test(path))) return null;
  if (/[\\/]$/.test(path)) return null;
  const name = path.split(/[\\/]/).pop() || '';
  return name && name !== '.' && name !== '..' ? { path, name } : null;
}

/** Cards come only from structured tool output_paths, never prose or storage metadata. */
export function outputFilesInResult(text: string): OutputFileReference[] {
  const found = new Map<string, OutputFileReference>();
  let visited = 0;
  function walk(value: unknown, depth = 0) {
    if (++visited > 1000 || depth > 8 || !value || typeof value !== 'object') return;
    if (Array.isArray(value)) { value.forEach(row => walk(row, depth + 1)); return; }
    const record = value as Record<string, unknown>;
    if (Array.isArray(record.output_paths)) {
      for (const path of record.output_paths) {
        if (typeof path !== 'string') continue;
        const file = outputFileReference(path, undefined, true);
        if (file && found.size < 20) found.set(file.path, file);
      }
    }
    // Standard tool-call / parallel-call envelopes. Do not inspect args, skill
    // content, examples, arbitrary metadata or GCP storage references.
    for (const key of ['result', 'results', 'data', 'tools']) {
      const child = record[key];
      if (typeof child === 'string') {
        try { walk(JSON.parse(child), depth + 1); } catch { /* Plain output is not an artifact declaration. */ }
      } else walk(child, depth + 1);
    }
  }
  try { walk(JSON.parse(text)); } catch { /* Text alone cannot declare downloadable outputs. */ }
  return [...found.values()];
}

/** Final answers reuse exact tool-declared paths; filenames never create new paths. */
export function outputFilesInResponse(text: string, known: OutputFileReference[] = []): OutputFileReference[] {
  const prose = text.replace(/```[\s\S]*?```/g, '');
  const found = new Map<string, OutputFileReference>();
  for (const file of known) {
    if (prose.includes(file.name)) found.set(file.path, file);
  }
  return [...found.values()].slice(0, 20);
}

export function outputFileQuery(path: string, scope: OutputFileScope): URLSearchParams {
  const query = new URLSearchParams({ path, profile: scope.profile || 'default' });
  if (scope.sessionId) query.set('session_id', scope.sessionId);
  return query;
}

export function outputFilesLink(file: OutputFileReference, scope: OutputFileScope): string {
  const index = Math.max(file.path.lastIndexOf('/'), file.path.lastIndexOf('\\'));
  let folder = index < 0 ? '.' : file.path.slice(0, index) || '/';
  if (/^[a-z]:$/i.test(folder)) folder += '\\';
  const query = outputFileQuery(folder, scope);
  query.set('file', file.path);
  return `/files?${query}`;
}

/** HEAD checks access/errors; a native browser download streams without a JS/base64 buffer. */
export async function downloadOutputFile(file: OutputFileReference, scope: OutputFileScope): Promise<void> {
  const query = outputFileQuery(file.path, scope);
  const response = await authedFetch(`/api/files/download?${query}`, { method: 'HEAD' });
  if (!response.ok) {
    const errors: Record<number, string> = { 400: 'Choose a regular file to download.', 401: 'Sign in again to download this file.', 403: 'Access to this file is not allowed.',
      404: 'This file or its originating conversation is no longer available.', 409: 'This file is unavailable here; check its execution backend or whether it is in use.',
      413: 'This file exceeds the server download limit.' };
    throw new Error(errors[response.status] || `Download failed (HTTP ${response.status}).`);
  }
  // Existing download-only authentication. The token is never persisted in chat/file links.
  const token = window.__SCI_SESSION_TOKEN__;
  if (token) query.set('token', token);
  const anchor = document.createElement('a');
  anchor.href = `${SCI_BASE_PATH}/api/files/download?${query}`;
  anchor.download = file.name;
  anchor.rel = 'noreferrer';
  document.body.append(anchor); anchor.click(); anchor.remove();
}
