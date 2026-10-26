# Durable Boltzmann tool-log lookup

This protocol is for `platform_tools` only. It does not alter Omics routing,
Omics checkpoints, conversation memory, or the existing workflow logger.

## Two status sources

1. `boltzmann_status` (the `fetch_status` helper) polls the live Boltzmann
   result endpoint. Its `(job_name, doc_id)` pair and returned terminal status
   are authoritative for the current state of the submitted job.
2. `boltzmann_fetch_tool_log` reads one durable MongoDB document to explain a
   terminal result. It is useful for the platform's recorded error/message,
   output metadata, timing, billing, and other persisted details. It is not a
   replacement for live polling and it never submits, updates, searches, or
   retries a job.

When `boltzmann_status` receives a terminal `failed` or `error` response,
summarize its sanitized diagnostic. If more detail is needed and a verified
documented collection mapping exists, explicitly call the read-only log helper. Do not
claim an automatic durable lookup occurred when no such call was made.

### Live status diagnostics

The status result preserves the service's `status`, `info` (including nested
`info.info` and the traceback in `info.message`), and top-level `message` when
present. Credentials and diagnostic URLs are redacted, not stack frames or
exception descriptions. Use these diagnostics to explain the failure; do not
claim that reporting a traceback repairs the worker.

The result endpoint can return documented `running` or `failed` job dictionaries
with HTTP 404. Those recognized bodies retain their job state. HTTP codes are
not included in the agent-facing status result. Authentication failures and
unrecognized, malformed or missing responses still mean the job outcome could
not be checked, not a fabricated failure or success.

Polling retains the original service message. If its window expires, `timeout`
and `polling_message` explain the polling limit separately; keep tracking the
same `job_name` and `doc_id`, never automatically resubmit the scientific job.

### Submission and upload errors

Service errors also preserve returned `info`, including `info.info` and the full
traceback in `info.message`, plus top-level `message` and validation `detail`.
Credentials and diagnostic URLs are redacted; HTTP status codes are not part of
the agent-facing error dictionary. Missing diagnostics stay absent: never claim
a traceback was returned when the backend supplied only a short message.

For submission errors, `status: unknown` describes the unconfirmed job outcome.
`service_status`, when present, preserves the service response's own status;
it is not evidence that a scientific worker ran or that no job was created.
For example, `Failed to calculate credits` identifies the reported service stage,
not the exact cause, insufficient balance, or a completed CatPred negative test.
Without a job ID, reconcile the attempt rather than fetching an invented ID or
automatically submitting again.

## Endpoint contract

The documented operation is `POST /v5/tools/mongodb_fetcher`. The API's
OpenAPI contract (operation `read_mongodb_v5_tools_mongodb_fetcher_post`)
requires exactly these JSON fields:

```json
{
  "collection": "<exact collection name>",
  "experiment_id": "<exact document/experiment id>"
}
```

`/v4/tools/mongodb_fetcher` is retained as a compatibility route. The adapter
uses v5 by default and allows an operator-provided
`BOLTZMANN_MONGODB_FETCHER_URL` override without changing skill instructions.

## Safe invocation

Use the registered `boltzmann_fetch_tool_log` tool only after the current
conversation contains an accepted submit/workflow record with the exact job
name and document ID. Pass `job_name` and `experiment_id`; the handler resolves
the collection from the selected entry's `diagnostics` in
`references/tool-contracts.v1.json`. Only exact-job `source_documented` or
`matched` records participate. Source-only and superseded historical candidates
are not mappings. Missing or conflicting mappings stop this diagnostic lookup,
not ordinary status polling, and do not establish that a job failed.

For example, `Random_Antibody_Generation` resolves to `AB_GEN`, not to a
collection named after the job. These are documented mappings, not a claim of
current service availability. Never test alternative collections to find a job.
Resolve the ID from the immediate submit response or the current conversation's
workflow record; do not invent it or reuse a historical sample ID.

If the selected module gives a durable collection that differs from the
submission job name, the resolver preserves that exact collection (for example,
`equidock` for Vina score-only). Existing callers may still supply a verified
`collection` explicitly; supplying both requires a match. The submission job
name must still be used for live `boltzmann_status` polling.

The handler obtains credentials from the active profile. Never put credentials,
raw Mongo documents, or signed download URLs in user-facing text. Summarize only
the relevant diagnostic; do not assume arbitrary returned documents are redacted.

## Reconciliation and failure semantics

- Live `fetch_status` wins when its state disagrees with a durable document.
- A durable document enriches the explanation; it does not turn a missing
  document into a scientific failure.
- `not_found` means no document was returned for that exact pair.
- `unreachable` or `unauthorized` means the lookup could not be checked;
  report that limitation and preserve the live status.
- `malformed`, `error`, or `invalid_request` must be summarized as a lookup
  problem and must not be presented as a fabricated tool result.

The lookup is intentionally read-only and bounded to one exact pair per call.
