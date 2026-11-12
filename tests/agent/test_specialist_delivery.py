"""Reports retain exact contents across summary budgets, profile scopes and synchronous handoff."""
from types import SimpleNamespace
import time

from agent.specialist_policy import SpecialistPolicy
from agent.specialist_runs import record
from agent.specialist_delivery import reports_from_results, stage_sync, stage_delivery, VerbatimReport
from sci_cli.native_profile_creation import profile_scope


def test_long_report_is_restored_from_owning_profile_receipt_a_b_a(tmp_path, monkeypatch):
    from pathlib import Path
    from tools.delegate_tool_results import _apply_summary_budget
    from tools.process_registry_notifications import TimelineNotification
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    monkeypatch.setattr('tools.delegate_tool._load_config', lambda: {'max_summary_chars': 400})
    for home in (homes[0], homes[1], homes[0]):
        with profile_scope(home):
            report = f'Protocol: {home.name}\n\n# Exact report\n\n' + '| α | 42 |\n' * 800
            policy = SpecialistPolicy('auditor', str(home.resolve()), 'revision', frozenset(), frozenset(),
                                      frozenset(), ('auditor',), time.monotonic() + 60)
            child = SimpleNamespace(_specialist_policy=policy, _subagent_id='sa-0-fixture', model='fixture', provider='custom')
            row = {'specialist': 'auditor', 'run_id': 'sa-0-fixture', 'status': 'completed', 'summary': report}
            record(child, 'Audit', row)
            trimmed = dict(row)
            _apply_summary_budget([trimmed], None)
            assert trimmed['summary_truncated'] and trimmed['summary'] != report
            assert reports_from_results([trimmed]) == report
            notification = TimelineNotification.for_delegation('event', {'type': 'async_delegation',
                'is_batch': True, 'status': 'completed', 'results': [trimmed], 'goals': ['Audit']})
            assert notification.specialist_report == report


def test_sync_delivery_is_turn_scoped_and_ordinary_or_nested_delegation_still_synthesizes():
    row = {'specialist': 'auditor', 'status': 'completed', 'summary': '# Requested format\n\nUntouched.'}
    parent = SimpleNamespace(_current_turn_id='turn-a', _specialist_policy=None, _interrupt_requested=False)
    state = SimpleNamespace(turn_id='turn-a', api_call_count=1, current_turn_user_idx=0,
                            messages=[{'role': 'user', 'content': 'Audit'}], final_response=None)
    stage_sync(parent, [row])
    assert stage_delivery(parent, state)
    assert isinstance(state.final_response, VerbatimReport) and state.final_response == row['summary']
    assert state._turn_exit_reason == 'completed'
    stage_sync(parent, [row])
    state.turn_id = 'turn-b'
    assert not stage_delivery(parent, state)  # a stale handoff cannot replace another user turn
    assert reports_from_results([{'status': 'completed', 'summary': 'ordinary child'}]) is None
    parent._specialist_policy = 'pod-lead'
    stage_sync(parent, [row])
    assert not stage_delivery(parent, state)
    parent._specialist_policy = None
    state.turn_id = parent._current_turn_id = 'turn-c'
    # Intermediate work takes precedence over a final report in the same round,
    # regardless of the order in which independent tool calls finish.
    stage_sync(parent, [dict(row, delivery='intermediate')])
    stage_sync(parent, [row])
    assert not stage_delivery(parent, state)
    state.turn_id = parent._current_turn_id = 'turn-d'
    stage_sync(parent, [row])
    stage_sync(parent, [dict(row, delivery='intermediate')])
    assert not stage_delivery(parent, state)
    state.turn_id = parent._current_turn_id = 'turn-e'
    stage_sync(parent, [row])
    assert stage_delivery(parent, state)  # continuation does not leak into another user turn


def test_compacted_history_does_not_use_stale_user_index_for_delivery():
    parent = SimpleNamespace(_current_turn_id='turn-a', _specialist_policy=None, _interrupt_requested=False)
    state = SimpleNamespace(
        turn_id='turn-a', api_call_count=0, current_turn_user_idx=4,
        messages=[{'role': 'user', 'content': 'new request'}], final_response=None,
    )

    assert not stage_delivery(parent, state)
