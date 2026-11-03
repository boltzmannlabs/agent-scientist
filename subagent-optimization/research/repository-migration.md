# Repository migration — 3 November 2026

Current project: [agent-scientist/subagent-optimization](https://github.com/boltzmannlabs/agent-scientist/tree/subagent-optimization/subagent-optimization).
Tracking: [agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33).

The user authorized transfer from `BOLTCHEM-FEATURES/subagent-optimization`, issue
[agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33),
including the latest local development, followed by deletion of the old remote branch.
The source snapshot starts at commit `4f94947e` and includes the current uncommitted
specialist and public-source library preparation files: 73 files, 439,492 bytes.
A separate local backup preserves their pre-migration contents and SHA-256 manifest.

Only repository location, tracking links and migration documentation are updated.
Prototype code, specialist definition, dated results and scientific source hashes
are preserved. Historical descriptions of unpublished working sources remain dated
provenance; they do not describe the current publication state. This focused branch
contains only `subagent-optimization/`, with normal ancestry and no force push.
Main branches, the empty BOLTCHEM-FEATURES `Boltchem` branch and local native
connector changes are outside this migration.

The reusable environment remains in `science-environments/BoltChem`, tracked by
[science-environments#46](https://github.com/boltzmannlabs/science-environments/issues/46).
This move adds no scientific validation, real-profile installation or model calls.

## Migration verification

The 73-file source snapshot was stable on repeat hashing. Prototype code, specialist
configuration and dated evidence were preserved byte-for-byte; nine Markdown files
received location/tracking updates and this record was added. All JSON parsed and
local documentation links resolved. No credential patterns or oversized files were
found. CSV CRLF bytes were retained to preserve their recorded source hashes.

Portable checks passed: 32 policy, 43 context, 20 optional RDKit intake and 10
advisor checks, run in a disposable copy without rewriting the dated records.
Both coverage-planning checks also passed (107 portable checks total).

A fresh native canary through the host's official test runner collected two tests:
the disabled-definition import check passed, then the child-runtime check exceeded
the 180-second file timeout. This is an incomplete run, not a passing suite. The
runner's optional bytecode precompilation was separately terminated after stalling
so targeted tests could start. The earlier two-test passing record is retained as
historical evidence; the migration does not establish a fresh native-runtime pass.
No implementation changes or real model/scientific requests were made to address
this runtime issue during the repository transfer.
