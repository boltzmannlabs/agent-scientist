# Molecular optimization investigator — development v1

This is a host-mediated investigation loop for the separately versioned
[optimization specialist](../specialist/optimization-v1/README.md). The specialist
chooses a parent–library investigation from actual observations. The host validates
that request, executes the existing Boltzmann connector, records evidence in the
existing molecular environment and resumes the investigator after results arrive.

The earlier [library-only pilot](../pilot/README.md), saved definition and frozen
campaign remain historical experiments. This workflow does not reinterpret their
results or overwrite their state.

## Scientific assignment

The currently supported task uses the selected platform **Lipophilicity score
range 0–3**, QED strictly above **0.800452829768805**, and sparse Morgan count
radius-2 similarity strictly above **0.7** to the original reference. The same
valid, distinct nonreference molecule must satisfy all three conditions.

Lipophilicity is a raw provider score. Physical units and exact model revision
remain unverified; these results do not establish physical-property or experimental
improvement. The supplied local CReM code generates then predicts properties.
Deployed property-feedback optimization is not established by a successful job.

The next action binds a registered parent, library content identity and unchanged
property objective. A library can be reused with a different parent. Assessment
always uses the original task reference, even after changing generation parents.
Exact repeated or uncertain actions are not automatically retried.

## Execution and runtime ownership

```text
Fixed assignment + campaign observations
                 ↓
Native named specialist + selected optimization skill
                 ↓
Identity-bound action_requested outcome
                 ↓
Host admission → original SDK connector → scientific job
                 ↓
Host monitoring, download and molecular assessment
                 ↓
Updated campaign → next bounded specialist episode
```

The main agent delegates the investigation; it does not need to re-plan each
calculation. The private reasoning profile deliberately receives no copied
Boltzmann credentials. A requested action is not an accepted scientific job.
Only the owning host's original authenticated connector can create that job.

Two existing interpreters are used because their installed dependencies differ:

| Process | Current qualified interpreter | Responsibility |
| --- | --- | --- |
| Scientific host | `/usr/bin/python3`, Python 3.13 with the pinned RDKit runtime | Campaign state, identity checks, search summaries, admission and result assessment |
| Agent Scientist SDK | `/home/boltzmann13/agent-scientist/.venv/bin/python`, Python 3.14 | Native model/delegation runtime and original Boltzmann wrappers |

These are observed local paths, not interchangeable environment specifications.
Use an already prepared SDK interpreter and the scoring runtime required by the
frozen assessor. The launcher disables lazy provisioning; it does not install
packages, update the application or change source branches.

`connector_process.py` is private process transport to
`model_tools.handle_function_call` in that owning SDK. It selects the original
owning profile and its existing grants, and calls only the four existing
Boltzmann wrappers. Its validation operation reuses the SDK's canonical
validators. It adds no HTTP client, alternate scientific provider or credential
copying. A process timeout leaves an unknown outcome, not permission to resubmit.

The existing `leadopt_env` remains the scientific record. Small assignment and
execution-intent tables share its database; there is no second candidate database.
Admission enforces supported controllable limits. Environment budget warnings
alone do not enforce scientific execution.

## Skill loading and context

The core `smallmol-optimization` skill and its CReM reference are selected in the
new role. CReM is the only qualified generator in this workflow, so its small
reference is injected upfront alongside the core skill. This avoids an extra
model/tool round to fetch guidance already known to be relevant. Other references
within the selected skill remain available on demand. Selection does not make
unselected external skills or unavailable scientific tools accessible.

Native qualification checks actual injected content. The reviewed MolClaw,
BioSymphony and K-Dense principles are adapted and attributed in the skill;
unqualified upstream execution instructions are not substituted for our connector.

Campaign evidence remains canonical in the host. Decision context factors repeated
metadata and preserves candidate facts, failures and eligible actions. Typed short
identifiers can be presented to the model through `identifiers.py`; a checked,
reversible private map restores canonical IDs before host validation. Molecular
representations and reported scientific values are not rewritten. A source digest
alone is not treated as access to missing evidence.

## CLI setup

Run from this bundle using the scientific host interpreter. Set the private input
paths and an agreed future ISO-8601 deadline before initializing. The example
allowances below are prospective choices; initialization freezes them for this
assignment.

