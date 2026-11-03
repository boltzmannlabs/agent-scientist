# Boltzmann connector for Agent Scientist

The custom Agent Scientist distribution includes this connector, **not a credential or a subscription**.
The CLI setup command is available even when this plugin is not enabled in a profile.
Seeing `/add_boltzmann` does not authorize any scientific tools. Successful explicit setup enables
only Boltzmann, preserving unrelated plugin selections.

In the interactive CLI, run `/add_boltzmann` (case-insensitive). Enter the key in the masked prompt,
not as an argument or a chat message. Validation makes one read-only request to
`https://nodeapis.boltzmann.co/api/get-projects`, with a 15-second timeout and no redirects.
On success the key is saved through Sci credential storage in the active profile; a
profile-and-key-bound activation receipt contains only a hash. No job is submitted by setup.

Restart `agent-sci` after success. All five operations (submit, status, download, upload,
fetch-tool-log) are enabled together. The ordinary setup command does not mutate the current
conversation's tools, skills, or prompt. Existing `--now` explicitly opts into immediate refresh
for native profiles. Legacy isolated science profiles always defer activation until the next
session; their reviewed policy adds only the five Boltzmann operations, with per-call external
access approval. Local sandbox restrictions and pending local setup remain unchanged.
Missing, changed, removed, rejected, or revoked credentials block execution, including
status reads and signed-file downloads. Service outages also fail closed. A saved key alone
does not authorize the connector: `/add_boltzmann` must complete in each owning profile.

The optional stdio MCP adapter uses the same gate. It must run with the owning profile's
`SCI_HOME` and the Sci runtime with MCP support. Nothing here creates a remote MCP
service or copies credentials into isolated scientific project containers.

This is application-level gating, not a sandbox against someone who can edit local Python or
state files. The Boltzmann service remains responsible for actual account permissions and billing.
Other independent MCP servers are responsible for their own authentication.

The connector was brought forward from this project's existing local Boltzmann plugin.
Its prior workflow helpers and schemas are preserved; authorization and profile isolation were
updated. No private `.env`, configuration, API keys, results, or local sample data are bundled.

## Packaged workflow knowledge

The authorized `boltzmann:tools` skill includes the canonical job catalog,
request/file/limit definitions, generated scientific modules, diagnostic mappings and the
optional peptide conversion script. These files ship with Git checkouts and
Python package data; no private local plugin directory is needed. They are
instructions and contracts, not additional model tools or installed scientific
runtimes. The same five tools execute jobs.

Read `skills/boltzmann-tools/DISTRIBUTION.md` for provenance, sanitization,
historical verification limits, and excluded private/maintenance material.
Installing this knowledge never grants access: authorization remains profile-
and-key-bound, and every operation revalidates against the service.

## Scientific execution routing

Inventory questions such as "what Boltzmann tools do we have" use the installed
job catalog through `boltzmann:tools`, showing scientific display names by
domain and module rather than the five connector operations. All-tools requests
list active catalog entries; entries without an established executable request
are listed separately with their missing information. Listing requires no scientific job or upload.
Catalog membership does not establish account entitlement or execution readiness.
This guidance is loaded in a fresh conversation; existing cached prompts remain
unchanged. Helper descriptions are reserved for explicit integration questions.

For an authorized profile, the plugin supplies a session-frozen prompt section
that points to `boltzmann:tools` before generic generation skills. Plugin skills
are intentionally absent from the ordinary system-prompt skill index; deferred
tools remain discoverable through the existing tool-search bridge. This policy
does not add a core tool, perform a network check, or rebuild a live prompt.

Matching verified scientific workflows use Boltzmann by default. Missing inputs
need clarification; missing session tools need setup/restart guidance. Failed
authentication or blocked contracts do not authorize a silent local/other-provider
fallback. Alternative scientific execution requires an explicit request or informed
approval. Random-antibody generation must use the installed antibody contract and
report actual heavy/light output counts; it must not promise 20 pairs merely
because 20 samples were requested. These are model-routing instructions, not an
OS sandbox or a guarantee that an arbitrary model obeys every instruction.

