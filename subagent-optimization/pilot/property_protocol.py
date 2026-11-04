"""Freeze a platform Lipophilicity objective without inference or remote calls."""
from copy import deepcopy
import csv
import math
from pathlib import Path

from rdkit import Chem, rdBase
from rdkit.Chem import QED

from pilot.protocol import (DEFAULT_MODEL_PATH, DEFAULT_STUDY_DIR, DEFAULT_TASK_DIR,
                            LEAD_SHA256, _json, _require, _sha, build_protocol)

DEFAULT_QUALIFICATION_DIR = Path(
    "/home/boltzmann13/.local/state/smallmol-pilot/"
    "lipophilicity-qualification-20261103T121334792919Z")
GENERATION_PARAMETERS = {"global_models": [
    {"name": "Lipophilicity", "min_threshold": 0, "max_threshold": 3}]}
PROPERTY_KIND = "platform_lipophilicity_rdkit_v1"
BASELINE_ARTIFACT_SHA256 = "9563958118a785d7370322614c3b023c3bc47925c1f57e79b7170ea95ddd68fc"
GENERIC_SMILES_WARNING = "SMILES: smiles semantics are not verified by the generic CSV parser."


def _single_row(path):
    _sha(path)
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        _require(reader.fieldnames is not None and len(reader.fieldnames) == len(set(reader.fieldnames)),
                 "Explicit unique baseline CSV columns required")
        rows = list(reader)
    _require(len(rows) == 1 and None not in rows[0], "Baseline must contain exactly one complete row")
    return rows[0]


def _form(text):
    _require(isinstance(text, str) and text.strip(), "Baseline molecular representation required")
    mol = Chem.MolFromSmiles(text)
    _require(mol is not None, "Baseline molecular representation is invalid")
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True), mol


