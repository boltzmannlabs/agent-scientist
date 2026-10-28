"""Real process ownership recovery without model requests or live profile writes."""

import os
from pathlib import Path
import select
import signal
import subprocess
import sys
import time

import psutil
import pytest

from sci_cli.active_sessions import active_session_registry_snapshot, try_acquire_active_session
from sci_cli.cli_session_recovery import describe_owner, prepare_resume, _signal_reviewed_owner


ROOT = Path(__file__).resolve().parents[2]
CHILD = r'''
import os, signal, sys, time
from pathlib import Path
from sci_cli.active_sessions import try_acquire_active_session
from sci_state import SessionDB
home = Path(os.environ['SCI_HOME'])
db = SessionDB(home / 'state.db')
db.create_session('chat', 'cli', system_prompt='fixed cached prompt')
db.append_message('chat', role='user', content='saved question')
lease, refusal = try_acquire_active_session(session_id='chat', surface='cli', config={})
assert lease and not refusal
def close(signum, frame):
    db.append_message('chat', role='assistant', content='saved before close')
    db.close()
    # Deliberately leave the lease; process death must reclaim it even without /exit.
    raise SystemExit(0)
signal.signal(signal.SIGTERM, signal.SIG_IGN if sys.argv[1] == 'force' else close)
print('READY', flush=True)
while True:
    time.sleep(0.05)
'''


class UI:
    def __init__(self, *choices):
        self.choices = iter(choices)
        self.messages = []

    def show(self, text):
        self.messages.append(text)

    def choose(self, question, choices):
        answer = next(self.choices)
        assert answer in choices
        return answer


def launch(home, mode="normal"):
    home.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen([sys.executable, "-u", "-c", CHILD, mode], cwd=ROOT,
        env={**os.environ, "SCI_HOME": str(home)}, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    ready, _, _ = select.select([process.stdout], [], [], 30)
    if not ready or process.stdout.readline().strip() != b"READY":
        process.kill()
        raise AssertionError(process.communicate(timeout=10))
    return process


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("mode", ["normal", "suspended", "cancel", "dead", "force", "wait"])
def test_recovery_requires_consent_and_old_writer_exit_across_profiles(tmp_path, monkeypatch, mode):
    from sci_state import SessionDB
    import sci_cli.cli_session_recovery as recovery
    a, b = tmp_path / "a", tmp_path / "b"
    owner = launch(a, mode)
    other = launch(b)
    try:
        monkeypatch.setenv("SCI_HOME", str(a))
        entry = active_session_registry_snapshot()[0]
        refused, message = try_acquire_active_session(session_id="chat", surface="cli", config={})
        assert refused is None and message.reason == "SESSION_NOT_OWNED"
        if mode == "suspended":
            owner.send_signal(signal.SIGSTOP)
            limit = time.monotonic() + 5
            while psutil.Process(owner.pid).status() != psutil.STATUS_STOPPED and time.monotonic() < limit:
                time.sleep(0.01)
            assert "suspended" in describe_owner(entry)
        if mode == "dead":
            owner.kill()
            owner.wait(timeout=5)
        if mode in ("force", "wait"):
            real_wait = recovery._wait_for_exit
            waits = iter([False, None])
            monkeypatch.setattr(recovery, "_wait_for_exit",
                lambda p, ui, seconds: False if next(waits) is False else real_wait(p, ui, seconds))
        ui = UI("Cancel" if mode == "cancel" else "Close previous window and resume here",
                "Force close old CLI" if mode == "force" else "Wait longer")
        result = prepare_resume("chat", ui)
        if mode == "cancel":
            assert not result and owner.poll() is None
            assert active_session_registry_snapshot()[0]["lease_id"] == entry["lease_id"]
            return
        assert result
        owner.wait(timeout=5)
        lease, error = try_acquire_active_session(session_id="chat", surface="cli", config={})
        assert lease and not error
        # A -> B -> A: B's writer and registry remain unchanged, despite the same chat ID.
        monkeypatch.setenv("SCI_HOME", str(b))
        assert active_session_registry_snapshot()[0]["pid"] == other.pid
        assert other.poll() is None
        lease.release()  # releases A even while B is selected
        monkeypatch.setenv("SCI_HOME", str(a))
        assert active_session_registry_snapshot() == []
        db = SessionDB(a / "state.db", read_only=True)
        try:
            assert db.get_session("chat")["system_prompt"] == "fixed cached prompt"
            contents = [m["content"] for m in db.get_messages("chat")]
            assert contents[0] == "saved question"
            if mode not in ("dead", "force"):
                assert contents[-1] == "saved before close"
        finally:
            db.close()
    finally:
        for process in (owner, other):
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("change", ["identity", "lease", "surface", "multiple"])
def test_recovery_never_signals_an_unreviewed_or_shared_owner(tmp_path, change):
    from sci_cli.active_sessions import _lease_paths, _read_entries, _write_entries
    process = launch(tmp_path)
    try:
        entry = active_session_registry_snapshot(tmp_path)[0]
        state, _ = _lease_paths(registry_home=tmp_path)
        entries = _read_entries(state, strict=True)
        if change == "identity":
            entries[0]["process_start_time"] -= 100
            entry = entries[0].copy()
        elif change == "lease":
            entries[0]["lease_id"] = "new-owner"
        elif change == "surface":
            entries[0]["surface"] = "desktop"
            entry = entries[0].copy()
        else:
            entries.append({**entries[0], "session_id": "other", "lease_id": "another-chat"})
        _write_entries(state, entries)
        with pytest.raises(ValueError):
            _signal_reviewed_owner(entry, tmp_path)
        assert process.poll() is None
    finally:
        process.kill()
        process.communicate(timeout=10)
