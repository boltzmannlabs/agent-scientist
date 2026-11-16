// @vitest-environment jsdom
import { afterEach, expect, it, vi } from 'vitest';
import { downloadOutputFile, linkedOutputFile, outputFileReference, outputFilesInResult, outputFilesInResponse, outputFilesLink, splitFileText } from './output-files';

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); delete window.__SCI_SESSION_TOKEN__; });

it('recognizes files independently of extensions, preserves paths and scope, and excludes external/executable links', () => {
  for (const name of ['pairs.csv', 'model.pdb', 'reads.fasta', 'report.pdf', 'plot.png', 'report.docx', 'data.xlsx',
    'outputs.zip', 'weights.safetensors', 'archive.unknown', 'README', '测量 report.json', 'script.exe']) {
    const path = '/workspace/outputs/' + name;
    const file = outputFileReference(path)!;
    expect(file).toEqual({ path, name });
    expect(outputFilesInResult(JSON.stringify({ result: { files: [{ path }] } }))).toEqual([file]);
    expect(outputFilesInResult(JSON.stringify({ provider_specific_result: { arbitrary_name: path } }))).toEqual([]);
    expect(splitFileText(path).find(part => part.file)?.file).toEqual(name === 'README' ? undefined : file);
    const query = new URL(outputFilesLink(file, { profile: 'lab a', sessionId: 'saved&1' }), 'https://sci.test').searchParams;
    expect(query.get('path')).toBe('/workspace/outputs');
    expect(query.get('file')).toBe(path); expect(query.get('profile')).toBe('lab a'); expect(query.get('session_id')).toBe('saved&1');
  }
  expect(outputFileReference('file:///C:/Lab/run%20one/file.csv')?.path).toBe('C:/Lab/run one/file.csv');
  expect(outputFileReference('C:\\Lab\\run one\\file.csv')?.name).toBe('file.csv');
  expect(linkedOutputFile('/workspace/report%20one.csv')?.path).toBe('/workspace/report one.csv');
  expect(linkedOutputFile('</workspace/report one.csv>')?.path).toBe('/workspace/report one.csv');
  const relative = outputFileReference('outputs/report.csv', undefined, true)!;
  expect(new URL(outputFilesLink(relative, { profile: 'a', sessionId: 'saved' }), 'https://sci.test').searchParams.get('path')).toBe('outputs');
  expect(splitFileText('Saved /workspace/report.csv, and /workspace/report.bin.').filter(part => part.file).map(part => part.file!.name)).toEqual(['report.csv', 'report.bin']);
  for (const path of ['https://other.test/report.csv', 'javascript:/report.csv', '//other/report.csv',
    'file://other/report.csv', '\\\\other\\report.csv', '/project/bad\0.txt', '/project/bad\n.txt']) expect(outputFileReference(path, 'https://sci.test')).toBeNull();
  expect(splitFileText('https://other.test/report.csv').some(part => part.file)).toBe(false);
  expect(outputFilesInResult('```python\nprint("/workspace/secret.csv")\n```')).toEqual([]);
});

it('offers tool actions only for declared artifacts and save notices, never instructional paths or cache spillover', () => {
  const instructions = 'Use `/add_boltzmann`, avoid `/tmp`, read `references/tool-contracts.v1.json`. Saved /workspace/example.csv is an illustration.';
  expect(outputFilesInResult(JSON.stringify({ success: true, content: instructions, linked_files: { references: ['references/tool-contracts.v1.json'] } }))).toEqual([]);
  expect(outputFilesInResult('<persisted-output>\nFull output saved to: /home/lab/.sci/cache/spillover/call_123.txt\n</persisted-output>')).toEqual([]);
  expect(outputFilesInResult(JSON.stringify({ output_paths: ['/home/lab/.sci/cache/spillover/call_123.txt', '/workspace/folder', '/tmp'], output_folder: '/workspace/outputs' }))).toEqual([]);
  for (const value of ['/add_boltzmann', '/tmp', '/workspace/folder', '/custom/cache/spillover/call_1.txt', 'references/guide.md']) {
    expect(linkedOutputFile(value)).toBeNull();
    expect(splitFileText(value).some(part => part.file)).toBe(false);
  }
  const result = outputFilesInResult(JSON.stringify({ result: { output_paths: ['/workspace/report.csv', 'C:\\Lab\\result.json'], artifacts: [{ path: 'outputs/README' }], description: '/workspace/example.csv' } }));
  expect(result.map(file => file.path)).toEqual(['/workspace/report.csv', 'C:\\Lab\\result.json', 'outputs/README']);
  expect(outputFilesInResult('Saved `/workspace/report.csv`').map(file => file.name)).toEqual(['report.csv']);
});

it('checks errors with authenticated HEAD then uses native downloads without buffering bytes or persisting tokens', async () => {
  window.__SCI_SESSION_TOKEN__ = 'fixture-only-token';
  const fetch = vi.fn().mockResolvedValue({ ok: true, status: 200, blob: vi.fn() });
  vi.stubGlobal('fetch', fetch);
  const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (this: HTMLAnchorElement) {
    const query = new URL(this.href).searchParams;
    expect(query.get('profile')).toBe('a'); expect(query.get('session_id')).toBe('a-session');
    expect(query.get('token')).toBe('fixture-only-token'); expect(this.download).toBe('a file.unknown');
  });
  const file = outputFileReference('/workspace/a file.unknown')!;
  await downloadOutputFile(file, { profile: 'a', sessionId: 'a-session' });
  expect(fetch.mock.calls[0][1].method).toBe('HEAD');
  expect(fetch.mock.calls[0][1].headers.get('X-Sci-Session-Token')).toBe('fixture-only-token');
  expect(fetch.mock.calls[0][0]).not.toContain('token=');
  expect(click).toHaveBeenCalledOnce(); expect(document.querySelector('a')).toBeNull();
  for (const status of [401, 403, 404, 409, 413]) {
    fetch.mockResolvedValueOnce({ ok: false, status });
    await expect(downloadOutputFile(file, { profile: 'a' })).rejects.toThrow();
  }
  expect(click).toHaveBeenCalledOnce();
});


it('resolves result filenames across formats without guessing a folder or using hidden references', () => {
  const known = [{ name: 'report.pdf', path: '/workspace/project one/report.pdf' }];
  expect(outputFilesInResponse('Download report.pdf and an unrelated.csv', known)).toEqual(known);
  expect(outputFilesInResponse('Read `contract.json`. Use `/add_boltzmann` or `/tmp`.')).toEqual([]);
  expect(outputFilesInResponse('Results saved in `C:\\Lab\\outputs\\`\n\n| File |\n| --- |\n| results.csv / structure.pdb |').map(file => file.path)).toEqual(['C:\\Lab\\outputs/results.csv', 'C:\\Lab\\outputs/structure.pdb']);
  expect(outputFilesInResponse('Saved in /custom/cache/spillover/\ncall_123.txt')).toEqual([]);
  expect(outputFilesInResponse('Saved in /workspace/outputs/\n```python\nprint("example.csv")\n```')).toEqual([]);
});
