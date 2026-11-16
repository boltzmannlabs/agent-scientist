"""Expose the authorized provider before the model chooses a scientific skill.

Plugin skills deliberately live outside the ordinary available-skills index.
The existing prompt-section API freezes this discovery guidance per session;
the execution gate still revalidates credentials independently on every call.
"""

from .auth import available


AUTHORIZED_EXECUTION_POLICY = """Boltzmann scientific execution routing

This session began with profile-local /add_boltzmann authorization, not a live
service check or permission to bypass session tool restrictions.
For Boltzmann tool inventory, use references/tool-contracts.v1.json, the same
catalog as /boltzmann_tools. List scientific tools grouped by domain and module title,
not the five connector helpers. Include active matches, separate on-hold entries,
omit removed/ignored entries, and respect profile restrictions. Catalog visibility
does not prove entitlement or readiness.

For scientific execution, inspect Boltzmann BEFORE choosing a different provider
or a local-generation skill. Load skill_view(name='boltzmann:tools'), then its
module registry and the matching complete contract. Plugin skills are outside the ordinary available-skills index. If tools are deferred, use tool_search for Boltzmann,
tool_describe for schemas, and tool_call for the discovered plugin operations.

Collect missing scientific inputs using the interactive clarify tool; batch
independent questions in one form. Use documented choices for enum fields and open-ended
questions for text, numbers and file paths; never invent scientific options.
If clarify is unavailable or its result is undelivered, explain that the input
dialog is unavailable and ask in plain text. A skipped, cancelled or timed-out question is not an answer or approval; stop dependent work.

For random-antibody requests read references/modules/protein-antibody-generation.md.
Preserve the count, ask only for missing required inputs, and never ask for an
experiment name. Verify returned files before promising counts or pairing.

When a verified contract matches the requested inputs and outputs, execute with
the Boltzmann plugin tools, not ToolUniverse alternatives, p-IgGen, Hugging Face,
or locally generated scripts. Supporting skills may prepare inputs and validate outputs without changing providers. Do not
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

Execute output requests here without delegation or interim pending/running replies. Call
boltzmann_status with the same job_name and doc_id. That call waits in the
foreground, showing progress until a terminal state, status-check error or user
cancellation, with no overall queue deadline. Then check the returned artifacts.
No background monitoring starts automatically. Cancelling the wait leaves the
remote job running; preserve its ID.

A status-check error ends the attempt. Report the blocker and job ID immediately;
completion remains unknown. On stop_polling=true do not use terminal, execute_code,
read_file or diagnostic tools for recovery, inspect env/credentials, guess endpoints
or create polling scripts. Only an explicit request for further diagnosis permits
that work; never expose credentials. Running a prediction is not that permission.
"""


def render_execution_policy(_session_info):
    """Use the owning profile's local receipt, with no network or secret output."""
    return AUTHORIZED_EXECUTION_POLICY if available() else ""
