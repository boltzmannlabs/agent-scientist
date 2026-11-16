"""Session-scoped YOLO decisions; timeouts never masquerade as human answers."""

from contextvars import ContextVar
import json

TIMEOUT_SECONDS = 120
TIMEOUT_OVERRIDE = ContextVar("clarify_timeout_override", default=None)
PURPOSES = ("missing_input", "data_change", "provider_switch", "partial_validation",
            "unverified_reference", "execution_uncertainty", "explicit_approval")
AUTOMATIC = frozenset({"partial_validation", "unverified_reference", "execution_uncertainty"})
TIMED = frozenset({"missing_input", "data_change"})

GUIDANCE = (
    "Classify each clarification with purpose. User instructions requiring approval always take "
    "precedence: use explicit_approval even if another purpose would otherwise fit. In YOLO mode, "
    "partial_validation, unverified_reference and execution_uncertainty proceed under the mode's "
    "authorization, with warnings disclosed. Missing_input and data_change questions wait 120 seconds, "
    "then use recommended_answer only if it is grounded in the current contract or supplied inputs. "
    "When choices are offered, recommended_answer must copy one choice label exactly; put explanations "
    "in recommendation_basis, not in the answer. Never invent sequences, structures, targets or paths. "
    "For data changes describe the exact transformation and preserve the original file. Provider_switch "
    "and explicit_approval always require a user answer without a timeout. Cancellation, rejection, "
    "skipping and undelivered dialogs never authorize defaults. A defaulted or policy_applied result "
    "is a YOLO policy decision, not a user answer; disclose defaults and changes in the final report. "
    "Outside YOLO all questions retain their ordinary approval behavior."
)


def ask_yolo(questions, callback, result):
    """Group timed and strict questions so a provider question cannot inherit a deadline."""
    rows = {}
    outcomes = []
    notices = []
    for purposes, timeout in ((AUTOMATIC, None), (TIMED, TIMEOUT_SECONDS),
                              (frozenset({"provider_switch", "explicit_approval"}), 0)):
        group = [entry for entry in questions if entry["purpose"] in purposes]
        if not group:
            continue
        if purposes is AUTOMATIC:
            reply = {"answers": {}, "outcome": "policy_applied"}
        elif callback is None:
            reply = {"answers": {}, "outcome": "undelivered", "notice": "No user dialog is available; no fallback was authorized."}
        else:
            shown = []
            for entry in group:
                note = "Explicit answer required; no automatic timeout."
                if timeout:
                    default = entry.get("recommended_answer")
                    note = (f"YOLO: after {timeout} seconds use {default!r}. "
                            f"Basis: {entry.get('recommendation_basis')}" if default is not None else
                            f"YOLO: waits {timeout} seconds; no supported default is available.")
                shown.append({**entry, "question": entry["question"] + "\n" + note})
            token = TIMEOUT_OVERRIDE.set(timeout)
            try:
                reply = callback(shown)
            finally:
                TIMEOUT_OVERRIDE.reset(token)
        outcomes.append(reply["outcome"])
        if reply.get("notice"):
            notices.append(str(reply["notice"]))
        parsed = json.loads(result(group, reply))
        for entry, row in zip(group, parsed["responses"]):
            if purposes is AUTOMATIC:
                row.update(status="policy_applied", policy_response="Proceed under YOLO authorization; retain and report the warnings.")
            elif (reply["outcome"] == "timed_out" and row["status"] == "unanswered"
                  and timeout and entry.get("recommended_answer") is not None):
                row.update(status="defaulted", policy_response=entry["recommended_answer"],
                           recommendation_basis=entry["recommendation_basis"])
            rows[entry["qid"]] = row
        if reply["outcome"] in {"cancelled", "undelivered"}:
            break
    for entry in questions:
        if entry["qid"] not in rows:
            rows[entry["qid"]] = json.loads(result([entry], {"answers": {}, "outcome": "unanswered"}))["responses"][0]
    output = {"responses": [rows[e["qid"]] for e in questions],
              "outcome": outcomes[-1], "group_outcomes": outcomes, "yolo": True}
    if notices:
        output["notice"] = "\n".join(notices)
    return json.dumps(output)
