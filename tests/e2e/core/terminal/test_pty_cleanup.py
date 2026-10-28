"""Terminal cleanup waits for the worker's asynchronous idle acknowledgement."""

import pytest

from sci_cli import background_chats
from tests.e2e.core.terminal import _pty


@pytest.mark.platforms("linux")
def test_cleanup_waits_for_detached_worker_to_report_idle(tmp_path, monkeypatch):
    term = object.__new__(_pty.PtySci)
    term.classic_cli = True
    term.sci_home = tmp_path
    term.sid = 42
    term.seen_members = set()
    states = iter(["running", "idle"])
    actions = []
    last_state = None

    def request(action, **params):
        nonlocal last_state
        actions.append(action)
        if action == "status":
            last_state = next(states)
            return {"chats": [{"id": "fixture", "alive": True,
                               "attached": False, "state": last_state}]}
        assert last_state == "idle", "Do not stop a worker before its idle acknowledgement"
        return {"state": "stopped"}

    monkeypatch.setattr(background_chats, "read_server", lambda home: {"pid": 42})
    monkeypatch.setattr(background_chats, "request", request)
    monkeypatch.setattr(_pty, "session_members", lambda sid: [])

    assert term.leftover_processes(timeout=2) == []
    assert actions == ["status", "status", "stop", "shutdown"]
