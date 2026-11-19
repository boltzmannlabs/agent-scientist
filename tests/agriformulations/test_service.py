"""Real numerical operations, saved identities, input gates and local JSON boundary."""
import base64
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from agriformulations.rnd import simulation_catalog
from agri_tool.catalogue import EXAMPLE_RECIPE
from agri_tool.service import execute
from agri_tool.storage import Store


@pytest.fixture
def client(tmp_path):
    def call(operation, action="", payload=None, project_id=None, **kwargs):
        return execute({"operation": operation, "action": action, "payload": payload or {},
            **({"project_id": project_id} if project_id else {}), **kwargs}, tmp_path / "workspace")
    return call


@pytest.fixture
def project(client):
    result = client("recipes", "manual", {"recipe": deepcopy(EXAMPLE_RECIPE)})
    assert result["status"] == "completed", result
    return result["project_id"], result["result"]["recipes"][0]


@pytest.mark.parametrize("model", [m["key"] for m in simulation_catalog.catalogue()])
def test_every_catalogue_model_runs_through_saved_recipe_and_retrieves_exact_inputs(client, project, model):
    pid, recipe = project
    payload = {"recipe_id": recipe["recipe_id"], "active_name": recipe["active_components"][0]["name"], "inputs": {}, "assumptions": ["Explicit synthetic scenario; not measured"]}
    if model == "mixture_response":
        raw = deepcopy(EXAMPLE_RECIPE)
        raw["ingredients"][1].update(name="Second active", role="active", purity_pct=90)
        created = client("recipes", "manual", {"recipe": raw}, pid)
        recipe = created["result"]["recipes"][0]
        payload.update(recipe_id=recipe["recipe_id"], active_b_name="Second active")
    if model == "inverse_design":
        payload["inputs"]["evaluations"] = 12
    if model == "robustness":
        payload["inputs"]["samples"] = 10
    response = client("simulate", payload=payload, project_id=pid, model=model)
    assert response["status"] == "completed", response
    entry = response["result"]
    assert entry["kind"] == model
    assert entry["result"]["metrics"]
    assert entry["result"]["recipe_linkage"]["recipe_id"] == recipe["recipe_id"]
    saved = client("project", "result", {"id": entry["scenario_id"]}, pid)
    assert saved["result"]["record"] == entry
    assert entry["engine_version"] == entry["engine_manifest"]["fingerprint"]


def test_questions_validation_exact_retry_and_project_ownership(client, project, tmp_path):
    missing = client("recipes", "create", {"brief": {"name": "No active"}})
    assert missing["status"] == "needs_input" and missing["questions"]
    pid, recipe = project
    mode = client("design", project_id=pid)
    assert mode["status"] == "needs_input" and len(mode["questions"][0]["choices"]) == 2
    bad = deepcopy(EXAMPLE_RECIPE)
    bad["ingredients"][0]["pct"] = 90
    before = client("project", "get", project_id=pid)["revision"]
    assert client("recipes", "manual", {"recipe": bad}, pid)["status"] == "error"
    assert client("project", "get", project_id=pid)["revision"] == before
    request = {"recipe_id": recipe["recipe_id"], "inputs": {}}
    a = client("simulate", payload=request, project_id=pid, model="rheology", request_id="stable-run")
    b = client("simulate", payload=request, project_id=pid, model="rheology", request_id="stable-run")
    assert b["reused_request"] and a["result"] == b["result"]
    conflict = client("simulate", payload={**request, "inputs": {"flow_l_min": 10}}, project_id=pid, model="rheology", request_id="stable-run")
    assert conflict["status"] == "error"
    other = execute({"operation": "project", "project_id": pid}, tmp_path / "other-workspace")
    assert other["status"] == "error"
    stale = client("recipes", "select", {"recipe_id": recipe["recipe_id"], "expected_revision": 0}, pid)
    assert stale["error"]["code"] == "revision_conflict"


