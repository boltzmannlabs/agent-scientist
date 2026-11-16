// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it, vi } from 'vitest';
import BoltzmannPage from './BoltzmannPage';

vi.mock('@/contexts/useProfileScope', () => ({ useProfileScope: () => ({ profile: 'research', currentProfile: 'default' }) }));

it('submits the masked credential as JSON to the selected profile and clears the field', async () => {
  const requests: RequestInit[] = [];
  const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    if (String(url).includes('/login')) {
      expect(String(url)).toContain('profile=research');
      requests.push(init!);
      return new Response(JSON.stringify({ ok: false, message: 'Test validation declined' }), { headers: { 'Content-Type': 'application/json' } });
    }
    return new Response(JSON.stringify({ authorized: false, verified: false, message: 'Not connected' }), { headers: { 'Content-Type': 'application/json' } });
  });
  const host = document.createElement('div');
  document.body.append(host);
  const root = createRoot(host);
  try {
    await act(async () => root.render(<BoltzmannPage />));
    await act(async () => [...host.querySelectorAll('button')].find(b => b.textContent?.includes('Connect account'))!.click());
    const input = host.querySelector<HTMLInputElement>('#boltz-key')!;
    expect(input.type).toBe('password');
    await act(async () => {
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value')!.set!.call(input, 'fixture-key');
      input.dispatchEvent(new Event('input', { bubbles: true }));
    });
    await act(async () => host.querySelector('form')!.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })));
    expect(requests).toHaveLength(1);
    expect(new Headers(requests[0].headers).get('Content-Type')).toBe('application/json');
    expect(JSON.parse(requests[0].body as string)).toEqual({ api_key: 'fixture-key' });
    expect(input.value).toBe('');
    expect(host.textContent).toContain('Test validation declined');
    expect(host.textContent).not.toContain('fixture-key');
  } finally {
    await act(async () => root.unmount());
    host.remove(); fetchSpy.mockRestore();
  }
});
