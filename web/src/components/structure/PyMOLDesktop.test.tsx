// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { ProfileContext } from '@/contexts/profile-context';
import { PyMOLDesktop } from './PyMOLDesktop';
import { fetchJSON } from '@/lib/api';

vi.mock('@/lib/api', () => ({ fetchJSON: vi.fn() }));

it('only launches after an explicit click, scopes the request, and aborts an unfinished launch on close', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const request = vi.mocked(fetchJSON);
  request.mockImplementation(async (_url, init) => {
    if (init?.method === 'POST') return new Promise(() => {});
    return { installed: true, installing: false, package: 'fixture', desktops: [{ id: 'display', label: 'Server desktop (:1)' }] };
  });
  const container = document.createElement('div'); document.body.append(container);
  const root = createRoot(container);
  let signal: AbortSignal | null | undefined;
  try {
    await act(async () => root.render(<ProfileContext.Provider value={{ profile: 'omics', currentProfile: 'default', profiles: ['omics'], setProfile: vi.fn() }}>
      <PyMOLDesktop source={{ name: 'model.pdb', path: '/work/model.pdb' }} />
    </ProfileContext.Provider>));
    expect(request.mock.calls.every(([, init]) => !init?.method)).toBe(true);
    expect(container.textContent).toContain('SCI server’s desktop');
    await act(async () => container.querySelector('button')!.click());
    const [url, init] = request.mock.calls.find(([, init]) => init?.method === 'POST')!;
    expect(url).toBe('/api/structures/pymol/launch?profile=omics');
    expect(JSON.parse(init!.body as string)).toEqual({ path: '/work/model.pdb', desktop_id: 'display' });
    signal = init?.signal;
    expect(signal?.aborted).toBe(false);
  } finally { await act(async () => root.unmount()); container.remove(); }
  expect(signal?.aborted).toBe(true);
});
