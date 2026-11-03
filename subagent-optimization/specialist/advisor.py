"""Prepare and validate one advisory assignment; use the native saved child to reason.

No model client, scientific connector, state store or approval implementation.
The caller supplies authoritative development records and enforces access.
"""
from copy import deepcopy
import json

from prototype.context_contract.context_contract import ContractError, canonical, digest, require
from prototype.library_policy.policy import choose_library, action_signature

NAME = "smallmol-investigation"
CONTEXT_CHAR_LIMIT = 24000  # Technical handoff bound, not a token/cost budget.
TEXT_FIELDS = {"scientific_question", "hypothesis", "competing_explanation",
               "comparison_to_baseline", "expected_observation", "reversal_condition"}
LIST_FIELDS = {"supporting_ids", "counterexample_ids", "limitations", "information_requests"}
ANSWER_FIELDS = TEXT_FIELDS | LIST_FIELDS | {
    "schema_version", "input_digest", "disposition", "library_id", "scientific_claim"}


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def prepare(source, *, previous_input_digest=None, max_context_chars=CONTEXT_CHAR_LIMIT):
    """Build a bounded packet, or return a reason to avoid another model call.

    The whole supplied cohort is retained. Too much data is a blocker, never
    permission to drop inconvenient observations. There is no persistent cache.
    """
    require(isinstance(source, dict) and set(source) == {
        "task", "libraries", "batches", "chemistry", "resource_summary"}, "Incomplete source adapter")
    input_digest = digest(source)
    t, libs, batches = source["task"], source["libraries"], source["batches"]
    baseline = choose_library(t, libs, batches)
    result = {"input_digest": input_digest, "status": "skip", "reason": baseline["reason"],
              "baseline": baseline, "request": None, "packet": None}
    if baseline["disposition"] in {"not_applicable", "stop", "no_action"}:
        return result
    # Scientific weakness of the heuristic is not a data-quality failure: the
    # specialist may consider a justified new investigation after poor results.
    if baseline["disposition"] == "need_information" and baseline["reason"] != "no_hard_feasible_matched_output_observed":
        return {**result, "status": "need_information"}
    eligible = baseline.get("eligible_library_ids", [])
    if len(eligible) < 2:
        return {**result, "reason": "fewer_than_two_eligible_libraries"}
    if previous_input_digest == input_digest:
        return {**result, "reason": "unchanged_input_reuse_host_advice"}
    chemistry = source["chemistry"]
    require(isinstance(chemistry, dict), "Chemical notes must be an object")
    if chemistry.get("evidence_kind") not in {"artificial_fixture", "host_reviewed_development"}:
        return {**result, "status": "need_information", "reason": "chemical_review_scope_required"}
    if not all(_text(chemistry.get(k)) for k in ("reference_description", "context_description")):
        return {**result, "status": "need_information", "reason": "reference_and_context_description_required"}
    support_ids = sorted({cid for p in baseline["family_profiles"].values() for cid in p["support_ids"]})
    if not support_ids:
        return {**result, "status": "need_information", "reason": "reviewed_pair_evidence_required"}
    families = chemistry.get("family_definitions", {})
    needed = set(baseline["family_profiles"]) | {l["target_family"] for l in libs if l["id"] in eligible}
    if not isinstance(families, dict) or not all(_text(families.get(f)) for f in needed):
        return {**result, "status": "need_information", "reason": "chemical_family_definitions_required"}
    pairs, cards = chemistry.get("pair_notes", {}), chemistry.get("library_notes", {})
    require(isinstance(pairs, dict) and isinstance(cards, dict), "Pair/library notes must be objects")
    for cid in support_ids:
        note = pairs.get(cid, {})
        rows = [r for b in batches for r in b.get("rows", []) if r.get("chemical_id") == cid]
        if (not isinstance(note, dict) or not rows
                or not all(_text(note.get(k)) for k in ("review_reference", "transformation_description"))
                or any(note.get("row_sha256") != digest(r) for r in rows)):
            return {**result, "status": "need_information", "reason": "missing_or_stale_pair_note:" + cid}
    for lib in libs:
        if lib["id"] not in eligible:
            continue
        note = cards.get(lib["id"], {})
        if (not isinstance(note, dict) or note.get("action_signature") != action_signature(lib)
                or not all(_text(note.get(k)) for k in ("review_reference", "chemical_rationale"))
                or not isinstance(note.get("limitations"), list) or not note["limitations"]
                or not all(_text(x) for x in note["limitations"])):
            return {**result, "status": "need_information", "reason": "missing_or_stale_library_note:" + lib["id"]}
    fixed = choose_library(t, libs, batches, strategy="round_robin")
    packet = {"schema_version": 1, "input_digest": input_digest,
              "evidence_kind": chemistry["evidence_kind"], "task": deepcopy(t),
              "resource_summary": deepcopy(source["resource_summary"]),
              "eligible_library_ids": eligible, "admissible_pair_ids": support_ids,
              "libraries": deepcopy(libs), "batches": deepcopy(batches),
              "chemical_notes": deepcopy(chemistry),
              "family_profiles": baseline["family_profiles"],
              "baseline_comparisons": {
                  strategy: {k: b.get(k) for k in ("disposition", "library_id", "reason")}
                  for strategy, b in (("context_coverage", baseline), ("fixed_order", fixed))},
              "limitations": ["Host-supplied identities, reviews and notes are not authenticated here.",
                             "Full supplied cohort retained; no negative rows omitted by this adapter.",
                             "Parsed-input identities do not establish actual fragment equivalence.",
                             "Internal compute may be unknown; this is advisory, not a budget grant."]}
    require(type(max_context_chars) is int and max_context_chars > 0, "Positive technical context bound required")
    context = canonical(packet)
    if len(context) > max_context_chars:
        return {**result, "status": "need_information", "reason": "context_too_large_no_evidence_dropped"}
    request = {"specialist": NAME,
               "goal": "Review this unfinished molecular investigation and return one evidence-linked library-choice JSON, or abstain.",
               "context": context}
    return {**result, "status": "invoke", "reason": "scientific_library_choice", "packet": packet, "request": request}


