"""Expose the authorized provider before the model chooses a scientific skill.

Plugin skills deliberately live outside the ordinary available-skills index.
The existing prompt-section API freezes this discovery guidance per session;
the execution gate still revalidates credentials independently on every call.
"""

from .auth import available


AUTHORIZED_EXECUTION_POLICY = """Boltzmann scientific execution routing

Authorized at session start; each call still checks permission.
Use references/tool-contracts.v1.json, also used by /boltzmann_tools.
List scientific names grouped by domain and module title, not the five connector helpers.
Include all active entries for all-tools requests; separate on-hold and omit removed/ignored.
No jobs/uploads for inventory. Respect profile restrictions; membership is not readiness.

Inspect Boltzmann before another provider or local-generation skill.
Load skill_view(name='boltzmann:tools') and the matching complete module/contract.
Plugin skills are outside the ordinary index. For deferred tools use tool_search,
tool_describe, then tool_call; index absence does not mean unavailable.

Collect missing scientific inputs with the clarify tool when it is available in
an interactive session, not a plain-text list of questions. Batch independent
questions in one form. Use documented choices for enum fields and open-ended
questions for text, numbers and file paths; never invent scientific options.
Reuse explicit inputs already given; do not ask for CCO or its input mode again.
If clarify is unavailable or undelivered, explain and ask in plain text.
An unanswered question is not an answer or approval; only a YOLO policy_response
can supply supported defaults.
Follow clarify's YOLO policy; explicit false keeps a requested validation gate.

For random-antibody requests, start with
references/modules/protein-antibody-generation.md. Preserve the requested
count, ask only for missing required inputs, and never ask the user to name an
experiment. Do not promise counts or pairing before checking returned files.

When the contract matches the requested inputs/outputs, use Boltzmann plugin tools.
Supporting skills may prepare/validate data, never switch providers or install a
local generator. Do not inspect GPUs before choosing the execution provider.

If the session cannot discover the required plugin tools or boltzmann:tools,
stop and explain the missing setup/session access; request a restart of agent-sci
after /add_boltzmann. Do not treat deferred activation as 'no suitable tool exists'.
If authentication fails, a contract is blocked, or inputs are missing, explain
the blocker; do not silently switch providers. Get approval before alternative
scientific execution unless the user explicitly requested that alternative.
Literature, coding and non-execution questions need not use Boltzmann.

Submit once; retain and poll the same job ID. Never duplicate a pending or
ambiguously submitted job. Verify actual artifacts and counts, report partial
results honestly, and never automatically submit a top-up job.
Download final artifacts with boltzmann_download without output_folder unless
the user requested a location. Its default is the owning profile's persistent
workspace/outputs directory. Keep conversions there too, never in temporary
storage, and report the actual saved paths.

For an active request needing outputs, work directly in this conversation. Do
not delegate it or return interim pending/running status. After submission, call
boltzmann_status with the same job_name and doc_id. That call waits in the
foreground, showing progress until a terminal state, status-check error or user
cancellation, with no overall queue deadline. Then check the returned artifacts.
No background monitor or continuation is started automatically. Cancelling the
wait does not cancel the remote scientific job; preserve its ID for later checks.

A status-check error ends the attempt. Report the blocker and job ID immediately;
completion remains unknown. On stop_polling=true do not use terminal, execute_code,
read_file or diagnostic tools for recovery, inspect env/credentials, guess endpoints
or create polling scripts. Only an explicit request for further diagnosis permits
that work; never expose credentials. Running a prediction is not that permission.
"""


def render_execution_policy(_session_info):
    """Use the owning profile's local receipt, with no network or secret output."""
    return AUTHORIZED_EXECUTION_POLICY if available() else ""
