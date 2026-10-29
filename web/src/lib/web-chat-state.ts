import type { TranscriptMessage } from '@sci/shared';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'notice';
  text: string;
  name?: string;
  running?: boolean;
}
export interface WebChatState {
  messages: ChatMessage[];
  stream: string;
  busy: boolean;
  status: string;
  error: string;
}
export const emptyChat: WebChatState = { messages: [], stream: '', busy: false, status: '', error: '' };
export type ChatAction =
  | { type: 'hydrate'; messages: TranscriptMessage[]; stream?: string; busy?: boolean; error?: string }
  | { type: 'user'; text: string }
  | { type: 'delta'; text: string }
  | { type: 'interim'; text: string }
  | { type: 'complete'; text?: string; error?: string; status?: string }
  | { type: 'tool'; id: string; name: string; text: string; running: boolean }
  | { type: 'status'; text: string }
  | { type: 'error'; text: string }
  | { type: 'notice'; text: string };
const row = (role: ChatMessage['role'], text: string): ChatMessage => ({ id: crypto.randomUUID(), role, text });

export function chatReducer(state: WebChatState, action: ChatAction): WebChatState {
  switch (action.type) {
    case 'hydrate':
      return { ...emptyChat, busy: Boolean(action.busy), stream: action.stream || '', error: action.error || '',
        messages: action.messages.filter(m => m.display_kind !== 'hidden' && ['user', 'assistant', 'tool'].includes(m.role))
          .map(m => ({ ...row(m.role as ChatMessage['role'], m.text || (typeof m.content === 'string' ? m.content : '')), name: m.name || undefined }))
          .filter(m => m.text || m.name) };
    case 'user': return { ...state, messages: [...state.messages, row('user', action.text)], stream: '', busy: true, status: 'Working…', error: '' };
    case 'delta': return { ...state, stream: state.stream + action.text, busy: true, status: 'Writing…' };
    case 'interim': return { ...state, messages: [...state.messages, row('assistant', action.text || state.stream)], stream: '' };
    case 'complete': {
      const text = action.text || state.stream;
      const last = state.messages.at(-1);
      const alreadyHydrated = !state.busy && !state.stream && last?.role === 'assistant' && last.text === text;
      return { ...state, messages: text && !alreadyHydrated ? [...state.messages, row('assistant', text)] : state.messages,
        stream: '', busy: false, status: action.status === 'interrupted' ? 'Stopped' : '', error: action.error || '' };
    }
    case 'tool': {
      const message: ChatMessage = { id: action.id, role: 'tool', name: action.name, text: action.text, running: action.running };
      const exists = state.messages.some(m => m.id === action.id);
      return { ...state, messages: exists ? state.messages.map(m => m.id === action.id ? message : m) : [...state.messages, message],
        status: action.running ? `Using ${action.name}…` : 'Working…' };
    }
    case 'status': return { ...state, status: action.text };
    case 'error': return { ...state, error: action.text, busy: false, status: '' };
    case 'notice': return { ...state, messages: [...state.messages, row('notice', action.text)] };
  }
}
