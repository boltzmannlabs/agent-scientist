"""A bounded, chat-owned view of foreground polls; no job execution or storage."""

from collections import deque
from contextvars import ContextVar
from functools import wraps
import sys
import threading
import uuid

from gateway.session_context import get_session_env
from sci_constants import sci_home_key


_current = ContextVar("boltzmann_poll_display", default=None)
_active = {}
_lock = threading.Lock()


def rolling_polls(fetch):
    @wraps(fetch)
    def wrapped(collection_name, doc_id, *args, **kwargs):
        identity = uuid.uuid4().hex
        row = {
            "id": identity, "title": str(collection_name), "status": "Waiting for result",
            "job_id": str(doc_id), "active": True, "foreground": True,
            "home": sci_home_key(), "session_id": get_session_env("SCI_SESSION_ID", ""),
            "updates": deque(maxlen=5), "displayed": False,
        }
        token = _current.set(row)
        with _lock:
            _active[identity] = row
        try:
            return fetch(collection_name, doc_id, *args, **kwargs)
        finally:
            with _lock:
                _active.pop(identity, None)
                tail = tuple(row["updates"]) if not row["displayed"] else ()
            _current.reset(token)
            # Pipes and MCP stderr cannot replace earlier output. Emit only the
            # latest window on exit; the interactive dock consumes it live.
            for message in tail:
                print(message, file=sys.stderr, flush=True)
    return wrapped


def report_progress(message):
    row = _current.get()
    if row is not None:
        text = "".join(c for c in str(message) if c.isprintable())[:512]
        with _lock:
            row["updates"].append(text)


def snapshot(session_id="", **kwargs):
    if not session_id:
        return []
    home = sci_home_key()
    with _lock:
        rows = []
        for row in _active.values():
            if row["home"] != home or row["session_id"] != session_id or not row["updates"]:
                continue
            row["displayed"] = True
            rows.append({**{k: row[k] for k in ("id", "title", "status", "job_id", "active", "foreground")},
                         "recent_updates": list(row["updates"])})
        return rows
