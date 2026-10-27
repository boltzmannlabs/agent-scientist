"""Lifecycle controls preserve ownership; launch options survive the process boundary."""

from types import SimpleNamespace
from unittest.mock import Mock


def test_exit_menu_distinguishes_cancel_detach_and_stop(monkeypatch):
    from sci_cli import background_chat_lifecycle as lifecycle, background_chats
    from sci_cli.cli_modal_mixin import CLIModalMixin
    from agent import interrupt_compat
    stop = Mock()
    detach = Mock(return_value=True)
    monkeypatch.setattr(interrupt_compat, "request_hard_interrupt", stop)
    monkeypatch.setattr(background_chats, "detach_cli", detach)
    cli = SimpleNamespace(_background_managed=True, _agent_running=True, agent=object(),
                          _capture_modal_input_snapshot=Mock(), _restore_modal_input_snapshot=Mock(),
                          _invalidate=Mock(), _app=SimpleNamespace(exit=Mock()))
    for choice in ("cancel", "background", "cancel_task", "exit"):
        stop.reset_mock(); detach.reset_mock(); cli._app.exit.reset_mock()
        assert lifecycle.show_running_exit_choices(cli)
        CLIModalMixin._submit_slash_confirm_response(cli, choice)
        assert cli._slash_confirm_state is None
        assert stop.call_count == int(choice in ("cancel_task", "exit"))
        assert detach.call_count == int(choice == "background")
        assert cli._app.exit.call_count == int(choice == "exit")


def test_launch_options_and_profile_navigation_keep_the_owning_scope(tmp_path, monkeypatch):
    from sci_cli.background_chat_launch import worker_arguments, launch_interactive
    from sci_cli.main import _light_chat_parser
    from sci_cli import background_chat_lifecycle as lifecycle, background_chats
    parser = _light_chat_parser()
    args = parser.parse_args(["--cli", "chat", "--model", "chosen", "--provider", "custom",
                              "--skills", "a", "--skills", "b", "--reasoning", "low",
                              "--yolo", "--ignore-rules", "--max-turns", "5"])
    worker = parser.parse_args(worker_arguments(args))
    for field in ("model", "provider", "skills", "reasoning", "yolo", "ignore_rules", "max_turns"):
        assert getattr(worker, field) == getattr(args, field)
    assert worker.no_daemon and worker.cli
    assert not launch_interactive(worker)  # No recursive daemon launch.
    request = Mock()
    monkeypatch.setattr(background_chats, "request", request)
    for profile in ("a", "b", "a"):
        cli = SimpleNamespace(_pending_relaunch=["--cli", "-p", profile],
                              _pending_profile_home=str(tmp_path / profile), _should_exit=False)
        lifecycle.navigate(cli)
        assert request.call_args.kwargs["target_home"] == str(tmp_path / profile)
        assert request.call_args.kwargs["args"] == ["--cli", "-p", profile]
        assert not cli._should_exit and cli._pending_relaunch is None
