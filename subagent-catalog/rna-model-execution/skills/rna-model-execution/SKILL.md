---
name: rna-model-execution
description: Use when a ModelIntegrationSpec must be installed into an isolated environment, have its checkpoints verified, be executed for real inference, and registered with honest evidence.
version: 1.0.0
author: Agent Scientist
license: MIT
---

# RNA model execution procedure

## 1. Preflight the approvals

Before touching anything: spec path, fresh destination prefix, egress/install authorization naming sources, output
root, registry path. The packaged preflight states what is missing. Unapproved steps become BLOCKED stages carrying
the exact command awaiting approval — never skipped, never sourced elsewhere.

## 2. Isolate

Fresh venv/conda prefix (or approved container) at the parent-approved destination; fresh `git clone` at the spec's
exact commit (record the resolved commit hash). Never install into an existing prefix, SCI, or a shared interpreter.
Capture the install receipt (pip freeze / conda list equivalent) as a file. Failure keeps the partial state with a
resume hint.

## 3. Verify checkpoints

Download only from the spec's declared URLs. Verify against the spec's checksums (sha256 preferred). Record per
artifact: URL, retrieved-at, size, algorithm, expected vs observed, outcome (VERIFIED / MISMATCH / MISSING /
NO_CHECKSUM_PUBLISHED). MISMATCH or MISSING is a BLOCKED stage — random or partial weights are never a fallback.

## 4. Execute inference for real

Validate inputs against the spec's input schema first. Run the spec's official inference instructions; when the
interface class needs an adapter, write a thin file-based adapter in your workspace and record its path. Capture
per-record outcomes (input id → output, success/failure, runtime) into an output manifest. Never claim inference
that was not executed; never fill failed records with placeholders.

## 5. Validate outputs mechanically

Schema-check outputs against the spec's output schema; apply stated sanity bounds. Record per-check PASS/FAIL/NOT_RUN
in validation_results. Mechanical success is not biological validity — no benchmark or superiority language.

## 6. Report and register

Emit the ExecutionReport, validate it ({{resource.scripts/validate_report.py}}, exit 0 required), then advance the
registry with {{resource.scripts/registry.py}}: INSTALLED requires the environment receipt; EXECUTION_TESTED requires
the report with COMPLETED/PARTIAL inference; BENCHMARK_VALIDATED requires parent-supplied labels and a frozen
protocol; PRODUCTION_APPROVED only with an explicit parent directive quoted in the note. Adjacent transitions only;
failures leave the entry at its last true state.

Read the execution discipline contract at {{resource.references/execution-discipline.md}} and
[interface adapters](references/interface-adapters.md).
