"""Expose the authorized provider before the model chooses a scientific skill.

Plugin skills deliberately live outside the ordinary available-skills index.
The existing prompt-section API freezes this discovery guidance per session;
the execution gate still revalidates credentials independently on every call.
"""

from .auth import available


AUTHORIZED_EXECUTION_POLICY = """Boltzmann scientific execution routing

This profile had /add_boltzmann authorization when this session's policy was built.
That is not a live service check or permission to bypass session tool restrictions.
For Boltzmann tool inventory, use references/tool-contracts.v1.json, the same
catalog as /boltzmann_tools. List scientific tools grouped by domain and module title,
not the five connector helpers. Include active matches, separate on-hold entries,
omit removed/ignored entries, and respect profile restrictions. Catalog visibility
does not prove entitlement or readiness.

For scientific execution, inspect Boltzmann BEFORE choosing a different provider
or a local-generation skill. Load skill_view(name='boltzmann:tools'), then its
module registry and the matching complete contract. Plugin skills are not in
the ordinary available-skills index; absence from that index is not absence of
the Boltzmann workflow. If tools are deferred, use tool_search for Boltzmann,
tool_describe for schemas, and tool_call for the discovered plugin operations.

Collect missing scientific inputs with the clarify tool when it is available in
an interactive session, not a plain-text list of questions. Batch independent
questions in one form. Use documented choices for enum fields and open-ended
questions for text, numbers and file paths; never invent scientific options.
If clarify is unavailable or its result is undelivered, explain that the input
dialog is unavailable and ask in plain text. A skipped, cancelled or timed-out
question is not an answer or approval; stop work that depends on that input.

For random-antibody requests, start with
references/modules/protein-antibody-generation.md. Preserve the requested
count, ask only for missing required inputs, and never ask the user to name an
experiment. Do not promise counts or pairing before checking returned files.

When a verified contract matches the requested inputs and outputs, execute with
the Boltzmann plugin tools, not ToolUniverse alternatives, p-IgGen, Hugging Face,
or locally generated scripts. Supporting skills may guide input preparation and
output validation; they must not change the chosen execution provider. Do not
inspect GPUs or install/download a local generator before this provider decision.

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
"""


def render_execution_policy(_session_info):
    """Use the owning profile's local receipt, with no network or secret output."""
    return AUTHORIZED_EXECUTION_POLICY if available() else ""
