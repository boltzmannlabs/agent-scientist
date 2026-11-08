"""Profile-scoped client for persistent classic-CLI conversations."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time

import psutil

from sci_constants import get_sci_home

FRAME_LIMIT = 128 * 1024

# Display capabilities belong to the attaching terminal, not the daemon's
# original launcher (which may be a monochrome automation process).
TERMINAL_ENV_KEYS = frozenset({
    "TERM", "COLORTERM", "NO_COLOR", "FORCE_COLOR", "CLICOLOR", "CLICOLOR_FORCE",
    "TERM_PROGRAM", "TERM_PROGRAM_VERSION", "COLORFGBG", "VTE_VERSION",
    "WT_SESSION", "KITTY_WINDOW_ID", "KONSOLE_VERSION",
})


def terminal_environment():
    return {key: os.environ[key] for key in TERMINAL_ENV_KEYS if key in os.environ}


def locations(home=None):
    home = Path(home or get_sci_home()).resolve()
    root = home / "runtime" / "background-chats"
    digest = hashlib.sha256(str(home).encode()).hexdigest()[:24]
    endpoint = None
    if os.name == "posix":
        name = f"sci-chat-{os.getuid()}-{digest}.sock"  # windows-footgun: ok — POSIX transport
        # Scratch retention must never own a persistent service's control socket.
        endpoint = root / "control.sock"
        if len(os.fsencode(endpoint)) > 100:
            # no-tmp: ok — AF_UNIX needs a short fallback independent of SCI_HOME/TMPDIR.
            endpoint = Path("/tmp") / name
    return home, root, endpoint


def read_server(home=None):
    _, root, _ = locations(home)
    try:
        record = json.loads((root / "server.json").read_text(encoding="utf-8-sig"))
        process = psutil.Process(record["pid"])
        if abs(process.create_time() - record["started"]) > 0.01 or process.status() == psutil.STATUS_ZOMBIE:
            return None
        return record
    except (FileNotFoundError, psutil.NoSuchProcess):
        return None


def _connection_endpoints(home, record, endpoint):
    if os.name == "nt":
        address = record.get("endpoint")
        if (not isinstance(address, list) or len(address) != 2 or address[0] != "127.0.0.1"
                or type(address[1]) is not int or not 0 < address[1] < 65536):
            raise RuntimeError("Invalid Windows background service endpoint; refusing to send credentials.")
        return [tuple(address)]
    if record.get("endpoint"):
        return [str(record["endpoint"])]
    # Pre-endpoint records belong to live older services. Keep them reachable
    # without restarting workers, even when the attaching shell changed TMPDIR.
    digest = hashlib.sha256(str(home).encode()).hexdigest()[:24]
    name = f"sci-chat-{os.getuid()}-{digest}.sock"  # windows-footgun: ok — connect requires POSIX endpoint
    candidates = [endpoint, home / "cache" / "scratch" / name,
                  Path(tempfile.gettempdir()) / name,
                  Path("/tmp") / name]  # no-tmp: ok — legacy AF_UNIX fallback
    return list(dict.fromkeys(str(path) for path in candidates if len(os.fsencode(path)) <= 100))


def connect(home=None):
    home, _, endpoint = locations(home)
    record = read_server(home)
    if not record or (endpoint is None and os.name != "nt"):
        raise RuntimeError("No background chat service is running in this profile.")
    endpoints = _connection_endpoints(home, record, endpoint)
    for endpoint in endpoints:
        sock = socket.socket(socket.AF_INET if os.name == "nt" else socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(5)
        try:
            sock.connect(endpoint)
            send(sock, {"token": record["token"], "home": str(home)})
            return sock
        except (FileNotFoundError, ConnectionRefusedError):
            sock.close()
        except BaseException:
            sock.close()
            raise
    raise RuntimeError(
        f"Background chat service PID {record['pid']} is alive, but its socket is missing or refusing connections. "
        f"Profile: {home}. Checked: {', '.join(map(str, endpoints))}. "
        "No replacement was started; existing work may still be running. "
        "Recover the existing service before resuming its chats. "
        "Use `sci --no-daemon` for a separate foreground chat."
    )


def send(sock, data):
    payload = json.dumps(data, separators=(",", ":")).encode() + b"\n"
    if len(payload) > FRAME_LIMIT:
        raise ValueError("Background control message is too large.")
    sock.sendall(payload)


def request(action, *, home=None, **params):
    with connect(home) as sock:
        sock.settimeout(10)
        send(sock, {"action": action, **params})
        with sock.makefile("rb") as stream:
            line = stream.readline(FRAME_LIMIT + 1)
        if not line or len(line) > FRAME_LIMIT:
            raise RuntimeError("Background service disconnected or returned an oversized response.")
        result = json.loads(line)
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result


def ensure_server(home=None):
    from sci_cli.active_sessions import _FileLock
    from tools.environments.local import served_profile_child_env
    from sci_cli._launchers import runtime_command
    home, root, _ = locations(home)
    if os.name == "nt":
        from sci_cli.windows_ssh_runtime import _ensure_directory
        _ensure_directory(root)
    else:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
    with _FileLock(root / "start.lock"):
        if read_server(home):
            request("status", home=home)  # A live but unreachable service must not be duplicated.
            return
        env = served_profile_child_env(target_home=home, inherit_credentials=True)
        log_fd = os.open(root / "service.log", os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        with os.fdopen(log_fd, "ab") as log:
            repo = Path(__file__).resolve().parents[1]
            command = runtime_command(repo, [str(home)], module="sci_cli.background_chat_service", home=home)
            options = {"start_new_session": True}
            if os.name == "nt":
                from sci_cli._subprocess_compat import windows_detach_flags, windows_detach_flags_without_breakaway
                options = {"creationflags": windows_detach_flags()}
            try:
                child = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=log, close_fds=True, **options)
            except PermissionError:
                if os.name != "nt":
                    raise
                child = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                         stdout=log, stderr=log, close_fds=True,
                                         creationflags=windows_detach_flags_without_breakaway())
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f"Background service failed to start. See {root / 'service.log'}.")
            if read_server(home):
                request("status", home=home)
                return
            time.sleep(0.1)
        child.terminate()
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        raise RuntimeError("Background service startup timed out; its startup process was stopped.")


def find_worker(session_id, home=None):
    if not read_server(home):
        return None
    for item in request("status", home=home)["chats"]:
        if session_id in (item["id"], item.get("session_id")) and item["alive"]:
            return item
    return None


def find_view_worker(session_id, home=None):
    """Resume can address a side view; stop/start still address whole workers only."""
    if not read_server(home):
        return None
    chats = request("status", home=home)["chats"]
    for item in chats:
        if item["alive"] and session_id in (item["id"], item.get("session_id"), *item.get("view_sessions", [])):
            target = session_id if session_id in item.get("view_sessions", []) else None
            return {**item, "view_session": target}
    # Older services/workers cannot publish side view IDs. The native lease is
    # still authoritative: attach to that exact live owner, never open a writer
    # or infer ownership from a title, PID alone, or a different profile.
    from sci_cli.active_sessions import active_session_registry_snapshot
    owners = [entry for entry in active_session_registry_snapshot(home, strict=True)
              if entry.get("session_id") == session_id]
    if len(owners) != 1 or owners[0].get("surface") != "side":
        return None
    owner = owners[0]
    matches = [item for item in chats if item["alive"] and item["pid"] == owner["pid"]]
    if len(matches) != 1 or not owner.get("process_start_time"):
        return None
    try:
        process = psutil.Process(owner["pid"])
        if abs(process.create_time() - owner["process_start_time"]) > 0.01:
            return None
    except psutil.Error:
        return None
    return {**matches[0], "view_session": session_id, "legacy_side_view": True}


def publish_cli_state(cli):
    """Called by the existing display loop; only managed workers contact the service."""
    now = time.monotonic()
    if now - getattr(cli, "_background_publish_at", 0) < 2:
        return
    cli._background_publish_at = now
    if getattr(cli, "_background_managed", None) is False:
        return
    try:
        if not read_server():
            cli._background_managed = False
            return
        waiting = any(getattr(cli, name, None) for name in
                      ("_clarify_state", "_approval_state", "_sudo_state", "_secret_state"))
        busy = any(getattr(cli, name, False) for name in ("_agent_running", "_command_running", "_voice_processing"))
        from sci_cli.cli_session_views import open_views, receive_selection
        views = open_views(cli)
        side = getattr(cli, "_side_controller", None)
        if side:
            busy = busy or side.running
            waiting = waiting or any(getattr(side.ui, name, None) for name in
                                     ("_clarify_state", "_approval_state", "_sudo_state", "_secret_state"))
        state = "waiting for input" if waiting else ("running" if busy else "idle")
        from tools.process_registry import process_registry
        from tools.delegate_tool_registry import _active_subagents, _active_subagents_lock
        with _active_subagents_lock:
            children = len(_active_subagents)
        tasks = len(getattr(cli, "_background_tasks", {})) + process_registry.count_running() + children
        reply = request("worker", pid=os.getpid(), session_id=cli.session_id, state=state,
                        background_tasks=tasks, view_sessions=views,
                        view_ack=getattr(cli, "_background_view_ack", None))
        cli._background_managed = bool(reply.get("managed"))
        if reply.get("stop_requested"):
            from agent.interrupt_compat import request_hard_interrupt
            if getattr(cli, "agent", None) and getattr(cli, "_agent_running", False):
                request_hard_interrupt(cli.agent)
            cli._should_exit = True
            app = getattr(cli, "_app", None)
            if app is not None and app.loop is not None:
                app.loop.call_soon_threadsafe(app.exit)
        receive_selection(cli, reply.get("select_view"))
    except (OSError, ValueError, RuntimeError, psutil.Error):
        # Service loss closes its PTY; normal terminal-loss handling owns shutdown.
        pass


def detach_cli(cli):
    publish_cli_state(cli)
    if not getattr(cli, "_background_managed", False):
        return False
    request("detach", pid=os.getpid())
    return True
