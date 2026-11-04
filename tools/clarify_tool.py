"""Clarify tool: structured multiple-choice / open-ended questions to the user.
Schema, validation and a thin dispatcher; the UI lives in a platform-provided
callback (cli.py, gateway/run.py, tui_gateway)."""

import json
import re
from typing import Callable, Dict, List, Optional

MAX_CHOICES = 4  # the UI always appends an "Other (type your answer)" row
MAX_QUESTIONS = 5  # independent questions per call
# Per-choice cap. Surfaces wrap long choice text (newlines kept), so anything longer is rejected here, at the
# source, instead of a surface silently dropping a choice that ``choices_offered`` still reports as shown.
MAX_CHOICE_CHARS = 8000
# Applied to the first choice here (not per-surface) so every adapter renders it identically.
RECOMMENDED_LABEL = "(Recommended)"
_UNAVAILABLE = "Clarify tool is not available in this execution context."
_SHAPE = "Pass questions=[{question, choices?, multi_select?}]; a single question is a one-entry array."
_EXPERIMENT_NAMING_RE = re.compile(
    r"(?:"
    r"(?:please\s+)?(?:enter|provide|choose|select|confirm)\s+(?:a|the|your)?\s*(?:new\s+)?(?:experiment|job|run)\s+name"
    r"|(?:what|which)\s+(?:experiment|job|run)\s+name(?:\s+should\s+(?:i|we)\s+use)?"
    r"|what\s+(?:should|would)\s+(?:i|we|you)\s+(?:name|call)\s+(?:this|the|your)\s+(?:experiment|job|run)"
    r"|(?:new\s+)?(?:experiment|job|run)\s+name"
    r")[?!.:\s]*",
    re.IGNORECASE,
)
_SUBSTANTIVE_CHOICE_RE = re.compile(
    r"\b(?:approve|authorize|consent|submit|execute|upload|credit|cost|pay|spend|delete|overwrite|samples?)\b",
    re.IGNORECASE,
)
_EXISTING_RUN_LOOKUP_RE = re.compile(
    r"\b(?:existing|previous|earlier|past|historical|already\s+(?:ran|submitted)|"
    r"recover|find|lookup|search|status|dashboard|resume)\b",
    re.IGNORECASE,
)
_AUTO_EXPERIMENT_NAME_ANSWER = (
    "Use an Agent Scientist-generated experiment name. Preserve an exact name "
    "the user already supplied; otherwise generate one and continue without asking. "
    "This does not approve any separate scientific or submission decision."
)


def mark_recommended(choices: List[str]) -> List[str]:
    """Suffix the first choice (schema says best-first) with RECOMMENDED_LABEL; idempotent,
    and a lone choice is left untouched (nothing to prefer it over)."""
    first = str(choices[0]).strip() if choices else ""
    if len(choices) < 2 or first != strip_recommended(first):
        return choices
    return [f"{first} {RECOMMENDED_LABEL}"] + list(choices[1:])


def strip_recommended(text: str) -> str:
    """Remove the recommendation label so presentation never leaks into ``user_response``."""
    stripped = str(text).strip()
    if stripped.casefold().endswith(RECOMMENDED_LABEL.casefold()):
        return stripped[: -len(RECOMMENDED_LABEL)].strip()
    return stripped


