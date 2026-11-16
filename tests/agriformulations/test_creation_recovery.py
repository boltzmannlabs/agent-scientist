"""Project-birth and coupled-development recovery preserve exact identities."""
from copy import deepcopy

import pytest

from agri_tool import projects
from agri_tool.catalogue import DETAILS
from agri_tool.service import Context, execute
from agri_tool.storage import Store
from agriformulations.rnd import control


@pytest.mark.parametrize("action", ["create", "fork"])
def test_committed_project_creation_or_fork_survives_exit_before_response(tmp_path, monkeypatch, action):
    workspace = tmp_path / "workspace"
    source_id = None
    if action == "fork":
        source = execute({"operation": "project", "action": "create", "payload": {"name": "Preserved source"}}, workspace)
        source_id = source["project_id"]
    request_id = "commit-then-crash-" + action
    request = {"operation": "project", "action": action, "request_id": request_id,
               "payload": {"name": "Committed destination"}}
    if source_id:
        request["project_id"] = source_id
    original = projects.handle

    def crash_after_commit(kind, payload, context):
        result = original(kind, payload, context)
        if kind == action:
            raise SystemExit("Simulated exit after project commit before response")
        return result

    monkeypatch.setattr(projects, "handle", crash_after_commit)
    with pytest.raises(SystemExit):
        execute(request, workspace)
    monkeypatch.setattr(projects, "handle", original)
    store = Store(workspace)
    committed_id = store.job(request_id)["project_id"]
    assert committed_id and committed_id != source_id
    before = {r["project_id"] for r in store.list()}

    # A later user edit must survive recovery of the older creation request.
    renamed = execute({"operation": "project", "action": "rename", "project_id": committed_id,
                       "payload": {"name": "Newer user destination title"}}, workspace)
    assert renamed["status"] == "completed", renamed
    with store.connect() as db:
        db.execute("UPDATE requests SET owner=? WHERE request_id=?", (999999999, request_id))
    recovered = execute(request, workspace)
    assert recovered["status"] == "completed", recovered
    assert recovered["project_id"] == committed_id
    assert {r["project_id"] for r in store.list()} == before
    assert store.load(committed_id)["document"]["brief"]["name"] == "Newer user destination title"
    if source_id:
        assert store.load(source_id)["document"]["brief"]["name"] == "Preserved source"
        assert store.load(committed_id)["document"]["source_project"]["project_id"] == source_id


def test_development_resume_reuses_child_and_each_recipe_stage_has_its_own_identity(tmp_path, monkeypatch):
    workspace = tmp_path / "workspace"
    source = execute({"operation": "project", "action": "create",
                      "payload": {"name": "Research source"}}, workspace)
    source_id = source["project_id"]
    source_revision = source["revision"]
    brief = {
        "name": "Two explicit SC hypotheses", "format": "SC", "active_name": "Tebuconazole",
        "active_pct": 20, "batch_g": 500, "count": 2,
        "ingredients": [
            {"name": "Tebuconazole technical", "role": "active", "min_pct": 20, "max_pct": 25, "purity_pct": 95},
            {"name": "Sodium lignosulfonate", "role": "dispersant", "min_pct": 1, "max_pct": 5, "purity_pct": 100},
            {"name": "Water", "role": "solvent", "min_pct": 70, "max_pct": 80, "purity_pct": 100},
        ],
        "process": [{"instruction": "Hypothetical shared preparation; product properties unverified"}],
    }
    payload = deepcopy(DETAILS["design"]["develop"]["payload"])
    payload["brief"] = brief
    payload["scenarios"][0]["active_name"] = "Tebuconazole technical"
    request = {"operation": "design", "action": "develop", "project_id": source_id,
               "request_id": "coupled-development-resume", "payload": payload}
    checkpoint = Context.checkpoint

    def stop_after_first_completed_stage(context, state, message):
        checkpoint(context, state, message)
        if message.startswith("Saved kinetics"):
            control.current().cancel()

    monkeypatch.setattr(Context, "checkpoint", stop_after_first_completed_stage)
    cancelled = execute(request, workspace)
    assert cancelled["status"] == "cancelled", cancelled
    monkeypatch.setattr(Context, "checkpoint", checkpoint)
    child_id = cancelled["project_id"]
    assert child_id != source_id
    store = Store(workspace)
    initial_records = store.load(child_id)["document"]["analysis_runs"]
    assert initial_records and initial_records[0]["kind"] == "kinetics"
    initial_scenario = initial_records[0]["scenario_id"]
    assert len(store.list()) == 2

    retry = execute(request, workspace)
    assert retry["status"] == "cancelled"  # Transport retry cannot resume user-stopped work.
    resumed = execute({"operation": "project", "action": "resume", "request_id": "resume-control",
                       "payload": {"request_id": request["request_id"]}}, workspace)
    assert resumed["status"] == "completed", resumed
    assert resumed["project_id"] == child_id
    assert len(store.list()) == 2
    child = store.load(child_id)["document"]
    assert child["source_project"] == {"project_id": source_id, "revision": source_revision}
    assert store.load(source_id)["document"]["recipes"] == []
    records = child["analysis_runs"]
    assert len(records) == 6
    assert len({r["scenario_id"] for r in records}) == len(records)
    assert initial_scenario in {r["scenario_id"] for r in records}
    expected = {(recipe["recipe_id"], stage) for recipe in child["recipes"]
                for stage in ("kinetics", "stability", "dosage")}
    assert {(r["recipe_id"], r["kind"]) for r in records} == expected
    for record in records:
        retrieved = execute({"operation": "project", "action": "result", "project_id": child_id,
                             "payload": {"id": record["scenario_id"]}}, workspace)
        assert retrieved["status"] == "completed", retrieved
        assert retrieved["result"]["record"] == record
