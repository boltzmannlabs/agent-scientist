# RNA model discovery and integration specialist

Portable SCI leaf package, version 1.0.0. Finds and evaluates open-source RNA models/tools for missing workflow
capabilities and produces schema-validated ModelIntegrationSpecs. It never installs, executes or benchmarks;
execution belongs to `rna-model-execution`.

## What it does

- Classifies the biological task and states the exact capability gap.
- Checks the shared registry first (reuse before rediscovery).
- Searches approved source families (GitHub, Hugging Face, PubMed, Europe PMC, bioRxiv, Zenodo, official docs,
  bioinformatics repositories) **only under parent search/egress authorization**.
- Verifies pretrained-weight availability per candidate (WEIGHTS_PUBLIC / WEIGHTS_RESTRICTED / NO_WEIGHTS) with
  citations; NO_WEIGHTS models are never inference-ready.
- Evaluates candidates on evidence-attached multi-criteria (never accuracy alone) and ranks them.
- Emits a ModelIntegrationSpec v1 validated by the packaged CLI, and registry directives limited to
  DISCOVERED → EVIDENCE_REVIEWED → WEIGHTS_AVAILABLE.

## Layout

manifest.yaml · instructions.md (leaf contract incl. execution-environment/tool-call discipline) ·
skills/rna-model-discovery (procedure + evaluation criteria + source families) ·
references (ModelIntegrationSpec schema, shared registry schema, evidence rules) ·
scripts (request_contract preflight, validate_spec, shared registry CLI, SCI schema probe, package validator) ·
tests (metadata fixtures, synthetic spec, invalid spec, unit tests incl. registry state machine).

## Verification

    python3 -B tests/test_contract.py
    python3 -B scripts/validate_package.py --sci-source <sci-checkout> --sci-python <sci-python>

## Install

    /subagent package install "<this directory>"

Review tools, the optional python_core binding and references; then /new and route assignments by name.
Note: packaged files deliberately contain no absolute URLs or machine paths (SCI package scanner policy); specs
produced at run time carry real URLs and citations in run artifacts, not in this package.