```bash
cd /home/boltzmann13/agent-scientist-subagent-optimization/subagent-optimization

SMALLMOL_PYTHON=/usr/bin/python3
SMALLMOL_ENV_SOURCE=/home/boltzmann13/science-environments/environments/small-molecule-lead-optimization/src
SMALLMOL_HOST_ROOT=/home/boltzmann13/agent-scientist
SMALLMOL_SDK_PYTHON=/home/boltzmann13/agent-scientist/.venv/bin/python
SMALLMOL_OWNER_HOME=/home/boltzmann13/.sci
SMALLMOL_STATE=/home/boltzmann13/.local/state/smallmol-workflow/my-new-assignment

# Replace these with the reviewed private input paths and agreed future deadline.
SMALLMOL_PROTOCOL=/absolute/private/path/qualified-property-protocol.json
SMALLMOL_COMMON_STAGE=/absolute/private/path/original-completed-stage-or-pilot-state.json
SMALLMOL_COMMON_CSV=/absolute/private/path/original-generated-molecules.csv
SMALLMOL_COMMON_SHA=original_artifact_sha256_from_the_reviewed_receipt
SMALLMOL_DEADLINE=agreed_future_ISO8601_timestamp_with_timezone

SMALLMOL_STATE_ARGS=(--state-dir "$SMALLMOL_STATE" --environment-source "$SMALLMOL_ENV_SOURCE")
SMALLMOL_RUNTIME_ARGS=(--host-root "$SMALLMOL_HOST_ROOT" --sdk-python "$SMALLMOL_SDK_PYTHON" --owner-home "$SMALLMOL_OWNER_HOME")
```

`--environment-source` identifies the existing environment's **src directory**.
`--host-root` identifies the SDK source checkout. Neither is a request to install
or clone a repository. Keep the new state outside source checkouts and the original
owning profile; initialization requires a fresh directory. No API keys belong in
these variables or CLI arguments.

### Initialize and inspect

This imports the qualified protocol and an already completed common batch. The
stage input may be the original stage JSON or the old pilot state containing
`stages.common`. Its native receipts and downloaded-artifact hash must agree.

```bash
"$SMALLMOL_PYTHON" -B -m workflow.run init \
  "${SMALLMOL_STATE_ARGS[@]}" \
  --protocol "$SMALLMOL_PROTOCOL" \
  --assignment-id my-new-optimization-assignment \
  --max-submissions 3 --max-episodes 3 \
  --deadline-utc "$SMALLMOL_DEADLINE" \
  --common-stage "$SMALLMOL_COMMON_STAGE" \
  --common-csv "$SMALLMOL_COMMON_CSV" \
  --common-sha256 "$SMALLMOL_COMMON_SHA"

"$SMALLMOL_PYTHON" -B -m workflow.run inspect "${SMALLMOL_STATE_ARGS[@]}"
```

The shared common job counts **once against the total allowance**. With a total
of three, importing one common job leaves at most two new scientific-action
reservations. It is not submitted again. To start from the reference alone, omit
all three common-input flags; the three flags must otherwise be supplied together.

Submission allowances are conservative host reservations. They are not credits or
backend oracle counts. A single CReM job can return hundreds of property-scored
rows; imported unique-molecule counts do not reveal all internal prediction work.
Reference-qualification overhead is recorded separately in the assignment.

### Prepare a decision or invoke the specialist

Preparing a context consumes one episode allowance, but performs no model inference
or scientific submission:

```bash
"$SMALLMOL_PYTHON" -B -m workflow.run prepare \
  "${SMALLMOL_STATE_ARGS[@]}" --host-root "$SMALLMOL_HOST_ROOT"
```

To prepare **and actually invoke** the specialist in a fresh private episode
profile, use `--invoke`. This creates a separate episode; it does not invoke a
previously prepared episode:

```bash
"$SMALLMOL_PYTHON" -B -m workflow.run prepare \
  "${SMALLMOL_STATE_ARGS[@]}" "${SMALLMOL_RUNTIME_ARGS[@]}" --invoke
```

Use the number in the reported `episode_directory` in the next command. For
example, if a context-only preparation preceded it, the invoked episode is number
two, not number one. The native process resolves existing reasoning authorization
in the owning profile; credential files are not copied into the reasoning profile.
Its saved outcome must validate in `host_mediated` mode before execution.

### Execute one saved decision

```bash
"$SMALLMOL_PYTHON" -B -m workflow.run execute \
  "${SMALLMOL_STATE_ARGS[@]}" "${SMALLMOL_RUNTIME_ARGS[@]}" \
  --episode 2 --execute
```

Replace `2` with the actual invoked episode number. Without `--execute`, this
command returns `execution_disabled`. The host rechecks the saved assignment,
current evidence, action identity, original objective, warning approval and
resource availability. An already executed episode is not submitted again.

### Collect or advance one step

```bash
"$SMALLMOL_PYTHON" -B -m workflow.run collect \
  "${SMALLMOL_STATE_ARGS[@]}" "${SMALLMOL_RUNTIME_ARGS[@]}"

"$SMALLMOL_PYTHON" -B -m workflow.run step \
  "${SMALLMOL_STATE_ARGS[@]}" "${SMALLMOL_RUNTIME_ARGS[@]}" --execute
```

`collect` performs one observation pass on original known jobs, refreshes owned
status before downloading when needed, checks downloaded bytes and assesses them
with the qualified scientific host. It makes no model call and submits no new job.

`step --execute` performs at most one host-mediated continuation: collect pending
work, then invoke and execute one new decision if the assignment is ready. It is
not a background scheduler. Pending or ambiguous work prevents another scientific
decision. Without `--execute`, `step` can collect existing work but does not invoke
a new model episode or submit a new scientific action.

### Run the initialized investigation with one command

After `init`, this command drives the same existing assignment through bounded
collect/decision/action passes. Use it instead of manually repeating the commands
above. Run one driver process per assignment.

