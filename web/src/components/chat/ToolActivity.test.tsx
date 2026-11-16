// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { GatewayEvent, TranscriptMessage } from '@sci/shared';
import { ProfileContext } from '@/contexts/profile-context';
import { ChatTranscript } from './ChatTranscript';
import { useWebChat } from './useWebChat';

let listener: (event: GatewayEvent) => void;
let messages: TranscriptMessage[];
vi.mock('@/lib/gatewayClient', () => ({ GatewayClient: class {
  async connect() {}
  close() {}
  onAny(fn: typeof listener) { listener = fn; return () => {}; }
  onState() { return () => {}; }
  onRequest() { return () => {}; }
  async request(method: string) {
    if (method === 'session.resume') return { session_id: 'runtime', stored_session_id: 'saved', messages, info: {} };
    return {};
  }
} }));
function Conversation() {
  const { state } = useWebChat({ profile: 'fixture', resume: 'saved', cwd: '' });
  return <ChatTranscript state={state} onSuggestion={() => {}} sessionId="saved" />;
}
let container: HTMLDivElement;
let root: Root;
beforeEach(() => {
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  messages = [{ role: 'user', text: 'Inspect the files' }];
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); sessionStorage.clear(); vi.restoreAllMocks(); });
async function render() {
  await act(async () => root.render(<MemoryRouter><ProfileContext.Provider value={{ profile: 'fixture', currentProfile: 'fixture', profiles: ['fixture'], setProfile: () => {} }}><Conversation /></ProfileContext.Provider></MemoryRouter>));
}
async function emit(type: string, payload: unknown) {
  await act(async () => listener({ type, session_id: 'runtime', payload } as GatewayEvent));
}

it('renders generic live operations, results and artifacts without replacing descriptions or exposing reasoning', async () => {
  await render();
  await emit('tool.start', { tool_id: 'shell', name: 'terminal', preview: 'Inspect example.txt' });
  await emit('message.interim', { text: 'I am checking the results.' });
  await emit('tool.complete', { tool_id: 'shell', name: 'terminal', summary: 'Command finished', result: { output: 'hello world', exit_code: 0, output_path: '/tmp/report.csv' } });
  const card = container.querySelector('details')!;
  expect(card.querySelector('summary')?.textContent).toContain('Inspect example.txt');
  expect(card.textContent).toContain('Command finished');
  expect(card.querySelector('pre')?.textContent).toContain('hello world');
  await act(async () => card.querySelector('summary')!.click());
  expect(card.open).toBe(true);
  expect(container.querySelector('[aria-label="Download report.csv"]')).not.toBeNull();
  expect(container.querySelector('.chat-message--assistant')?.textContent).toContain('I am checking the results.');
  await emit('tool.complete', { tool_id: 'skill', name: 'skill_view', result: { content: 'Read the documentation first.' } });
  await emit('tool.complete', { tool_id: 'failure', name: 'custom_plugin', result: { error: 'Connection unavailable' } });
  await emit('tool.complete', { tool_id: 'protected', name: 'read_file', result: 'secret-raw-value', result_text: '[redacted]' });
  await emit('reasoning.delta', { text: 'private reasoning' });
  await emit('tool.complete', { tool_id: 'large', name: 'search', result: 'x'.repeat(100_000) });
  expect(container.textContent).toContain('Read the documentation first.');
  expect(container.textContent).toContain('Connection unavailable');
  expect(container.textContent).toContain('Display truncated');
  expect(container.textContent).not.toContain('secret-raw-value');
  expect(container.textContent).not.toContain('private reasoning');
  expect(container.textContent).not.toContain('No output returned');
  expect(container.querySelectorAll('details')).toHaveLength(5);
});

it('restores output and context and reconciles completion replay, distinguishing missing, empty and falsy results', async () => {
  messages.push({ role: 'tool', tool_call_id: 'saved-tool', name: 'terminal', context: 'Inspect example.txt', text: '{"output":"saved result"}', reasoning: 'not for display' });
  messages.push({ role: 'tool', tool_call_id: 'old-tool', name: 'legacy_tool', context: 'Older transcript' });
  await render();
  expect(container.textContent).toContain('saved result');
  expect(container.textContent).toContain('Output is not available in this transcript.');
  await emit('tool.complete', { tool_id: 'saved-tool', name: 'terminal', result: { output: 'saved result' } });
  expect(container.querySelectorAll('details')).toHaveLength(2);
  expect(container.querySelector('summary')?.textContent).toContain('Inspect example.txt');
  for (const [id, result] of [['empty', ''], ['zero', 0], ['false', false]] as const) {
    await emit('tool.complete', { tool_id: id, name: 'any_tool', result });
  }
  const outputs = [...container.querySelectorAll('details pre')].map(node => node.textContent);
  expect(outputs.filter(text => text === 'No output returned.')).toHaveLength(1);
  expect(outputs).toContain('0'); expect(outputs).toContain('false');
  expect(container.textContent).not.toContain('not for display');
});
