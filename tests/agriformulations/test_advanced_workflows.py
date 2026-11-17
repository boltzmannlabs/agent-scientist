"""End-to-end coverage of compact authoring, coupled development and evidence workflows."""
from copy import deepcopy
import json
import base64
import math
import pytest
import zipfile

from agri_tool.service import execute
from agri_tool.catalogue import DETAILS, EXAMPLE_RECIPE
from agri_tool.storage import Store


def test_compact_complete_request_and_coupled_product_development_preserve_all_actives(tmp_path):
    root = tmp_path / "workspace"
    created = execute({"operation": "project", "action": "create", "payload": {"name": "Research source"}}, root)
    source = created["project_id"]
    compact = deepcopy(DETAILS["design"]["complete"]["payload"])
    result = execute({"operation": "design", "action": "complete", "project_id": source, "payload": compact}, root)
    assert result["status"] == "completed", result
    assert result["result"]["delivery"] == {"requested_recipes": 2, "saved_recipes": 2, "requested_cases": 2, "saved_cases": 2}
    for r in result["result"]["recipes"]:
        assert abs(sum(i["pct"] for i in r["ingredients"]) - 100) < 1e-8
        assert abs(r["active_fraction"] - .2) < 1e-10
    brief = deepcopy(Store(root).load(source)["document"]["brief"])
    brief["count"] = 2
    brief["ingredients"][1].update(min_pct=1, max_pct=5)
    brief["ingredients"][-1].update(min_pct=70, max_pct=80)
    payload = deepcopy(DETAILS["design"]["develop"]["payload"])
    payload.update(brief=brief, rationale="Synthetic coupled workflow", assumptions=["Declared numerical scenarios only"])
    payload["scenarios"][0]["active_name"] = "Tebuconazole technical"
    development = execute({"operation": "design", "action": "develop", "project_id": source, "payload": payload}, root)
    assert development["status"] == "completed", development
    assert development["project_id"] != source
    records = development["result"]["scenarios"]
    assert len(records) == 6
    assert len({r["scenario_id"] for r in records}) == len(records)
    for record in records:
        loaded = execute({"operation": "project", "action": "result", "project_id": development["project_id"], "payload": {"id": record["scenario_id"]}}, root)
        assert loaded["result"]["record"]["recipe_id"] == record["recipe_id"]
    for dose in [r for r in records if r["kind"] == "dosage"]:
        assert dose["inputs"]["storage_retained_fraction"] == pytest.approx(math.exp(-.001 * 30), rel=1e-12)
    assert len(Store(root).load(source)["document"]["recipes"]) == 2
    assert "design_model" not in json.dumps(development["result"])
    exported = execute({"operation": "project", "action": "export", "project_id": development["project_id"]}, root)
    assert exported["status"] == "completed", exported
    with zipfile.ZipFile(next(a["path"] for a in exported["artifacts"] if a["media_type"] == "application/zip")) as archive:
        assert len([name for name in archive.namelist() if name.startswith("scientific_results/") and name.endswith(".png")]) == len(records)


