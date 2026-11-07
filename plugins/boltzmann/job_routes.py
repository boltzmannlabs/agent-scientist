"""Keep a monitor's delivery destination bound to its originating conversation."""

from contextlib import contextmanager


@contextmanager
def session_database(home):
    from sci_state import SessionDB

    path = home / "state.db"
    if not path.exists():
        yield None
        return
    db = SessionDB(db_path=path, read_only=True)
    try:
        yield db
    finally:
        db.close()


def capture_route(session_id, platform=""):
    from gateway.session_context import get_session_env
    from sci_constants import get_sci_home

    with session_database(get_sci_home()) as db:
        session = db.get_session(session_id) if db else None
    # A CLI has no channel routing key. An ambient key may belong to an earlier
    # cron run even when SCI_SESSION_ID has already been rebound to this chat.
    if platform == "cli" or session and session.get("source") == "cli":
        return {"platform": "cli", "session_key": session_id}
    if not session_id or get_session_env("SCI_SESSION_ID") != session_id:
        return {}
    route = {key: get_session_env("SCI_SESSION_" + key.upper()) for key in
             ("platform", "chat_id", "user_id", "user_name", "thread_id", "message_id")}
    route["session_key"] = get_session_env("SCI_SESSION_KEY") or session_id
    return route


def ensure_origin_route(store, row):
    source = store.get(row["checkpoint"]) if row.get("checkpoint") else None
    route = row.get("notification_origin") or (source or {}).get("notification_route")
    if not route:
        # Recover old misrouted CLI rows from persisted session ownership, never
        # from the internal worker's current session environment.
        with session_database(store.home) as db:
            session = db.get_session(row.get("session_id", "")) if db else None
        route = ({"platform": "cli", "session_key": row["session_id"]}
                 if session and session.get("source") == "cli"
                 else row.get("notification_route"))
    if not route:
        route = capture_route(row.get("session_id", ""))
    if route and (row.get("notification_route") != route or not row.get("notification_origin")):
        changes = {"notification_origin": route, "notification_route": route}
        if row.get("notification_route") != route:
            changes.update(notice_queued=False, notice_delivered=False,
                           notification_owner=None, notification_error=None)
        row = store.update(row["id"], **changes)
    return row


def owns_session(store, row, session_id):
    origin = row.get("session_id")
    if not origin or not session_id:
        return False
    if origin == session_id:
        return True
    with session_database(store.home) as db:
        return bool(db and db.resolve_resume_session_id(origin) == session_id)
