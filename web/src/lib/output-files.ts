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

/** Automatic chat actions need evidence of a file, not just a path-shaped token. */
export function fileActionReference(value: string, origin?: string, allowRelative = false, declaredFile = false): OutputFileReference | null {
  const file = outputFileReference(value, origin, allowRelative);
  if (!file) return null;
  const path = file.path.replace(/\\/g, '/');
  // Internal instructions and spillover are readable references, not deliverables.
  if (/(?:^|\/)(?:skills|references)\//i.test(path)
    || /(?:^|\/)cache\/spillover\//i.test(path)
    || /(?:^|\/)\.sci\/cache\//i.test(path)) return null;
  const hasSuffix = /^[^.].*\.[\p{L}\p{N}_-]+$/u.test(file.name);
  if (/^\/[^/]+$/.test(path) && !hasSuffix) return null; // Slash commands and root folders (e.g. /tmp).
  if (!hasSuffix && !declaredFile) return null;
  // A bare filename in inline code is commonly a source/schema mention.
  if (!allowRelative && !path.includes('/')) return null;
  return file;
}

export function linkedOutputFile(href: string, origin?: string): OutputFileReference | null {
  const value = href.trim().replace(/^<(.+)>$/, '$1');
  try {
    return fileActionReference(/^(?:https?:|file:|sandbox:)/i.test(value) ? value : decodeURIComponent(value), origin, true);
  } catch { return null; }
}

export function splitFileText(text: string): { text: string; file?: OutputFileReference }[] {
  const whole = fileActionReference(text);
  // A whole line or quoted/inline-code reference may contain spaces.
  if (whole && (whole.path.slice(1).includes('/') || /^[a-z]:/i.test(whole.path))) {
    return [{ text, file: whole }];
  }
  const result: { text: string; file?: OutputFileReference }[] = [];
  const pattern = /(?:^|[\s(])((?:sandbox:)?\/(?!\/)[^\s`<>"'|\])]+|[a-z]:[\\/][^\s`<>"'|\])]+)/gi;
  let end = 0;
  for (const match of text.matchAll(pattern)) {
    const token = match[1].replace(/[.,;:]+$/, '');
    const file = fileActionReference(token);
    if (!file || (!file.path.slice(1).includes('/') && !file.name.includes('.'))) continue;
    const start = match.index! + match[0].indexOf(match[1]);
    result.push({ text: text.slice(end, start) }, { text: token, file });
    end = start + token.length;
  }
  result.push({ text: text.slice(end) });
  return result;
}

/** Only declared artifacts or explicit save/download notices become tool-result cards. */
export function outputFilesInResult(text: string): OutputFileReference[] {
  const found = new Map<string, OutputFileReference>();
  const add = (value: string, declaredFile = false) => { const file = fileActionReference(value, undefined, true, declaredFile); if (file && found.size < 20) found.set(file.path, file); };
  let visited = 0;
  function walk(value: unknown, depth = 0, artifact = false, pathField = false, declaredFile = false) {
    if (++visited > 1000 || depth > 8) return;
    if (typeof value === 'string' && pathField) add(value, declaredFile);
    else if (Array.isArray(value)) value.forEach(row => walk(row, depth + 1, artifact, pathField, declaredFile));
    else if (value && typeof value === 'object') Object.entries(value).forEach(([key, row]) => {
      const collection = /^(?:files|artifacts|outputs|output_files)$/.test(key);
      const fileField = /^(?:output_file|download_file)$/.test(key) || (artifact && /^(?:path|file_path|local_path)$/.test(key));
      const outputPath = /^(?:local_path|download_path|output_path|output_paths|saved_path)$/.test(key);
      walk(row, depth + 1, artifact || collection, collection || fileField || outputPath, collection || fileField);
    });
  }
  try { walk(JSON.parse(text)); return [...found.values()]; } catch { /* Non-JSON results may contain save notices. */ }
  for (const line of text.replace(/```[\s\S]*?```/g, '').split('\n')) {
    if (!/^\s*(?:saved|downloaded|created|output file|artifact)\b/i.test(line)) continue;
    for (const match of line.matchAll(/`([^`]+)`|\[[^\]]*\]\(([^)]+)\)/g)) {
      const file = match[2] ? linkedOutputFile(match[2], typeof window === 'undefined' ? undefined : window.location.origin) : fileActionReference(match[1]);
      if (file) add(file.path, true);
    }
    splitFileText(line).forEach(part => { if (part.file) add(part.file.path); });
  }
  return [...found.values()];
}

/** Resolve filenames in a final report only against observed outputs or its stated save folder. */
export function outputFilesInResponse(text: string, known: OutputFileReference[] = []): OutputFileReference[] {
  const prose = text.replace(/```[\s\S]*?```/g, '');
  const found = new Map<string, OutputFileReference>();
  // A folder is context for the listed files, never itself a download target.
  const folderMatch = prose.match(/\b(?:saved in|saved to|output folder|output directory|results directory)\s*[:=]?\s*[`"']?((?:\/(?!\/)|[a-z]:[\\/])[^\r\n`"'<>]*?)(?=[`"'\r\n)]|$)/i);
  const folder = folderMatch?.[1].trim().replace(/[\\/]$/, '');
  const candidates = [...known].sort((a, b) => b.name.length - a.name.length);
  for (const file of candidates) {
    const start = prose.indexOf(file.name);
    if (start < 0 || prose.includes(file.path)) continue; // Absolute references already have inline actions.
    if (fileActionReference(file.path, undefined, true, true)) found.set(file.path, file);
  }
  if (folder) {
    const filename = /(?:^|[\s`*|(])([\p{L}\p{N}_-][\p{L}\p{N}_.-]*\.[\p{L}\p{N}_-]+)(?=$|[\s`*|/),;])/gu;
    for (const match of prose.matchAll(filename)) {
      const name = match[1];
      if (candidates.some(file => file.name === name) || prose.includes(`${folder}/${name}`)) continue;
      const file = fileActionReference(`${folder}/${name}`, undefined, true);
      if (file) found.set(file.path, file);
    }
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
