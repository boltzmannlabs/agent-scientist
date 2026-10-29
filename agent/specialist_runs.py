"""Durable named-run receipts alongside the existing full delegation transcripts."""
from __future__ import annotations
import json
import os
from pathlib import Path
import time
from sci_constants import get_sci_home, mkdir_under_sci_home
from utils import atomic_json_write


def record(child, goal, result=None):
    policy = getattr(child, "_specialist_policy", None)
    from agent.specialist_policy import SpecialistPolicy
    if not isinstance(policy, SpecialistPolicy):
        return
    run_id = child._subagent_id
    root = Path(policy.home) / "subagent-runs"
    if root.is_symlink():
        raise ValueError("Run receipt directory must not be a symbolic link.")
    mkdir_under_sci_home(root)
    path = root / f"{run_id}.json"
    if result is None:
        row = {"run_id": run_id, "specialist": policy.name, "revision": policy.revision,
               "goal": goal, "status": "queued", "started_at": time.time(), "pid": os.getpid(),
               "session_id": getattr(child, "session_id", None),
               "parent_session_id": getattr(child, "_parent_session_id", None),
               "transcript": getattr(child, "_live_transcript_path", None)}
    else:
        row = json.loads(path.read_text(encoding="utf-8-sig")) if path.exists() else {"run_id": run_id, "specialist": policy.name}
        row.update({"status": result.get("status", "unknown"), "finished_at": time.time(),
                    "result": {k: v for k, v in result.items() if not k.startswith("_")}})
    atomic_json_write(path, row, mode=0o600)


def history(home=None):
    from tools.delegate_tool_registry import list_active_subagents
    root = Path(home or get_sci_home()) / "subagent-runs"
    if root.is_symlink():
        raise ValueError("Run receipt directory must not be a symbolic link.")
    active = {r["subagent_id"]: r for r in list_active_subagents()}
    rows = []
    for path in root.glob("sa-*.json"):
        if path.is_symlink():
            continue
        row = json.loads(path.read_text(encoding="utf-8-sig"))
        if row.get("status") == "queued":
            live = active.get(row["run_id"])
            row["status"] = "running" if live else "unknown"
            if live:
                row["progress"] = {k: live.get(k) for k in ("current_tool", "iteration", "tool_count", "started_at")}
            if not live:
                row["note"] = "No live worker is recorded here. It may have stopped or belong to another process; this is not proof a remote job stopped."
        rows.append(row)
    return sorted(rows, key=lambda r: r.get("started_at", 0), reverse=True)
