"""Foreground polling keeps one job through long waits, errors and interruption."""

from types import SimpleNamespace

import pytest

from plugins.boltzmann import nodeapi_helpers as helpers
from plugins.boltzmann.polling_display import snapshot
from gateway.session_context import scoped_current_session_id
from tools.interrupt import set_interrupt


@pytest.mark.parametrize("ending", ["success", "failed", "cancelled", "auth", "malformed", "stop"])
def test_foreground_poll_stays_with_job_and_reports_terminal_or_unresolved(monkeypatch, ending, capsys):
    clock, checks = [0.0], []

    def pause(seconds):
        clock[0] += 24 * 3600

    def get(url, **kwargs):
        assert kwargs["json"] == {"docId": "existing-job", "job_name": "fixture"}
        assert 0 < kwargs["timeout"] <= 60
        checks.append(kwargs)
        if len(checks) in {1, 4, 5, 11, 12}:
            raise helpers.requests.exceptions.Timeout("controlled transport timeout")
        if len(checks) <= 20:
            status = "pending" if len(checks) < 10 else "running"
            return SimpleNamespace(status_code=404, json=lambda: {"status": status, "message": "queued"})
        if ending == "stop":
            set_interrupt(True)
        body = {"status": "running" if ending == "stop" else ending}
        if ending == "malformed":
            body = {"message": "no status"}
        return SimpleNamespace(status_code=401 if ending == "auth" else 200, json=lambda: body)

    def forbidden(*args, **kwargs):
        pytest.fail("Polling must not submit or cancel a remote job")

    monkeypatch.setattr(helpers, "time", SimpleNamespace(monotonic=lambda: clock[0], sleep=pause))
    monkeypatch.setattr(helpers.requests, "get", get)
    monkeypatch.setattr(helpers.requests, "post", forbidden)
    monkeypatch.setattr(helpers.requests, "delete", forbidden)
    monkeypatch.setattr(helpers, "_log_platform_terminal", lambda *args: None)
    try:
        with scoped_current_session_id("poll-owner"):
            result = helpers.fetch_status("fixture", "existing-job", token="fixture-key",
                                          max_wait=1, poll_once=True, wait_until_terminal=True)
    finally:
        set_interrupt(False)

    assert len(checks) == 21 and clock[0] >= 48 * 3600
    assert result["doc_id"] == "existing-job" and not result.get("timeout")
    terminal = ending in {"success", "failed", "cancelled"}
    assert bool(result.get("job_terminal_confirmed")) is terminal
    if not terminal:
        assert result["status"] == "unknown" and result["error"]
        assert result["safe_to_retry"] is False
    if ending == "stop":
        assert result["cancelled"] and "remote job was not cancelled" in result["error"]
    captured = capsys.readouterr()
    assert not captured.out  # Keep MCP stdio free of progress text.
    output = captured.err
    assert "running" in output and "elapsed" in output
    assert "pending" not in output and "Network error" not in output
    assert len(output.splitlines()) == 5
    assert "Further polling updates hidden" not in output
    assert snapshot(session_id="poll-owner") == []
