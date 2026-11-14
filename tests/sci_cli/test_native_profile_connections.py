"""Real loopback MCP discovery obeys consent and publishes explicit permissions."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_mcp_handshake_credentials_selection_and_cancellation(tmp_path, monkeypatch):
    from sci_cli.native_profile_services import setup_mcp
    from sci_cli.native_profile_creation import profile_scope, create_native
    from sci_cli.config import atomic_config_replace, read_user_config_raw, save_env_value_secure
    from sci_cli.skill_add import Cancelled
    from sci_cli.profiles import get_profile_dir
    from agent.secret_scope import build_profile_secret_scope
    calls = []
    cancel_during = threading.Event()
    probe_cancel = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_error(405)

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            calls.append((data["method"], self.headers.get("Authorization")))
            if data["method"] == "initialize" and cancel_during.is_set():
                probe_cancel.set()
            if "id" not in data:
                self.send_response(202)
                self.end_headers()
                return
            methods = {
                "initialize": {"protocolVersion": data.get("params", {}).get("protocolVersion", "2025-03-26"),
                               "capabilities": {"tools": {}}, "serverInfo": {"name": "fixture", "version": "1"}},
                "tools/list": {"tools": [{"name": name, "description": "Fixture tool", "inputSchema": {
                    "type": "object", "properties": {}}} for name in ("search", "delete")]},
            }
            assert data["method"] in methods, "business tools must never execute during setup"
            body = json.dumps({"jsonrpc": "2.0", "id": data["id"], "result": methods[data["method"]]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    main = tmp_path / ".sci"
    main.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(main))
    monkeypatch.setattr("sci_cli.profiles._notify_multiplexer", lambda *_: None)
    monkeypatch.setattr("sci_cli.profiles._maybe_register_gateway_service", lambda *_: None)
    atomic_config_replace(main / "config.yaml", {"model": {"provider": "openai-codex", "default": "fixture"}})
    with profile_scope(main):
        save_env_value_secure("API_KEY", "fixture-secret")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    # Cold MCP imports share this deadline; allow loaded parallel CI workers.
    source = {"url": f"http://127.0.0.1:{server.server_port}/mcp", "transport": "http",
              "headers": {"Authorization": "Bearer ${API_KEY}"}, "connect_timeout": 15}
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    ui = SimpleNamespace(show=Mock())
    try:
        ui.choose = Mock(side_effect=["Use existing key from source profile", Cancelled()])
        with pytest.raises(Cancelled):
            setup_mcp(SimpleNamespace(), ui, main, "literature", source, scratch)
        assert calls == []
        answers = iter(["Use existing key from source profile", "Check connection"])

        def choose(question, choices):
            if "allowed tools" in question:
                return next((s for s in choices if s.startswith("search —")), "Done")
            return next(answers)

        ui.choose = choose
        service = setup_mcp(SimpleNamespace(), ui, main, "literature", source, scratch)
        assert service.verified and service.tools == ["search"]
        assert service.config["tools"]["include"] == ["search"]
        assert {method for method, _ in calls} <= {"initialize", "notifications/initialized", "tools/list"}
        assert all(auth == "Bearer fixture-secret" for _, auth in calls)
        target = get_profile_dir("study")
        create_native("study", main, [], [service], [], {"backend": "local", "cwd": str(target / "workspace")}, "Scientist")
        cfg = read_user_config_raw(target / "config.yaml")
        assert "fixture-secret" not in json.dumps(cfg)
        assert "fixture-secret" not in str(ui.show.call_args_list)
        assert "API_KEY" not in build_profile_secret_scope(target)
        assert list(service.secrets.values()) == ["fixture-secret"]
        with profile_scope(target):
            from sci_cli.mcp_config import _resolve_mcp_server_config
            resolved = _resolve_mcp_server_config(cfg["mcp_servers"]["literature"])
            assert resolved["headers"]["Authorization"] == "Bearer fixture-secret"
        assert source["headers"]["Authorization"] == "Bearer ${API_KEY}"
        from sci_cli.mcp_config import _probe_single_server
        cancel_during.set()
        with profile_scope(main), pytest.raises(InterruptedError, match="cancelled"):
            _probe_single_server("cancelled", source, cancel_event=probe_cancel)
        # A cleanup failure must not be hidden behind a successful cancellation.
        async def failed_shutdown():
            raise OSError("fixture cleanup failure")

        async def connection_with_failed_cleanup(*_):
            probe_cancel.set()
            return SimpleNamespace(_tools=[], shutdown=failed_shutdown)

        probe_cancel.clear()
        monkeypatch.setattr("tools.mcp_tool_discovery._connect_server", connection_with_failed_cleanup)
        with profile_scope(main), pytest.raises(RuntimeError, match="cleanup could not be verified"):
            _probe_single_server("failed-cleanup", source, cancel_event=probe_cancel)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.platforms("posix")
def test_native_relaunch_targets_only_selected_home_and_preserves_persisted_prompt(tmp_path, monkeypatch):
    from sci_cli.native_profile_session import request_switch, relaunch_profile
    from sci_cli.profiles import create_profile
    from sci_cli.config import atomic_config_replace
    from sci_state import SessionDB
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.config import save_env_value_secure
    import os
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / ".sci"
    root.mkdir()
    monkeypatch.setenv("SCI_HOME", str(root))
    (root / ".env").write_text("PRIVATE_MAIN_API_KEY=main-only\n")
    monkeypatch.setattr("sci_cli.profiles._notify_multiplexer", lambda *_: None)
    monkeypatch.setattr("sci_cli.profiles._maybe_register_gateway_service", lambda *_: None)
    home = create_profile("target", no_skills=True, no_alias=True)
    atomic_config_replace(home / "config.yaml", {"terminal": {"backend": "local"}})
    assert (home / "workspace").is_dir()
    with profile_scope(home):
        save_env_value_secure("BOLTZMANN_API_KEY", "target-key")
    monkeypatch.setenv("PRIVATE_MAIN_API_KEY", "main-only")
    db = SessionDB(home / "state.db")
    try:
        db.create_session("fixture-session", source="cli", system_prompt="byte-stable cached prompt")
    finally:
        db.close()
    cli = SimpleNamespace(_app=SimpleNamespace(is_running=True, loop=Mock(), exit=Mock()))
    request_switch(cli, "target", SimpleNamespace(show=Mock()))
    assert cli._pending_relaunch[-2:] == ["--resume", "fixture-session"]
    monkeypatch.setattr("sci_cli.relaunch.build_relaunch_argv", lambda args, **kw: ["fixture-sci", *args])
    monkeypatch.chdir(tmp_path)
    executed = []
    monkeypatch.setattr(os, "execvpe", lambda file, args, env: executed.append((file, args, env)))
    relaunch_profile(cli)
    env = executed[0][2]
    assert env["SCI_HOME"] == str(home)
    assert env.get("PRIVATE_MAIN_API_KEY") != "main-only"
    assert env["BOLTZMANN_API_KEY"] == "target-key"
    assert Path.cwd() == home / "workspace"
    db = SessionDB(home / "state.db", read_only=True)
    try:
        assert db.get_session("fixture-session")["system_prompt"] == "byte-stable cached prompt"
    finally:
        db.close()
