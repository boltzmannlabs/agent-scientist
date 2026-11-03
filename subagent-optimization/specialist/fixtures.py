"""Artificial development data and a CANNED answer, never a scientific case."""
from prototype.context_contract.context_contract import digest
from prototype.library_policy.fixtures import controlled_histories
from prototype.library_policy.policy import action_signature


def source():
    task, libraries, _, history = controlled_histories()
    notes = {r["chemical_id"]: {
        "row_sha256": digest(r), "review_reference": "ARTIFICIAL_REVIEW_NOT_A_PERSON",
        "transformation_description": "Artificial isolated family label; no chemical structure or mechanism represented."}
        for batch in history for r in batch["rows"]}
    return {"task": task, "libraries": libraries, "batches": history,
            "resource_summary": {"internal_compute": "unknown", "dollar_limit": None,
                                 "permission": "no scientific execution in this fixture"},
            "chemistry": {
                "evidence_kind": "artificial_fixture",
                "reference_description": "ARTIFICIAL_REFERENCE is an ID, not a molecular structure.",
                "context_description": "Fictional context and values; no measured or predicted chemical endpoint.",
                "family_definitions": {"FAMILY_F": "Artificial family F; no physical transformation defined.",
                                       "FAMILY_G": "Artificial family G; no physical transformation defined."},
                "pair_notes": notes,
                "library_notes": {lib["id"]: {
                    "action_signature": action_signature(lib),
                    "review_reference": "ARTIFICIAL_CARD_NOT_A_REVIEW",
                    "chemical_rationale": "Fictional family association to exercise the handoff only.",
                    "limitations": ["No actual library, chemistry or enrichment claim."]}
                    for lib in libraries}}}


def canned_answer(input_digest, library_id="LIBRARY_D"):
    return {"schema_version": 1, "input_digest": input_digest,
            "disposition": "recommend", "library_id": library_id,
            "scientific_question": "Does an untried fixture family investigation justify another step?",
            "hypothesis": "Illustrative transfer hypothesis only; there are no molecules in this fixture.",
            "competing_explanation": "Small artificial groups cannot establish transferable chemistry.",
            "supporting_ids": ["ARTIFICIAL_ID_g1"], "counterexample_ids": ["ARTIFICIAL_ID_f3"],
            "comparison_to_baseline": "This canned example can agree with or differ from the helper; it is not a model's reasoning.",
            "expected_observation": "A future compatible result could test the supplied family association.",
            "reversal_condition": "Reverse if the intended family is absent or the apparent pattern is contradicted.",
            "limitations": ["Artificial example, no molecular efficacy, calibration or advantage demonstrated.",
                            "Library family enrichment and internal compute are unknown."],
            "information_requests": [], "scientific_claim": "hypothesis_only"}
