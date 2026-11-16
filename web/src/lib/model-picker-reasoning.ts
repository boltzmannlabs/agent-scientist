import type { ModelOptionProvider } from '@sci/shared';
import { REASONING_EFFORTS } from '@sci/shared';

export function modelReasoningChoices(provider: ModelOptionProvider | null | undefined, model: string): string[] {
  const capability = provider?.capabilities?.[model];
  if (capability?.reasoning === false) return [];
  const enabled = capability?.supported_efforts == null
    ? [...REASONING_EFFORTS]
    : REASONING_EFFORTS.filter(level => capability.supported_efforts!.includes(level));
  return capability?.can_disable_reasoning === false ? enabled : ['none', ...enabled];
}
