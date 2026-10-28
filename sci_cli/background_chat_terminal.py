"""Attach a real terminal to a persistent PtySession; Ctrl+] only detaches."""

import base64
import json
import os
import select
import signal
import sys

from sci_cli.background_chats import FRAME_LIMIT, connect, send


def _attach_once(chat_id, *, home=None, takeover=False):
    if os.name != "posix" or not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("Attach requires an interactive Linux/macOS/WSL terminal.")
    import termios
    import tty

    outcome = {}
    with connect(home) as sock:
        size = os.get_terminal_size()
        send(sock, {"action": "attach", "id": chat_id, "takeover": takeover,
                    "cols": size.columns, "rows": size.lines})
        # Keep all bytes after the handshake: the server may replay output in the same packet.
        pending = bytearray()
        while b"\n" not in pending:
            chunk = sock.recv(65536)
            if not chunk:
                raise RuntimeError("Service disconnected during attachment.")
            pending.extend(chunk)
            if len(pending) > FRAME_LIMIT:
                raise RuntimeError("Invalid background attachment response.")
        first, _, tail = pending.partition(b"\n")
        reply = json.loads(first)
        if reply.get("error"):
            raise RuntimeError(reply["error"])
        if reply.get("attached") != chat_id:
            raise RuntimeError("Unexpected background conversation identity.")
        saved = termios.tcgetattr(sys.stdin.fileno())
        stop, resize = [False], [False]
        previous = {}

        def disconnected(signum, frame):
            stop[0] = True

        def resized(signum, frame):
            resize[0] = True

        def suspended(signum, frame):
            outcome["suspend"] = True
            stop[0] = True

        try:
            for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):  # windows-footgun: ok — _attach_once rejects non-POSIX
                previous[sig] = signal.signal(sig, disconnected)
            previous[signal.SIGWINCH] = signal.signal(signal.SIGWINCH, resized)
            previous[signal.SIGTSTP] = signal.signal(signal.SIGTSTP, suspended)
            # Do not flush keys typed during attachment. Announce readiness only
            # after the input mode is installed, so an immediate detach is honored.
            tty.setraw(sys.stdin.fileno(), when=termios.TCSANOW)
            print("Attached. Ctrl+] detaches; /exit disconnects. Ctrl+C during a task offers stop/background/exit.\r", flush=True)
            if reply.get("truncated"):
                print("Live terminal replay is limited to its recent tail. Ctrl+O opens the saved transcript.\r", flush=True)
            pending = bytearray(tail)
            sock.settimeout(2)
            while not stop[0]:
                while not stop[0] and b"\n" in pending:
                    raw, _, rest = pending.partition(b"\n")
                    pending = bytearray(rest)
                    event = json.loads(raw)
                    if "output" in event:
                        sys.stdout.buffer.write(base64.b64decode(event["output"], validate=True))
                        sys.stdout.buffer.flush()
                    elif "relaunch" in event:
                        outcome = event
                        stop[0] = True
                    elif "closed" in event:
                        outcome.setdefault("closed", event["closed"])
                        stop[0] = True
                    elif "error" in event:
                        raise RuntimeError(event["error"])
                if stop[0]:
                    break
                if resize[0]:
                    resize[0] = False
                    size = os.get_terminal_size()
                    send(sock, {"action": "resize", "cols": size.columns, "rows": size.lines})
                readable, _, _ = select.select([sock, sys.stdin], [], [], 0.2)
                if sock in readable:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    pending.extend(chunk)
                    if len(pending) > FRAME_LIMIT and b"\n" not in pending:
                        raise RuntimeError("Invalid oversized background event.")
                if sys.stdin in readable:
                    chunk = os.read(sys.stdin.fileno(), 8192)
                    if not chunk or b"\x1d" in chunk:  # Ctrl+] is the explicit detach shortcut.
                        break
                    if chunk == b"\x1a":
                        outcome["suspend"] = True
                        break
                    send(sock, {"action": "input", "data": base64.b64encode(chunk).decode()})
        finally:
            from sci_cli.cli_terminal_input import _TERMINAL_INPUT_MODE_RESET_SEQ
            try:
                # The worker keeps its renderer alive, so it cannot erase the
                # viewer's prompt chrome. Hand the shell a clean viewport and
                # known cursor position; CSI 2J leaves scrollback intact.
                sys.stdout.write(_TERMINAL_INPUT_MODE_RESET_SEQ + "\x1b[r\x1b[H\x1b[2J")
                sys.stdout.flush()
            except OSError:
                pass  # A terminal closed by its owner cannot accept mode resets.
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            try:
                termios.tcsetattr(sys.stdin.fileno(), termios.TCSANOW, saved)
            except termios.error:
                pass  # A closed terminal cannot be restored.
            try:
                send(sock, {"action": "detach"})
            except OSError:
                pass
    return outcome


def attach(chat_id, *, home=None, takeover=False):
    from sci_cli.background_chats import find_worker
    while True:
        outcome = _attach_once(chat_id, home=home, takeover=takeover)
        worker = find_worker(chat_id, home=home)
        session = worker.get("session_id") if worker else None
        command = f"sci --resume {session}" if session else f"sci background attach {chat_id}"
        if outcome.get("suspend"):
            print(f"\nTerminal interface suspended; the task stays on the server. Use fg or {command}.", flush=True)
            # Suspend only this UI, never the service or its task. SIGSTOP also
            # works when a launcher makes the viewer's process group orphaned.
            os.kill(os.getpid(), signal.SIGSTOP)
            takeover = False
            continue
        if "relaunch" in outcome:
            from types import SimpleNamespace
            from sci_cli.native_profile_session import relaunch_profile
            relaunch_profile(SimpleNamespace(_pending_relaunch=outcome["relaunch"],
                                             _pending_profile_home=outcome["home"]))
            return
        if worker:
            print(f"\nDisconnected. Task status: {worker['state']}. Reconnect with `{command}`. "
                  f"Stop with `sci background stop {chat_id}`.")
        else:
            print("\nLocal chat stopped. Its saved conversation can be resumed; interrupted work is not restarted.")
        return
