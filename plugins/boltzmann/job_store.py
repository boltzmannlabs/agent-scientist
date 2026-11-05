"""Private, transactional job-monitor checkpoints, independent of upload receipts."""

from contextlib import contextmanager
import hashlib
import json
import os
import sqlite3
import time
import uuid

from sci_cli.plugins_state import PluginState
from sci_constants import get_sci_home, mkdir_under_sci_home

MAX_RECORD_BYTES = 1024 * 1024
MAX_STORAGE_BYTES = 256 * 1024 * 1024
TERMINAL = frozenset({"completed", "success", "100%completed", "failed", "error", "cancelled", "canceled"})
STOP_MONITOR = TERMINAL | {"deleted", "not_found"}


def identity(job, doc_id):
    if not all(isinstance(v, str) and 0 < len(v) <= 500 for v in (job, doc_id)):
        raise ValueError("Monitoring requires the exact nonempty job name and document ID.")
    return hashlib.sha256(json.dumps([job, doc_id]).encode()).hexdigest()


class JobStore:
    def __init__(self):
        self.home = get_sci_home()
        self.root = PluginState("boltzmann").data_dir / "job-monitors-v1"
        self.path = self.root / "jobs.sqlite3"

    @contextmanager
    def connect(self):
        for path in (self.root.parent.parent, self.root.parent, self.root, self.path,
                     self.path.with_name(self.path.name + "-journal")):
            if path.is_symlink():
                raise ValueError("Monitor storage must not use symbolic links.")
        mkdir_under_sci_home(self.root)
        os.chmod(self.root, 0o700)
        descriptor = os.open(self.path, os.O_CREAT | os.O_WRONLY, 0o600)
        os.close(descriptor)
        os.chmod(self.path, 0o600)
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            conn.execute("PRAGMA journal_mode=DELETE")
            conn.execute("PRAGMA synchronous=FULL")
            page_size = conn.execute("PRAGMA page_size").fetchone()[0]
            conn.execute(f"PRAGMA max_page_count={MAX_STORAGE_BYTES // page_size}")
            conn.execute("CREATE TABLE IF NOT EXISTS records (id TEXT PRIMARY KEY, data TEXT NOT NULL)")
            conn.execute("CREATE TABLE IF NOT EXISTS leases (id TEXT PRIMARY KEY, owner TEXT, expires REAL)")
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _save(self, conn, key, row):
        encoded = json.dumps(row, ensure_ascii=True, allow_nan=False)
        if len(encoded.encode()) > MAX_RECORD_BYTES or self.path.stat().st_size > MAX_STORAGE_BYTES:
            raise ValueError("Monitor storage capacity unavailable. Inspect `sci boltzmann-jobs status`; "
                             "do not delete active jobs or resubmit an accepted job.")
        conn.execute("INSERT OR REPLACE INTO records VALUES (?, ?)", (key, encoded))

    def get(self, key):
        with self.connect() as conn:
            value = conn.execute("SELECT data FROM records WHERE id=?", (key,)).fetchone()
            return json.loads(value[0]) if value else None

    def update(self, key, **changes):
        with self.connect() as conn:
            value = conn.execute("SELECT data FROM records WHERE id=?", (key,)).fetchone()
            if not value:
                raise ValueError("Monitor not found in the active profile.")
            row = json.loads(value[0])
            row.update(changes, updated=time.time())
            self._save(conn, key, row)
            return row

    def list(self):
        with self.connect() as conn:
            return [json.loads(data) for (data,) in conn.execute("SELECT data FROM records WHERE id LIKE 'job:%'")]

    def track(self, job, doc_id, *, session_id="", result=None):
        key = "job:" + identity(job, doc_id)
        with self.connect() as conn:
            value = conn.execute("SELECT data FROM records WHERE id=?", (key,)).fetchone()
            row = json.loads(value[0]) if value else {
                "id": key, "job_name": job, "doc_id": doc_id, "created": time.time(),
                "state": "accepted", "stopped": False, "checks": 0, "errors": 0,
                "next_check": 0, "session_id": session_id, "continuation": "waiting"}
            if session_id and not row.get("session_id"):
                row["session_id"] = session_id
            # Never restart a stopped or terminal monitor merely by looking at its status.
            if result and not row["stopped"] and row["state"] not in STOP_MONITOR:
                row.update(self.observation(row, result))
            row["updated"] = time.time()
            self._save(conn, key, row)
            return row

    @staticmethod
    def observation(row, result):
        status = str(result.get("status", "unknown")).lower().strip()
        terminal = (status in TERMINAL and result.get("job_terminal_confirmed") is True
                    or status in {"deleted", "not_found"} and result.get("monitor_terminal_confirmed") is True)
        failed_check = bool(result.get("error")) and not terminal
        errors = row.get("errors", 0) + 1 if failed_check else 0
        state = status if terminal or status in {"pending", "running"} else "unknown"
        if result.get("authorization_required"):
            state = "paused_auth"
        return {"state": state, "last_result": result, "errors": errors,
                **({"alert_queued": False, "monitor_error": None} if not failed_check else {}),
                "checks": row.get("checks", 0) + 1,
                "next_check": time.time() + min(30 * 2 ** min(errors, 5), 900)}

    def acquire(self, key, owner, seconds=120):
        with self.connect() as conn:
            lease = conn.execute("SELECT owner, expires FROM leases WHERE id=?", (key,)).fetchone()
            if lease and lease[0] != owner and lease[1] > time.time():
                return False
            conn.execute("INSERT OR REPLACE INTO leases VALUES (?, ?, ?)", (key, owner, time.time() + seconds))
            return True

    def release(self, key, owner):
        with self.connect() as conn:
            conn.execute("DELETE FROM leases WHERE id=? AND owner=?", (key, owner))

    def worker_health(self):
        with self.connect() as conn:
            value = conn.execute("SELECT expires FROM leases WHERE id='worker'").fetchone()
            return bool(value and value[0] > time.time())

    def finish_if_idle(self, owner):
        # Couple the final work scan and lease release. A submission racing an
        # idle worker must either keep it alive or observe no owner and start one.
        with self.connect() as conn:
            rows = [json.loads(data) for (data,) in conn.execute("SELECT data FROM records WHERE id LIKE 'job:%'")]
            if any(not row["stopped"] and (row["state"] not in STOP_MONITOR
                   or row.get("checkpoint") and row["continuation"] == "waiting") for row in rows):
                return False
            conn.execute("DELETE FROM leases WHERE id='worker' AND owner=?", (owner,))
            conn.execute("DELETE FROM leases WHERE id='launch'")
            return True


def new_owner():
    return uuid.uuid4().hex
