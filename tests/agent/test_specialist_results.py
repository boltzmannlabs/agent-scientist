"""Worker execution and the report's declared task outcome remain separate."""
from agent.specialist_results import assess_entry


def test_explicit_blocked_outcome_with_tool_activity_preserves_report():
    text = 'Outcome: BLOCKED BEFORE EXECUTION\nNo target program was run.\nA report was written.'
    entry = {'status': 'completed', 'exit_reason': 'completed', 'summary': text,
             'run_id': 'sa-0-fixture', 'tool_trace': [{'tool': 'write_file', 'status': 'ok'}]}
    result = assess_entry(entry)
    assert result['status'] == result['exit_reason'] == 'completed' and result['task_outcome'] == 'blocked'
    assert result['summary'] == text and result['run_id'] == 'sa-0-fixture'
    assert assess_entry(dict(result)) == result
    for header in ('**Outcome:** BLOCKED', 'Status: incomplete', 'Task outcome: failed', '{"task_outcome":"blocked"}'):
        report = assess_entry({'status': 'completed', 'exit_reason': 'completed', 'summary': header})
        assert report['status'] == report['exit_reason'] == 'completed'
        assert report['task_outcome'] in {'blocked', 'incomplete', 'failed'}
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
    assert row['status'] == 'completed' and row['result']['task_outcome'] == 'blocked'
    # Old retained receipts get an honest view without silently rewriting their evidence.
    from utils import atomic_json_write
    row.update(status='completed', result=legacy)
    atomic_json_write(path, row, mode=0o600)
    before = path.read_bytes()
    assert history()[0]['status'] == 'completed' and history()[0]['result']['task_outcome'] == 'blocked'
    assert path.read_bytes() == before
    from agent.specialist_delivery import stage_sync, stage_delivery, report_from_event
    parent = SimpleNamespace(_current_turn_id='a', _specialist_policy=None, _interrupt_requested=False)
    stage_sync(parent, [dict(result, specialist='reviewer')])
    assert not stage_delivery(parent, SimpleNamespace(turn_id='a', api_call_count=1))
    assert report_from_event({'type': 'async_delegation', 'results': [dict(result, specialist='reviewer')]}) is None


def test_completed_review_mentions_blockers_without_claiming_its_task_is_blocked():
    for text in ('Review complete. Two historical blocked runs were identified.',
                 'Outcome: completed\nThe report includes a blocked-job example.',
                 'Status: unblocked\nAll fixture checks passed.',
                 '> Outcome: BLOCKED\nThe supplied document says that; this review is complete.'):
        result = assess_entry({'status': 'completed', 'exit_reason': 'completed', 'summary': text})
        assert result['status'] == 'completed'
    limited = assess_entry({'status': 'completed', 'exit_reason': 'completed',
                           'summary': 'Outcome: INCOMPLETE\nAll outputs delivered; backend conventions are undocumented.'})
    assert limited['status'] == 'completed' and limited['exit_reason'] == 'completed'
    assert limited['task_outcome'] == 'incomplete' and 'error' not in limited
    actual_failure = dict(status='failed', exit_reason='provider_error', summary='Saved output', error='Connection lost')
    assert assess_entry(dict(actual_failure)) == actual_failure