def test_design_compare_optimize_replay_and_portable_export(client, project):
    pid, recipe = project
    amounts = {i["name"]: i["pct"] for i in recipe["ingredients"]}
    amounts["Xanthan gum"] += .1; amounts["Water"] -= .1
    revised = client("recipes", "variant", {"recipe_id": recipe["recipe_id"], "percentages": amounts}, pid)
    r2 = revised["result"]["recipes"][0]
    active = recipe["active_components"][0]["name"]
    study = {"name": "Handling", "goal": "Explicit physical hypotheses", "candidates": [
        {"recipe_id": r["recipe_id"], "active_name": active, "inputs": {"flow": {"consistency_pa_sn": k}}} for r, k in [(recipe, .8), (r2, 1.2)]],
        "scenarios": [{"id": "flow", "model": "rheology", "inputs": {"yield_stress_pa": 0, "flow_index": 1}, "candidate_parameters": ["consistency_pa_sn"]}],
        "criteria": [{"scenario": "flow", "metric": "pressure_bar", "maximum": .8, "goal": "minimize"}], "assumptions": ["Synthetic property scenarios"]}
    compared = client("design", "study", {"study": study}, pid)
    assert compared["status"] == "completed", compared
    assert compared["result"]["summary"]["complete_candidates"] == 2
    result = client("design", "optimize", {"recipe_id": recipe["recipe_id"], "active_name": active,
        "inputs": {"base_model": "rheology", "base_inputs": {"yield_stress_pa": 0, "flow_index": 1},
            "variables": [{"parameter": "consistency_pa_sn", "low": .01, "high": 2, "scale": "log"}],
            "objectives": [{"metric": "pressure_bar", "goal": "minimize"}], "constraints": [{"metric": "viscosity_at_100_s_pa_s", "minimum": .5}], "evaluations": 12},
        "study": study, "scenario_id": "flow"}, pid)
    assert result["status"] == "completed", result
    assert result["result"]["whole_study_replays"]
    assert all(s["summary"]["complete_candidates"] == 2 for s in result["result"]["whole_study_replays"])
    exported = client("project", "export", project_id=pid)
    assert exported["status"] == "completed", exported
    pdf = next(a for a in exported["artifacts"] if a["media_type"] == "application/pdf")
    assert Path(pdf["path"]).read_bytes().startswith(b"%PDF-")
    archive = next(a for a in exported["artifacts"] if a["media_type"] == "application/zip")
    with zipfile.ZipFile(archive["path"]) as z:
        assert "report.pdf" in z.namelist()
        assert not any(name.endswith(".html") for name in z.namelist())
        assert len(z.namelist()) == len(set(z.namelist()))
        document = json.loads(z.read("project.json"))
        assert len(document["recipes"]) == 2 and document["design_studies"]
        assert any(n.endswith(".png") for n in z.namelist())


def test_data_source_review_fit_and_stale_calibration_gates(client, project):
    pid, recipe = project
    raw = "shear,stress,batch\n" + "\n".join(f"{x},{.5*x},B1" for x in [1,2,5,10,100,1000])
    file = {"filename": "flow.csv", "content_base64": base64.b64encode(raw.encode()).decode(), "kind": "rheology",
        "recipe_id": recipe["recipe_id"], "active_name": recipe["active_components"][0]["name"], "source_kind": "synthetic", "instrument": "Synthetic verification relation",
        "mapping": {"x": "shear", "value": "stress", "batch": "batch"}, "x_unit": "1/s", "value_unit": "Pa"}
    imported = client("data", "import", {"file": file}, pid)
    assert imported["status"] == "completed", imported
    did = imported["result"]["dataset_id"]
    reviewed = client("data", "review", {"dataset_id": did, "review": {"status": "reviewed", "notes": "Synthetic arithmetic only", "excluded_source_rows": []}}, pid)
    assert reviewed["status"] == "completed"
    fitted = client("data", "fit", {"dataset_id": did}, pid)
    assert fitted["status"] == "completed", fitted
    assert fitted["result"]["source_kind"] == "synthetic"
    assert not fitted["result"]["prediction_gate"]["empirical_validation_established"]
    run = client("simulate", model="rheology", payload={"recipe_id": recipe["recipe_id"], "fit_id": fitted["result"]["fit_id"], "inputs": {}}, project_id=pid)
    assert run["status"] == "error"  # Default display grid includes .1 s^-1, outside calibration.
    run = client("simulate", model="rheology", payload={"recipe_id": recipe["recipe_id"], "fit_id": fitted["result"]["fit_id"], "inputs": {"shear_rates_s": [1,10,100,1000]}}, project_id=pid)
    assert run["status"] == "completed", run
    client("data", "review", {"dataset_id": did, "review": {"status": "rejected", "notes": "Synthetic example excluded", "excluded_source_rows": []}}, pid)
    stale = client("simulate", model="rheology", payload={"recipe_id": recipe["recipe_id"], "fit_id": fitted["result"]["fit_id"], "inputs": {}}, project_id=pid)
    assert stale["status"] == "error"


