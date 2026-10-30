import { renderToStaticMarkup } from 'react-dom/server';
import { expect, it } from 'vitest';
import { Markdown } from './Markdown';
it('renders comparison tables and preserves escaped pipes and inline formatting', () => {
  const html = renderToStaticMarkup(<Markdown content={'Comparison\n\n| Measure | Result |\n| --- | --- |\n| **Count** | 12 |\n| Symbol | a\\|b |'} />);
  expect(html).toContain('<table'); expect(html).toContain('<thead>');
  expect(html).toContain('Count</strong>'); expect(html).toContain('a|b');
  expect(html.match(/<td /g)).toHaveLength(4);
});
it('keeps code fences literal and blocks unsafe links inside table cells', () => {
  const html = renderToStaticMarkup(<Markdown content={'| Link | Value |\n| --- | --- |\n| [unsafe](javascript:alert) | <script>bad</script> |\n\n```text\n| A | B |\n| --- | --- |\n```'} />);
  expect(html.match(/<table/g)).toHaveLength(1);
  expect(html).not.toContain('href="javascript:'); expect(html).not.toContain('<script>');
  expect(html).toContain('&lt;script&gt;'); expect(html).toContain('<pre');
});
