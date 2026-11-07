"""Export the visible user/assistant transcript for the interactive CLI."""

from __future__ import annotations

import shlex
from pathlib import Path

from sci_constants import get_sci_home
from sci_cli.session_export import render_chat_export


def export_chat(cli, command: str, *, session: dict | None = None) -> Path | None:
    """Write the current chat (or supplied side-chat snapshot) as Markdown."""
    try:
        args = shlex.split(command.strip())
    except ValueError as exc:
        print(f"Could not parse export path: {exc}")
        return None
    if len(args) > 2:
        print('Usage: /export-chat [output.md]')
        return None

    if session is None:
        db = getattr(cli, "_session_db", None)
        session_id = getattr(cli, "session_id", None)
        if db and session_id:
            try:
                session = db.export_session(session_id, include_compacted=True)
            except Exception:
                session = None
        if not session:
            history = getattr(cli, "conversation_history", None) or []
            if not history:
                print("There are no chat messages to export.")
                return None
            session = {
                "id": session_id or "chat",
                "title": getattr(cli, "session_title", None),
                "model": getattr(cli, "model", None),
                "started_at": getattr(getattr(cli, "session_start", None), "timestamp", lambda: None)(),
                "messages": history,
            }

    messages = [m for m in session.get("messages") or [] if isinstance(m, dict)
                and m.get("role") in ("user", "assistant")]
    if not messages:
        print("There are no user/assistant messages to export.")
        return None

    if len(args) == 2:
        target = Path(args[1]).expanduser()
        if not target.is_absolute():
            target = Path.cwd() / target
    else:
        saved = get_sci_home() / "sessions" / "saved"
        saved.mkdir(parents=True, exist_ok=True)
        safe_id = "".join(ch for ch in str(session.get("id") or "chat")
                          if ch.isalnum() or ch in "-_") or "chat"
        target = saved / f"sci_chat_{safe_id}.md"

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(render_chat_export(session), encoding="utf-8")
    except OSError as exc:
        print(f"Chat export failed: {exc}")
        return None
    print(f"Chat exported to {target}")
    return target
