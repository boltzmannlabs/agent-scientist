# Boltzmann foreground waiting and legacy monitors

A queued job is not a failed job. The result endpoint sometimes uses HTTP 404
for documented `pending`, `running` and `failed` bodies. The connector accepts
those states only with a usable message or information body. Authentication
failures, malformed responses and missing routes remain status-check errors.
Other terminal states on HTTP 404 require matching job identifiers as well as a
usable body; a generic `status: error` missing-route response is not a failed job.

## Waiting and results

Native SCI and the bundled MCP adapter keep `boltzmann_status` in the foreground.
Submission returns the accepted job ID; the agent immediately checks that same ID
and waits for a terminal result before continuing the workflow. No detached monitor,
continuation conversation, or asynchronous completion notification is started by
these calls. Required output downloads and verification happen in the same turn.

There is no overall queue/running deadline. Each status HTTP request has a
60-second timeout; transient transport failures retry with bounded backoff.
Authorization errors, malformed responses, and other definitive status-check
errors return to the agent with the job outcome unresolved. The classic CLI's live
status panel shows the latest five polling updates, including transient network
retries. Each new check replaces the oldest visible entry without appending to
scrollback. The view belongs to this chat and profile, and clears when the call
ends. Normal updates include observed state, elapsed time, and job ID. Noninteractive
clients without this panel receive the latest five updates on stderr when the call
ends. Hiding older updates does not stop polling or hide the returned result, error,
or cancellation. Ctrl+C or Stop interrupts polling;
this does **not** cancel the remote job. Keep the ID for later inspection, never
submit another job merely because waiting was interrupted.

SCI must remain running for this foreground wait. External MCP clients may impose
their own request deadlines. Existing workers started by older SCI sessions are
not killed by a code update; inspect and stop those monitors explicitly if needed.

`pending` and `running` remain nonterminal. Existing success, failure and
cancellation spellings remain supported. A matching, explicit `deleted` or
`not_found` job response can stop monitoring, but HTTP 404 alone cannot. This
support does not assert that the current backend emits those absence spellings.
Absence does not establish successful scientific completion or release unresolved
upload receipts.

The legacy Python `fetch_status()` helper still supports bounded polling and
explicit `max_wait`. If its window ends, it preserves the last pending/running
state and reports that the window ended. The old documented
`BOLTZMANN_MAX_POLL_SECONDS` environment override was never implemented; it is not
a supported setting. Native/MCP foreground waiting does not depend on per-tool runtime estimates.

## Legacy monitors: inspect, stop and resume

The sections below describe retained monitoring records and explicitly resumed
legacy workers. Normal tool calls no longer create them, attach checkpoints, or
register automatic restart/notification hooks.

```bash
sci boltzmann-jobs status
sci boltzmann-jobs status job:<monitor-id>
sci boltzmann-jobs stop job:<monitor-id>
sci boltzmann-jobs resume job:<monitor-id>
sci boltzmann-jobs resume
```

Use the exact `id` returned in `monitor` or the status listing, including `job:`.
Status shows the profile home, worker lease, last result/check, next check,
continuation report and any monitoring/notification failure. A startup state
`starting` is not confirmation of a running worker. `stop` stops monitoring and
future continuation; it does not cancel a remote calculation. `resume` monitors
existing IDs, never submits replacements.

One worker lease per profile prevents competing workers. The worker uses the
profile's current key and authorization on each check, without credential copies
or fallback to another profile. Missing/revoked credentials pause useful polling
and are rechecked with backoff. A live conversation receives outcome/blocker
notifications through SCI's existing background-process notification channel,
subject to its notification settings. Closed/offline conversations retain their
reports for status inspection and the next resumed turn. Notification queuing is
not a guarantee that an offline client displayed the message.

The original conversation owns the notification destination. Internal cron
continuations and their dependent jobs cannot replace that destination. Existing
CLI records with a stale continuation route are repaired from their saved source
session when that conversation is reopened.

`notice_queued` means the result was offered to the live notification queue;
`notice_delivered` means the owning conversation produced a response to that
notice. It does not prove that a person read it. A process lease prevents repeated
offers while that process is alive. If the process exits before handling the
notice, a resumed conversation can offer the saved report again after the lease
expires (up to two minutes). A persisted reply is checked before replay, including
compression/resume history. Retrying delivery never reruns the scientific job or
its continuation. `notification_error` records failures while preserving results.

