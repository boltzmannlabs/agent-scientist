"""Artificial nonchemical fixtures; not biological sequences, molecules or predictions."""
from copy import deepcopy
from context_contract import build_context, digest


def synthetic_snapshot():
    sig = {"endpoint": "artificial_score", "unit": "arbitrary", "method": "fixture_only",
           "method_version": "fixture-v1", "context": "synthetic_not_science", "kind": "synthetic"}
    objective = {"id": "goal-1", **sig, "baseline_id": "reference", "direction": "maximize",
                 "support": "internal_control", "support_evidence": "fixture://artificial-comparison"}
    constraint = {"id": "gate-1", **sig, "minimum": 0}
    observations = []
    rows = []
    for cid, value in (("reference", 1), ("branch-a", 2), ("branch-b", 0), ("unfocused", 3)):
        obs = {"id": f"obs-{cid}", "candidate_id": cid, "form_id": f"form-{cid}",
               **sig, "status": "completed", "qualifier": "=", "value": value,
               "source": f"fixture://synthetic/{cid}"}
        observations.append(obs)
        identity = {"id": cid, "representation": f"SYNTHETIC_NOT_MOLECULE_{cid}",
                    "form_id": f"form-{cid}", "source": "fixture-only"}
        if cid != "reference":
            identity["parent_id"] = "reference"
        rows.append({"identity": identity,
                     "scope_status": "pass", "objectives": [{"rule_id": "goal-1",
                     "candidate_evidence": {"status": "covered", "matching_observations": [deepcopy(obs)]},
                     "assessment": {"candidate_id": cid, "objective_id": "goal-1",
                                    "status": "pass" if value > 1 else "fail", "improvement": value - 1},
                     "change": "improved" if value > 1 else "unchanged" if value == 1 else "worsened"}],
                     "constraints": [{"rule_id": "gate-1", "candidate_evidence": {
                                      "status": "covered", "matching_observations": [deepcopy(obs)]},
                                      "assessment": {"status": "pass"}}]})
    rules = {"objectives": [objective], "constraints": [constraint]}
    progress = {
        "schema_version": 1, "campaign_id": "synthetic-campaign",
        "task_identity": {"id": "synthetic-task", "version": "development-v1", "digest": digest(rules),
                          "question": "Artificial decision-contract demonstration only"},
        "rules": rules, "baseline_coverage": [{"candidate_id": "reference", "status": "covered"}],
        "candidates": rows, "attempts": [], "warnings": [],
        "decisions": {"latest_recorded": None, "inconclusive_history": []},
        "resource_summary": {"scientific_assessments": {"unknown|campaign": {
            "category": "unknown", "scope": "campaign", "amount": None, "record_ids": ["usage-unknown"]}}},
        "unresolved_usage_commitments": [{"attempt_id": "external-unknown", "amount": None}],
    }
    policy = {
        "allowed_actions": [
            {"id": "review", "kind": "inspect_evidence", "description": "Inspect named existing records"},
            {"id": "assess", "kind": "evaluate_candidates", "description": "Recommend a permitted assessment; do not execute"},
            {"id": "ask", "kind": "clarify", "description": "Ask for missing task information"},
            {"id": "finish", "kind": "stop", "description": "Return control under task stopping rules"},
        ],
        "reference_candidate_ids": ["reference"],
        "termination": {"state": "continue", "reason": "Synthetic development fixture",
                        "source": "fixture://reviewed-policy"},
        "resource_policy": "No synthetic numerical caps; unknown usage remains unknown.",
    }
    return {"progress": progress, "observations": observations, "policy": policy}


def canned_recommendation(context):
    return {
        "schema_version": 1, "decision_id": "synthetic-decision-1",
        "campaign_id": context["campaign_id"], "task_digest": context["task_identity"]["digest"],
        "snapshot_digest": context["snapshot_digest"], "rules_digest": context["rules_digest"],
        "action_id": "assess", "candidate_ids": ["branch-a"], "evidence_ids": ["obs-branch-a"],
        "scientific_question": "Can a subsequent permitted observation resolve the artificial branch question?",
        "rationale": "Canned fixture rationale; no model made this decision.",
        "assumptions": ["All values and representations are artificial, not scientific evidence."],
        "expected_information": "An artificial observation to exercise the handoff contract.", "stop_reason": "",
        "outcome_claim": "not_assessed",
    }


def fixture_triplet():
    snapshot = synthetic_snapshot()
    context = build_context(snapshot, ["branch-a", "branch-b"])
    return snapshot, context, canned_recommendation(context)


def sync_artificial_projection(snapshot, observation_id):
    """Keep deliberately changed fixture metadata consistent; no scientific scoring."""
    full = next(r for r in snapshot["observations"] if r["id"] == observation_id)
    for candidate in snapshot["progress"]["candidates"]:
        for group in ("objectives", "constraints"):
            for item in candidate[group]:
                refs = item["candidate_evidence"].get("matching_observations", [])
                for ref in refs:
                    if ref["id"] == observation_id:
                        for field in ("status", "qualifier", "value"):
                            ref[field] = full[field]
                        if full["status"] != "completed" or full["qualifier"] != "=" or full["value"] is None:
                            item["candidate_evidence"]["status"] = "unresolved"
                            item["assessment"]["status"] = "unresolved"