def parse_answer(text):
    """Reject duplicate keys and non-JSON wrappers instead of guessing intent."""
    def unique_pairs(pairs):
        obj = {}
        for key, value in pairs:
            require(key not in obj, "Duplicate JSON answer key")
            obj[key] = value
        return obj
    try:
        answer = json.loads(text, object_pairs_hook=unique_pairs)
    except (ValueError, TypeError) as exc:
        raise ContractError("One plain JSON answer required") from exc
    require(isinstance(answer, dict), "Answer must be a JSON object")
    canonical(answer)
    return answer


def accept(assignment, answer, current_source):
    """Check shape, citations, eligibility and freshness; do not endorse prose/science."""
    fresh = prepare(current_source)
    require(assignment == fresh and fresh["status"] == "invoke", "Stale or altered assignment; refresh before acceptance")
    packet = fresh["packet"]
    require(isinstance(answer, dict) and set(answer) == ANSWER_FIELDS, "Missing or additional answer fields")
    canonical(answer)
    require(type(answer["schema_version"]) is int and answer["schema_version"] == 1, "Unsupported answer version")
    require(answer["input_digest"] == fresh["input_digest"], "Answer cites a different input snapshot")
    require(answer["scientific_claim"] == "hypothesis_only", "Advice cannot establish scientific success")
    require(isinstance(answer["disposition"], str)
            and answer["disposition"] in {"recommend", "need_information", "no_action"}, "Unknown answer disposition")
    for field in TEXT_FIELDS:
        require(isinstance(answer[field], str), "Answer text field required: " + field)
    for field in LIST_FIELDS:
        value = answer[field]
        require(isinstance(value, list) and all(_text(x) for x in value), "Invalid answer list: " + field)
        require(len(value) == len(set(value)), "Duplicate answer list entry: " + field)
    cited = set(answer["supporting_ids"]) | set(answer["counterexample_ids"])
    require(cited <= set(packet["admissible_pair_ids"]), "Unknown or unqualified evidence citation")
    require(answer["limitations"], "Explicit limitations required")
    selected = None
    if answer["disposition"] == "recommend":
        require(answer["library_id"] in packet["eligible_library_ids"], "Library is not an eligible untried action")
        require(all(_text(answer[k]) for k in TEXT_FIELDS), "Recommendation needs a complete scientific explanation")
        require(cited and not answer["information_requests"], "Recommendation needs cited evidence and no unresolved requirements")
        selected = next(l for l in current_source["libraries"] if l["id"] == answer["library_id"])
    else:
        require(answer["library_id"] is None, "Abstention cannot select an action")
        require(_text(answer["hypothesis"]), "Abstention needs an explanation")
        if answer["disposition"] == "need_information":
            require(answer["information_requests"], "Specify the missing information")
    return {"status": "mechanically_valid_advice", "input_digest": fresh["input_digest"],
            "advice_digest": digest(answer), "disposition": answer["disposition"],
            "library_id": answer["library_id"], "action_signature": action_signature(selected) if selected else None,
            "scientific_validity": "not_assessed", "execution": "not_performed"}
