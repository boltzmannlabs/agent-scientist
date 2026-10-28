from cli import SciCLI
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sci_cli.active_sessions import (
    active_session_registry_snapshot,
    try_acquire_active_session,
)


def test_cli_claim_active_session_respects_global_limit(tmp_path, monkeypatch):
    monkeypatch.setenv("SCI_HOME", str(tmp_path / ".sci"))
    cfg = {"max_concurrent_sessions": 1}
    held, message = try_acquire_active_session(
        session_id="held-session",
        surface="tui",
        config=cfg,
    )
    assert message is None
    assert held is not None

    cli = object.__new__(SciCLI)
    cli.session_id = "new-cli-session"
    cli.config = cfg
    cli._active_session_lease = None
    printed: list[str] = []
    cli._console_print = lambda text: printed.append(text)

    try:
        assert cli._claim_active_session("cli") is False
        assert len(printed) == 1
        # Names the holding surface ("tui"), not the blocked one.
        assert "tui" in printed[0]

        held.release()

        assert cli._claim_active_session("cli") is True
        assert [entry["session_id"] for entry in active_session_registry_snapshot()] == [
            "new-cli-session"
        ]
    finally:
        held.release()
        cli._release_active_session()


@pytest.mark.parametrize("mode", ["registry_error", "noninteractive", "interactive"])
def test_claim_fails_closed_and_recovery_requires_interactive_entry(monkeypatch, mode):
    from sci_cli.active_sessions import ActiveSessionRefusal, SESSION_NOT_OWNED
    from sci_cli import active_sessions, cli_session_recovery
    shell = object.__new__(SciCLI)
    shell.session_id, shell.config, shell._active_session_lease = "saved", {}, None
    shell._console_print = Mock()
    lease = SimpleNamespace(release=Mock())
    refusal = ActiveSessionRefusal("Owned elsewhere", SESSION_NOT_OWNED)
    acquire = Mock(side_effect=OSError("registry unreadable") if mode == "registry_error"
                   else [(None, refusal), (lease, None)])
    offer = Mock(return_value=True)
    monkeypatch.setattr(active_sessions, "try_acquire_active_session", acquire)
    monkeypatch.setattr(cli_session_recovery, "offer_startup_recovery", offer)
    try:
        assert shell._claim_active_session(interactive_recovery=mode == "interactive") is (mode == "interactive")
        if mode == "interactive":
            offer.assert_called_once_with("saved")
            assert acquire.call_count == 2  # Never bypass atomic acquisition after closing the owner.
        else:
            offer.assert_not_called()
            assert shell._active_session_lease is None
    finally:
        shell._release_active_session()
