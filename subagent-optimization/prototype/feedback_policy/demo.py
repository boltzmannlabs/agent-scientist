"""Print an artificial offline rehearsal. Never submits a scientific request."""
import json

from feedback_policy import classify_batch, decide, select_panel, summarize_final
from fixtures import action, candidate, config, panel_rows, snapshot


def main():
    settings = config()
    cards = [action("crem"), action("graph_ga")]
    cases = {
        "feasible_lead_no_new_candidates": snapshot(),
        "measured_solubility_deficit": snapshot([
            candidate(), candidate("FIXTURE_SOL_FAILURE", role="generated", sol=-6)]),
        "missing_parent_evidence": snapshot([candidate(sol=None)]),
        "pending_existing_job": snapshot(),
    }
    cases["pending_existing_job"]["jobs"] = [{"id": "fixture-job", "status": "pending"}]
    result = {"fixture_only": True, "scientific_execution": "none", "decisions": {}}
    for name, state in cases.items():
        decision = decide(state, cards + [action("assess")], settings)
        result["decisions"][name] = {
            "disposition": decision["disposition"], "reason": decision["reason"],
            "route": decision["chosen"]["route"] if decision["chosen"] else None,
            "rationale": decision.get("rationale"),
        }
    rows = panel_rows()
    result["search_feedback"] = classify_batch(
        rows, [candidate("FIXTURE_IMPROVEMENT", role="generated", vina=-9.95)], settings,
        objective_active=True, intended_change_observed=False)
    panel = select_panel(rows, settings)
    result["complete_final_panel"] = summarize_final(panel, rows, settings)
    rows[0]["measurements"]["vina"]["status"] = "failed"
    result["failed_final_slot"] = summarize_final(panel, rows, settings)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
