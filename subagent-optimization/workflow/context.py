"""Build explicit task/episode contracts without inference or scientific dispatch.

The host owns source qualification. These projections retain every candidate and
eligible action, factor repeated identities, and never silently truncate evidence.
"""

from copy import deepcopy
from datetime import datetime
import json
import math
from pathlib import Path

from pilot.bridge import JOB_NAME, require_property_models
from pilot.property_assessment import PlatformPropertyAssessor
from workflow.session import digest


GENERIC_SMILES_WARNING = (
    "SMILES: smiles semantics are not verified by the generic CSV parser."
)


def from_property_protocol(protocol, assignment_id, artifact_directory, limits):
    """Translate an already qualified property protocol; perform no DB/file writes."""
    if not isinstance(assignment_id, str) or not assignment_id.strip():
        raise ValueError("Explicit assignment identity required")
    protocol = deepcopy(protocol)
    parameters = require_property_models(protocol.get("generation_parameters"))
    expected = {
        "global_models": [
            {"name": "Lipophilicity", "min_threshold": 0, "max_threshold": 3}
        ]
    }
    if parameters != expected:
        raise ValueError(
            "This workflow requires the selected Lipophilicity score range 0–3"
        )
    assessor = deepcopy(protocol["assessor"])
    PlatformPropertyAssessor(assessor).baseline_check()
    reference = deepcopy(protocol["reference"])
    if any(
        reference[k] != assessor["reference"][k]
        for k in ("id", "form_id", "representation")
    ):
        raise ValueError("Assessor and task original reference differ")
    if assessor["target_min"] != 0 or assessor["target_max"] != 3:
        raise ValueError("Assessor and selected property range differ")
    for key, minimum in (("max_scientific_submissions", 0), ("max_episodes", 1)):
        if type(limits.get(key)) is not int or limits[key] < minimum:
            raise ValueError("Explicit cumulative submission/episode limits required")
    if datetime.fromisoformat(limits["deadline_utc"]).tzinfo is None:
        raise ValueError("Timezone-aware deadline required")
    baseline = assessor["baseline"]
    objective = {
        "target_min": 0,
        "target_max": 3,
        "qed_min_exclusive": baseline["qed"],
        "similarity_min_exclusive": 0.7,
        "generation_parameters": parameters,
        "physical_units": "provider_score_unverified",
        "model_revision": "unverified",
    }
    version = assessor["rdkit_version"]
    signatures = {
        "lipophilicity": {
            "unit": "provider_score_unverified",
            "method": "Boltzmann Lipophilicity",
            "method_version": "unverified",
            "context": "raw platform score; physical units/model revision unverified",
            "kind": "predicted",
        },
        "qed": {
            "unit": "dimensionless",
            "method": "RDKit QED",
            "method_version": version,
            "context": "Exact molecular form; original reference QED retained unrounded",
            "kind": "predicted",
        },
        "lead_similarity": {
            "unit": "dimensionless",
            "method": "sparse Morgan count radius2 Tanimoto to original reference",
            "method_version": version,
            "context": "Original reference form " + reference["form_id"],
            "kind": "predicted",
        },
    }
    libraries = deepcopy(protocol["libraries"])
    approvals = protocol.get("partial_validation_approvals", [])
    for library in libraries:
        matching = [
            a
            for a in approvals
            if a.get("library_id") == library["id"]
            and a.get("library_content_sha256") == library["content_sha256"]
        ]
        library["approved_generic_smiles_warning"] = bool(
            len(matching) == 1
            and matching[0].get("approved") is True
            and matching[0].get("only_warning") == GENERIC_SMILES_WARNING
        )
    source = "Frozen original-reference evidence supplied by property protocol; caller owns source qualification"
    starting = {k: reference[k] for k in ("id", "form_id", "representation")}
    starting["source"] = reference.get("source") or source
    initial = [
        {
            "id": "baseline-" + endpoint,
            "candidate_id": reference["id"],
            "form_id": reference["form_id"],
            "endpoint": endpoint,
            "value": baseline[endpoint],
            "qualifier": "=",
            "status": "completed",
            **signatures[endpoint],
            "source": source,
        }
        for endpoint in ("lipophilicity", "qed", "lead_similarity")
    ]
    constraints = [
        {
            "id": "constraint-" + endpoint,
            "endpoint": endpoint,
            **signatures[endpoint],
            "minimum": lo,
            **({"maximum": hi} if hi is not None else {}),
        }
        for endpoint, lo, hi in (
            ("lipophilicity", 0, 3),
            ("qed", math.nextafter(baseline["qed"], math.inf), None),
            ("lead_similarity", math.nextafter(0.7, math.inf), None),
        )
    ]
    task_objective = {
        "id": "approach-property-interval",
        "endpoint": "lipophilicity",
        **signatures["lipophilicity"],
        "baseline_id": reference["id"],
        "direction": "range",
        "target_min": 0,
        "target_max": 3,
        "support": "later_assessment",
        "support_evidence": "Returned provider scores; internal property-feedback optimization remains unverified",
    }
    task = {
        "schema_version": 1,
        "id": "task-" + digest(assignment_id)[:24],
        "version": "smallmol-optimization-v1",
        "question": "Find valid distinct nonreference candidates jointly satisfying the property, QED and original-reference similarity rules.",
        "context": "Computational provider-score development task; no physical-property or experimental improvement claim.",
        "sources": [source],
        "starting_candidates": [starting],
        "initial_observations": initial,
        "objectives": [task_objective],
        "constraints": constraints,
        "allowed_jobs": [JOB_NAME],
        "candidate_scope": {"mode": "analogues"},
        "budgets": {
            "scientific_submission_attempts": limits["max_scientific_submissions"]
        },
        "evaluation": {
            "kind": "search_score",
            "protocol": "Same-candidate joint constraints; independent calculation is not an independent predictor",
            "source_version": "smallmol-optimization-v1;provider-revision-unverified",
            "objectives": [deepcopy(task_objective)],
            "constraints": deepcopy(constraints),
        },
    }
    spec = {
        "assignment_id": assignment_id,
        "campaign_id": "campaign-" + digest(assignment_id)[:24],
        "reference": reference,
        "objective": objective,
        "assessor": assessor,
        "libraries": libraries,
        "limits": deepcopy(limits),
        "artifact_directory": str(Path(artifact_directory).expanduser().resolve()),
        "observation_signatures": signatures,
        "source_protocol_digest": digest(protocol),
        "shared_reference_qualification_effort": deepcopy(
            protocol.get("reference_qualification_effort", {"status": "not supplied"})
        ),
    }
    return spec, task


