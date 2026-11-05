# Boltzmann queued jobs and durable monitoring

A queued job is not a failed job. The result endpoint sometimes uses HTTP 404
for documented `pending`, `running` and `failed` bodies. The connector accepts
those states only with a usable message or information body. Authentication
failures, malformed responses and missing routes remain status-check errors.
Other terminal states on HTTP 404 require matching job identifiers as well as a
usable body; a generic `status: error` missing-route response is not a failed job.

## Waiting and results

Native SCI and the bundled MCP adapter save monitors for accepted jobs and jobs
checked through `boltzmann_status`. A tool call uses a short result-check window
(30 seconds; the separate authorization check has its existing 15-second timeout).
The background worker normally checks every 30 seconds. Check failures back off
up to 15 minutes, preserving the same job ID. There is **no overall queue/running
deadline**. This avoids the agent executor's generic deadline and the plugin's
outer safety deadline interrupting a long scientific wait.

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
a supported setting. Native/MCP monitoring no longer depends on per-tool runtime
estimates or repeated long status calls.

## Inspect, stop and resume

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

Workers survive closing a terminal. No process can poll while the host is off;
saved monitoring restarts when the owning SCI session starts, or through
`sci boltzmann-jobs resume`. The live-session watcher also restarts a worker whose
lease has expired. This feature does not install an operating-system boot service.

## Approved workflow continuation

Native conversations checkpoint the task, recent user/assistant context, source
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
  existing process notification channel; retained reports remain authoritative.
- Native registration, MCP entry points and tool descriptions attach monitoring
  without adding a core model tool. The generic `pre_api_request` observer adds
  `available_tool_names`; it does not modify the model request or cached prompt.

Focused regression checks:

```bash
scripts/run_tests.sh tests/plugins/test_boltzmann_job_monitor.py \
  tests/plugins/test_boltzmann_authorization.py \
  tests/agent/test_api_request_tool_scope.py
```

The broader connector checks also cover upload receipts, contracts, enzyme
validation, MCP argument forwarding and distributed NetSolP modes. Optional
Gemmi/RDKit-dependent checks require those dependencies in the test interpreter.