def test_metadata_search_review_citations_and_offline_failure_remain_explicit(tmp_path, monkeypatch):
    from agriformulations.rnd import research
    root = tmp_path / "workspace"
    pid = execute({"operation": "project", "action": "create", "payload": {"name": "Evidence"}}, root)["project_id"]
    def source(params):
        return [{"kind": "literature", "provider": "Test provider", "doi": "10.0000/test", "title": "Synthetic metadata fixture",
            "url": "https://example.org/fixture", "year": 2026, "abstract": "Fixture text, not a real scientific source", "authors": ["Fixture Author"]}], {"provider": "Test provider"}
    monkeypatch.setattr(research, "crossref", source)
    monkeypatch.setattr(research, "europe_pmc", source)
    searched = execute({"operation": "research", "action": "search", "project_id": pid, "payload": {"kind": "literature", "query": "fixture"}}, root)
    assert searched["status"] == "completed", searched
    result = searched["result"]
    payload = {"search_id": result["search_id"], "record_id": result["results"][0]["record_id"], "status": "reviewed", "evidence_stage": "full_text_reviewed"}
    missing = execute({"operation": "research", "action": "save_source", "project_id": pid, "payload": payload}, root)
    assert missing["status"] == "error"
    reviewed = execute({"operation": "research", "action": "save_source", "project_id": pid,
        "payload": {**payload, "notes": "Synthetic API fixture only; no actual full text", "evidence_stage": "abstract_reviewed"}}, root)
    assert reviewed["status"] == "completed"
    cited = execute({"operation": "research", "action": "citations", "project_id": pid}, root)
    assert cited["artifacts"] and cited["result"]["citations"][0]["title"] == "Synthetic metadata fixture"
    def fail(params):
        raise OSError("Scripted offline provider")
    monkeypatch.setattr(research, "crossref", fail)
    monkeypatch.setattr(research, "europe_pmc", fail)
    unavailable = execute({"operation": "research", "action": "search", "project_id": pid, "payload": {"kind": "literature", "query": "fixture"}}, root)
    assert unavailable["status"] == "partial"
    assert unavailable["result"]["status"] == "unavailable" and unavailable["warnings"]


def test_recipe_file_preview_and_release_specifications_are_executable(tmp_path):
    root = tmp_path / "workspace"
    csv = "name,role,pct,purity_pct\nActive,active,20,100\nWater,solvent,80,100\n"
    preview = execute({"operation": "recipes", "action": "preview", "payload": {"file": {"filename": "recipe.csv", "content_base64": base64.b64encode(csv.encode()).decode()}}}, root)
    assert preview["status"] == "completed", preview
    raw = {"name": "Imported hypothesis", "format": "SC", "batch_g": 500, "ingredients": preview["result"]["ingredients"]}
    created = execute({"operation": "recipes", "action": "manual", "payload": {"recipe": raw}}, root)
    assert created["status"] == "completed", created
    simulated = execute({"operation": "simulate", "model": "kinetics", "project_id": created["project_id"], "payload": {"inputs": {"model": "first_order", "rate_per_day": .1,
        "release_specs": [{"day": 5, "min_fraction": .3, "max_fraction": .5}]}}}, root)
    assert simulated["status"] == "completed", simulated
    assert simulated["result"]["result"]["spec_results"][0]["verdict"] == "PASS"


def test_local_learning_preserves_experimental_origin_gate(tmp_path):
    root = tmp_path / "workspace"
    brief = {"name": "Synthetic mixture basis", "active_name": "Tebuconazole", "format": "SC", "active_pct": 20,
        "batch_g": 500, "count": 8, "seed": 42, "ingredients": [
            {"name": "Tebuconazole technical", "role": "active", "purity_pct": 95, "min_pct": 20, "max_pct": 25},
            {"name": "Dispersant A", "role": "dispersant", "purity_pct": 100, "min_pct": 1, "max_pct": 5},
            {"name": "Water", "role": "solvent", "purity_pct": 100, "min_pct": 70, "max_pct": 80}], "process": [{"instruction": "Synthetic shared process"}]}
    created = execute({"operation": "recipes", "action": "create", "payload": {"brief": brief}}, root)
    assert created["status"] == "completed", created
    measurements = [{"recipe_id": r["recipe_id"], "batch_id": "B1", "value": r["ingredients"][1]["fraction"] * 1000} for r in created["result"]["recipes"]]
    result = execute({"operation": "data", "action": "learn", "project_id": created["project_id"], "payload": {"measurements": measurements, "source_kind": "synthetic"}}, root)
    assert result["status"] == "completed", result
    assert not result["result"]["utility_pass"] and not result["result"]["empirical_validation_established"]
    assert all(p["prediction"] is None for p in result["result"]["predictions"])
