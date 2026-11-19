// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { expect, it, vi } from 'vitest';
import { Markdown } from '@/components/Markdown';
import { OutputFile } from './OutputFile';
import { api } from '@/lib/api';
import { ChatTranscript } from '@/components/chat/ChatTranscript';
import { emptyChat } from '@/lib/web-chat-state';
import { ProfileContext } from '@/contexts/profile-context';

vi.mock('@/lib/api', async importOriginal => ({ ...await importOriginal<typeof import('@/lib/api')>(), api: { readFile: vi.fn() } }));

it('previews explicit output artifacts only after a click and restores their scoped actions', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  vi.mocked(api.readFile).mockResolvedValue({ name: 'report.csv', path: '/workspace/report.csv', size: 30,
    mime_type: 'text/csv', data_url: `data:text/csv;base64,${btoa('<script>never execute</script>')}`,
    root: null, locked_root: null, can_change_path: true });
  try {
    await act(async () => root.render(<MemoryRouter>
      {['/workspace/report.csv', 'C:\\Lab\\data set.bin', '/workspace/document.docx'].map(path =>
        <OutputFile key={path} file={{ path, name: path.split(/[\\/]/).pop()! }} scope={{ profile: 'lab', sessionId: 'saved' }} />)}
      <Markdown content={'```python\nprint("/workspace/not-an-artifact.csv")\n```'} />
    </MemoryRouter>));
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
      <ChatTranscript state={{ ...emptyChat, messages: [{ id: 'stored-tool', role: 'tool', name: 'any_provider_tool', text: JSON.stringify({ output_paths: ['/workspace/from-tool.csv'] }) }] }}
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
  const render = (profile: string) => root.render(<MemoryRouter><OutputFile file={{ path: "/workspace/weights.bin", name: "weights.bin" }} scope={{ profile }} /></MemoryRouter>);
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

it('keeps commands, skill references and spillover as text while retaining real output actions in chat', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const instructions = 'Use `/add_boltzmann`, avoid `/tmp`, read `tool-contracts.v1.json` and `references/guide.md`.';
  try {
    await act(async () => root.render(<MemoryRouter><ProfileContext.Provider value={{ profile: 'lab', currentProfile: 'lab', profiles: ['lab'], setProfile: vi.fn() }}>
      <ChatTranscript state={{ ...emptyChat, messages: [
        { id: 'skill', role: 'tool', name: 'skill_view', text: JSON.stringify({ content: instructions, linked_files: { references: ['references/guide.md'] } }) },
        { id: 'spillover', role: 'tool', name: 'any_tool', text: 'Full output saved to: /home/lab/.sci/cache/spillover/call_123.txt' },
        { id: 'reply', role: 'assistant', text: instructions + '\n\n`/home/lab/.sci/cache/spillover/call_123.txt`\n\n[Report](outputs/report.csv)' },
        { id: 'output', role: 'tool', name: 'custom_plugin', text: JSON.stringify({ output_paths: ['/workspace/results.csv'] }) },
      ] }} onSuggestion={vi.fn()} sessionId="saved" />
    </ProfileContext.Provider></MemoryRouter>));
    expect([...host.querySelectorAll('[aria-label^="Download "]')].map(node => node.getAttribute('aria-label'))).toEqual(['Download results.csv']);
    expect(host.textContent).toContain('/add_boltzmann');
    expect(host.textContent).toContain('call_123.txt');
    expect(api.readFile).not.toHaveBeenCalled();
  } finally { await act(async () => root.unmount()); host.remove(); }
});

it('restores exact declared output paths and never turns GCP references into duplicate file cards', async () => {
  Object.assign(globalThis, { IS_REACT_ACT_ENVIRONMENT: true });
  const host = document.createElement('div'); document.body.append(host); const root = createRoot(host);
  const report = 'Done. Results (saved in /workspace/outputs/)\n\n| File | Contents |\n| --- | --- |\n| heavy_H-18.csv / heavy_H-18.fasta | heavy chains |\n| light_L-18.csv / light_L-18.fasta | light chains |\n\nUse `/add_boltzmann`. Read `references/tool-contracts.v1.json`. Cache: `/custom/cache/spillover/call_123.txt`';
  try {
    await act(async () => root.render(<MemoryRouter><ProfileContext.Provider value={{ profile: 'lab', currentProfile: 'lab', profiles: ['lab'], setProfile: vi.fn() }}>
      <ChatTranscript state={{ ...emptyChat, messages: [
        { id: 'user', role: 'user', text: 'Generate sequences' },
        { id: 'download', role: 'tool', name: 'any_download_tool', text: JSON.stringify({ output_paths: ['/workspace/outputs/heavy_H-18.csv', '/workspace/outputs/light_L-18.csv'] }) },
        { id: 'convert', role: 'tool', name: 'any_conversion_tool', text: JSON.stringify({ output_paths: ['/workspace/outputs/heavy_H-18.fasta', '/workspace/outputs/light_L-18.fasta'], gcp_paths: ['bucket/output/extra.csv'] }) },
        { id: 'final', role: 'assistant', text: report + '\n\nGCP artifact paths:\n[heavy_H-18.csv](bucket/job/heavy_H-18.csv)\n`bucket/job/light_L-18.csv`\nSaved in /other/guessed/: not-downloaded.csv' },
      ] }} onSuggestion={vi.fn()} sessionId="retained-session" />
    </ProfileContext.Provider></MemoryRouter>));
    const response = host.querySelector('.chat-message--assistant')!;
    const buttons = [...response.querySelectorAll('[aria-label^="Download "]')];
    expect(buttons.map(button => button.getAttribute('aria-label'))).toEqual([
      'Download heavy_H-18.csv', 'Download light_L-18.csv', 'Download heavy_H-18.fasta', 'Download light_L-18.fasta',
    ]);
    for (const link of response.querySelectorAll('a')) {
      const query = new URL(link.getAttribute('href')!, 'https://sci.test').searchParams;
      expect(query.get('profile')).toBe('lab'); expect(query.get('session_id')).toBe('retained-session');
      expect(query.get('path')).toBe('/workspace/outputs');
    }
    expect(api.readFile).not.toHaveBeenCalled();
  } finally { await act(async () => root.unmount()); host.remove(); }
});
