// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { Markdown } from '@/components/Markdown';
import { OutputFileContext } from './output-file-context';
import { api } from '@/lib/api';
import { ChatTranscript } from '@/components/chat/ChatTranscript';
import { emptyChat } from '@/lib/web-chat-state';
import { ProfileContext } from '@/contexts/profile-context';

vi.mock('@/lib/api', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api')>(), api: { readFile: vi.fn() } }));

it('links ordinary, quoted and Markdown file references, keeps code literal and previews text only after a click', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  vi.mocked(api.readFile).mockResolvedValue({ name: 'report.csv', path: '/workspace/report.csv', size: 30,
    mime_type: 'text/csv', data_url: `data:text/csv;base64,${btoa('<script>never execute</script>')}`,
    root: null, locked_root: null, can_change_path: true });
  try {
    await act(async () => root.render(<MemoryRouter><OutputFileContext.Provider value={{ profile: 'lab', sessionId: 'saved' }}>
      <Markdown content={'/workspace/report.csv\n\n`C:\\Lab\\data set.bin`\n\n[Report](/workspace/document.docx)\n\n```python\nprint("/workspace/not-an-artifact.csv")\n```'} />
    </OutputFileContext.Provider></MemoryRouter>));
    expect(api.readFile).not.toHaveBeenCalled();
    expect(host.querySelectorAll('a').length).toBe(3);
    expect(host.textContent).toContain('data set.bin'); expect(host.textContent).toContain('document.docx');
    expect(host.querySelector('pre')?.textContent).toContain('not-an-artifact.csv');
    const preview = [...host.querySelectorAll('button')].find(button => button.textContent === 'Preview')!;
    await act(async () => { preview.click(); });
    expect(api.readFile).toHaveBeenCalledWith('/workspace/report.csv', expect.any(AbortSignal), { profile: 'lab', sessionId: 'saved' }, 20 * 1024 * 1024);
    expect(document.querySelector('[role="dialog"] pre')?.textContent).toContain('<script>never execute</script>');
    expect(document.querySelector('[role="dialog"] script')).toBeNull();
    await act(async () => root.render(<MemoryRouter><ProfileContext.Provider value={{ profile: 'lab', currentProfile: 'default', profiles: ['lab'], setProfile: vi.fn() }}>
      <ChatTranscript state={{ ...emptyChat, messages: [{ id: 'stored-tool', role: 'tool', name: 'any_provider_tool', text: JSON.stringify({ output_path: '/workspace/from-tool.csv' }) }] }}
        onSuggestion={vi.fn()} sessionId="saved" />
    </ProfileContext.Provider></MemoryRouter>));
    const actions = host.querySelector('[aria-label="Files referenced by tool result"]')!;
    expect(actions.textContent).toContain('from-tool.csv');
    expect(actions.closest('details')).toBeNull();
    expect(actions.querySelector('a')?.getAttribute('href')).toContain('session_id=saved');
    expect(api.readFile).toHaveBeenCalledOnce(); // hydrating a saved result never fetches the file
  } finally { await act(async () => root.unmount()); host.remove(); vi.mocked(api.readFile).mockReset(); }
});

it('discards open previews across profile switches and reports unavailable formats without removing download actions', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  vi.mocked(api.readFile).mockRejectedValue(new Error('File not found'));
  const render = (profile: string) => root.render(<MemoryRouter><OutputFileContext.Provider value={{ profile }}><Markdown content={'`/workspace/weights.bin`'} /></OutputFileContext.Provider></MemoryRouter>);
  try {
    await act(async () => render('a'));
    await act(async () => { [...host.querySelectorAll('button')].find(button => button.textContent === 'Preview')!.click(); });
    expect(document.querySelector('[role="alert"]')?.textContent).toContain('File not found');
    expect(document.querySelector('[role="dialog"]')?.textContent).toContain('Download complete file');
    await act(async () => render('b')); expect(document.querySelector('[role="dialog"]')).toBeNull();
    await act(async () => render('a')); expect(document.querySelector('[role="dialog"]')).toBeNull();
    expect(vi.mocked(api.readFile)).toHaveBeenCalledOnce();
  } finally { await act(async () => root.unmount()); host.remove(); vi.mocked(api.readFile).mockReset(); }
});
