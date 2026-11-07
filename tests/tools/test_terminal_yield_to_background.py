"""A follow-up message queues guidance without detaching the foreground command."""
import json
import shlex
import sys
import threading
import time

import pytest

from agent.interrupt_control import InterruptControlMixin
from tools import interrupt as interrupt_mod
from tools.terminal_tool import terminal_tool

pytestmark = pytest.mark.platforms("linux")


class _Agent(InterruptControlMixin):
    _executing_tools = True
    _interrupt_requested = False
    _pending_steer = None
    _pending_redirect = None
    api_mode = "chat_completions"

    def __init__(self):
        self._pending_steer_lock = threading.Lock()
        self._pending_redirect_lock = threading.Lock()
        self._tool_worker_threads = set()
        self._tool_worker_threads_lock = threading.Lock()
        self._execution_thread_id = None


@pytest.mark.parametrize("cancel", [False, True])
def test_redirect_keeps_foreground_ownership_until_completion_or_stop(tmp_path, monkeypatch, cancel):
    monkeypatch.setenv("SCI_HOME", str(tmp_path))
    agent = _Agent()
    res = {}
    started, finish = tmp_path / "started", tmp_path / "finish"
    script = ("from pathlib import Path; import time; "
              f"Path({str(started)!r}).touch(); print('started', flush=True); "
              f"\nwhile not Path({str(finish)!r}).exists(): time.sleep(0.05)"
              "\nprint('done', flush=True)")
    command = shlex.join([sys.executable, "-c", script])

    def forbidden(*args, **kwargs):
        pytest.fail("Foreground command was detached")

    monkeypatch.setattr("tools.terminal_tool.spawn_background_process", forbidden)
    monkeypatch.setattr("tools.terminal_tool._check_all_guards", lambda *a, **k: {"approved": True})

    def worker():
        try:
            res["result"] = json.loads(terminal_tool(command, task_id="foreground-test", timeout=90))
        finally:
            interrupt_mod.set_interrupt(False)

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 15
        while not started.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert started.exists(), res
        with agent._tool_worker_threads_lock:
            agent._tool_worker_threads.add(thread.ident)
        assert agent.redirect("check the outputs after completion")
        assert agent._pending_steer == "check the outputs after completion"
        assert not interrupt_mod.is_thread_yield_requested(thread.ident)
        if cancel:
            interrupt_mod.set_interrupt(True, thread.ident)
        else:
            finish.touch()
        thread.join(15)
        assert not thread.is_alive()
        result = res["result"]
        assert result["exit_code"] == (130 if cancel else 0), result
        assert result.get("status") != "yielded_to_background"
        assert "session_id" not in result
        assert "started" in result["output"]
        if not cancel:
            assert "done" in result["output"]
    finally:
        finish.touch()
        interrupt_mod.set_interrupt(True, thread.ident)
        thread.join(15)
        interrupt_mod.set_interrupt(False, thread.ident)


def test_yield_request_without_steer_leaves_foreground_wait_alone():
    """No yield handler (internal env.execute consumers) -> the request is ignored and the
    command runs to completion; an unrelated stale yield bit must not leak into it either."""
    from tools.environments.local import LocalEnvironment

    env = LocalEnvironment()
    try:
        interrupt_mod.request_yield(threading.current_thread().ident)
        result = env.execute("echo alpha; sleep 0.3; echo omega", timeout=10)
        assert result["returncode"] == 0
        assert "omega" in result["output"]
    finally:
        interrupt_mod.consume_yield(threading.current_thread().ident)
        env.cleanup()