def _clean_answer(raw, multi: bool):
    """Strip presentation (the label, multi-select JSON) from a locked answer: a multi-select
    answer is a list, a JSON array string, or one typed ("Other") answer."""
    if not multi:
        return strip_recommended(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        raw = parsed if isinstance(parsed, list) else [raw]
    return [strip_recommended(item) for item in raw if str(item).strip()]


def _normalize_questions(questions) -> tuple:
    """Validate ``questions`` -> ``(normalized, error)``. Entries carry ``qid`` (stable wire id
    ``q<index>`` surfaces key answers by), ``question``, decorated ``choices``, bare
    ``choices_offered`` and ``multi_select``."""
    if not isinstance(questions, list) or not questions:
        return None, f"questions must be a non-empty array. {_SHAPE}"
    if len(questions) > MAX_QUESTIONS:
        return None, f"questions supports at most {MAX_QUESTIONS} items."
    normalized = []
    for index, item in enumerate(questions):
        if not isinstance(item, dict):
            return None, f"questions[{index}] must be an object. {_SHAPE}"
        text = str(item.get("question") or "").strip()
        if not text:
            return None, f"questions[{index}].question must be non-empty text."
        choices = item.get("choices")
        if choices is not None:
            if not isinstance(choices, list) or not all(isinstance(c, str) for c in choices):
                return None, f"questions[{index}].choices must be a list of strings."
            for pos, choice in enumerate(choices):
                if len(choice.strip()) > MAX_CHOICE_CHARS:
                    return None, (f"questions[{index}].choices[{pos}] is {len(choice.strip())} characters; the limit is "
                                  f"{MAX_CHOICE_CHARS}. Move detail into the question text and resend.")
            cleaned = [c.strip() for c in choices if c.strip()][:MAX_CHOICES]
            if choices and not cleaned:
                # A card with no options strands the turn: say so instead of silently asking open-ended.
                return None, (f"questions[{index}].choices has {len(choices)} entries but all are blank. "
                              "Send real labels, or omit choices to ask open-ended.")
            choices = cleaned or None
        normalized.append({
            "qid": f"q{index}", "question": text,
            "choices": mark_recommended(list(choices)) if choices else None,
            "choices_offered": list(choices) if choices else None,
            "multi_select": bool(item.get("multi_select")) and bool(choices)})
    return normalized, None


def _response_status(qid: str, answers: dict, multi: bool) -> tuple:
    raw = answers.get(qid)
    cleaned = _clean_answer(raw, multi) if raw not in (None, "") else None
    if cleaned:
        return "answered", cleaned
    return ("skipped" if qid in answers else "unanswered"), None


def _is_experiment_name_choice(entry: dict) -> bool:
    """Recognize a clarification that asks the user to name a new run."""
    text = " ".join([entry["question"], *(entry.get("choices_offered") or [])])
    return bool(_EXPERIMENT_NAMING_RE.fullmatch(entry["question"])
                and not _EXISTING_RUN_LOOKUP_RE.search(text)
                and not _SUBSTANTIVE_CHOICE_RE.search(text))


def _result(normalized: List[dict], reply: dict) -> str:
    """Result JSON from a callback reply ``{"answers": {qid: raw | None}, "outcome", "notice"?}``:
    every response carries ``status`` and ``user_response`` (null unless answered); ``outcome``
    says how the wait ended and ``notice`` (surface-supplied) says why."""
    answers = reply.get("answers") or {}
    responses = []
    for entry in normalized:
        status, value = _response_status(entry["qid"], answers, entry["multi_select"])
        responses.append({"question": entry["question"], "choices_offered": entry["choices_offered"],
                          "status": status, "user_response": value})
    result: Dict[str, object] = {"responses": responses, "outcome": reply["outcome"]}
    if reply.get("notice"):
        result["notice"] = str(reply["notice"])
    return json.dumps(result, ensure_ascii=False)


def clarify_tool(questions, callback: Optional[Callable] = None) -> str:
    """Ask 1-5 questions in one call. ``callback(questions) -> {"answers", "outcome", "notice"?}``
    is platform injected (cli.py / gateway / tui_gateway) and receives the normalized list."""
    normalized, error = _normalize_questions(questions)
    if error:
        return tool_error(error)
    # A run label is metadata, not a user decision. Resolve that question in
    # the tool boundary so a model or stale skill cannot put it in a UI modal.
    auto_answers = {}
    interactive = []
    for entry in normalized:
        if _is_experiment_name_choice(entry):
            auto_answers[entry["qid"]] = _AUTO_EXPERIMENT_NAME_ANSWER
        else:
            interactive.append(entry)
    if not interactive:
        return _result(normalized, {"answers": auto_answers, "outcome": "submitted"})
    if callback is None:
        return tool_error(_UNAVAILABLE)
    try:
        reply = callback(interactive)
        answers = dict(reply.get("answers") or {})
        answers.update(auto_answers)
        reply["answers"] = answers
        return _result(normalized, reply)
    except Exception as exc:
        return tool_error(f"Failed to get user input: {exc}")


def check_clarify_requirements() -> bool:
    """Clarify tool has no external requirements -- always available."""
    return True


CLARIFY_SCHEMA = {
    "name": "clarify",
    "description": (
        "Ask the user one or more questions when you need a decision, "
        "clarification, or feedback before proceeding. Pass every question "
        f"in `questions` (1-{MAX_QUESTIONS} entries) — a single question is a "
        "one-entry array, and several INDEPENDENT questions belong in ONE "
        "call (one form beats a chain of clarify calls; if one answer would "
        "change another question, ask separately). Per question: "
        f"single-select (up to {MAX_CHOICES} choices — put your recommended "
        "option FIRST, the UI marks it '(Recommended)' and auto-appends an "
        "'Other' free-text row), multi-select (multi_select=true), or "
        "open-ended (omit choices). Options go ONLY in `choices`, never "
        "enumerated inside the question text (choices render as pickable "
        "rows; options written into the question are dead prose the user "
        "can't click). Result: {responses: [...], outcome} in question order. "
        "Each response has status answered, skipped or unanswered "
        "(user_response is null unless answered); outcome is submitted, "
        "cancelled, timed_out or undelivered, with a notice saying why "
        "when the wait ended without a submit. Prefer deciding "
        "low-stakes questions yourself; don't use this for dangerous-command "
        "confirmation (the terminal tool handles that). Never ask the user to "
        "name or confirm a new experiment/run; preserve a name explicitly "
        "supplied in their request, otherwise generate it and continue. "
        "Questions that only request a new run name are resolved automatically."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "questions": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_QUESTIONS,
                "description": (
                    "The question(s). Each: question text (options excluded), "
                    "optional choices (recommended first; omit for free-text), "
                    "optional multi_select. Responses come back in question "
                    "order with the question text echoed."
                ),
                "items": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "choices": {
                            "type": "array",
                            "items": {"type": "string", "maxLength": MAX_CHOICE_CHARS},
                            "maxItems": MAX_CHOICES,
                        },
                        "multi_select": {"type": "boolean"},
                    },
                    "required": ["question"],
                },
            },
        },
        "required": ["questions"],
    },
}

# --- Registry ---
from tools.registry import registry, tool_error

registry.register(
    name="clarify",
    toolset="clarify",
    schema=CLARIFY_SCHEMA,
    handler=lambda args, **kw: clarify_tool(args.get("questions"), callback=kw.get("callback")),
    check_fn=check_clarify_requirements,
    emoji="❓",
)
