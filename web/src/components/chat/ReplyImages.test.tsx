// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { authedFetch } from '@/lib/api';
import { ReplyImages } from './ReplyImages';

vi.mock('@/lib/api', () => ({ authedFetch: vi.fn() }));
let root: Root;
let container: HTMLDivElement;
const fetchImage = vi.mocked(authedFetch);
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div');
  document.body.append(container);
  root = createRoot(container);
  vi.stubGlobal('URL', Object.assign(URL, {
    createObjectURL: vi.fn(() => 'blob:figure'), revokeObjectURL: vi.fn(),
  }));
  fetchImage.mockResolvedValue({ ok: true, headers: new Headers(),
    blob: async () => new Blob(['png'], { type: 'image/png' }) } as Response);
});
afterEach(async () => {
  await act(async () => root.unmount());
  container.remove(); vi.resetAllMocks(); vi.unstubAllGlobals();
});
async function render(text: string, profile = 'a', sessionId = 'saved') {
  await act(async () => root.render(<ReplyImages text={text} scope={{ profile, sessionId }} />));
}

it('previews unique delivered images with authenticated profile and session scope, including saved Figure rows', async () => {
  await render('MEDIA:"/work/reaction figure.png"\nMEDIA:"/work/reaction figure.png"\n- Figure: /work/second.png (also .svg and editable .cdxml there)');
  expect(container.querySelectorAll('img')).toHaveLength(2);
  expect(fetchImage).toHaveBeenCalledTimes(2);
  const query = new URL(fetchImage.mock.calls[0][0] as string, 'https://sci.test').searchParams;
  expect(query.get('path')).toBe('/work/reaction figure.png');
  expect(query.get('profile')).toBe('a'); expect(query.get('session_id')).toBe('saved');
  expect(container.querySelector('img')?.alt).toContain('reaction figure.png');
});

it('does not refetch an unchanged image on transcript updates and releases URLs on scope changes', async () => {
  await render('MEDIA:/work/figure.png');
  await render('New explanation\nMEDIA:/work/figure.png');
  expect(fetchImage).toHaveBeenCalledTimes(1);
  await render('MEDIA:/work/figure.png', 'b', 'another');
  expect(fetchImage).toHaveBeenCalledTimes(2);
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:figure');
  const query = new URL(fetchImage.mock.calls[1][0] as string, 'https://sci.test').searchParams;
  expect(query.get('profile')).toBe('b'); expect(query.get('session_id')).toBe('another');
});

it('ignores code examples, remote URLs, documents and unlabelled file paths', async () => {
  await render('```text\nMEDIA:/example.png\n```\nMEDIA:https://example.test/a.png\nMEDIA:/work/report.svg\n/work/file.png');
  expect(fetchImage).not.toHaveBeenCalled();
  expect(container.querySelector('img')).toBeNull();
});

it.each(['denied', 'declared-size', 'actual-size', 'network'])('keeps the transcript usable when image loading fails: %s', async reason => {
  if (reason === 'network') fetchImage.mockRejectedValueOnce(new Error('offline'));
  else fetchImage.mockResolvedValueOnce({ ok: reason !== 'denied',
    headers: new Headers(reason === 'declared-size' ? { 'content-length': '8000001' } : {}),
    blob: async () => ({ size: reason === 'actual-size' ? 8000001 : 3 }),
  } as Response);
  await render('MEDIA:/work/figure.png');
  expect(container.querySelector('img')).toBeNull();
  expect(URL.createObjectURL).not.toHaveBeenCalled();
});
