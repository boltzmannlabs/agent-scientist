// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { ProfileContext } from '@/contexts/profile-context';
import type { ManagedFilesResponse } from '@/lib/api';
import FilesPage from './FilesPage';

const mocks = vi.hoisted(() => ({ list: vi.fn(), header: { setAfterTitle: vi.fn(), setEnd: vi.fn() } }));
vi.mock('@/lib/api', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api')>(), api: { listFiles: mocks.list } }));
vi.mock('@/contexts/usePageHeader', () => ({ usePageHeader: () => mocks.header }));
vi.mock('@/plugins', () => ({ PluginSlot: () => null }));
vi.mock('@/components/structure/StructurePreview', () => ({ OpenLocalStructure: () => null }));

const listing = (name: string, path = '/workspace/outputs'): ManagedFilesResponse => ({
  path, root: null, locked_root: null, can_change_path: true, parent: '/workspace',
  entries: [{ path: path + '/' + name, name, is_directory: false, size: 10, mtime: 1, mime_type: 'text/csv' }],
});

it('opens and highlights a linked output folder and keeps the conversation scope for file actions', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  mocks.list.mockResolvedValue(listing('paired sequences.csv'));
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const query = new URLSearchParams({ profile: 'lab', path: '/workspace/outputs', file: '/workspace/outputs/paired sequences.csv', session_id: 'saved' });
  try {
    await act(async () => root.render(<MemoryRouter initialEntries={['/files?' + query]}>
      <ProfileContext.Provider value={{ profile: 'lab', currentProfile: 'default', profiles: ['lab'], setProfile: vi.fn() }}><FilesPage /></ProfileContext.Provider>
    </MemoryRouter>));
    expect(mocks.list).toHaveBeenCalledWith('/workspace/outputs', { profile: 'lab', sessionId: 'saved' });
    expect(host.querySelector('[data-highlighted="true"]')?.getAttribute('data-file-path')).toBe('/workspace/outputs/paired sequences.csv');
    const link = host.querySelector('a')!;
    expect(new URL(link.href).searchParams.get('session_id')).toBe('saved');
    expect(new URL(link.href).searchParams.get('profile')).toBe('lab');
  } finally { await act(async () => root.unmount()); host.remove(); mocks.list.mockReset(); }
});

it('discards stale folder reads after profile changes and keeps remote listings read-only', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  let oldRead!: (value: ManagedFilesResponse) => void;
  mocks.list.mockImplementationOnce(() => new Promise(resolve => { oldRead = resolve; }))
    .mockResolvedValueOnce({ ...listing('remote.bin'), read_only: true }).mockResolvedValueOnce(listing('new-a.csv'));
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const render = (profile: string) => root.render(<MemoryRouter initialEntries={['/files?path=%2Fworkspace%2Foutputs']}>
    <ProfileContext.Provider value={{ profile, currentProfile: 'default', profiles: ['a', 'b'], setProfile: vi.fn() }}><FilesPage /></ProfileContext.Provider>
  </MemoryRouter>);
  try {
    await act(async () => render('a'));
    await act(async () => render('b'));
    await act(async () => oldRead(listing('stale-a.csv')));
    expect(host.textContent).toContain('remote.bin'); expect(host.textContent).not.toContain('stale-a.csv');
    expect(host.querySelector<HTMLButtonElement>('[aria-label="Delete remote.bin"]')?.disabled).toBe(true);
    await act(async () => render('a'));
    expect(host.textContent).toContain('new-a.csv'); expect(host.textContent).not.toContain('remote.bin');
    expect(mocks.list.mock.calls.map(call => call[1].profile)).toEqual(['a', 'b', 'a']);
  } finally { await act(async () => root.unmount()); host.remove(); mocks.list.mockReset(); }
});