Existing user-installed plugins with the same name can override the bundled
plugin. Inspect the discovered plugin location when updating an existing
machine; do not overwrite a user's plugin automatically. Fresh installations
without an override use this repository's bundled connector.

## Upload validation receipt storage

Upload evidence lives in `<SCI_HOME>/plugin-data/<Boltzmann namespace>/upload-receipts-v1/`,
separate from the 10 MiB `state.json` settings/authorization file. The directory uses mode
0700 and records mode 0600 on POSIX; Windows installations should keep their SCI home under
their private user account. File writes use fsync and atomic replacement, with a shared
thread/process lock. Profiles have separate stores; receipt content and authorization
fingerprints are never shared by this storage layer.

The explicit limit is **256 MiB of committed and reserved receipt/attempt files per profile**.
A validated upload reserves a padded on-disk slot, sized from its complete evidence plus
bounded response metadata, **before uploading**. A new submission reserves its job-tracking
record before contacting the service. Concurrent requests cannot oversubscribe the quota.
Atomic replacement temporarily needs another copy of the record being written; keep disk
headroom (up to one additional record, bounded by the store limit). Upload reference and job-ID
metadata are bounded to 16 KiB of JSON each. A later disk failure or invalid service response
can still prevent finalization; this is reported as a partial/unknown outcome with the protected
reservation ID, not as success or permission to upload/submit again.

Old `upload:*` entries migrate automatically on receipt use. Every destination is durably
written before the old keys are atomically removed under the existing plugin-state lock.
Authorization and unrelated values remain in `state.json`. Interrupted migrations resume by
verifying already-copied evidence; conflicts, malformed state, or quota failures stop with
guidance and preserve the source. Never delete `state.json` to free receipt capacity.

### Retention and safe maintenance

- Successfully uploaded, never-submitted receipts are retained for **30 days**.
- Submission attempts pin their input receipts before the request. Running jobs, ambiguous
  submissions, missing job IDs, timeouts, and interrupted uploads do not expire automatically.
- Once **all linked jobs** have confirmed terminal responses, receipts remain reusable for
  **30 days after the last terminal observation**. Repeated terminal polls do not restart that
  clock. Reusing a receipt for another submission pins it again. HTTP/authentication failures
  and polling timeouts are not terminal-job evidence.
- Migrated receipts have unknown historical job links and stay protected indefinitely. A new
  job finishing does not prove their old jobs finished. Inspection identifies these records;
  reconcile old or ambiguous jobs with support rather than deleting their evidence.
- Cleanup runs on upload admission and after status bookkeeping, or explicitly using the command
  below. There is no background service or silent network polling. It deletes only eligible
  receipts and then unreferenced terminal-attempt records. Cleanup failure is reported; already
  completed atomic steps are not described as rolled back. A failed cleanup does not turn a
  retrieved job result into a failed scientific job.

From the desired active profile (or with `sci -p PROFILE`):

```bash
sci boltzmann-receipts status
sci boltzmann-receipts migrate
sci boltzmann-receipts cleanup
```

`status` reports the directory, used/allowed bytes, migration backlog, reservation and job IDs,
retention deadlines, and protection reasons. It does not expose credentials or validation
inventories. These commands make **no service requests** and do not delete remote uploads.
If the plugin's CLI command is unavailable, the source installation also supports
`python -m plugins.boltzmann.receipt_cli status` in its managed Python environment with the
intended `SCI_HOME`. Do not run it against another profile's directory.

When full, inspect the store, poll known outstanding jobs through the normal authorized status
tool, and clean up eligible expired records. If space is still unavailable because records are
protected or inside retention, stop new uploads and reconcile the unresolved work; do not bypass
validation, delete protected records, or repeatedly upload the same input. After an update,
restart processes using the old connector before resuming work so old code cannot keep writing
legacy receipts into `state.json`.
