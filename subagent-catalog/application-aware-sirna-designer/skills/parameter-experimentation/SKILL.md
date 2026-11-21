---
name: parameter-experimentation
description: Use when choosing, configuring or tuning native siRNA tool/model parameters, or when asked for the best combination of settings.
version: 1.0.0
author: Agent Scientist
license: MIT
---

# Source-grounded parameter experimentation

Turn "find the best settings" into a reproducible, evidence-backed search. Never answer from remembered defaults.

## 1. Go to the source first

Locate the approved source root from the assignment (setup report, provider decision, source permission record).
Extract the real parameter surface before proposing anything:

- CLI tools: run `<binary> --help` (file-based; capture output to your workspace) and read the argument parser in source.
- Python models: read `__init__` signatures, config modules (e.g. `sirna_env/config.py`), thresholds JSON, runner scripts.
- R/native runners: read the header usage block and `commandArgs` / environment variables.

Record a parameter sheet artifact: parameter name, type, range, default, source file and symbol/line, and whether it is
frozen by contract (gates, vetoes) or experimentally tunable. {{resource.references/parameter-catalog.md}} seeds known
entries; verify each against source and record corrections.

## 2. Freeze the experiment frame

Before running anything: the input fixture (native fixture record), the acceptance metric from the frozen gate
manifest, the budget (max configurations, wall-clock), and the output root. Tuning on labels you will report is
forbidden: freeze or split first under the benchmark policy.

## 3. Run combinations file-based

One job per configuration. Write driver scripts to files in your workspace (never inline `-c`/`-e`). Capture for every
configuration: exact command, exit code, stdout/stderr tail, metric values in native units. Accumulate a results table
(CSV or JSON) as you go, so an interrupted sweep still yields partial evidence.

## 4. Vary deliberately

Prefer one surface at a time with the rest fixed (context window, top-k, weights, thresholds), then targeted
interactions between the two best axes. Frozen thresholds may tighten, never loosen. Respect declared budgets; stop and
report partial coverage rather than overrun.

## 5. Report honestly

Best combination with its evidence trail, negative results, failed configurations, and parameter-sheet corrections.
Distinguish exploratory tuning from validated performance. A tuned combination is configuration evidence, not a new
model claim, and never establishes clinical safety or potency.

Read [source verification checklist](references/source-verification.md).