```bash
"$SMALLMOL_PYTHON" -B -m workflow.run run \
  "${SMALLMOL_STATE_ARGS[@]}" "${SMALLMOL_RUNTIME_ARGS[@]}" \
  --execute --poll-seconds 30 --max-wait-seconds 900
```

`run` never initializes a campaign. Without `--execute` it reports
`execution_disabled`; it does not run the model or scientific loop. During healthy
pending work it only observes original known jobs. It does not call the LLM or
submit another action until that work settles. Individual sleeps are capped at
30 seconds; the poll interval must be at least one second. The default driver
window is 900 seconds, and the fixed assignment deadline remains a hard stop.
These driver settings do not increase the assignment's scientific or episode
allowances.

The command emits progress JSON lines and a final structured report with the
outcome, recorded usage and private artifact paths. It records a final selection
only after all outstanding work settles. Host-qualified objective success closes
with the qualified IDs. Reached resource/deadline/no-action limits close settled
work with an empty selection and an explicit unsuccessful stopping reason.

A maximum-wait timeout leaves the same assignment available for resume. A deadline
with outstanding work also leaves it unfrozen; existing remote jobs are not
cancelled. Use explicit `collect` to retrieve an original job after its deadline,
then inspect or close the settled assignment. Unknown submissions, missing job
identities, artifact-mapping/local-processing failures and blocked model outcomes
halt as `needs_attention`, rather than consuming more model calls in a loop.

Ctrl-C preserves original receipts for resume and does not cancel a remote job.
Resolve reported issues in the original state; do not rerun `init` or create a
replacement scientific job. A qualified saved decision can be executed without
repeating its model call. An uninvoked context-only preparation is reported for
attention rather than silently replaced by another episode.

The process exits with code 2 for `needs_attention` and 130 for interruption. A
normal stopped run can have no qualifying molecule; process completion is not
scientific objective success. Full output is retained in a private
`run-report-*.json` file, alongside the original campaign and episode evidence.

## State, recovery and completion

```text
private state directory/
  workflow.json                 Assignment/source identities
  campaign.sqlite               Existing environment + operational intent
  artifacts/                    Downloads, hashes and intake diagnostics
  episodes/episode-NNNN/         Assignment, native result, logs, execution receipt
    reasoning-home/             Isolated nonsecret role/skill installation
  connector-rpc/                Private owning-host process requests and receipts
  collection-*.json              Observation-pass outcomes
  run-report-*.json               Bounded driver status and resource summary
```

No new scientific action is admitted after objective success, freezing,
evaluation blockers, a reached deadline or exhausted allowance. Existing-job
collection remains an explicit operation. A pending job releases the reasoning
process; resources do not reset when the specialist resumes.

`Success` is retained in the native receipt and normalized separately for workflow
processing. A downloaded artifact is not yet a scientifically assessed result.
Unknown submission outcomes retain original intent and receipts; reconcile them
rather than inventing job IDs or creating replacement jobs. Read-only transport
errors do not establish scientific failure. A failed native reasoning episode can
still have consumed model resources, even though it submitted no scientific job.

The only approved partial-validation exception is the recorded generic CSV SMILES
warning for the exact admitted library. Canonical validation still runs, and a new
warning or error is not covered by that approval. Model-authored observations
cannot replace host calculation or original connector evidence.

## Evidence and current limits

See the [current qualification report](../results/optimization-v1-validation.md)
and [validation evidence index](../results/README.md) for exact commands,
counts and source hashes. Portable tests, actual SDK
middleware canaries, actual model inference and scientific jobs are distinct
evidence categories.

The completed development case used two actual specialist reasoning episodes and
three generation jobs, including one previously completed shared batch and two
new jobs. Across 834 returned rows, the final archive contained 790 distinct forms
including the reference. No candidate met the joint objective. The host stopped
at the submission allowance with no pending scientific jobs; it did not spend an
extra model call on a final narrative. Both adaptive choices matched the configured
deterministic policy at their respective decision points.

The core skill and selected CReM guide were verified in actual native context.
A fresh task-guided main control and specialist control received the same frozen
first-decision evidence and both selected the same parent and carbon-rich library.
This is one matched decision, not a full matched workflow or specialist advantage.

Identifier presentation reduced that packet from 250,708 canonical characters to
124,506 transmitted characters while retaining its scientific rows and choices.
Reported specialist input tokens changed from 121,573 before that presentation
to 52,478 in the later control. These are observed episode counts, not a verified
billing reduction or general performance guarantee. The exact controls and limits
are recorded in the linked qualification report.

This evidence establishes real native decisions, connector follow-ups, context
integration and bounded stopping. It does not establish better molecular outcomes,
protected-holdout performance, experimental potency or a completed repeated
main-agent versus specialist workflow comparison. The fresh user-demo assignment
is separate from this completed development campaign.

No default-profile specialist installation or further Git push is implied by these
commands or this documentation. Keep raw receipts, signed URLs, credentials,
private generated structures and native traces outside publication checkouts.
