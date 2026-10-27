"""A detached/suspended viewer must return a clean, cooked terminal to the shell."""

import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

import psutil
import pytest


ROOT = Path(__file__).resolve().parents[2]
VIEWER = r'''
import base64, json, socket, sys, threading
from sci_cli import background_chat_terminal as terminal, background_chats

def connect(home):
    client, server = socket.socketpair()
    def serve():
        with server:
            stream = server.makefile('rb')
            stream.readline()
            # Reproduce a live renderer that leaves text below its cursor.
            frame = b'\x1b[2J\x1b[HSCI_BANNER\x1b[20;1HSTALE_TOOLBAR\x1b[2;1HVIEW_READY'
            events = [{'attached': 'fixture'},
                      {'output': base64.b64encode(frame).decode()}]
            if sys.argv[1] == 'server_close':
                events += [{'closed': 0}, {'output': base64.b64encode(b'LATE_DRAW').decode()}]
            server.sendall(b''.join(json.dumps(event).encode() + b'\n' for event in events))
            try:
                while stream.readline():
                    pass
            except OSError:
                pass
            finally:
                stream.close()
    threading.Thread(target=serve, daemon=True).start()
    return client

terminal.connect = connect
background_chats.find_worker = lambda *args, **kwargs: {'session_id': 'saved-chat', 'state': 'running'}
terminal.attach('fixture')
print('SHELL_PROMPT> ', end='', flush=True)
'''


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("action", ["detach", "suspend", "server_close"])
def test_viewer_cleans_display_and_restores_tty_before_returning_control(tmp_path, action):
    import fcntl
    import struct
    import termios

    master, slave = os.openpty()
    fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 100, 0, 0))
    original = termios.tcgetattr(slave)
    child = subprocess.Popen([sys.executable, "-u", "-c", VIEWER, action], cwd=ROOT,
        env={**os.environ, "SCI_HOME": str(tmp_path), "TERM": "xterm-256color"},
        stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
    os.close(slave)
    output = bytearray()

    def until(marker):
        deadline = time.monotonic() + 30
        while marker not in output and time.monotonic() < deadline:
            if select.select([master], [], [], 0.1)[0]:
                try:
                    output.extend(os.read(master, 65536))
                except OSError:
                    break
        assert marker in output, output.decode(errors="replace")

    def assert_clean_handoff(message):
        before = output[:output.index(message)]
        # Erase the entire visible display AFTER the worker's final drawing,
        # not just keyboard modes or text below its arbitrary cursor position.
        drawn = before.rfind(b"STALE_TOOLBAR")
        erased = before.rfind(b"\x1b[2J")
        homed = before.rfind(b"\x1b[H")
        assert drawn >= 0 and erased > drawn and homed > drawn
        assert b"\x1b[3J" not in output  # Retain shell scrollback.
        assert b"LATE_DRAW" not in output
        restored = termios.tcgetattr(master)
        expected = original.copy()
        # BSD sets PENDIN while restoring canonical mode: it is pending-input
        # state, not a changed terminal setting (xnu bsd/sys/termios.h).
        restored[3] &= ~getattr(termios, "PENDIN", 0)
        expected[3] &= ~getattr(termios, "PENDIN", 0)
        assert restored == expected

    try:
        until(b"VIEW_READY")
        if action == "suspend":
            os.write(master, b"\x1a")
            until(b"Terminal interface suspended")
            deadline = time.monotonic() + 5
            while psutil.Process(child.pid).status() != psutil.STATUS_STOPPED and time.monotonic() < deadline:
                time.sleep(0.01)
            assert psutil.Process(child.pid).status() == psutil.STATUS_STOPPED
            assert_clean_handoff(b"Terminal interface suspended")
            output.clear()
            child.send_signal(signal.SIGCONT)
            until(b"VIEW_READY")
        if action != "server_close":
            os.write(master, b"\x1d")
        until(b"SHELL_PROMPT> ")
        assert child.wait(timeout=10) == 0
        assert_clean_handoff(b"Disconnected.")
    finally:
        if child.poll() is None:
            child.kill()
        child.wait(timeout=10)
        os.close(master)
