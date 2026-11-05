"""Task completion must not be inferred from a delivered blocked-status report."""
from agent.specialist_results import assess_entry


def test_explicit_blocked_outcome_with_tool_activity_preserves_report():
    text = 'Outcome: BLOCKED BEFORE EXECUTION\nNo target program was run.\nA report was written.'
    entry = {'status': 'completed', 'exit_reason': 'completed', 'summary': text,
             'run_id': 'sa-0-fixture', 'tool_trace': [{'tool': 'write_file', 'status': 'ok'}]}
    result = assess_entry(entry)
    assert result['status'] == 'failed' and result['task_outcome'] == result['exit_reason'] == 'blocked'
    assert result['summary'] == text and result['run_id'] == 'sa-0-fixture'
    assert assess_entry(dict(result)) == result
    for header in ('**Outcome:** BLOCKED', 'Status: incomplete', 'Task outcome: failed', '{"task_outcome":"blocked"}'):
        assert assess_entry({'status': 'completed', 'exit_reason': 'completed', 'summary': header})['status'] == 'failed'
    from types import SimpleNamespace
    from sci_constants import get_sci_home
    from agent.specialist_policy import SpecialistPolicy
    from agent.specialist_runs import record, history
    import json
    import time
    home = get_sci_home()
    policy = SpecialistPolicy('reviewer', str(home.resolve()), 'revision', frozenset(), frozenset(),
                              frozenset(), ('reviewer',), time.monotonic() + 30)
    child = SimpleNamespace(_specialist_policy=policy, _subagent_id='sa-0-fixture')
    legacy = {'status': 'completed', 'exit_reason': 'completed', 'summary': text, 'run_id': 'sa-0-fixture'}
    record(child, 'Execute the task', legacy)
    path = home / 'subagent-runs/sa-0-fixture.json'
    row = json.loads(path.read_text())
    assert row['status'] == 'failed' and row['result']['task_outcome'] == 'blocked'
    # Old retained receipts get an honest view without silently rewriting their evidence.
    from utils import atomic_json_write
    row.update(status='completed', result=legacy)
    atomic_json_write(path, row, mode=0o600)
    before = path.read_bytes()
    assert history()[0]['status'] == 'failed' and history()[0]['result']['task_outcome'] == 'blocked'
    assert path.read_bytes() == before


def test_completed_review_mentions_blockers_without_claiming_its_task_is_blocked():
    for text in ('Review complete. Two historical blocked runs were identified.',
                 'Outcome: completed\nThe report includes a blocked-job example.',
                 'Status: unblocked\nAll fixture checks passed.',
                 '> Outcome: BLOCKED\nThe supplied document says that; this review is complete.'):
        result = assess_entry({'status': 'completed', 'exit_reason': 'completed', 'summary': text})
        assert result['status'] == 'completed'
