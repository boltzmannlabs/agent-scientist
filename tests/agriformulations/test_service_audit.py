"""Recovery and observation identity invariants through the real service."""
import base64
from copy import deepcopy
import json
from concurrent.futures import ThreadPoolExecutor
import threading
import zipfile

import pytest

from agri_tool.catalogue import EXAMPLE_RECIPE
from agri_tool.service import execute
from agri_tool.storage import Store
from agriformulations.rnd import control, simulation_service


@pytest.fixture
def case(tmp_path):
    root = tmp_path / "workspace"
    created = execute({"operation":"recipes", "action":"manual", "payload":{"recipe":deepcopy(EXAMPLE_RECIPE)}}, root)
    assert created["status"] == "completed", created
    return root, created["project_id"], created["result"]["recipes"][0]


def test_cancelled_batch_resumes_original_request_without_duplicate_scenarios(case, monkeypatch):
    root, pid, recipe = case
    original = simulation_service.record
    def cancel_after_checkpoint(state, request):
        result = original(state, request)
        control.current().cancel()
        return result
    monkeypatch.setattr(simulation_service,"record",cancel_after_checkpoint)
    request = {"operation":"simulate", "action":"batch", "project_id":pid, "request_id":"resume-batch", "payload":{"requests":[
        {"recipe_id":recipe["recipe_id"],"model":"rheology","inputs":{}},
        {"recipe_id":recipe["recipe_id"],"model":"suspension","inputs":{}}]}}
    stopped = execute(request, root)
    assert stopped["status"] == "cancelled", stopped
    monkeypatch.setattr(simulation_service,"record",original)
    retry = execute(request, root)
    assert retry["status"] == "cancelled"  # A transport retry is not consent to resume.
    resumed = execute({"operation":"project","action":"resume","payload":{"request_id":"resume-batch"}}, root)
    assert resumed["status"] == "completed", resumed
    saved = Store(root).load(pid)["document"]
    assert {r["kind"] for r in saved["analysis_runs"]} == {"rheology","suspension"}
    assert len(saved["analysis_runs"]) == 2


def test_crash_recovery_preserves_newer_user_project_settings(case, monkeypatch):
    root, pid, recipe = case
    original = simulation_service.record
    def crash_after_checkpoint(state, request):
        original(state, request)
        raise SystemExit("simulated process exit after durable checkpoint")
    monkeypatch.setattr(simulation_service,"record",crash_after_checkpoint)
    request = {"operation":"simulate", "model":"rheology", "project_id":pid, "request_id":"crash-and-resume", "payload":{"recipe_id":recipe["recipe_id"],"inputs":{},"expected_revision":Store(root).load(pid)["revision"]}}
    with pytest.raises(SystemExit):
        execute(request, root)
    monkeypatch.setattr(simulation_service,"record",original)
    with Store(root).connect() as db:
        db.execute("UPDATE requests SET owner=? WHERE request_id=?",(999999999,"crash-and-resume"))
    renamed = execute({"operation":"project","action":"rename","project_id":pid,"payload":{"name":"Newer user title"}},root)
    assert renamed["status"] == "completed", renamed
    resumed = execute(request, root)
    assert resumed["status"] == "completed", resumed
    assert Store(root).load(pid)["document"]["brief"]["name"] == "Newer user title"


def test_same_file_different_selected_assays_remain_distinct_datasets(case):
    root,pid,recipe = case
    raw = "shear,stress,batch,condition\n"+"\n".join(
        f"{x},{k*x},B1,{name}" for name,k in [("assay-a",.5),("assay-b",2.)] for x in [1,2,5,10,100,1000])
    file = {"filename":"two-assays.csv","content_base64":base64.b64encode(raw.encode()).decode(),"kind":"rheology",
        "recipe_id":recipe["recipe_id"],"active_name":recipe["active_components"][0]["name"],"source_kind":"synthetic", "instrument":"Synthetic arithmetic",
        "mapping":{"x":"shear","value":"stress","batch":"batch","condition":"condition"},"x_unit":"1/s","value_unit":"Pa"}
    results = []
    for name in ["assay-a","assay-b"]:
        result = execute({"operation":"data","action":"import","project_id":pid,"payload":{"file":{**file,"condition_value":name}}},root)
        assert result["status"] == "completed", result
        results.append(result["result"])
    assert results[0]["dataset_id"] != results[1]["dataset_id"]
    assert {r["condition_id"] for r in results[1]["observations"]} == {"assay-b"}
    assert len(Store(root).load(pid)["document"]["imports"]) == 2


def test_concurrent_explicit_user_edits_refuse_a_stale_revision(case,monkeypatch):
    from agri_tool import projects
    root,pid,_ = case
    revision = Store(root).load(pid)["revision"]
    original = projects.handle
    barrier = threading.Barrier(2)
    def concurrent(action,payload,context):
        if action == "rename":
            barrier.wait(timeout=5)
        return original(action,payload,context)
    monkeypatch.setattr(projects,"handle",concurrent)
    def rename(name):
        return execute({"operation":"project","action":"rename","project_id":pid,"payload":{"name":name,"expected_revision":revision}},root)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(rename,["User choice A","User choice B"]))
    assert sorted(r["status"] for r in results) == ["completed","error"],results
    rejected = next(r for r in results if r["status"] == "error")
    assert rejected["error"]["code"] == "revision_conflict"


def test_recipe_creation_crash_reuses_the_already_created_project(tmp_path,monkeypatch):
    from agri_tool import recipe_actions
    root = tmp_path / "workspace"
    original = recipe_actions.add
    def crash_after_save(context,result):
        original(context,result)
        raise SystemExit("simulated exit after first project save")
    monkeypatch.setattr(recipe_actions,"add",crash_after_save)
    request = {"operation":"recipes","action":"manual","request_id":"first-project","payload":{"recipe":deepcopy(EXAMPLE_RECIPE)}}
    with pytest.raises(SystemExit):
        execute(request,root)
    projects = Store(root).list()
    assert len(projects) == 1
    monkeypatch.setattr(recipe_actions,"add",original)
    with Store(root).connect() as db:
        db.execute("UPDATE requests SET owner=? WHERE request_id=?",(999999999,"first-project"))
    resumed = execute(request,root)
    assert resumed["status"] == "completed",resumed
    assert resumed["project_id"] == projects[0]["project_id"]
    assert len(Store(root).list()) == 1


def test_historical_dossier_includes_each_available_phase_gate(tmp_path,monkeypatch):
    from agriformulations.labops import dossier
    source = tmp_path / "historical"
    phases = ["v2","v3","v4","v5","v6"]
    for phase in phases:
        folder = source / "reports" / phase
        folder.mkdir(parents=True)
        (folder / (phase+"_gate.json")).write_text(json.dumps({"historical_phase":phase,"passed":False}))
    monkeypatch.setattr(dossier,"REPO_ROOT",source)
    archive = dossier.export_dossier(tmp_path / "dossier.zip")
    with zipfile.ZipFile(archive) as z:
        for phase in phases:
            assert json.loads(z.read("gates/"+phase+"_gate.json")) == {"historical_phase":phase,"passed":False}
