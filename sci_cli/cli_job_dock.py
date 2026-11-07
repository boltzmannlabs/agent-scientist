"""Read plugin job snapshots for the classic CLI's existing live-work dock."""

import time

from agent.i18n import t
from sci_constants import get_sci_home


class JobDock:
    def __init__(self):
        # The spinner can run outside a turn. Bind the owning CLI's home explicitly.
        self.home = get_sci_home()

    def snapshot(self, session_id, now):
        from sci_cli.plugins import get_plugin_manager
        from sci_cli.plugins_loader import _plugin_home_scope

        if not session_id:
            return []
        with _plugin_home_scope(self.home):
            manager = get_plugin_manager()
            batches = manager.invoke_hook("cli_background_jobs", session_id=session_id, now=now)
        return [row for batch in batches if isinstance(batch, list) for row in batch
                if isinstance(row, dict) and all(isinstance(row.get(k), str) for k in ("id", "title", "status"))]


def _duration(seconds):
    seconds = max(0, int(seconds))
    minutes, seconds = divmod(seconds, 60)
    return f"{minutes}m {seconds:02d}s" if minutes else f"{seconds}s"


def lines(jobs, *, now, limit):
    result = [t("cli.jobs.heading", count=len(jobs))]
    for row in jobs[:limit]:
        glyph = "◴◷◶◵"[int(now) % 4] if row.get("active") else "•"
        elapsed = (_duration((row.get("ended_at") or now) - row["started_at"])
                   if isinstance(row.get("started_at"), (int, float)) else "")
        result.append(f"{glyph} {row['title']} — {row['status']}" + (f" · {elapsed}" if elapsed else ""))
        timing = []
        if row.get("job_id"):
            timing.append(t("cli.jobs.id", id=str(row["job_id"])[-8:]))
        if isinstance(row.get("last_checked_at"), (int, float)):
            timing.append(t("cli.jobs.last_check", age=_duration(now - row["last_checked_at"])))
        if isinstance(row.get("next_check_at"), (int, float)):
            delta = row["next_check_at"] - now
            timing.append(t("cli.jobs.next_check", delay=_duration(delta)) if delta > 0 else t("cli.jobs.check_due"))
        if timing:
            result.append("  " + " · ".join(timing))
        if row.get("detail"):
            result.append("  " + str(row["detail"]))
    if len(jobs) > limit:
        result.append(t("cli.jobs.more", count=len(jobs) - limit))
    return result


def dock_lines(jobs, *, now=None, rows=24):
    now = time.time() if now is None else now
    foreground = [row for row in jobs if row.get("foreground")]
    background = [row for row in jobs if not row.get("foreground")]
    result = []
    for row in foreground:
        result.append(f"◴ {row['title']} — {row['status']}")
        updates = row.get("recent_updates")
        if isinstance(updates, (list, tuple)):
            result.extend("  " + text for text in updates[-5:] if isinstance(text, str))
    if background:
        result.extend(lines(background, now=now, limit=2 if rows >= 32 else 1))
    return result
