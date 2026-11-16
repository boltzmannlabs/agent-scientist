"""Profile navigation moves viewers without prompting to replace live runtimes."""

import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.sci_cli.test_background_chats import Viewer, service, WORKER


@pytest.mark.platforms("posix")
def test_profile_navigation_opens_fresh_main_and_reuses_named_workers(tmp_path, monkeypatch):
    from sci_cli import background_chat_terminal as terminal, cli_runtime_refresh
    from sci_cli.background_chat_launch import launch_interactive
    from sci_cli.background_chats import request, find_worker
    from sci_cli.cli_session_recovery import StartupRecoveryUI
    from sci_cli.native_profile_session import request_switch, relaunch_profile
    from sci_cli._parser import build_top_level_parser

    root = tmp_path / ".sci"
    other = root / "profiles" / "other"
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(root))
    monkeypatch.setattr(os, "get_terminal_size", lambda *args: os.terminal_size((100, 30)))
    monkeypatch.setattr("sci_cli.background_chat_launch.service_eligible", lambda *a, **kw: True)
    monkeypatch.setattr(StartupRecoveryUI, "choose", Mock(side_effect=AssertionError("No navigation prompts")))
    monkeypatch.setattr(cli_runtime_refresh, "refresh_attached_worker",
                        Mock(side_effect=AssertionError("Navigation must not refresh code")))
    daemons, viewers, workers = [], [], {}
    launches = []

    class ViewerRelaunch(Exception):
        pass

    def capture_launch(root, args, **kwargs):
        launches.append(args)
        raise ViewerRelaunch()

    monkeypatch.setattr("sci_cli._launchers.runtime_command", capture_launch)

    def attach_once(chat_id, *, home=None, takeover=False, view_session=None):
        active = Path(os.environ["SCI_HOME"])
        viewer = Viewer(active, chat_id, takeover=takeover)
        viewers.append(viewer)
        viewer.until(b"READY")
        if active == root:
            assert find_worker(chat_id, active)["pid"] != workers[active]["pid"]
        else:
            assert find_worker(chat_id, active)["pid"] == workers[active]["pid"]
        return {}  # Return control to the test, leaving this viewer attached.

    monkeypatch.setattr(terminal, "_attach_once", attach_once)
    try:
        for target in (root, other):
            target.mkdir(parents=True, exist_ok=True)
            (target / "config.yaml").write_text("{}\n")
            # Several fresh main chats can coexist; each fixture owns its own ID.
            daemons.append(service(target, worker_source=WORKER.replace("'fixture'", "'fixture-' + str(os.getpid())")))
            key = request("start", home=target, cwd=str(tmp_path))["id"]
            viewer = Viewer(target, key)
            viewers.append(viewer)
            viewer.until(b"READY")
            workers[target] = find_worker(key, target)
        for source, target, name in ((other, root, "main"), (root, other, "other"), (other, root, "main")):
            previous = request("status", home=target)["chats"]
            monkeypatch.setenv("SCI_HOME", str(source))
            cli = SimpleNamespace(_app=SimpleNamespace(is_running=True, loop=Mock(), exit=Mock()))
            request_switch(cli, name, SimpleNamespace(show=Mock()))
            with pytest.raises(ViewerRelaunch):
                relaunch_profile(cli)
            argv = launches[-1].copy()
            # The entry point consumes -p before argparse; bind the resulting scope.
            index = argv.index("-p")
            del argv[index:index + 2]
            monkeypatch.setenv("SCI_HOME", cli._pending_profile_home)
            args = build_top_level_parser()[0].parse_args(argv)
            assert launch_interactive(args)
            assert len(request("status", home=target)["chats"]) == len(previous) + int(target == root)
            assert find_worker(workers[source]["id"], source)["alive"]
            assert find_worker(workers[target]["id"], target)["alive"]
    finally:
        for viewer in viewers:
            viewer.close()
        for daemon in daemons:
            daemon.terminate()
            daemon.communicate(timeout=20)


def test_profile_navigation_preserves_foreground_owner_and_opens_separate_chat(tmp_path, monkeypatch):
    from sci_cli.background_chat_launch import launch_interactive, worker_arguments
    from sci_cli import background_chats, background_chat_terminal
    from sci_cli.cli_session_recovery import StartupRecoveryUI
    from sci_cli.active_sessions import try_acquire_active_session
    from sci_cli._parser import build_top_level_parser
    from sci_state import SessionDB

    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    with SessionDB(home / "state.db") as db:
        db.create_session("foreground", "cli")
    lease, error = try_acquire_active_session(session_id="foreground", surface="cli", config={})
    assert lease and not error
    monkeypatch.setattr("sci_cli.background_chat_launch.service_eligible", lambda *a, **kw: True)
    monkeypatch.setattr(StartupRecoveryUI, "choose", Mock(side_effect=AssertionError("No navigation prompts")))
    monkeypatch.setattr(background_chats, "find_view_worker", lambda _: None)
    monkeypatch.setattr(background_chats, "ensure_server", Mock())
    start = Mock(return_value={"id": "separate"})
    monkeypatch.setattr(background_chats, "request", start)
    attach = Mock()
    monkeypatch.setattr(background_chat_terminal, "attach", attach)
    monkeypatch.setattr(os, "get_terminal_size", lambda *args: os.terminal_size((80, 24)))
    parser = build_top_level_parser()[0]
    args = parser.parse_args(["--cli", "--profile-switch", "--resume", "foreground"])
    try:
        assert launch_interactive(args)
        assert start.call_args.kwargs["session_id"] is None
        attach.assert_called_once_with("separate", takeover=False, view_session=None, refresh=False)
        from sci_cli.active_sessions import active_session_registry_snapshot
        assert any(owner["session_id"] == "foreground" for owner in active_session_registry_snapshot())
        assert not parser.parse_args(worker_arguments(args)).profile_switch
    finally:
        lease.release()
