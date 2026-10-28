"""Terminal ownership survives suspension but not an actual CLI close."""

import errno
import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import threading
import time

import psutil
import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
import os, signal, threading, time
# A shell-like supervisor keeps the foreground group non-orphaned. POSIX
# intentionally ignores job-control stop signals in orphaned process groups.
read_fd, write_fd = os.pipe()
signal.signal(signal.SIGTTOU, signal.SIG_IGN)
signal.signal(signal.SIGHUP, signal.SIG_IGN)
child = os.fork()
if child:
    os.close(read_fd)
    os.setpgid(child, child)
    os.tcsetpgrp(0, child)
    os.write(write_fd, b'G')
    os.close(write_fd)
    _, status = os.waitpid(child, 0)
    os._exit(os.waitstatus_to_exitcode(status) if os.WIFEXITED(status) else 1)
os.close(write_fd)
os.setpgid(0, 0)
os.read(read_fd, 1)
os.close(read_fd)
from pathlib import Path
from prompt_toolkit import PromptSession
from prompt_toolkit.key_binding import KeyBindings
from cli import SciCLI
from sci_cli.cli_shutdown import begin_interactive_shutdown

cli = object.__new__(SciCLI)
cli.session_id = 'pty-chat'
cli.config = {}
cli._active_session_lease = None
cli._agent_running = False
cli.agent = None
cli._attached_images = []
cli._should_exit = False
cli._terminal_io_broken = False
cli._pet_stop_anim = lambda: None
assert cli._claim_active_session()
keys = KeyBindings()
keys.add('c-c')(cli._tui_clear_or_exit)
keys.add('c-z')(cli._tui_handle_ctrl_z)
@keys.add('c-x')
def broken(event):
    cli._mark_terminal_io_broken('fixture terminal lost')
session = PromptSession(key_bindings=keys)
cli._app = session.app
cli._tui_install_signal_handlers()
def worker():
    while not cli._should_exit:
        time.sleep(0.01)
cli._tui_process_thread = threading.Thread(target=worker, daemon=True)
cli._tui_process_thread.start()
try:
    session.prompt('FIXTURE_READY> ')
except (KeyboardInterrupt, EOFError):
    pass
finally:
    begin_interactive_shutdown(cli)
    Path(os.environ['SCI_HOME'], 'closed').write_text('saved before release')
    cli._release_active_session()
'''


def read_until(fd, expected, timeout=30):
    output = b""
    deadline = time.monotonic() + timeout
    while expected not in output and time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], min(0.2, max(0, deadline - time.monotonic())))
        if ready:
            try:
                output += os.read(fd, 65536)
            except OSError as exc:
                if exc.errno != errno.EIO:
                    raise
                break
    assert expected in output, output.decode(errors="replace")[-2000:]


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("close", ["ctrl_c", "terminal_close", "broken_io", "suspend_then_move"])
def test_real_pty_close_and_suspend_are_distinct(tmp_path, close):
    import fcntl
    import pty
    import termios
    from sci_cli.active_sessions import active_session_registry_snapshot
    from sci_cli.cli_session_recovery import prepare_resume
    master, slave = pty.openpty()

    def own_terminal():
        os.setsid()
        fcntl.ioctl(0, termios.TIOCSCTTY, 0)

    env = {**os.environ, "SCI_HOME": str(tmp_path), "TERM": "xterm", "PROMPT_TOOLKIT_NO_CPR": "1"}
    process = subprocess.Popen([sys.executable, "-u", "-c", SCRIPT], cwd=ROOT, env=env,
        stdin=slave, stdout=slave, stderr=slave, preexec_fn=own_terminal)
    os.close(slave)
    owner_pid = None
    try:
        read_until(master, b"FIXTURE_READY>")
        owner_pid = active_session_registry_snapshot(tmp_path)[0]["pid"]
        if close == "terminal_close":
            os.close(master)
            master = None  # actual PTY hangup, no injected shutdown signal
        elif close == "suspend_then_move":
            os.write(master, b"\x1a")
            read_until(master, b"paused, not closed")
            deadline = time.monotonic() + 5
            while psutil.Process(owner_pid).status() != psutil.STATUS_STOPPED and time.monotonic() < deadline:
                time.sleep(0.01)
            assert psutil.Process(owner_pid).status() == psutil.STATUS_STOPPED
            assert active_session_registry_snapshot(tmp_path)[0]["pid"] == owner_pid

            class UI:
                def show(self, text):
                    pass

                def choose(self, question, choices):
                    return "Close previous window and resume here"

            assert prepare_resume("pty-chat", UI(), registry_home=tmp_path)
        else:
            os.write(master, b"\x03" if close == "ctrl_c" else b"\x18")
        process.wait(timeout=15)
        assert (tmp_path / "closed").read_text() == "saved before release"
        assert not active_session_registry_snapshot(tmp_path)
    finally:
        if process.poll() is None:
            for child in psutil.Process(process.pid).children(recursive=True):
                try:
                    child.kill()
                except psutil.NoSuchProcess:
                    pass
            process.kill()
        process.wait(timeout=10)
        if master is not None:
            os.close(master)


def test_shutdown_arms_backstop_before_flush_and_keeps_busy_writer_fenced(tmp_path, monkeypatch):
    import cli as module
    from cli import SciCLI
    from sci_cli.active_sessions import active_session_registry_snapshot
    from sci_cli.cli_shutdown import begin_interactive_shutdown
    monkeypatch.setenv("SCI_HOME", str(tmp_path))
    armed = []
    monkeypatch.setattr(module, "_arm_exit_watchdog_on_shutdown_signal", lambda: armed.append(True))
    cli = object.__new__(SciCLI)
    cli.session_id, cli.config, cli._active_session_lease = "busy", {}, None
    cli.agent, cli._agent_running = None, False
    assert cli._claim_active_session()
    # A real blocked worker cannot be safely released for another writer.
    ready, stop = threading.Event(), threading.Event()

    def worker():
        ready.set()
        stop.wait(15)

    cli._tui_process_thread = threading.Thread(target=worker)
    cli._tui_process_thread.start()
    ready.wait(5)
    cli._pending_relaunch = ["--resume", "other"]
    try:
        begin_interactive_shutdown(cli)
        assert armed and cli._should_exit and cli._pending_relaunch is None
        cli._release_active_session()
        assert active_session_registry_snapshot()[0]["session_id"] == "busy"
    finally:
        stop.set()
        cli._tui_process_thread.join(5)
        cli._release_active_session()
    assert not active_session_registry_snapshot()
