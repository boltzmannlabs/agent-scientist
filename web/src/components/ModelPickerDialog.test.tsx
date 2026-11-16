// @vitest-environment jsdom
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { MemoryRouter } from 'react-router';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ModelPickerDialog } from './ModelPickerDialog';
import type { ModelOptionsResult } from '@sci/shared';

let root: Root;
let container: HTMLDivElement;
const options: ModelOptionsResult = { provider: 'boltzmann_models', model: 'discoveryrsi', providers: [{
  slug: 'boltzmann_models', name: 'Boltzmann', models: ['discoveryrsi', 'qwen'],
  capabilities: {
    discoveryrsi: { reasoning: true, fast: false, supported_efforts: ['low', 'medium', 'high'], can_disable_reasoning: false },
    qwen: { reasoning: false, fast: false, supported_efforts: [] },
  },
}] };
async function click(text: string) {
  const button = Array.from(document.querySelectorAll('button')).find(b => b.textContent?.trim().startsWith(text));
  expect(button).toBeDefined();
  await act(async () => button!.click());
}
beforeEach(() => {
  (globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
  container = document.createElement('div'); document.body.append(container); root = createRoot(container);
});
afterEach(async () => { await act(async () => root.unmount()); container.remove(); });

it('offers only supported efforts and preserves the selected effort through cost confirmation', async () => {
  const onApply = vi.fn().mockResolvedValueOnce({ confirm_required: true, confirm_message: 'Review cost' }).mockResolvedValueOnce({});
  await act(async () => root.render(<MemoryRouter><ModelPickerDialog loader={async () => options}
    onApply={onApply} onClose={vi.fn()} reasoningEffort="medium" /></MemoryRouter>));
  await click('discoveryrsi');
  const select = document.querySelector('[aria-label="Reasoning effort"]') as HTMLSelectElement;
  expect(Array.from(select.options).map(o => o.value)).toEqual(['', 'low', 'medium', 'high']);
  expect(select.value).toBe('medium');
  await act(async () => { select.value = 'high'; select.dispatchEvent(new Event('change', { bubbles: true })); });
  await click('Switch'); await click('Switch anyway');
  expect(onApply.mock.calls.map(call => call[0])).toEqual([
    expect.objectContaining({ model: 'discoveryrsi', reasoningEffort: 'high', persistGlobal: false, confirmExpensiveModel: false }),
    expect.objectContaining({ model: 'discoveryrsi', reasoningEffort: 'high', persistGlobal: false, confirmExpensiveModel: true }),
  ]);
});

it('does not send an effort for a route that declares no effort control', async () => {
  const request = vi.fn().mockImplementation(async (method: string) => method === 'model.options' ? options : {});
  await act(async () => root.render(<MemoryRouter><ModelPickerDialog gw={{ request } as never}
    sessionId="owned-session" onClose={vi.fn()} reasoningEffort="medium" /></MemoryRouter>));
  await click('qwen');
  expect(document.querySelector('[aria-label="Reasoning effort"]')).toBeNull();
  expect(document.body.textContent).toContain('provider manages');
  await click('Switch');
  expect(request).toHaveBeenCalledWith('config.set', expect.objectContaining({
    session_id: 'owned-session', value: 'qwen --provider boltzmann_models',
  }));
});
