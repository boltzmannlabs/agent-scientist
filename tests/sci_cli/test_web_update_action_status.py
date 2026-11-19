"""Update status follows the current attempt across dashboard restarts."""

import asyncio
from types import SimpleNamespace

import pytest

from sci_cli import web_server_gateway as state
from sci_cli.web_routers import actions


@pytest.fixture
def action_state(tmp_path, monkeypatch):
    monkeypatch.setattr(state, '_ACTION_LOG_DIR', tmp_path)
    for name in ('_ACTION_PROCS', '_ACTION_RESULTS', '_ACTION_IDS', '_ACTION_COMMANDS'):
        monkeypatch.setattr(state, name, {})
    monkeypatch.setattr('sci_cli.update_lock.read_live_update', lambda: None)
    monkeypatch.setattr(actions, '_latest_update_receipt_summary', lambda: None)
    return tmp_path


def test_live_and_finished_attempt_never_reuses_previous_completion(action_state, monkeypatch):
    old, new = 'a' * 32, 'b' * 32
    (action_state / 'update.log').write_text(f'=== sci-update completed {old} ===\n')
    monkeypatch.setattr(actions, '_latest_update_receipt_summary', lambda: {'action_id': old, 'outcome': 'partial'})
    proc = SimpleNamespace(pid=123, poll=lambda: None)
    state._ACTION_PROCS['sci-update'] = proc
    state._ACTION_IDS['sci-update'] = new
    running = asyncio.run(actions.get_action_status('sci-update'))
    assert running['running'] and running['action_id'] == new
    assert 'receipt' not in running
    assert f'=== sci-update completed {old} ===' not in running['lines']
    proc.poll = lambda: 0
    proc.wait = lambda timeout: 0
    finished = asyncio.run(actions.get_action_status('sci-update'))
    repeated = asyncio.run(actions.get_action_status('sci-update'))
    assert finished['action_id'] == repeated['action_id'] == new
    assert not repeated['running'] and repeated['exit_code'] == 0


def test_restart_waits_for_live_update_and_preserves_partial_result(action_state, monkeypatch):
    action_id = 'b' * 32
    (action_state / 'update.log').write_text(f'=== sci-update completed {action_id} ===\n')
    receipt = {'action_id': action_id, 'outcome': 'partial', 'finished_at': '2026-11-16T00:00:00Z'}
    monkeypatch.setattr(actions, '_latest_update_receipt_summary', lambda: receipt)
    monkeypatch.setattr('sci_cli.update_lock.read_live_update', lambda: SimpleNamespace(pid=321))
    running = asyncio.run(actions.get_action_status('sci-update'))
    assert running['running'] and running['exit_code'] is None and running['pid'] == 321
    assert 'action_id' not in running and 'receipt' not in running
    monkeypatch.setattr(actions, 'is_commit_build', lambda _: False)
    monkeypatch.setattr(actions, '_dashboard_local_update_managed_externally', lambda: False)
    monkeypatch.setattr('sci_cli.update_contract.evaluate_update_admission', lambda _: None)
    monkeypatch.setattr(actions, '_spawn_sci_action', lambda *_, **__: pytest.fail('must reattach without spawning'))
    attached = asyncio.run(actions.update_sci())
    assert attached['already_running'] and attached['pid'] == 321
    monkeypatch.setattr('sci_cli.update_lock.read_live_update', lambda: None)
    finished = asyncio.run(actions.get_action_status('sci-update'))
    assert not finished['running'] and finished['exit_code'] == 1
    assert finished['receipt'] == receipt and finished['action_id'] == action_id
