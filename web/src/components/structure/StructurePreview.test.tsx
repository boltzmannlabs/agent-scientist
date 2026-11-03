// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import { ProfileContext } from '@/contexts/profile-context';
import { Markdown } from '@/components/Markdown';

const mounted = vi.fn();
vi.mock('./StructureViewport', () => ({ default: ({ source }: { source: { name: string } }) => {
  mounted(source);
  return <div>Fixture viewport {source.name}</div>;
} }));

it('opens structure links only on click and closes them permanently on profile switch', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const container = document.createElement('div'); document.body.append(container);
  const root = createRoot(container);
  const render = (profile: string, suffix = '') => root.render(<ProfileContext.Provider value={{ profile, currentProfile: 'a', profiles: ['a', 'b'], setProfile: vi.fn() }}>
    <Markdown content={'Output: [model](/workspace/model.pdb)\n\n[External](https://example.test/model.pdb)' + suffix} />
  </ProfileContext.Provider>);
  try {
    await act(async () => render('a'));
    expect(mounted).not.toHaveBeenCalled();
    expect(container.querySelector('a')?.href).toBe('https://example.test/model.pdb');
    await act(async () => { container.querySelector('button')!.click(); await new Promise(resolve => setTimeout(resolve, 20)); });
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Fixture viewport model.pdb');
    const openedSource = mounted.mock.calls.at(-1)![0];
    await act(async () => render('a', '\nNew streamed text'));
    expect(mounted.mock.calls.at(-1)![0]).toBe(openedSource);
    await act(async () => render('b'));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
    await act(async () => render('a'));
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  } finally { await act(async () => root.unmount()); container.remove(); }
});
