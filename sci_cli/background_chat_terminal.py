"""Attach a real terminal to a persistent PtySession; Ctrl+] only detaches."""

import base64
import codecs
import json
import os
import signal
import sys

from sci_cli.background_chats import FRAME_LIMIT, connect, send


def _attach_once(chat_id, *, home=None, takeover=False, view_session=None):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise RuntimeError("Attach requires an interactive terminal.")
    from sci_cli.background_chat_console import terminal_console

    outcome = {}
    with connect(home) as sock:
        sock.settimeout(12)  # View selection needs the worker's two-second heartbeat/ack.
        size = os.get_terminal_size()
        send(sock, {"action": "attach", "id": chat_id, "takeover": takeover,
                    "cols": size.columns, "rows": size.lines, "view_session": view_session,
                    "terminal_program": os.environ.get("TERM_PROGRAM", "")})
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
        console = terminal_console(outcome)
        stop = [False]
        owns_activity = False
        try:
            console.__enter__()
            if reply.get("terminal_activity"):
                # The shell title belongs to this viewer, not the persistent
                # worker. Save once per attachment, outside replayed output.
                owns_activity = True
                sys.stdout.write("\x1b[22;2t\x1b]9;4;0;\x07")
            # Each accepted attachment owns the visible transcript. Clear before
            # replay, including terminal scrollback, so previous chats cannot
            # accumulate above this one. Persisted histories remain untouched.
            # Clear the viewport first: some terminals push it into scrollback.
            from sci_cli.cli_terminal_input import _TERMINAL_INPUT_MODE_RESET_SEQ
            sys.stdout.write(_TERMINAL_INPUT_MODE_RESET_SEQ + "\x1b[r\x1b[H\x1b[2J\x1b[3J")
            sys.stdout.flush()
            if reply.get("truncated"):
                print("Live terminal replay is limited to its recent tail. Ctrl+O opens the saved transcript.\r", flush=True)
            pending = bytearray(tail)
            output_pending = memoryview(b"")
            # Service frame boundaries can split UTF-8. Windows console byte
            # writes can stall flushing an incomplete character; keep decoder
            # state across both frames and bounded replay chunks.
            decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
            sock.settimeout(2)
            while not stop[0] and not console.stopped:
                # A replay frame can contain 32 KiB of terminal output. ConPTY
                # can wait for input while rendering it: yield between bounded
                # writes, not just between service frames, so keys keep flowing.
                if not output_pending and b"\n" in pending:
                    raw, _, rest = pending.partition(b"\n")
                    pending = bytearray(rest)
                    event = json.loads(raw)
                    if "output" in event:
                        output_pending = memoryview(base64.b64decode(event["output"], validate=True))
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
                if output_pending:
                    sys.stdout.write(decoder.decode(output_pending[:4096]))
                    sys.stdout.flush()
                    output_pending = output_pending[4096:]
                if console.resized:
                    console.resized = False
                    size = os.get_terminal_size()
                    send(sock, {"action": "resize", "cols": size.columns, "rows": size.lines})
                socket_ready, input_data = console.poll(sock, timeout=0 if output_pending or b"\n" in pending else None)
                if socket_ready and not output_pending and b"\n" not in pending:
                    chunk = sock.recv(65536)
                    if not chunk:
                        break
                    pending.extend(chunk)
                    if len(pending) > FRAME_LIMIT and b"\n" not in pending:
                        raise RuntimeError("Invalid oversized background event.")
                if input_data is not None:
                    chunk = input_data
                    if not chunk:
                        break
                    # Windows can deliver the last typed key and Ctrl+] together.
                    # Forward that prefix (e.g. q to close history) before detach.
                    chunk, detach, _ = chunk.partition(b"\x1d")
                    if os.name == "posix" and chunk == b"\x1a":
                        outcome["suspend"] = True
                        break
                    if chunk:
                        send(sock, {"action": "input", "data": base64.b64encode(chunk).decode()})
                    if detach:
                        break
        finally:
            from sci_cli.cli_terminal_input import _TERMINAL_INPUT_MODE_RESET_SEQ
            try:
                # The worker keeps its renderer alive, so it cannot erase the
                # viewer's prompt chrome. Hand the shell a clean viewport and
                # known cursor position; CSI 2J leaves scrollback intact.
                sys.stdout.write(_TERMINAL_INPUT_MODE_RESET_SEQ + "\x1b[r\x1b[H\x1b[2J")
                if owns_activity:
                    sys.stdout.write("\x1b]9;4;0;\x07\x1b[23;2t")
                sys.stdout.flush()
            except OSError:
                pass  # A terminal closed by its owner cannot accept mode resets.
            console.__exit__()
            try:
                send(sock, {"action": "detach"})
            except OSError:
                pass
    return outcome


def attach(chat_id, *, home=None, takeover=False, view_session=None):
    from sci_cli.background_chats import find_view_worker, find_worker
    from sci_cli.cli_runtime_refresh import refresh_attached_worker
    from sci_cli.skill_add import Cancelled
    worker = find_worker(chat_id, home=home)
    wire_view_session = view_session
    if worker and view_session != worker.get('session_id') and view_session is not None:
        selected = find_view_worker(view_session, home=home)
        if not selected or selected['id'] != worker['id']:
            raise RuntimeError('The side chat owner changed. Retry resume; no conversation was restarted.')
        if selected.get('legacy_side_view'):
            wire_view_session = None
            print('This older background runtime cannot select a side view automatically. '
                  'Connecting to its existing parent CLI; press Ctrl+/ or use /btw to open the side chat. '
                  'The parent, saved history and running work remain unchanged.')
        else:
            print('Reopening the existing side view. Its owning runtime and main chat keep running; '
                  'source updates apply after that runtime is closed normally.')
    elif worker:
        try:
            refreshed = refresh_attached_worker(worker, home=home)
        except Cancelled:
            print('Attachment cancelled. No replacement conversation was opened.')
            return
        if refreshed['id'] != worker['id']:
            chat_id, takeover = refreshed['id'], False
            view_session = None
            wire_view_session = None
    while True:
        outcome = _attach_once(chat_id, home=home, takeover=takeover, view_session=wire_view_session)
        worker = find_worker(chat_id, home=home)
        session = (view_session or worker.get("session_id")) if worker else None
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
