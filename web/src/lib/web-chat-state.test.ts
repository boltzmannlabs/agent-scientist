import { expect, it } from 'vitest';
import { chatReducer, emptyChat } from './web-chat-state';

it('reconciles streamed and resumed completions without repeating a final answer', () => {
  let state = chatReducer(emptyChat, { type: 'user', text: 'Question' });
  state = chatReducer(state, { type: 'delta', text: 'Partial' });
  state = chatReducer(state, { type: 'complete', text: 'Full answer' });
  expect(state.messages.map(m => m.text)).toEqual(['Question', 'Full answer']);
  state = chatReducer(state, { type: 'complete', text: 'Full answer' });
  expect(state.messages).toHaveLength(2);
  state = chatReducer(state, { type: 'user', text: 'Repeat it' });
  state = chatReducer(state, { type: 'complete', text: 'Full answer' });
  expect(state.messages.map(m => m.text)).toEqual(['Question', 'Full answer', 'Repeat it', 'Full answer']);
});

it('keeps partial output visible on failure and never exposes hidden prompt scaffolding on resume', () => {
  let state = chatReducer(emptyChat, { type: 'hydrate', messages: [
    { role: 'system', text: 'system prompt' }, { role: 'user', text: 'hidden source', display_kind: 'hidden' },
    { role: 'user', text: 'Visible question' },
  ] });
  state = chatReducer(state, { type: 'delta', text: 'Partial answer' });
  state = chatReducer(state, { type: 'error', text: 'Request timed out' });
  expect(state.messages.map(m => m.text)).toEqual(['Visible question']);
  expect(state.stream).toBe('Partial answer');
  expect(state.error).toBe('Request timed out');
  expect(state.busy).toBe(false);
});
