"""Conservative outcome checks for named specialists; retain all raw output."""
import re

_PLAN = re.compile(r"^(?:i(?:['’]ll| will| am going to)|let me)\s+(?:start|begin|read|review|verify|check|calculate|use|inspect)\b", re.I)


def assess(child, entry):
    from agent.specialist_policy import SpecialistPolicy
    if not isinstance(getattr(child, '_specialist_policy', None), SpecialistPolicy):
        return entry
    if entry.get('status') != 'completed' or entry.get('exit_reason') != 'completed':
        return entry
    text = str(entry.get('summary') or '').strip()
    # A narrowly recognized promise with zero tool activity is not a delivered task.
    # This does not attempt to certify arbitrary answers or replace declared output-schema checks.
    if (len(text) < 350 and len(re.split(r'[.!?]\s+', text)) == 1 and _PLAN.match(text)
            and not re.search(r'[\d=:]', text) and not entry.get('tool_trace')):
        entry.update(status='failed', exit_reason='incomplete_response', task_outcome='incomplete',
                     error='Specialist returned only a short plan, with no executed tools or delivered review. '
                           'The raw response is retained; no automatic retry or replacement was started.')
    else:
        entry['task_outcome'] = 'returned_answer_not_independently_verified'
    return entry
