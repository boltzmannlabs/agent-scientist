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
