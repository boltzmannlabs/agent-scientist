"""Read and check immutable inputs for a fresh conditional decision pilot.

No candidate scoring, model decoding, service authorization or campaign writes.
The run owner persists the returned JSON before collecting generated outcomes.
"""
from __future__ import annotations
from copy import deepcopy
import hashlib
import json
from pathlib import Path

import numpy as np
from rdkit import rdBase
from prototype.library_audit.audit import audit_bytes, normalization_policy_id
from prototype.library_options.material import digest
from pilot.bridge import require_property_models

MODEL_SHA256 = "0878479f24da0c09ad85a6fc4b992faeb02ec426465c7f79008e969da4e40f76"
SCORER_SHA256 = "71855efd492c8af40f96f8a7ffcd271083087a55081887a51ca66d628c35765c"
LEAD_SHA256 = "46b6a09d344b2bd9c69a8df152fc5bfe30006b590a3014a2333ca2a16e2ccb39"
DEFAULT_TASK_DIR = Path("/home/boltzmann13/science-environments/environments/small-molecule-lead-optimization/tasks/drd2")
DEFAULT_STUDY_DIR = Path(__file__).resolve().parents[1] / "research/library-alternatives/run-v1"
DEFAULT_MODEL_PATH = Path("/home/boltzmann13/.cache/science-environments/drd2/a0622fc2fe16812c7530bca20dcca9a9fd874513/support/drd2.pkl")
TOOL_SOURCE_ROOT = Path("/home/boltzmann13/BOLTCHEM-FEATURES/v5/Molecule Optimzation/crem")
ARMS = ["base", "base_algorithm", "base_algorithm_specialist"]


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(path):
    path = Path(path)
    _require(path.is_file() and not path.is_symlink(), "Regular artifact required: " + str(path))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json(path):
    def nonfinite(value):
        raise ValueError("Non-finite JSON constant: " + value)
    result = json.loads(Path(path).read_text(), parse_constant=nonfinite)
    _require(isinstance(result, dict), "Object artifact required: " + str(path))
    return result


