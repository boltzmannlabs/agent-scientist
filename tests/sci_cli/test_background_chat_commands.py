"""Background handoff never runs a second writer or bypasses idle/consent checks."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_shell_and_slash_registration_and_reviewed_handoff(tmp_path, monkeypatch):
    from sci_cli import background_chat_commands as commands
    from sci_cli.main import _build_cli_parser
    from sci_cli.commands import resolve_command, COMMANDS
    from sci_cli import skill_add, profiles
    from sci_state import SessionDB
    from pathlib import Path
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    home = tmp_path / ".sci"
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr(profiles, "get_active_profile_name", lambda: "main")
    parser, _ = _build_cli_parser()
    args = parser.parse_args(["background", "start", "--detach", "--json"])
    assert args.func is commands.command and args.detach and args.json
    assert resolve_command("/BACKGROUND").name == "background"
    assert "/detach" in COMMANDS
    ui = SimpleNamespace(show=Mock(), choose=Mock(return_value="Continue"))
    monkeypatch.setattr(skill_add, "WizardUI", lambda cli: ui)
    with SessionDB(home / "state.db") as db:
        db.create_session("saved", "cli", system_prompt="unchanged")
        cli = SimpleNamespace(session_id="saved", _session_db=db, _agent_running=False,
            _app=SimpleNamespace(loop=SimpleNamespace(call_soon_threadsafe=Mock()), exit=Mock()))
        commands.slash(cli, "/background")
        assert cli._pending_relaunch == ["-p", "main", "background", "start", "saved"]
        assert cli._pending_profile_home == str(home)
        assert db.get_session("saved")["system_prompt"] == "unchanged"
        for text, running in [("/background", True), ('/background "', False)]:
            del cli._pending_relaunch
            cli._agent_running = running
            commands.slash(cli, text)
            assert not hasattr(cli, "_pending_relaunch")
            cli._pending_relaunch = None
        cli._agent_running = False
        ui.choose.side_effect = skill_add.Cancelled
        commands.slash(cli, "/background")
        assert cli._pending_relaunch is None


def test_resume_joins_live_worker_before_claiming_a_writer(monkeypatch):
    from sci_cli import background_chat_commands as commands, background_chat_terminal
    from sci_cli.cli_session_recovery import StartupRecoveryUI
    from sci_cli.skill_add import Cancelled
    import sys
    import os
    worker = {"id": "worker", "pid": os.getpid() + 1, "attached": True}
    monkeypatch.setattr(commands, "find_worker", lambda key: worker)
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    choice = Mock(return_value="Move viewer")
    monkeypatch.setattr(StartupRecoveryUI, "choose", choice)
    attach = Mock()
    monkeypatch.setattr(background_chat_terminal, "attach", attach)
    cli = SimpleNamespace(_resumed=True, session_id="saved", _console_print=Mock())
    assert commands.attach_on_resume(cli) is True
    attach.assert_called_once_with("worker", takeover=True)
    attach.reset_mock()
    choice.side_effect = Cancelled
    assert commands.attach_on_resume(cli) is True
    attach.assert_not_called()
    worker["pid"] = os.getpid()
    assert commands.attach_on_resume(cli) is False  # Managed worker must claim its own lease.


@pytest.mark.platforms("posix")
def test_configured_idle_expiry_uses_real_profile_loader(tmp_path, monkeypatch):
    from pathlib import Path
    from sci_cli.background_chat_service import ChatService
    from sci_cli.config import atomic_config_write
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for name, timeout in [("a", 0), ("b", 12), ("a", 0)]:
        home = tmp_path / name
        home.mkdir(exist_ok=True)
        monkeypatch.setenv("SCI_HOME", str(home))
        atomic_config_write(home / "config.yaml", {"session": {"background_idle_timeout": timeout}})
        assert ChatService(home).idle_timeout == timeout


def test_busy_transport_commands_are_immediate_and_never_interrupt_or_queue(monkeypatch):
    from sci_cli import background_chat_commands as commands, background_chats, skill_add
    from sci_cli.cli_tui_mixin import CLITuiMixin
    import queue
    ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=AssertionError("busy command opened a modal")))
    monkeypatch.setattr(skill_add, "WizardUI", lambda cli: ui)
    detach = Mock(return_value=True)
    monkeypatch.setattr(background_chats, "detach_cli", detach)
    event = SimpleNamespace(app=SimpleNamespace(current_buffer=Mock(), invalidate=Mock()))
    cli = SimpleNamespace(_agent_running=True, _background_managed=False,
                          _pending_input=queue.Queue(), agent=Mock())
    for text in ("/background", "/background attach other", "/detach"):
        assert CLITuiMixin._tui_enter_inline_command(cli, event, text, False) is True
        assert cli._pending_input.empty()
        assert not getattr(cli, "_should_exit", False)
        cli.agent.interrupt.assert_not_called()
    assert any("not queued" in str(call) for call in ui.show.call_args_list)
    detach.reset_mock()
    cli._background_managed = True
    assert CLITuiMixin._tui_enter_inline_command(cli, event, "/background", False)
    detach.assert_called_once_with(cli)
    cli.agent.interrupt.assert_not_called()
    assert cli._pending_input.empty()
