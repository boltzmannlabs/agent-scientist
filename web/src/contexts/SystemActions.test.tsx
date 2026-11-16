// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api } from '@/lib/api';
import { SystemActionsProvider } from './SystemActions';
import { useSystemActions } from './useSystemActions';

vi.mock('@/lib/api', () => ({ api: {
  updateSci: vi.fn(), restartGateway: vi.fn(), getActionStatus: vi.fn(), getStatus: vi.fn(),
} }));
const messages = { status: { actionFinished: 'Finished', actionFailed: 'Failed' } };
vi.mock('@/i18n', () => ({ useI18n: () => ({ t: messages }) }));
vi.mock('@sci/ui/ui/components/toast', () => ({ Toast: ({ toast }: { toast: { message: string } | null }) => <div>{toast?.message}</div> }));

let root: Root;
let container: HTMLDivElement;
function Harness() {
  const actions = useSystemActions();
  return <>
    <button onClick={() => void actions.runAction('update')}>Update</button>
    <button onClick={actions.dismissLog}>Dismiss</button>
    <output>{JSON.stringify({ busy: actions.isBusy, running: actions.isRunning, message: actions.statusMessage })}</output>
  </>;
}
async function click(text: string) {
  await act(async () => Array.from(container.querySelectorAll('button')).find(b => b.textContent === text)!.click());
}
beforeEach(async () => {
  vi.useFakeTimers(); vi.clearAllMocks();
  sessionStorage.clear();
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
  await act(async () => root.render(<SystemActionsProvider><Harness /></SystemActionsProvider>));
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.useRealTimers(); });

it('polls consecutive updates, restores monitoring after reload, and ignores old responses', async () => {
  let attempt = 0;
  vi.mocked(api.updateSci).mockImplementation(async () => ({ ok: true, name: 'sci-update', pid: 10, action_id: String(++attempt) }));
  vi.mocked(api.getActionStatus).mockImplementation(async () => ({ name: 'sci-update', running: false, exit_code: 0, pid: 10, lines: [], action_id: String(attempt) }));
  for (let i = 0; i < 3; i++) {
    await click('Update');
    expect(api.getActionStatus).toHaveBeenCalledTimes(i + 1);
    expect(container.querySelector('output')!.textContent).toContain('"busy":false');
  }
  let release!: (value: Awaited<ReturnType<typeof api.getActionStatus>>) => void;
  vi.mocked(api.getActionStatus).mockImplementationOnce(() => new Promise(resolve => { release = resolve; }));
  await click('Update');
  await act(async () => root.unmount());
  root = createRoot(container);
  await act(async () => root.render(<SystemActionsProvider><Harness /></SystemActionsProvider>));
  expect(api.updateSci).toHaveBeenCalledTimes(4);
  expect(container.querySelector('output')!.textContent).toContain('"busy":false');
  await act(async () => release({ name: 'sci-update', running: true, exit_code: null, pid: 10, lines: [] }));
  expect(container.querySelector('output')!.textContent).toContain('"busy":false');
  expect(sessionStorage.getItem('sci.pendingUpdate')).toBeNull();
});

it('reconnects without resubmitting and does not accept stale or partial results as success', async () => {
  vi.mocked(api.updateSci).mockResolvedValue({ ok: true, name: 'sci-update', pid: 10, action_id: 'new' });
  vi.mocked(api.getActionStatus)
    .mockImplementationOnce((_name, _lines, options) => new Promise((_resolve, reject) => {
      options?.signal?.addEventListener('abort', () => reject(new Error('connection lost')));
    }))
    .mockResolvedValueOnce({ name: 'sci-update', running: false, exit_code: 0, pid: null, lines: [], action_id: 'old' })
    .mockResolvedValueOnce({ name: 'sci-update', running: false, exit_code: 0, pid: null, lines: [], action_id: 'new', receipt: { outcome: 'partial' } });
  await click('Update');
  await act(async () => vi.advanceTimersByTimeAsync(10000));
  expect(container.querySelector('output')!.textContent).toContain('Reconnecting');
  await act(async () => vi.advanceTimersByTimeAsync(1500));
  expect(container.querySelector('output')!.textContent).toContain('"busy":true');
  await act(async () => vi.advanceTimersByTimeAsync(1500));
  expect(container.querySelector('output')!.textContent).toContain('"busy":false');
  expect(container.textContent).not.toContain('Finished');
  expect(container.textContent).toContain('attention');
  expect(api.updateSci).toHaveBeenCalledTimes(1);
});