def _action_projection(action):
    """Retain planning facts without copying raw private signed-link receipts."""
    result = {
        k: deepcopy(action[k])
        for k in ("action_key", "parent_id", "library_id", "state", "created")
        if k in action
    }
    result["request_digest"] = digest(action.get("request", {}))
    if action.get("assessment"):
        result["assessment"] = deepcopy(action["assessment"])
    result["receipt_kinds"] = [r["kind"] for r in action.get("receipts", [])]
    if action.get("submit", {}).get("doc_id"):
        result["doc_id"] = action["submit"]["doc_id"]
    diagnostics = []
    for receipt in action.get("receipts", []):
        value = receipt.get("value", {})
        if not isinstance(value, dict):
            continue
        for key in ("error", "errors", "message", "service_status"):
            if value.get(key) and "http" not in str(value[key]).lower():
                diagnostics.append(
                    {"stage": receipt["kind"], key: deepcopy(value[key])}
                )
    result["diagnostics"] = diagnostics
    return result


def episode_context(session, capability_contract):
    """Start ONE bounded episode and return its complete schema-valid assignment.

    This consumes an episode allowance. Read-only previews should use search_view
    rather than calling this function. All observations remain in the host store.
    """
    if not isinstance(capability_contract, dict) or not capability_contract:
        raise ValueError("Current canonical capability contract required")
    capability_contract = deepcopy(capability_contract)
    if capability_contract.get("execution_mode", "host_mediated") != "host_mediated":
        raise ValueError("This context builder uses explicit host_mediated execution")
    capability_contract["execution_mode"] = "host_mediated"
    report = session.report()
    view = session.search_view()
    actions = session.attempts()
    episode = session.begin_episode()
    parent_options = [
        {
            "candidate_id": row["candidate_id"],
            "form_id": row["form_id"],
            "representation": row["representation"],
            "admissible": row["parent_admissible"],
        }
        for row in view["rows"]
        if row["parent_admissible"]
    ]
    helper = deepcopy(view)
    helper["nonparent_identity_columns"] = [
        "candidate_id",
        "representation",
        "form_id_override",
    ]
    helper["nonparent_form_rule"] = (
        "For candidate-<digest>, absent form_id_override means canonical-isomeric-<same digest>; other identities always include an override"
    )
    helper["nonparent_identities"] = []
    for row in view["rows"]:
        if row["parent_admissible"]:
            continue
        candidate_id = row["candidate_id"]
        expected_form = (
            "canonical-isomeric-" + candidate_id[len("candidate-") :]
            if candidate_id.startswith("candidate-")
            else None
        )
        helper["nonparent_identities"].append(
            [
                candidate_id,
                row["representation"],
                None if row["form_id"] == expected_form else row["form_id"],
            ]
        )
    source_candidates = {c["candidate_id"]: c for c in session.candidates()}
    helper["row_columns"] = [
        "status",
        "reason",
        "is_reference",
        "parent_admissible",
        "qualified_candidate",
        "lipophilicity",
        "qed",
        "lead_similarity",
        "lipophilicity_pass",
        "qed_pass",
        "similarity_pass",
        "lipophilicity_gap",
        "qed_gap",
        "similarity_gap",
    ]
    compact_rows = []
    for row in view["rows"]:
        constraints = row.get("constraints", {})
        values = row.get("values", {})
        passes, gaps = constraints.get("passes", {}), constraints.get("gaps", {})
        facts = [
            row.get("status"),
            row.get("reason"),
            row.get("is_reference"),
            row.get("parent_admissible"),
            row.get("qualified_candidate"),
        ]
        facts.extend(values.get(k) for k in ("lipophilicity", "qed", "lead_similarity"))
        facts.extend(passes.get(k) for k in ("lipophilicity", "qed", "lead_similarity"))
        facts.extend(gaps.get(k) for k in ("lipophilicity", "qed", "lead_similarity"))
        compact = {
            "candidate_id": row["candidate_id"],
            "facts": facts,
            "evidence_ids": source_candidates[row["candidate_id"]]["evidence_ids"],
        }
        aliases = [
            a for a in row.get("alias_candidate_ids", []) if a != row["candidate_id"]
        ]
        if aliases:
            compact["alias_candidate_ids"] = aliases
        compact_rows.append(compact)
    helper["rows"] = compact_rows
    helper["eligible_actions"] = [
        {k: a[k] for k in ("action_key", "parent_candidate_id", "library_id")}
        for a in view["eligible_actions"]
    ]
    projected_actions = [_action_projection(a) for a in actions]
    for projected, action in zip(projected_actions, actions):
        artifact = action.get('assessment', {}).get('artifact_sha256')
        if artifact:
            projected['result_evidence'] = {
                'artifact_sha256': artifact,
                'candidate_ids': sorted({o['candidate_id'] for o in report['observations'] if o.get('artifact') == artifact}),
                'interpretation':'Observed products from this parent/library action; not isolated-edit causal effects'}
    helper["scientific_decisions"] = [
        {
            "decision_id": d["id"],
            "question": d["question"],
            "outcome": d["outcome"],
            "action_key": d["next_action"],
            "evidence_ids": deepcopy(d["evidence_ids"]),
            "rationale": d["rationale"],
        }
        for d in report.get("decisions", [])
    ]
    history = "\n".join(d["rationale"] for d in report.get("decisions", []))
    prose_map = []
    for c in report["candidates"]:
        if c["id"] in history:
            prose_map.append({"canonical_label": c["id"], "candidate_id": c["id"]})
        if c["form_id"] in history:
            prose_map.append({"canonical_label": c["form_id"], "form_id": c["form_id"]})
    for o in report["observations"]:
        if o["id"] in history:
            prose_map.append({"canonical_label": o["id"], "evidence_ids": [o["id"]]})
    for a in actions:
        if a["action_key"] in history:
            prose_map.append(
                {"canonical_label": a["action_key"], "action_key": a["action_key"]}
            )
    helper["historical_prose_reference_map"] = prose_map
    helper["attempted_actions"] = [
        {"action_key": a["action_key"], "state": a["state"]} for a in actions
    ]
    helper["intake_batches"] = []
    for intake in sorted(
        Path(session.spec["artifact_directory"]).glob("intake-*.json")
    ):
        if intake.is_symlink():
            raise ValueError("Intake diagnostics must be regular host artifacts")
        record = json.loads(intake.read_text())
        helper["intake_batches"].append(
            {
                "diagnostics": record["diagnostics"],
                "source_digest": digest(record["provenance"]),
            }
        )
    helper["projection"] = {
        "all_candidate_rows_retained": True,
        "all_eligible_actions_retained": True,
        "row_encoding": "facts values correspond exactly to row_columns; absent calculated values are null; full evidence IDs occur once per candidate",
        "candidate_identity_location": "parent_options for admissible parents; nonparent_identities for every other candidate",
        "library_identity_location": "library_options",
        "canonical_form_omission": "Derived graph identity remains host-checked; exact supplied representations and losslessly encoded form IDs retained in identity tables",
        "action_alias_omission": "action_id aliases action_key; repeated parent/form/representation and library SHA factored into identity tables",
        "private_receipt_boundary": "Raw connector receipts remain in the host DB; hashes, receipt kinds, job IDs and planning diagnostics retained here",
    }
    pending = []
    for action in actions:
        if action["state"] in {"complete", "failed", "upload_blocked"}:
            continue
        job = {
            "job_name": JOB_NAME,
            "status": action["state"],
            "receipt_id": action["action_key"],
        }
        if action.get("submit", {}).get("doc_id"):
            job["doc_id"] = action["submit"]["doc_id"]
        pending.append(job)
    assignment = {
        "schema_version": 1,
        "assignment_id": session.assignment_id,
        "campaign_id": session.campaign_id,
        "episode_id": session.assignment_id + ":episode:" + str(episode),
        "task_digest": report["task_digest"],
        "evidence_snapshot_digest": digest(report),
        "objective_config_digest": digest(session.spec["objective"]),
        "task": deepcopy(report["task"]),
        "capability_contract": deepcopy(capability_contract),
        "helper_summaries": helper,
        "parent_options": parent_options,
        "library_options": [
            {
                "library_id": lib["id"],
                "content_sha256": lib["content_sha256"],
                "local_path": lib["csv_path"],
                "admitted": True,
            }
            for lib in session.spec["libraries"]
        ],
        "prior_actions": projected_actions,
        "pending_jobs": pending,
        "resources": {
            "limits": deepcopy(session.spec["limits"]),
            "episodes_started": episode,
            "scientific_submission_allowance_this_episode": (
                min(
                    1,
                    max(
                        0,
                        session.spec["limits"]["max_scientific_submissions"]
                        - len(actions),
                    ),
                )
                if capability_contract.get("execution_mode") == "host_mediated"
                and not pending
                and not view.get("evaluation_blockers")
                and not view.get("qualified_candidate_ids")
                and not view.get("assignment_frozen")
                else 0
            ),
            "reserved_scientific_actions": len(actions),
            "remaining_scientific_submissions": max(
                0, session.spec["limits"]["max_scientific_submissions"] - len(actions)
            ),
            "scientific_submission_intents": sum(
                any(r["kind"] == "submit_intent" for r in a["receipts"])
                for a in actions
            ),
            "recorded_usage": deepcopy(report["resource_summary"]),
            "shared_reference_qualification_effort": deepcopy(
                session.spec.get(
                    "shared_reference_qualification_effort", {"status": "not supplied"}
                )
            ),
            "internal_backend_oracle_work": "unknown",
        },
        "limitations": list(view["limitations"])
        + [
            "Environment checks are advisory; host dispatch admission enforces the declared controllable limits"
        ],
    }
    assignment["input_digest"] = digest(assignment)
    from jsonschema import Draft202012Validator

    schema = (
        Path(__file__).resolve().parents[1]
        / "specialist/optimization-v1/assignment.schema.json"
    )
    Draft202012Validator(json.loads(schema.read_text())).validate(assignment)
    return assignment
