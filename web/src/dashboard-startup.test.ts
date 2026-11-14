// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest';
import html from '../index.html?raw';

function startup() {
  const frame = document.createElement('iframe');
  document.body.append(frame);
  const view = frame.contentWindow as Window & typeof globalThis;
  const doc = view.document;
  doc.documentElement.innerHTML = html;
  const script = [...doc.scripts].find(node => !node.src)!;
  let timeout: (() => void) | undefined;
  const run = new Function('window', 'document', 'setTimeout', 'clearTimeout', script.textContent!);
  run(view, doc, (callback: () => void) => { timeout = callback; return 1; }, vi.fn());
  return { view, doc, expire: () => timeout!(), close: () => frame.remove() };
}

describe('dashboard bootstrap independent of its JavaScript bundle', () => {
  it('shows loading before React starts and removes it after the app commits', () => {
    const page = startup();
    try {
      const panel = page.doc.getElementById('dashboard-startup')!;
      expect(panel.hidden).toBe(false);
      expect(panel.textContent).toContain('Loading your dashboard');
      page.view.dispatchEvent(new page.view.Event('sci:dashboard-ready'));
      expect(panel.hidden).toBe(true);
      // An uncaught render failure must also recover after initial startup.
      page.view.dispatchEvent(new page.view.Event('sci:dashboard-error'));
      expect(panel.hidden).toBe(false);
      expect(panel.getAttribute('role')).toBe('alert');
    } finally { page.close(); }
  });

  it('offers recovery when the entry module fails or loading never completes', () => {
    const page = startup();
    try {
      const doc = page.doc;
      const originalUrl = page.view.location.href;
      const recovery = doc.getElementById('dashboard-recovery')!;
      expect(recovery.hidden).toBe(true);
      doc.querySelector('script[type="module"]')!.dispatchEvent(new page.view.Event('error'));
      expect(recovery.hidden).toBe(false);
      expect(doc.getElementById('dashboard-reload')?.textContent).toBe('Reload dashboard');
      recovery.hidden = true;
      page.expire();
      expect(recovery.hidden).toBe(false);
      expect(page.view.location.href).toBe(originalUrl);
    } finally { page.close(); }
  });
});
