"""Reviewed CLI handoff: stop the old writer, then use normal lease acquisition.

Never clear a live lease to make resume work. A stopped process is still a writer
and may continue later; process identity must survive both review and signaling.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path

import psutil


def _owner_process(entry):
    pid = int(entry["pid"])
    started = entry.get("process_start_time")
    if not started:
        raise ValueError("The old process has no recorded identity. Close it in its original terminal.")
    process = psutil.Process(pid)
    if abs(process.create_time() - float(started)) > 0.01:
        raise ValueError("The process identity changed. Retry resume; no process was stopped.")
    return process


def describe_owner(entry):
    """Process state is evidence of ownership, not evidence of model/job activity."""
    try:
        process = _owner_process(entry)
        state = process.status()
        terminal = (process.terminal() or "no attached terminal") if os.name == "posix" else "terminal details unavailable"
        if state in (psutil.STATUS_STOPPED, psutil.STATUS_TRACING_STOP):
            label = "suspended (Ctrl+Z pauses SCI; it does not close it)"
        elif state == psutil.STATUS_ZOMBIE:
            label = "exited; retry resume to recover the saved conversation"
        else:
            label = "process alive (this does not mean a model request is running)"
        return f"Owner: {label}; PID {process.pid}; {terminal}."
    except (psutil.Error, ValueError, TypeError, KeyError):
        return "Owner state could not be verified. No other writer will be admitted until it is safe."


def _current_owner(session_id, home):
    from sci_cli.active_sessions import active_session_registry_snapshot
    owners = [e for e in active_session_registry_snapshot(home, strict=True)
              if e.get("session_id") == session_id]
    if len(owners) > 1:
        raise ValueError("More than one owner is recorded. Close those sessions before resuming.")
    return owners[0] if owners else None


def _signal_reviewed_owner(entry, home, *, force=False):
    from sci_cli.active_sessions import _FileLock, _lease_paths, _read_entries
    state_path, lock_path = _lease_paths(registry_home=home)
    # Serialize against a lease replacement/profile switch. psutil's signal path
    # also checks PID reuse; never signal a bare PID from an old menu snapshot.
    with _FileLock(lock_path):
        entries = _read_entries(state_path, strict=True)
        current = next((e for e in entries if e.get("lease_id") == entry["lease_id"]), None)
        if current != entry:
            raise ValueError("Chat ownership changed during review. Retry resume; nothing was stopped.")
        if entry.get("surface") != "cli" or os.name != "posix":
            raise ValueError("Close this chat in its owning application before resuming here.")
        process = _owner_process(entry)
        if process.pid == os.getpid() or process.uids().real != os.getuid():  # windows-footgun: ok — non-POSIX refused above
            raise ValueError("Cannot close this process from here. Use its original terminal.")
        if sum(e.get("pid") == process.pid for e in entries) != 1:
            raise ValueError("That process owns several chats. Close the target in its original application.")
        if force:
            process.kill()
        else:
            process.send_signal(signal.SIGTERM)
            # Queue termination before continuing a suspended process so it goes
            # through its shutdown handler, not back to research work.
            if process.status() in (psutil.STATUS_STOPPED, psutil.STATUS_TRACING_STOP):
                process.send_signal(signal.SIGCONT)
        return process


def _wait_for_exit(process, ui, seconds):
    started = time.monotonic()
    while time.monotonic() - started < seconds:
        try:
            process.wait(timeout=min(2, max(0.1, seconds - (time.monotonic() - started))))
            return True
        except psutil.TimeoutExpired:
            ui.show(f"Closing previous SCI window: {int(time.monotonic() - started)}s elapsed…")
    return False


class StartupRecoveryUI:
    """Startup owns the terminal; running prompt_toolkit uses WizardUI instead."""

    def show(self, text):
        print(text, flush=True)

    def choose(self, question, choices):
        from sci_cli.curses_ui import curses_single_select
        from sci_cli.skill_add import Cancelled
        items = [c for c in choices if c != "Cancel"]
        index = curses_single_select(question, items, default_index=len(items))
        if index is None:
            raise Cancelled()
        return items[index]


def prepare_resume(session_id, ui, *, registry_home=None):
    """False means cancelled/blocked; True still requires normal atomic acquisition."""
    from sci_constants import get_sci_home
    from sci_cli.skill_add import Cancelled
    home = Path(registry_home) if registry_home is not None else Path(get_sci_home())
    stop_requested = False
    try:
        entry = _current_owner(session_id, home)
        if entry is None:
            return True
        ui.show(describe_owner(entry))
        if entry.get("surface") != "cli" or os.name != "posix" or entry.get("pid") == os.getpid():
            ui.show("Close this chat in its owning application, then resume it here. No ownership changed.")
            return False
        ui.show("Moving this chat closes the entire previous CLI, including its local turn and background work. "
                "Saved messages are retained. Submitted remote jobs may continue; their IDs must be "
                "checked before any retry. This does not rerun the last request.")
        action = ui.choose("Move this chat here?", ("Cancel", "Close previous window and resume here"))
        if action != "Close previous window and resume here":
            return False
        try:
            process = _signal_reviewed_owner(entry, home)
        except psutil.NoSuchProcess:
            return True  # normal acquisition rechecks/prunes; never delete by session ID
        stop_requested = True
        if not _wait_for_exit(process, ui, 15):
            ui.show("The old CLI has not exited. It still owns the chat. Forced close can lose "
                    "unsaved output and leave subprocesses or remote jobs running.")
            choice = ui.choose("How should recovery continue?", ("Cancel", "Wait longer", "Force close old CLI"))
            if choice == "Force close old CLI":
                try:
                    _signal_reviewed_owner(entry, home, force=True)
                except psutil.NoSuchProcess:
                    pass
            if choice not in ("Wait longer", "Force close old CLI") or not _wait_for_exit(process, ui, 15):
                ui.show("Recovery stopped: the old writer has not exited. No new writer was opened.")
                return False
        ui.show("Previous CLI exited. Opening the saved conversation; no request will be rerun.")
        return True
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show("Recovery cancelled. " + ("The previous CLI was already asked to close; "
                "that request cannot be undone." if stop_requested else "The existing chat was left unchanged."))
    except (psutil.Error, OSError, ValueError, RuntimeError) as exc:
        ui.show(f"Cannot safely recover this chat: {exc}. No new writer was opened.")
    return False


def offer_startup_recovery(session_id):
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    return prepare_resume(session_id, StartupRecoveryUI())
