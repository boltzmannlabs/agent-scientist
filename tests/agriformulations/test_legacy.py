"""Historical report access and isolated deterministic replay contracts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import threading
import time

import pytest

from agri_tool.legacy import handle


from agriformulations._paths import resource_root
ENGINE = resource_root()


class Context:
    def __init__(self, root, engine):
        self.root = root
        self.engine = engine
        root.mkdir(parents=True, exist_ok=True)

    def artifact(self, path, media_type="application/octet-stream", name=None):
        content = path.read_bytes()
        sha = hashlib.sha256(content).hexdigest()
        destination = self.root / "artifacts" / sha / (name or path.name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
        return {"artifact_id": sha, "path": str(destination), "name": name or path.name,
                "sha256": sha, "bytes": len(content), "media_type": media_type}


def test_archive_access_is_constrained_and_retains_historical_status(tmp_path):
    context = Context(tmp_path / "workspace", ENGINE)
    catalogue = handle("catalogue", {}, context)
    assert catalogue["runners"] and catalogue["reports"]
    for entry in catalogue["runners"]:
        assert entry["module"].startswith("scripts.")
        assert entry["note"]
    result = handle("report", {"path": "v11/v11_gate.json"}, context)
    assert result["historical"] is True
    assert result["content"]["fickian_claim_infeasible"] is True
    artifact = result["artifacts"][0]
    assert hashlib.sha256(Path(artifact["path"]).read_bytes()).hexdigest() == result["sha256"]
    for path in ("../UPSTREAM_MANIFEST.json", "/etc/passwd", "v11/../../README.md", "v11\\v11_gate.json"):
        with pytest.raises(ValueError):
            handle("report", {"path": path}, context)
    with pytest.raises(ValueError, match="registered"):
        handle("run", {"runner": "scripts.reproduce"}, context)
    with pytest.raises(ValueError, match="Unsupported"):
        handle("run", {"runner": "v11_zero_order", "command": "echo unsafe"}, context)


def test_registered_zero_order_replay_is_real_isolated_and_retrievable(tmp_path):
    context = Context(tmp_path / "workspace", ENGINE)
    original = context.engine / "reports/v11/v11_gate.json"
    before = original.read_bytes()
    result = handle("run", {"runner": "v11_zero_order", "timeout_seconds": 60}, context)
    assert result["status"] == "completed", result["log_tail"]
    assert result["execution"]["returncode"] == 0
    assert result["execution"]["isolated"] is True
    assert "reports/v11/v11_gate.json" in result["changed_outputs"] or any(
        name.endswith("execution_manifest.json") for name in result["changed_outputs"])
    # The original immutable archive and the newly executed output are distinct.
    assert original.read_bytes() == before
    isolated_gate = context.root / "legacy_runs" / result["run_id"] / "engine/reports/v11/v11_gate.json"
    gate = json.loads(isolated_gate.read_text())
    assert gate["fickian_claim_infeasible"] and gate["zero_order_claim_feasible"]
    assert gate["recovery_pass"] and gate["determinism_pass"]
    assert gate["proposal_submitted"] is False
    assert handle("get", {"run_id": result["run_id"]}, context)["execution"] == result["execution"]
    assert any(row["run_id"] == result["run_id"] for row in handle("runs", {}, context)["runs"])
    with pytest.raises(ValueError, match="not found"):
        handle("get", {"run_id": result["run_id"]}, Context(tmp_path / "other", context.engine))


def test_cancellation_stops_the_child_and_retains_completed_evidence(tmp_path, monkeypatch):
    from agriformulations.rnd import control

    engine = tmp_path / "fixture_engine"
    (engine / "scripts").mkdir(parents=True)
    (engine / "scripts/__init__.py").write_text("")
    (engine / "scripts/run_v11_zero_order.py").write_text(
        "from pathlib import Path\nimport time,json,os\n"
        "p=Path('reports');p.mkdir(exist_ok=True)\n"
        "(p/'completed.json').write_text(json.dumps({'partial':True,'cuda_visible':os.environ.get('CUDA_VISIBLE_DEVICES'),'inherited_secret':'OPENAI_API_KEY' in os.environ}))\n"
        "print('checkpoint completed',flush=True)\ntime.sleep(300)\n")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-must-not-reach-worker")
    context = Context(tmp_path / "workspace", engine)
    token = control.RunControl()
    outcome = []

    def execute():
        try:
            with control.scope(token):
                handle("run", {"runner": "v11_zero_order", "timeout_seconds": 60}, context)
        except control.RunCancelled as exc:
            outcome.append(str(exc))

    thread = threading.Thread(target=execute)
    thread.start()
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline and not list(context.root.glob("legacy_runs/*/engine/reports/completed.json")):
        time.sleep(.02)
    assert list(context.root.glob("legacy_runs/*/engine/reports/completed.json"))
    token.cancel()
    thread.join(timeout=5)
    assert not thread.is_alive()
    assert outcome and "stopped" in outcome[0]
    run = json.loads(next(context.root.glob("legacy_runs/*/run.json")).read_text())
    assert run["status"] == "cancelled"
    assert "reports/completed.json" in run["changed_outputs"]
    assert any(artifact["name"] == "completed.json" for artifact in run["artifacts"])
    output = json.loads(next(context.root.glob("legacy_runs/*/engine/reports/completed.json")).read_text())
    assert output["cuda_visible"] == ""
    assert output["inherited_secret"] is False
