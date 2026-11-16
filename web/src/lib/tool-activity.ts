import type { ToolLabel } from '@sci/shared';

// The gateway bounds display text too; retain a client bound for older servers.
const MAX_OUTPUT_CHARS = 64 * 1024;
export function toolOutputText(value: unknown): string {
  if (value === undefined || value === null) return '';
  let text: string;
  if (typeof value === 'string') {
    try { text = JSON.stringify(JSON.parse(value), null, 2); }
    catch { text = value; }
  } else text = JSON.stringify(value, null, 2);
  return text.length > MAX_OUTPUT_CHARS
    ? `${text.slice(0, MAX_OUTPUT_CHARS)}\n[Display truncated; additional output is not shown.]` : text;
}

export interface ToolActivity {
  id: string;
  name: string;
  text: string;
  context?: string;
  summary?: string;
  running: boolean;
  outputAvailable: boolean;
}

export function toolActivity(payload: Record<string, unknown>, running: boolean): ToolActivity {
  const labels = Array.isArray(payload.labels) ? payload.labels as ToolLabel[] : [];
  const context = payload.preview || payload.context || labels.map(label => label.preview).filter(Boolean).join(' · ');
  // A supplied display projection is redacted by the server. Never fall back to
  // raw data just because that projection is empty.
  const output = payload.result_text ?? payload.result;
  return {
    id: String(payload.tool_id),
    name: labels.map(label => label.text).filter(Boolean).join(' · ') || String(payload.name || 'Tool activity'),
    context: typeof context === 'string' ? context : undefined,
    summary: typeof payload.summary === 'string' ? payload.summary : undefined,
    text: running ? '' : toolOutputText(output),
    running,
    outputAvailable: !running && (Object.hasOwn(payload, 'result_text') || Object.hasOwn(payload, 'result')),
  };
}
