---
name: parameter-experimentation
description: Use when choosing, configuring or tuning native CRISPR tool/model parameters, or when asked for the best combination of settings.
version: 1.0.0
author: Agent Scientist
license: MIT
---

# Source-grounded parameter experimentation

Turn "find the best settings" into a reproducible, evidence-backed search over the retained CRISPR environment.
Never answer from remembered defaults.

## 1. Go to the source first

Locate the approved source root from the assignment (environment root, prior-run base, setup report). Extract the real
parameter surface before proposing anything:

- R runners: read the header usage block, `commandArgs(trailingOnly=TRUE)`, environment variables (`CRISPR_PRIOR_BASE`)
  and thread pins.
- Python models/scorers: `__init__` signatures, argparse blocks, config modules, checkpoint metadata.
- Request contracts: `priorities.weights`, `priorities.hard_vetoes`, `priorities.min_standards` in the versioned
  request schema.

Record a parameter sheet artifact: name, type, range, default, source file and symbol, and whether frozen by contract
(vetoes, min_standards, endpoint context lengths) or experimentally tunable.
{{resource.references/parameter-catalog.md}} seeds known entries; verify each against source and record corrections.

## 2. Freeze the experiment frame

Before running: input fixture, acceptance metric from the request's priorities/min_standards, budget (max
configurations, wall-clock), output root. Tuning on labels you will report is forbidden: freeze or split first under
the benchmark policy.

## 3. Run combinations file-based

One job per configuration; driver scripts written to files in your workspace (never inline `-c`/`-e`). Capture exact
commands, exit codes, log tails and metric values in native units into a results table as you go, so an interrupted
sweep still yields partial evidence. Keep the pinned thread settings and interpreter profiles of the retained recipe.

## 4. Vary deliberately

One surface at a time with the rest fixed (region flank, endpoint choice, weights, inference batch size), then
targeted interactions between the two best axes. Never merge the separate interpreter profiles. Respect budgets;
report partial coverage rather than overrun.

## 5. Report honestly

Best combination with its evidence trail, negative results, failed configurations, parameter-sheet corrections.
A tuned configuration is configuration evidence, not a new model claim, and never establishes editing safety or
clinical readiness.

Read [source verification checklist](references/source-verification.md).
