# RNA model execution and inference specialist

Portable SCI leaf package, version 1.0.0. Turns a ModelIntegrationSpec into an isolated, verified, actually-executed
inference capability, and advances the shared registry with honest evidence. It never discovers models and never
claims biological validity from mechanical success.

## What it does

- Preflights approvals (spec, fresh destination, egress authorization, output root, registry path); unapproved steps
  become BLOCKED stages carrying the exact pending command.
- Installs into a fresh venv/conda prefix (or approved container) from a pristine clone at the spec's commit; never
  touches SCI or existing environments; keeps resumable receipts.
- Downloads checkpoints only from spec URLs and verifies checksums (VERIFIED / MISMATCH / MISSING /
  NO_CHECKSUM_PUBLISHED per artifact); never substitutes random or partial weights.
- Executes real inference through the official path (thin file-based adapters by interface class when needed);
  captures per-record outcomes and preserves input-to-output mapping.
- Validates outputs mechanically against the spec's schemas; emits a schema-validated ExecutionReport v1.
- Advances the registry INSTALLED → EXECUTION_TESTED → BENCHMARK_VALIDATED (evidence-gated, adjacent-forward);
  PRODUCTION_APPROVED only with an explicit parent directive quoted.

## Layout

manifest.yaml · instructions.md (leaf contract incl. execution-environment/tool-call discipline) ·
skills/rna-model-execution (procedure + interface adapter rules) ·
references (ExecutionReport schema, shared registry schema, execution discipline) ·
scripts (request_contract preflight, validate_report, shared registry CLI, SCI schema probe, package validator) ·
tests (metadata fixtures, synthetic/invalid reports, unit tests incl. execution-side registry transitions).

## Verification

    python3 -B tests/test_contract.py
    python3 -B scripts/validate_package.py --sci-source <sci-checkout> --sci-python <sci-python>

## Install

    /subagent package install "<this directory>"

The shared registry CLI (scripts/registry.py) and registry schema are byte-identical copies with
rna-model-discovery; keep them in sync when either changes.