Legacy remote-job monitoring uses a detached worker, not a `delegate_task`
subagent. Saved legacy jobs do not appear in the foreground polling panel.
Inspect their progress, worker health and storage errors explicitly with
`sci boltzmann-jobs status`. Rendering the chat does not read or alter those
records, start workers, poll the service, or acknowledge their results.

`sci boltzmann-jobs status` retains detailed job state, continuation reports and
delivery acknowledgement. A foreground reply may end while monitoring continues;
completion or a blocker returns to the owning conversation when background-process
notifications are enabled.

Workers survive closing a terminal. No process can poll while the host is off;
saved monitoring can be restarted explicitly through
`sci boltzmann-jobs resume`. Session startup no longer restarts it automatically. This feature does not install an operating-system boot service.

## Approved workflow continuation

Older native conversations checkpointed the task, recent user/assistant context, source
model/provider and complete allowed tool names before API schema deferral. Only
checkpoints attached to jobs are persisted. When all jobs for that checkpoint
are terminal, a separate conversation uses SCI's existing cron execution path to
collect/verify results and continue remaining approved work. Polling itself uses
no model calls. The original conversation's prompt, tool snapshot and history are
not rewritten. New dependent jobs return to durable monitoring.

Execution intersects current profile capabilities with the originating tool
allowlist. A continuation cannot use a newly granted unrelated tool. Accepted
input fingerprints block repeat submissions within the continuation; an ambiguous
submission blocks automatic continuation until reconciled. No automatic top-up,
provider substitution or remote cancellation is authorized. Missing inputs or
new permissions/charges require user review.

`reported` means a continuation turn produced a report, not that the scientific
workflow is proven successful. Inspect its response and actual outputs. Missing
checkpoints (including MCP-only callers) do not grant permission to invent a
workflow. Restricted specialists carry additional skill/path/delegation/deadline
grants; they must continue through their owning specialist scope rather than an
unrestricted replacement. A process interrupted during continuation is marked for
review, not automatically replayed. The retained cron conversation/report allows
reconciliation before further scientific actions.

## Storage and validation

Monitor records are separate from `state.json` and upload receipts:

```text
<active SCI_HOME>/plugin-data/<Boltzmann namespace>/job-monitors-v1/jobs.sqlite3
```

The directory is private (0700), the database is 0600, SQLite commits are
transactional with full synchronization, and symlinked storage is rejected.
Records have a 1 MiB limit and the database has a 256 MiB limit. No API keys are
stored. Unresolved monitors and their results are not automatically deleted.
Upload evidence retains its separate active/unknown-job protection and 30-day
terminal retention policy. Storage/startup failures preserve the accepted job ID
and warn the user instead of claiming that the remote job failed.

Verification uses temporary homes, simulated time, controlled responses and a
separate worker process against a localhost-only server. No production scientific
jobs are needed. Controlled connector tests do not establish hosted worker
availability or scientific correctness.

## Implementation and checks

- `nodeapi_helpers.py`: validated queue-state handling, bounded single checks and
  confirmed terminal results without mistaking a missing route for a failed job.
- `job_store.py`: private transactional checkpoints and atomic worker handoff.
- `job_monitor.py`: detached profile worker, authentication/backoff, inspect,
  stop/resume and restart handling.
- `job_continuation.py`: approved task checkpoints, frozen tool permissions,
  duplicate-submission protection and existing cron execution integration.
- `job_notifications.py`: session-owned outcome/blocker notifications using the
  existing process notification channel, acknowledged by the owning turn and
  recoverable after restart; retained reports remain authoritative.
- `job_routes.py`: immutable source destinations and resume-lineage ownership.
- `polling_display.py`: profile- and chat-scoped latest-five foreground updates.
- Native registration and MCP entry points wait in the current call without
  attaching monitors or task checkpoints. The native status tool declares
  `manages_timeout=True`; the executor keeps its wait sequential and interruptible.
  The legacy continuation permission guard remains registered for explicitly
  resumed older workers. New conversations receive the foreground instructions;
  existing cached prompts are not rewritten.

Focused regression checks:

```bash
scripts/run_tests.sh tests/plugins/test_boltzmann_foreground.py \
  tests/plugins/test_boltzmann_job_monitor.py \
  tests/plugins/test_boltzmann_job_delivery.py \
  tests/plugins/test_boltzmann_job_display.py \
  tests/plugins/test_boltzmann_authorization.py \
  tests/agent/test_api_request_tool_scope.py
```

The broader connector checks also cover upload receipts, contracts, enzyme
validation, MCP argument forwarding and distributed NetSolP modes. Optional
Gemmi/RDKit-dependent checks require those dependencies in the test interpreter.