def build_property_protocol(task_dir=DEFAULT_TASK_DIR, study_dir=DEFAULT_STUDY_DIR,
                            model_path=DEFAULT_MODEL_PATH, generation_parameters=None,
                            baseline_record_path=DEFAULT_QUALIFICATION_DIR / "verified-reference.json",
                            qualification_path=DEFAULT_QUALIFICATION_DIR / "qualification.json"):
    """Return JSON-ready protocol; freeze before new candidate outcomes.

    Selection must match the explicit user-selected model/bounds. The legacy
    builder supplies structural/library admission only; its evaluator, active
    scoring pins, rules and interpretation are replaced. No classifier executes.
    """
    _require(generation_parameters == GENERATION_PARAMETERS,
             "Explicit exact Lipophilicity model selection and range 0–3 are required")
    protocol = build_protocol(task_dir, study_dir, model_path,
                              generation_parameters=deepcopy(generation_parameters))
    old_assessor = protocol["assessor"]
    baseline_record_path, qualification_path = (Path(p).resolve()
                                                 for p in (baseline_record_path, qualification_path))
    verified, qualification = _json(baseline_record_path), _json(qualification_path)
    _require(verified.get("job_name") == qualification.get("job_name") == "Property_Prediction"
             and qualification.get("status") == "reference_verified", "Completed property qualification required")
    doc_id = verified.get("doc_id")
    _require(isinstance(doc_id, str) and doc_id
             and qualification.get("submit", {}).get("doc_id") == doc_id
             and qualification.get("last_monitor", {}).get("doc_id") == doc_id
             and str(qualification["last_monitor"].get("status", "")).lower() in {"success", "completed"},
             "Baseline receipts disagree or do not establish completion")
    _require(qualification.get("source_reference") == protocol["reference"]
             and qualification.get("source_reference_sha256") == LEAD_SHA256
             and verified.get("reference_identity_verified") is True, "Property reference/form changed")
    _require(qualification.get("optimization_parameters_for_later") == GENERATION_PARAMETERS,
             "Qualified optimization model/range changed")
    _require(qualification.get("property_prediction_parameters") == {
        "global_models": ["Lipophilicity"], "uncertainty": 0, "explainability": 0},
        "Reference prediction uses another property selection")
    expected_target = {"property": "Lipophilicity", "minimum": 0, "maximum": 3,
                       "units": "platform-reported model score; physical unit not yet verified"}
    _require(verified.get("target") == qualification.get("optimization_target_selected_by_user") == expected_target,
             "Qualified target differs from the selected model-score range")
    _require(verified.get("physical_units_verified") is False
             and verified.get("model_weight_revision_verified") is False,
             "Requalify changed model/unit evidence explicitly")
    inputs = Path(qualification["input_csv"])
    outputs = qualification.get("download", {}).get("output_paths", [])
    _require(len(outputs) == 1, "A single downloaded baseline artifact is required")
    artifact = Path(outputs[0])
    _require(_sha(inputs) == qualification.get("input_csv_sha256"), "Baseline input bytes changed")
    _require(_sha(artifact) == verified.get("artifact_sha256") == BASELINE_ARTIFACT_SHA256
             == qualification.get("verified_reference", {}).get("artifact_sha256"),
             "Baseline output artifact identity changed")
    source_row, result_row = _single_row(inputs), _single_row(artifact)
    reference_form, reference_mol = _form(protocol["reference"]["representation"])
    _require(_form(source_row.get("SMILES"))[0] == _form(result_row.get("SMILES"))[0] == reference_form,
             "Actual baseline CSV structures differ from the original reference")
    _require(verified.get("returned_rows") == 1 and verified.get("property_column") == "Lipophilicity"
             and list(result_row) == verified.get("output_columns"), "Baseline output schema changed")
    value = float(result_row["Lipophilicity"])
    _require(math.isfinite(value) and value == verified.get("reported_model_score") == -8.72
             and result_row["Lipophilicity"] == verified.get("reported_text"), "Baseline model score changed")
    qed = QED.qed(reference_mol)
    _require(qed == old_assessor["baseline"]["qed"] == 0.800452829768805,
             "Original local QED baseline no longer reproduces")
    approval = qualification.get("partial_validation_approval", {})
    _require(approval.get("approved") is True and approval.get("only_warning") == GENERIC_SMILES_WARNING,
             "Concrete user approval for the generic CSV warning is absent")

    bundle = Path(__file__).resolve().parents[1]
    for path in (old_assessor["scorer_path"], old_assessor["model_path"],
                 str(Path(task_dir).resolve() / "baseline.json"),
                 str(Path(task_dir).resolve() / "source-manifest.json")):
        protocol["source_artifact_sha256"].pop(path, None)
    for path in (baseline_record_path, qualification_path, inputs, artifact,
                 Path(__file__), bundle / "pilot/protocol.py", bundle / "pilot/assessment.py",
                 bundle / "pilot/property_assessment.py"):
        protocol["source_artifact_sha256"][str(path)] = _sha(path)
    baseline = {"lipophilicity": value, "qed": qed, "lead_similarity": 1.0}
    protocol.update({
        "protocol_name": "lipophilicity-library-decision-pilot-v1",
        "scope": "Fresh bounded task-guided Lipophilicity model-score decision pilot; not unrestricted Agent Scientist or experimental discovery",
        "assessor": {"kind": PROPERTY_KIND, "reference": deepcopy(protocol["reference"]),
                     "baseline": baseline, "property_column": "Lipophilicity", "target_min": 0, "target_max": 3,
                     "rdkit_version": rdBase.rdkitVersion,
                     "implementation_sha256": _sha(bundle / "pilot/property_assessment.py"),
                     "identity_implementation_sha256": _sha(bundle / "pilot/assessment.py"),
                     "baseline_artifact_sha256": BASELINE_ARTIFACT_SHA256},
        "rules": {"objectives": [
            {"metric": "lipophilicity", "operator": "between_inclusive", "minimum": 0, "maximum": 3},
            {"metric": "qed", "operator": "gt", "threshold": qed}],
            "constraints": [{"metric": "lead_similarity", "operator": "gt", "threshold": 0.7}],
            "joint_on_same_candidate": True, "valid_distinct_nonbaseline_required": True,
            "weighted_score_substitution": False},
        "property_qualification": {
            "job_name": "Property_Prediction", "doc_id": doc_id,
            "verified_reference_path": str(baseline_record_path), "qualification_path": str(qualification_path),
            "artifact_path": str(artifact), "artifact_sha256": BASELINE_ARTIFACT_SHA256,
            "reported_reference_model_score": value, "physical_units_verified": False,
            "model_weight_revision_verified": False, "reference_already_in_target_range": False,
            "baseline_only": True, "predictor_independent_of_generator": False,
            "interpretation": "One completed provider prediction for the exact reference; no optimization or specialist gain established"},
        "reference_qualification_effort": {
            "scientific_submissions": 1, "returned_reference_rows": 1,
            "selected_property_models": ["Lipophilicity"],
            "attribution": "Physically executed once; same reference evidence attributed to every arm",
            "internal_compute_and_credits": "Unknown here; native billing receipt retained privately"},
        "partial_validation_approvals": [
            {"library_id": lib["id"], "library_content_sha256": lib["content_sha256"],
             "approved": True, "only_warning": GENERIC_SMILES_WARNING,
             "scope": "This exact generic CSV warning only; structures audited separately; other warnings/errors not approved"}
            for lib in protocol["libraries"]],
        "scientific_guidance": protocol["scientific_guidance"] + (
            " This objective uses the provider's Lipophilicity model-score range [0,3] inclusive, "
            "strict local QED improvement and reference similarity >0.7 jointly. "
            "DRD2 activity is not an objective. Physical units and model revision are unverified. "
            "Do not substitute RDKit logP or infer experimental lipophilicity."),
        "evaluator_independence": "Independent assessment code checks supplied provider predictions, identity, local QED and similarity; it is not an independent predictor or experiment",
        "context_limits": {"maximum_assignment_chars": 262144,
                           "on_excess": "block_without_truncation",
                           "basis": "Prospective bounded assignment-data allowance, identical for all arms; all candidate evidence retained",
                           "is_token_or_compute_budget": False},
        "history": {"previous_attempts": "Original model-free/DRD2 attempts preserved separately; not resumed or reinterpreted",
                    "read_only_account_lookup": "No experiments found for this user and job_name",
                    "lookup_interpretation": "No invented IDs, inferred job outcomes or resubmissions follow from this lookup"},
        "interpretation": "Computational model-score development pilot on one public lead and known libraries; no measured property, protected holdout, verified model revision, independent-predictor validation, general specialist superiority or causal gain claim",
    })
    return protocol
