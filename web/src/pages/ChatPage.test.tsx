// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { beforeEach, afterEach, expect, it, vi } from 'vitest';
import type { GatewayEvent, ServerRequest } from '@sci/shared';
import { ProfileContext } from '@/contexts/profile-context';
import { PageHeaderContext } from '@/contexts/page-header-context';

const instances: FakeGateway[] = [];
class FakeGateway {
  eventHandlers = new Set<(event: GatewayEvent) => void>();
  requestHandlers = new Set<(request: ServerRequest) => unknown>();
  stateHandlers = new Set<(state: string) => void>();
  closed = false;
  connect = vi.fn(async () => {});
  request = vi.fn(async (method: string, params: Record<string, unknown>) => {
    if (method === 'session.create' || method === 'session.resume') return {
      session_id: `runtime-${params.profile}`, stored_session_id: `stored-${params.profile}`, messages: [],
      info: { model: `model-${params.profile}` }, message_count: 0,
    };
    return { status: 'streaming' };
  });
  constructor() { instances.push(this); }
  onAny = (handler: (event: GatewayEvent) => void) => { this.eventHandlers.add(handler); return () => { this.eventHandlers.delete(handler); }; };
  onState = (handler: (state: string) => void) => { this.stateHandlers.add(handler); return () => { this.stateHandlers.delete(handler); }; };
  onRequest = (handler: (request: ServerRequest) => unknown) => { this.requestHandlers.add(handler); return () => { this.requestHandlers.delete(handler); }; };
  close = () => { this.closed = true; };
  emit = (type: string, payload: unknown, profile = 'a') => this.eventHandlers.forEach(h => h({ type, payload, session_id: `runtime-${profile}` } as GatewayEvent));
}
vi.mock('@/lib/gatewayClient', () => ({ GatewayClient: class { constructor() { return new FakeGateway(); } } }));
vi.mock('@/components/ChatSessionList', () => ({ ChatSessionList: () => <div>Conversation history</div> }));
import ChatPage from './ChatPage';
let root: Root; let container: HTMLDivElement;
const headers = { setTitle: vi.fn(), setEnd: vi.fn(), setAfterTitle: vi.fn() };
async function render(profile = 'a', active = true) {
  await act(async () => root.render(<MemoryRouter><ProfileContext.Provider value={{ profile, currentProfile: 'a', profiles: ['a', 'b'], setProfile: vi.fn() }}>
    <PageHeaderContext.Provider value={headers}><ChatPage isActive={active} /></PageHeaderContext.Provider>
  </ProfileContext.Provider></MemoryRouter>));
}
async function fill(text: string) {
  const field = container.querySelector('.chat-composer textarea') as HTMLTextAreaElement;
  await act(async () => {
    Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value')!.set!.call(field, text);
    field.dispatchEvent(new Event('input', { bubbles: true }));
  });
}
async function click(label: string) {
  const button = container.querySelector(`[aria-label="${label}"]`) as HTMLButtonElement;
  await act(async () => button.click());
}
beforeEach(() => {
  vi.stubGlobal('localStorage', { getItem: () => null, setItem: vi.fn(), removeItem: vi.fn() });
  instances.length = 0; sessionStorage.clear();
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); vi.clearAllMocks(); vi.unstubAllGlobals(); });

it('sends one prompt, renders streamed text once, and requires explicit approval without leaking secrets into history', async () => {
  await render(); const gw = instances[0];
  expect(container.querySelector('.xterm')).toBeNull();
  await fill('Explain evidence'); await click('Send message');
  expect(gw.request.mock.calls.filter(([method]) => method === 'prompt.submit')).toEqual([
    ['prompt.submit', { session_id: 'runtime-a', profile: 'a', text: 'Explain evidence', surface: 'web' }],
  ]);
  await act(async () => { gw.emit('message.delta', { text: 'Evidence is ' }); gw.emit('message.delta', { text: 'observable.' }); });
  expect(container.textContent).toContain('Evidence is observable.');
  const respond = vi.fn();
  const approval: ServerRequest = { id: 'srq-1', method: 'approval', params: { session_id: 'runtime-a', description: 'Run fixture?', choices: ['once', 'deny'] }, respond, fail: vi.fn() };
  await act(async () => gw.requestHandlers.forEach(h => h(approval)));
  expect(respond).not.toHaveBeenCalled();
  await act(async () => (Array.from(container.querySelectorAll('button')).find(b => b.textContent === 'Allow once')!).click());
  expect(respond).toHaveBeenCalledWith({ choice: 'once' });
  await act(async () => gw.requestHandlers.forEach(h => h({ ...approval, id: 'srq-2', method: 'secret', params: { session_id: 'runtime-a', prompt: 'API key' } })));
  expect(container.querySelector('input[type=password]')).not.toBeNull();
  await act(async () => { gw.emit('request.cancel', { id: 'srq-2' }); gw.emit('message.complete', { text: 'Evidence is observable.', status: 'complete' }); });
  expect(container.querySelectorAll('.chat-message--assistant')).toHaveLength(1);
  expect(container.querySelector('.chat-message--assistant')?.textContent).toContain('Evidence is observable.');
  expect(container.querySelector('[aria-label="Stop response"]')).toBeNull();
  const started = instances.length;
  await render('a', false); await render('a', true);
  expect(instances).toHaveLength(started);
  expect(container.querySelector('[role=log]')?.textContent).not.toContain('API key');
});

it('isolates A→B→A and reconnects by resuming authoritative state without resending prompts', async () => {
  await render('a'); const first = instances[0];
  await fill('Only profile A'); await click('Send message');
  await act(async () => first.emit('message.complete', { text: 'Answer A', status: 'complete' }));
  await render('b'); const second = instances.at(-1)!;
  expect(first.closed).toBe(true);
  expect(container.textContent).not.toContain('Only profile A');
  expect(second.request).toHaveBeenCalledWith('session.create', expect.objectContaining({ profile: 'b' }));
  await act(async () => first.emit('message.delta', { text: 'stale event' }));
  expect(container.textContent).not.toContain('stale event');
  await render('a'); const third = instances.at(-1)!;
  expect(third.request).toHaveBeenCalledWith('session.resume', expect.objectContaining({ profile: 'a', session_id: 'stored-a' }));
  await act(async () => third.stateHandlers.forEach(h => h('closed')));
  expect(container.textContent).toContain('Work may still be running');
  expect((container.querySelector('.chat-composer textarea') as HTMLTextAreaElement).disabled).toBe(true);
  await act(async () => (Array.from(container.querySelectorAll('button')).find(b => b.textContent === 'Reconnect')!).click());
  expect(third.request.mock.calls.filter(([method]) => method === 'prompt.submit')).toHaveLength(0);
  expect(third.request.mock.calls.filter(([method]) => method === 'session.resume')).toHaveLength(2);
});
