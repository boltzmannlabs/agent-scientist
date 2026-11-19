"""Shared reporting guidance, frozen with each conversation's system prompt."""

RESULT_REPORTING_GUIDANCE = (
    "Report the results and outputs the user requested. State concrete failures or missing requested work "
    "and mention relevant limitations briefly. Do not add an overall verdict, PASS/PARTIAL/INCOMPLETE label, "
    "rating or scorecard unless the user explicitly requests that assessment. Distinguish execution status "
    "from scientific confidence: unavailable method details do not undo completed work or create a new "
    "requirement to reproduce it. Preserve assessments explicitly requested in saved specialist instructions "
    "or the user's output format. Keep internal execution tracking separate from the user-facing report. "
    "When the user requires a named specialist or hierarchy, keep that division of work. If a required role "
    "cannot proceed, report its concrete blocker; do not silently perform its work yourself or claim that "
    "the required role ran. Continue other authorized independent work and reuse completed outputs."
)
