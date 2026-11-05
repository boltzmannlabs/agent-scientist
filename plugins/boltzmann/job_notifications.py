"""Surface saved monitor outcomes through the existing process-completion channel."""

import threading
import hashlib
import json

from agent.memory_provider import spawn_context_thread
from sci_constants import sci_home_key

from .job_store import JobStore, STOP_MONITOR
from .results import safe_detail

_WATCHERS = set()
_LOCK = threading.Lock()


def deliver_ready(store, row, enqueue):
    if row.get("notice_queued") or not row.get("notification_route"):
        return False
    continuation = row.get("continuation", "")
    terminal = row["state"] in STOP_MONITOR
    ready = terminal and continuation in {"reported", "blocked", "waiting", "not_requested"}
    alert = row["state"] == "paused_auth" or row.get("monitor_error") or continuation.startswith(("interrupted", "blocked;"))
    if not ready and not alert:
        return False
    if alert and row.get("alert_queued"):
        return False
    if row.get("checkpoint") and continuation == "waiting" and not alert:
        return False
    response = row.get("continuation_result", {}).get("response", "")
    if alert:
        response = row.get("monitor_error") or row.get("last_result", {}).get("error") or continuation
    text = (f"Boltzmann job {row['job_name']}: {row['state']}. "
            "The saved job was not resubmitted. "
            + (safe_detail(response) if response else "Inspect sci boltzmann-jobs status for the saved result.")
            + "\nThis is an outcome notification. Do not repeat work already performed by the saved continuation.")
    source = store.get(row["checkpoint"]) if row.get("checkpoint") and ready else None
    if source and source.get("notice_group") == source.get("handled"):
        store.update(row["id"], notice_queued=True)
        return False
    event_id = row["id"] + ":" + hashlib.sha256(text.encode()).hexdigest()[:16]
    enqueue({"type": "watch_match", "session_id": event_id, **row["notification_route"],
             "command": "Boltzmann durable job monitoring", "pattern": "Boltzmann state update",
             "output": text, "started_at": row["created"]})
    store.update(row["id"], **({"alert_queued": True} if alert else {"notice_queued": True}))
    if source:
        with store.connect() as conn:
            latest = json.loads(conn.execute("SELECT data FROM records WHERE id=?", (row["checkpoint"],)).fetchone()[0])
            store._save(conn, row["checkpoint"], {**latest, "notice_group": source.get("handled")})
    return True


def watch(session_id):
    if not session_id or session_id == "mcp":
        return
    key = (sci_home_key(), session_id)
    with _LOCK:
        if key in _WATCHERS:
            return
        _WATCHERS.add(key)

    store = JobStore()

    def run():
        from tools.process_registry import process_registry
        try:
            while True:
                rows = [row for row in store.list() if row.get("session_id") == session_id]
                for row in rows:
                    deliver_ready(store, row, process_registry.completion_queue.put)
                import time
                pending = [row for row in rows if not row["stopped"] and row["state"] not in STOP_MONITOR
                           and row["next_check"] <= time.time()]
                if pending and not store.worker_health():
                    from .job_monitor import ensure_worker
                    ensure_worker(store)
                if not rows or all(row["stopped"] or row.get("notice_queued")
                                   or row["state"] in STOP_MONITOR and row.get("alert_queued")
                                   or row.get("continuation") == "not_requested" for row in rows):
                    return
                threading.Event().wait(5)
        except Exception as exc:
            for row in store.list():
                if row.get("session_id") == session_id:
                    store.update(row["id"], notification_error=f"Live notification failed ({type(exc).__name__}); "
                                 "the saved report remains available in sci boltzmann-jobs status.")
        finally:
            with _LOCK:
                _WATCHERS.discard(key)

    thread = spawn_context_thread(run, name="boltzmann-job-notifications", daemon=True)
    thread.start()
