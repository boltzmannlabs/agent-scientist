"""Conservative outcome checks for named specialists; retain all raw output."""
import re
import json

_PLAN = re.compile(r"^(?:i(?:['’]ll| will| am going to)|let me)\s+(?:start|begin|read|review|verify|check|calculate|use|inspect)\b", re.I)
_OUTCOME = re.compile(r'^\s*(?:#{1,6}\s*)?(?:\*\*)?(?:outcome|status|task outcome)(?:\*\*)?\s*:\s*'
                      r'(?:\*\*)?\s*(blocked(?: before execution)?|incomplete|failed)\b', re.I | re.M)


def assess(child, entry):
    from agent.specialist_policy import SpecialistPolicy
    if not isinstance(getattr(child, '_specialist_policy', None), SpecialistPolicy):
        return entry
    return assess_entry(entry)


def assess_entry(entry):
    """Interpret an explicit task-outcome header; completing an answer is not completing its task."""
    if entry.get('status') != 'completed' or entry.get('exit_reason') != 'completed':
        return entry
    text = str(entry.get('summary') or '').strip()
    header = _OUTCOME.search('\n'.join(text.splitlines()[:12]))
    outcome = header[1].lower() if header else ''
    if text.startswith('{'):
        try:
            data = json.loads(text)
        except ValueError:
            data = None
        if isinstance(data, dict) and isinstance(data.get('task_outcome'), str):
            declared = data['task_outcome'].lower()
            if declared in {'blocked', 'failed', 'incomplete'}:
                outcome = declared
    if outcome:
        outcome = 'blocked' if outcome.startswith('blocked') else outcome
        entry.update(status='failed', exit_reason=outcome, task_outcome=outcome,
                     error=f'Specialist reported {outcome} execution. Its original report and tool evidence are retained; '
                           'no automatic retry or replacement was started.')
        return entry
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