def build_protocol(task_dir=DEFAULT_TASK_DIR, study_dir=DEFAULT_STUDY_DIR,
                   model_path=DEFAULT_MODEL_PATH, generation_parameters=None):
    """Return a deterministic JSON-ready specification; caller freezes it to disk.

    The one-follow-up horizon defines this study, not a general tool budget.
    Paths are explicit public-source dependency references, not credentials.
    """
    parameters = require_property_models(generation_parameters)
    task_dir, study_dir, model_path = (Path(p).resolve() for p in (task_dir, study_dir, model_path))
    manifest = _json(task_dir / "source-manifest.json")
    lead = _json(task_dir / "lead.json")
    prior = _json(task_dir / "baseline.json")
    curation = _json(study_dir / "curation.json")
    material = _json(study_dir / "material.json")
    index = _json(study_dir / "lookup-index.json")
    study_validation = _json(study_dir / "validation.json")
    cohort_protocol = study_dir.parent / "protocol-v1.json"
    # Bind the content of the index itself, not only its pointer to material.
    # The study owner remains the trust boundary; hashes do not authenticate it.
    for path in (study_dir / "curation.json", study_dir / "material.json",
                 study_dir / "lookup-index.json", cohort_protocol):
        expected = [value for name, value in study_validation["artifact_sha256"].items()
                    if Path(name).name == path.name]
        _require(len(expected) == 1 and _sha(path) == expected[0], "Study artifact hash mismatch: " + path.name)
    _require(_sha(task_dir / "lead.json") == LEAD_SHA256, "Original lead/form changed")
    _require(_sha(task_dir / "score.py") == SCORER_SHA256, "Pinned task scorer changed")
    _require(_sha(model_path) == MODEL_SHA256, "Pinned model bytes changed")
    _require(manifest["source_model"]["sha256"] == prior["model_sha256"] == MODEL_SHA256,
             "Model provenance disagrees")
    for name in ("lead.json", "score.py", "baseline.json"):
        _require(_sha(task_dir / name) == manifest["task_files"][name]["sha256"],
                 "Task artifact differs from source manifest: " + name)
    method = "drd2-task-assessment-v1;rdkit=" + rdBase.rdkitVersion + ";numpy=" + np.__version__
    _require(method == manifest["runtime"]["method_version"] == prior["method_version"],
             "Scoring runtime differs from the qualified baseline")
    rows = prior.get("summaries", [])
    _require(len(rows) == 1 and rows[0]["candidate_id"] == lead["id"] and rows[0]["status"] == "completed",
             "Ambiguous baseline record")
    baseline = {k: rows[0]["values"][k] for k in ("drd2_p_active", "qed", "lead_similarity")}
    _require(baseline["lead_similarity"] == 1.0, "Baseline similarity changed")
    _require(material["lead"] == lead and material["lead_file_sha256"] == LEAD_SHA256,
             "Structural material uses a different original reference/form")
    _require(material["curation_sha256"] == _sha(study_dir / "curation.json"), "Curation binding changed")
    _require(index["material_report_sha256"] == _sha(study_dir / "material.json"), "Material binding changed")
    _require(_sha(cohort_protocol) == curation["protocol_sha256"]
             == curation["acquisition"]["protocol_sha256_before_acquisition"], "Acquisition protocol binding changed")
    _require(material["rdkit_version"] == rdBase.rdkitVersion
             and curation["normalization_policy_id"] == normalization_policy_id(), "Structure runtime policy changed")
    _require(index["schema_version"] == 1 and index["basis"]["lead_sha256"] == LEAD_SHA256,
             "Lookup index reference/version changed")
    _require(index["basis"]["rdkit_version"] == rdBase.rdkitVersion
             and index["basis"]["normalization_policy_id"] == normalization_policy_id()
             and index["basis"]["preparation_and_lookup_source"] == material["source_sha256"],
             "Lookup preparation policy changed")
    _require(index["scope_id"] == digest(index["basis"]), "Lookup scope digest disagrees")
    for rel, expected in material["source_sha256"].items():
        _require(_sha(TOOL_SOURCE_ROOT / rel) == expected, "Inspected local tool source changed: " + rel)
    indexed = {lib["id"]: lib for lib in index["libraries"]}
    _require(len(indexed) == len(index["libraries"]), "Duplicate indexed library ID")
    libraries, bins = [], []
    for lib in curation["libraries"]:
        lid, csv_path = lib["id"], study_dir / lib["csv"]
        _require(lid in indexed, "Source library absent from lookup index")
        _require(_sha(csv_path) == lib["intake_audit"]["content_sha256"], "Source CSV bytes changed: " + lid)
        audit = audit_bytes(csv_path.read_bytes())
        _require(audit["normalized_identity_complete"] and not audit["structure_scope_needs_review"],
                 "Incomplete/out-of-scope source structures: " + lid)
        for key in ("content_sha256", "normalized_input_set_sha256", "normalized_sequence_sha256",
                    "normalized_multiset_sha256", "normalization_policy_id", "row_count", "canonical_unique_count"):
            _require(audit[key] == lib["intake_audit"][key], "Recorded source audit changed: " + lid)
        smi_audit = audit_bytes((study_dir / lib["smi"]).read_bytes(), "smi")
        for key in ("normalized_sequence_sha256", "normalized_multiset_sha256"):
            _require(smi_audit[key] == audit[key], "CSV/SMI preparation differs: " + lid)
        for key in ("content_sha256", "normalized_input_set_sha256"):
            _require(indexed[lid][key] == audit[key], "Index/library identity differs: " + lid)
        _require(len(indexed[lid]["lookup_ids"]) == len(set(indexed[lid]["lookup_ids"]))
                 == material["library_material"][lid]["lookup_pair_count"], "Indexed lookup counts differ: " + lid)
        bins.append(lib["source_bins"])
        libraries.append({"id": lid, "csv_path": str(csv_path),
                          "content_sha256": audit["content_sha256"],
                          "normalized_input_set_sha256": audit["normalized_input_set_sha256"],
                          "normalization_policy_id": audit["normalization_policy_id"],
                          "source_count": audit["row_count"],
                          "material_sha256": material["library_material"][lid]["logical_rows_sha256"],
                          "lookup_pair_count": material["library_material"][lid]["lookup_pair_count"],
                          "review_basis": "internal_computational_development_checks",
                          "chemical_effect_or_expert_endorsement": False,
                          "isolated_edit_annotations_available": False})
    _require(set(indexed) == {lib["id"] for lib in libraries} and "mixed_reference" in indexed,
             "Library menu changed or mixed reference absent")
    _require(bool(bins) and all(x == bins[0] for x in bins), "Source size/ring matching changed")
    _require(set(index["lookup_dimensions"]) == set().union(*(set(lib["lookup_ids"]) for lib in index["libraries"])),
             "Lookup dimension coverage differs from menu")
    bundle = Path(__file__).resolve().parents[1]
    specialist_path = bundle / "specialist/definition.json"
    _require(specialist_path.is_file() and not specialist_path.is_symlink(), "Regular specialist definition required")
    specialist_raw = specialist_path.read_bytes()
    specialist = json.loads(specialist_raw)
    _require(isinstance(specialist, dict) and specialist.get("name") == "smallmol-investigation",
             "Unexpected specialist definition/name")
    for field in ("tools", "skills", "skill_files", "children", "sources"):
        _require(isinstance(specialist.get(field), list) and not specialist[field],
                 "Advisory pilot requires an explicit empty specialist grant: " + field)
    for field in ("purpose", "instructions", "output"):
        _require(isinstance(specialist.get(field), str) and specialist[field].strip(),
                 "Nonempty frozen specialist behavior required: " + field)
    for field in ("max_iterations", "timeout_seconds"):
        _require(type(specialist.get(field)) is int and specialist[field] > 0,
                 "Positive integer specialist role limit required: " + field)
    frozen_specialist = {"path": str(specialist_path), "sha256": hashlib.sha256(specialist_raw).hexdigest(),
                         **{field: deepcopy(specialist[field]) for field in
                            ("name", "purpose", "instructions", "output", "tools", "skills", "skill_files", "children", "sources",
                             "max_iterations", "timeout_seconds")}}
    common_guidance = (
        "Choose one remaining library or abstain. Use all supplied observations, including counterexamples, "
        "against the original unrounded baseline and strict constraints. Lookup coverage is not scientific "
        "quality. Do not assert isolated edits, unique sites, causal effects, measured potency or calibrated "
        "uncertainty without evidence. Scientific execution stays with the common host executor; do not alter "
        "the task or submit outside it. The frozen task-specific purpose, instructions and expected "
        "output are supplied identically to all arms through specialist_definition; do not repeat them.")
    hashes = {str(task_dir / name): _sha(task_dir / name)
              for name in ("lead.json", "score.py", "baseline.json", "source-manifest.json")}
    hashes.update({str(study_dir / name): _sha(study_dir / name)
                   for name in ("curation.json", "material.json", "lookup-index.json", "validation.json")})
    hashes[str(cohort_protocol)] = _sha(cohort_protocol)
    hashes[str(specialist_path)] = frozen_specialist["sha256"]
    for dependency in (bundle / "pilot/assessment.py", bundle / "prototype/library_audit/audit.py"):
        hashes[str(dependency)] = _sha(dependency)
    return {
        "schema_version": 1, "protocol_name": "drd2-library-decision-pilot-v1", "task_type": "lead_optimization",
        "scope": "Fresh conditional task-guided main-policy decision pilot after shared observations; not an unrestricted Agent Scientist benchmark",
        "arms": list(ARMS), "initial_library_id": "mixed_reference", "decision_horizon": 1,
        "libraries": libraries, "lookup_index": deepcopy(index), "reference": deepcopy(lead),
        "assessor": {"scorer_path": str(task_dir / "score.py"), "model_path": str(model_path),
                     "lead_path": str(task_dir / "lead.json"), "scorer_sha256": SCORER_SHA256,
                     "model_sha256": MODEL_SHA256, "lead_sha256": LEAD_SHA256,
                     "method_version": method, "baseline": baseline},
        "generation_parameters": parameters,
        "generation": {"job_name": "Fragment_Based_Optimization", "backend": "existing_nodeapi_connector",
                       "property_model_selection_required": True,
                       "model_selection_validation": "Shape only here; existing connector owns schema/file/auth validation",
                       "local_scientific_fallback": False},
        "resources": {"max_unique_candidate_evaluations": None, "max_credits": None,
                      "max_reasoning_calls": None, "max_reasoning_tokens": None, "actual_internal_compute": None,
                      "accounting": "Record requested, actual, estimated and unknown; include parent/child failures"},
        "rules": {"objectives": [{"metric": k, "operator": "gt", "threshold": baseline[k]}
                                  for k in ("drd2_p_active", "qed")],
                  "constraints": [{"metric": "lead_similarity", "operator": "gt", "threshold": 0.7}],
                  "joint_on_same_candidate": True, "valid_distinct_nonbaseline_required": True,
                  "weighted_score_substitution": False},
        "stop_policy": {"shared_initial_success": "no_remaining_decision; no agent comparison exercised",
                        "arm_success": "stop on a distinct candidate satisfying every original rule",
                        "pending_or_unknown_submission": "reconcile original attempt; never replace or resubmit"},
        "initialization_accounting": {"actual_collection": "once-only shared batch",
                                      "per_arm_attribution": "same initial evidence and effort attributed equally",
                                      "physical_and_attributed_totals": "report separately; do not multiply actual common work"},
        "specialist_definition": frozen_specialist,
        "scientific_guidance": common_guidance,
        "arm_treatments": {"base": {"provided_coverage_helper": False, "specialist": False},
                           "base_algorithm": {"provided_coverage_helper": True, "specialist": False},
                           "base_algorithm_specialist": {"provided_coverage_helper": True, "specialist": True}},
        "routing_policy": {"specialist_name": "smallmol-investigation",
                           "eligible": "common batch unfinished and meaningful remaining library choice",
                           "base_algorithm_specialist_requires_native_named_child": True,
                           "missing_invocation": "routing_failure or not_exercised; never silently count main-only fallback",
                           "imported_advice_is_native_execution_proof": False,
                           "natural_prompt_routing_recall": "separate future study; this pilot enforces eligible route",
                           "general_installed_routing_claim": False},
        "comparison_requirements": {"same_scientific_guidance": True, "same_initial_evidence": True,
                                    "same_frozen_specialist_guidance_for_all_arms": True,
                                    "same_tools_and_execution_safeguards": True,
                                    "helper_vs_specialist_same_admissible_information": True,
                                    "model_settings_and_allowances": "register and match before actual model decisions",
                                    "all_parent_child_work_recorded": True, "additional_calls_are_free": False},
        "evidence_kinds": ["fixture", "imported_nodeapi_artifact", "existing_connector_runtime",
                           "imported_policy_decision", "native_agent_runtime"],
        "review_basis": "internal_computational_development_checks; no external expert endorsement",
        "review_limits": "No external SME gate. Existing annotation/library approval flags are unchanged. Unknown edit attribution stays unknown; database membership is not desirable-chemistry endorsement.",
        "source_artifact_sha256": hashes,
        "interpretation": "One public lead and known sources support descriptive development findings only; no protected holdout, training-independence or general specialist-superiority claim.",
    }
