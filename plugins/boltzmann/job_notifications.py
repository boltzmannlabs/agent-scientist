"""Surface saved monitor outcomes through the existing process-completion channel."""

import threading
import hashlib
import json
import time
import uuid

from agent.memory_provider import spawn_context_thread
from sci_constants import sci_home_key

from .job_store import JobStore, STOP_MONITOR
from .results import safe_detail
from .job_routes import ensure_origin_route, owns_session, session_database

_WATCHERS = set()
_LOCK = threading.Lock()
_DELIVERY_OWNER = uuid.uuid4().hex


def _already_handled(store, row, event_id):
    """Recover acknowledgement after a crash between the saved reply and hook."""
    with session_database(store.home) as db:
        if db is None:
            return False
        session_id = db.resolve_resume_session_id(row["session_id"])
        offset, waiting = 0, False
        prefix = f"[IMPORTANT: Background process {event_id} matched watch pattern "
        while True:
            messages = db.get_messages(session_id, include_compacted=True, include_ancestors=True,
                                       limit=100, offset=offset)
            for message in messages:
                if message["role"] == "user":
                    waiting = str(message.get("content") or "").startswith(prefix)
                elif (waiting and message["role"] == "assistant" and message.get("content")
                      and not message.get("tool_calls")):
                    return True
            if len(messages) < 100:
                return False
            offset += len(messages)


def _mark_handled(store, row, event_id, *, alert=False):
    now = time.time()
    store.update(row["id"], notification_handled_event_id=event_id,
                 notification_handled_at=now, notification_error=None,
                 **({"alert_delivered": True} if alert else {"notice_delivered": True}))
    if row.get("checkpoint") and not alert:
        with store.connect() as conn:
            value = conn.execute("SELECT data FROM records WHERE id=?", (row["checkpoint"],)).fetchone()
            if value:
                source = json.loads(value[0])
                store._save(conn, row["checkpoint"], {**source, "notice_delivered_group": row.get("notification_group", source.get("handled"))})
    store.release("notice:" + ((row.get("checkpoint") if not alert else None) or row["id"]), _DELIVERY_OWNER)


def acknowledge(session_id="", user_message="", assistant_response="", **kwargs):
    """A queued event is handled only after the owning session produces its reply."""
    if not assistant_response or not isinstance(user_message, str):
        return
    if not user_message.startswith("[IMPORTANT: Background process job:"):
        return
    store = JobStore()
    if not store.path.exists():
        return
    for row in store.list():
        event_id = row.get("notification_event_id")
        if (event_id and owns_session(store, row, session_id)
                and user_message.startswith(f"[IMPORTANT: Background process {event_id} matched watch pattern ")):
            _mark_handled(store, row, event_id, alert=row.get("notification_is_alert", False))


def deliver_ready(store, row, enqueue):
    row = ensure_origin_route(store, row)
    if row.get("notice_delivered") or not row.get("notification_route"):
        return False
    continuation = row.get("continuation", "")
    terminal = row["state"] in STOP_MONITOR
    ready = terminal and continuation in {"reported", "blocked", "waiting", "not_requested"}
    alert = row["state"] == "paused_auth" or row.get("monitor_error") or continuation.startswith(("interrupted", "blocked;"))
    if not ready and not alert:
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
    if source and source.get("handled") and source.get("notice_delivered_group") == source["handled"]:
        store.update(row["id"], notice_delivered=True)
        return False
    event_id = row["id"] + ":" + hashlib.sha256(text.encode()).hexdigest()[:16]
    if row.get("notification_handled_event_id") == event_id:
        return False
    # Keep an offer alive while the owner is busy. Other processes may recover it
    # after a crash, but normal watcher ticks do not enqueue duplicate replies.
    lease = "notice:" + (row.get("checkpoint") if source and not alert else row["id"])
    if not store.acquire(lease, _DELIVERY_OWNER):
        return False
    offered = source if source and source.get("handled") else row
    if (offered.get("notification_owner") == _DELIVERY_OWNER
            and (offered.get("notification_event_id") == event_id
                 or source and source.get("notice_group") == source.get("handled"))):
        return False
    if _already_handled(store, row, event_id):
        _mark_handled(store, row, event_id, alert=bool(alert))
        return False
    delivery = {"notification_owner": _DELIVERY_OWNER, "notification_event_id": event_id,
                "notification_queued_at": time.time(), "notification_is_alert": bool(alert),
                "notification_group": source.get("handled") if source else None,
                "notification_error": None,
                **({"alert_queued": True} if alert else {"notice_queued": True})}
    # Save identity before publishing: a fast consumer may acknowledge immediately.
    store.update(row["id"], **delivery)
    try:
        enqueue({"type": "watch_match", "session_id": event_id, **row["notification_route"],
                 "command": "Boltzmann durable job monitoring", "pattern": "Boltzmann state update",
                 "output": text, "started_at": row["created"]})
    except Exception:
        store.update(row["id"], notification_owner=None, notification_error="Result could not be queued; saved report retained for retry.")
        store.release(lease, _DELIVERY_OWNER)
        raise
    if source:
        with store.connect() as conn:
            latest = json.loads(conn.execute("SELECT data FROM records WHERE id=?", (row["checkpoint"],)).fetchone()[0])
            store._save(conn, row["checkpoint"], {**latest, "notice_group": source.get("handled"), **delivery})
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
                rows = [row for row in store.list() if owns_session(store, row, session_id)]
                for row in rows:
                    deliver_ready(store, row, process_registry.completion_queue.put)
                pending = [row for row in rows if not row["stopped"] and row["state"] not in STOP_MONITOR
                           and row["next_check"] <= time.time()]
                if pending and not store.worker_health():
                    from .job_monitor import ensure_worker
                    ensure_worker(store)
                if not rows or all(row["stopped"] or row.get("notice_delivered")
                                   or row["state"] in STOP_MONITOR and row.get("alert_delivered")
                                   or row.get("continuation") == "not_requested" for row in rows):
                    return
                threading.Event().wait(5)
        except Exception as exc:
            for row in store.list():
                if owns_session(store, row, session_id):
                    store.update(row["id"], notification_error=f"Live notification failed ({type(exc).__name__}); "
                                 "the saved report remains available in sci boltzmann-jobs status.")
        finally:
            with _LOCK:
                _WATCHERS.discard(key)

    thread = spawn_context_thread(run, name="boltzmann-job-notifications", daemon=True)
    thread.start()