def test_cost_library_workflow_history_and_no_nested_llm(client, project, monkeypatch):
    from agriformulations.rnd import gpt_agents, gpt_connection, codex_connection
    def forbidden(*args, **kwargs):
        raise AssertionError("Numerical tool invoked a language model")
    monkeypatch.setattr(gpt_agents, "answer", forbidden)
    monkeypatch.setattr(gpt_connection.GPTConnection, "respond", forbidden)
    monkeypatch.setattr(codex_connection.CodexConnection, "respond", forbidden)
    pid, recipe = project
    library = client("recipes", "library_save", {"recipe_id": recipe["recipe_id"]}, pid)
    assert library["status"] == "completed", library
    entries = client("recipes", "library_search", {"query": recipe["name"]})["result"]["entries"]
    assert library["result"] in entries
    annotated = client("recipes", "library_save", {"recipe_id": recipe["recipe_id"], "notes": "Additional source caveat"}, pid)
    assert annotated["result"]["library_id"] != library["result"]["library_id"]
    assert annotated["result"] in client("recipes", "library_search", {"query": recipe["name"]})["result"]["entries"]
    cost = client("cost", payload={"recipe_id": recipe["recipe_id"], "prices": {i["name"]: {"cost_per_kg": 100} for i in recipe["ingredients"]},
        "assumptions": {"currency": "INR", "yield_pct": 100, "processing_per_input_kg": 0, "packaging_per_saleable_kg": 0, "fixed_batch_cost": 0, "overhead_pct": 0, "freight_per_batch": 0, "tax_pct": 0}}, project_id=pid)
    assert cost["status"] == "completed", cost
    assert cost["result"]["result"]["final_cost_per_saleable_kg"] == pytest.approx(100)
    workflow = client("design", "workflow", {"workflow": {"name": "Shared screen", "goal": "Explicit scenarios", "recipe_ids": [recipe["recipe_id"]], "scenarios": [
        {"name": "Settling", "model": "suspension", "inputs": {}}, {"name": "Flow", "model": "rheology", "inputs": {}}]}}, pid)
    assert workflow["status"] == "completed", workflow
    assert workflow["result"]["summary"]["evaluated"] == 2
    assert len(client("project", "history", project_id=pid)["result"]["revisions"]) >= 2
    forked = client("project", "fork", {"name": "Independent revision"}, pid)
    assert forked["project_id"] != pid
    assert client("project", "get", project_id=pid)["result"]["brief"]["name"] != "Independent revision"


def test_json_cli_structured_errors_and_independent_process_storage(tmp_path):
    command = [sys.executable, "-I", "-m", "agri_tool", "--workspace", str(tmp_path / "cli")]
    bad = subprocess.run(command, input="{", capture_output=True, text=True, timeout=20)
    assert json.loads(bad.stdout)["status"] == "error"
    created = subprocess.run(command, input=json.dumps({"operation": "project", "action": "create", "payload": {"name": "Persisted across processes"}}), capture_output=True, text=True, timeout=20)
    response = json.loads(created.stdout)
    loaded = subprocess.run(command, input=json.dumps({"operation": "project", "project_id": response["project_id"]}), capture_output=True, text=True, timeout=20)
    assert json.loads(loaded.stdout)["result"]["brief"]["name"] == "Persisted across processes"
