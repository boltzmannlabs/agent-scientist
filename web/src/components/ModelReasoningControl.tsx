import type { ModelOptionProvider } from '@sci/shared';
import { modelReasoningChoices } from '@/lib/model-picker-reasoning';

interface Props {
  provider: ModelOptionProvider | null;
  model: string;
  value: string;
  disabled: boolean;
  onChange(value: string): void;
}

export function ModelReasoningControl({ provider, model, value, disabled, onChange }: Props) {
  const choices = modelReasoningChoices(provider, model);
  return <div className="px-5 py-3 border-t border-border text-xs">
    {choices.length ? <label className="flex items-center gap-3">
      <span>Reasoning effort</span>
      <select aria-label="Reasoning effort" className="border border-border bg-card px-2 py-1" disabled={disabled || !model}
        value={choices.includes(value) ? value : ''} onChange={event => onChange(event.target.value)}>
        <option value="">Keep current effort</option>
        {choices.map(level => <option key={level} value={level}>{level}</option>)}
      </select>
    </label> : <p>Effort selection is unavailable for this model; the provider manages its behavior.</p>}
    <p className="mt-1 text-muted-foreground">Thinking visibility follows your display settings.</p>
  </div>;
}
