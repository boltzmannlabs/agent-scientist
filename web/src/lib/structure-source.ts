export const MAX_STRUCTURE_BYTES = 20 * 1024 * 1024;

export interface StructureSource {
  name: string;
  path?: string;
  file?: File;
  profile?: string;
  sessionId?: string;
}

export function structureFormat(name: string): 'pdb' | 'mmcif' | null {
  if (/\.pdb$/i.test(name)) return 'pdb';
  if (/\.(?:cif|mmcif)$/i.test(name)) return 'mmcif';
  return null;
}

/** Only explicit server files, never guessed relative paths or external URLs. */
export function structureSourceFromLink(href: string, origin?: string): StructureSource | null {
  let path = href.trim();
  try {
    if (/^https?:/i.test(path) || path.startsWith('/api/files/')) {
      if (!origin) return null;
      const url = new URL(path, origin);
      if (url.origin !== origin || !/\/api\/files\/(?:read|download)$/.test(url.pathname)) return null;
      path = url.searchParams.get('path') || '';
    } else if (/^file:/i.test(path)) {
      const url = new URL(path);
      if (url.hostname && url.hostname !== 'localhost') return null;
      path = decodeURIComponent(url.pathname);
      if (/^\/[a-z]:\//i.test(path)) path = path.slice(1);
    } else {
      path = decodeURIComponent(path.replace(/^sandbox:/, ''));
    }
  } catch { return null; }
  if (path.includes('\0') || path.startsWith('//') || path.startsWith('\\\\')) return null;
  if (!path.startsWith('/') && !/^[a-z]:[\\/]/i.test(path)) return null;
  const name = path.split(/[\\/]/).pop() || '';
  return structureFormat(name) ? { name, path } : null;
}

export function validateStructureSize(size: number) {
  if (!Number.isFinite(size) || size <= 0) throw new Error('This structure file is empty.');
  if (size > MAX_STRUCTURE_BYTES) throw new Error('Structure preview supports files up to 20 MiB. Download this file to use a desktop viewer.');
}

export function decodeStructureFile(dataUrl: string, size: number): string {
  validateStructureSize(size);
  const match = /^data:[^,]*;base64,([A-Za-z0-9+/=\r\n]+)$/.exec(dataUrl);
  if (!match || match[1].length > Math.ceil(MAX_STRUCTURE_BYTES / 3) * 4 + 4) {
    throw new Error('The server returned an invalid or oversized structure file.');
  }
  const bytes = Uint8Array.from(atob(match[1]), c => c.charCodeAt(0));
  validateStructureSize(bytes.length);
  return new TextDecoder('utf-8', { fatal: true }).decode(bytes);
}
