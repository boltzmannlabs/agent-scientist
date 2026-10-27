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
        endpoint = Path(tempfile.gettempdir()) / name
        if len(os.fsencode(endpoint)) > 100:
            # no-tmp: ok — AF_UNIX needs a short fallback independent of a long TMPDIR.
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


def connect(home=None):
    home, _, endpoint = locations(home)
    record = read_server(home)
    if not record or endpoint is None:
        raise RuntimeError("No background chat service is running in this profile.")
    # A reconnecting shell may have a different TMPDIR from the service owner.
    endpoint = record.get("endpoint", str(endpoint))
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect(str(endpoint))
        send(sock, {"token": record["token"], "home": str(home)})
        return sock
    except BaseException:
        sock.close()
        raise


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
    if os.name != "posix":
        raise RuntimeError("Persistent CLI chats currently require Linux/macOS or WSL.")
    from sci_cli.active_sessions import _FileLock
    from tools.environments.local import served_profile_child_env
    from sci_cli._launchers import runtime_command
    home, root, _ = locations(home)
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
            child = subprocess.Popen(command,
                cwd=repo, env=env, stdin=subprocess.DEVNULL,
                stdout=log, stderr=log, start_new_session=True, close_fds=True)
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
        state = "waiting for input" if waiting else ("running" if busy else "idle")
        from tools.process_registry import process_registry
        from tools.delegate_tool_registry import _active_subagents, _active_subagents_lock
        with _active_subagents_lock:
            children = len(_active_subagents)
        tasks = len(getattr(cli, "_background_tasks", {})) + process_registry.count_running() + children
        reply = request("worker", pid=os.getpid(), session_id=cli.session_id, state=state,
                        background_tasks=tasks)
        cli._background_managed = bool(reply.get("managed"))
    except (OSError, ValueError, RuntimeError, psutil.Error):
        # Service loss closes its PTY; normal terminal-loss handling owns shutdown.
        pass


def detach_cli(cli):
    publish_cli_state(cli)
    if not getattr(cli, "_background_managed", False):
        return False
    request("detach", pid=os.getpid())
    return True
