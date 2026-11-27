---
title: "Cheme As Code — Calculate, validate and draw chemical process designs"
sidebar_label: "Cheme As Code"
description: "Calculate, validate and draw chemical process designs"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Cheme As Code

Calculate, validate and draw chemical process designs.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/science/process-engineering/cheme-as-code` |
| Version | `1.2.0` |
| Author | Gopi Krishna; Sci Agent |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `chemical-engineering`, `flowsheets`, `material-balances`, `process-design` |
| Related skills | [`reaction-draw`](../../bundled/science/science-chemistry-reaction-draw.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Sci loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# ChemE-as-Code Skill

Create and assess chemical process projects with the managed ChemE-as-Code CLI.
Use engineering files, calculations and diagrams to explain process behaviour;
keep design maturity, numerical consistency and experimental evidence distinct.

## When to Use

Select for process flowsheets, material or energy balances, manufacturing process
studies, P&IDs, equipment studies and process economic or environmental assessments.
The user does not need to name this skill. For a molecular reaction mechanism use
`reaction-draw`; use the existing retrosynthesis tools for synthesis route planning.
Connect their results to a process only when the user requests process engineering.

## Prerequisites

Use `terminal` to invoke `sci cheme`; no new core tool, Boltzmann key or extra LLM
is needed. `sci cheme --check-env` probes installed dependencies without installing.
If missing, `sci cheme --setup` prepares a locked, isolated runtime through Sci's
package manager. Respect an installation refusal and explain missing capabilities.

The runtime includes diagram rasterization, property libraries, units and the
read-only API dependencies. Use `sci cheme --check-backends` to check optional
components. `--setup-viewer` builds the pinned interactive Viewer;
`--setup-idaes` prepares IDAES/IPOPT; `--setup-dwsim` builds the pinned Docker image
and requires Docker. Setup runs only when the task requires that component.
Licensed datasets remain separate. Do not infer numerical readiness from
`--setup` alone. Read references/capabilities.md (source checkout: `skills/science/process-engineering/cheme-as-code/references/capabilities.md`)
when a task needs simulation, interactive viewing or an assessment.

## How to Run

Use `read_file`, `write_file` and `patch` for task-owned engineering files, and
`terminal` for the managed command. `--project` chooses an existing working folder;
arguments after `--` are passed to the upstream CLI without shell interpretation.

```text
sci cheme --check-env
sci cheme --setup
sci cheme --check-backends
sci cheme --setup-viewer
sci cheme --setup-idaes
sci cheme --setup-dwsim
sci cheme --project PROJECT_DIR --viewer --port 8765
sci cheme -- --help
sci cheme -- init PROJECT_DIR --name "Process study"
sci cheme --project PROJECT_DIR -- schema process-flowsheet
sci cheme --project PROJECT_DIR -- validate --json
sci cheme --project PROJECT_DIR -- process propagate --fill --json
sci cheme --project PROJECT_DIR -- process streams --json
sci cheme --project PROJECT_DIR -- process build
sci cheme --project PROJECT_DIR -- render process/BFD.xml process/PFD.xml --png
sci cheme --project PROJECT_DIR --chat-diagrams
```

Replace PROJECT_DIR with the actual workspace path. Keep each command's exit
status and inspect its findings. Read-only checks and calculations can report
incomplete information; explain it before proceeding. Do not change engineering
inputs just to silence findings. Check upstream help for command-specific flags.

## Quick Reference

| Need | Resource or command |
|---|---|
| First analytical example | `templates/mixer/plant.yaml` and `templates/mixer/process/*.yaml` |
| Schema and command discovery | `sci cheme -- schema`, `sci cheme -- process --help` |
| Stream mapping and balances | `process streams --json` |
| Derive supported missing flows | `process propagate --fill --json` |
| BFD/PFD files and images | `process build`, then `render --png` |
| Evidence and report format | references/reporting.md (source checkout: `skills/science/process-engineering/cheme-as-code/references/reporting.md`) |
| Optional capabilities | references/capabilities.md (source checkout: `skills/science/process-engineering/cheme-as-code/references/capabilities.md`) |
| Interactive project inspection | `sci cheme --project PROJECT_DIR --viewer` |
| Numerical simulation | `process simulate --fill`, backend in `process/simulation.yaml` |

## Procedure

1. Explain the objective, required outputs and acceptance criteria. Establish
   feed composition and basis, throughput, units, operating conditions, reaction
   data, target purity or recovery and study boundaries as relevant. Ask specific
   questions for essential missing inputs; propose assumptions for approval when
   needed. Never silently import demonstration values into a real project.
2. Create a task-owned project with `init`, or inspect an existing project's
   `plant.yaml`. Use the command's schemas and upstream project skills as technical
   references, adapting their CLI examples to `sci cheme`. Agent Scientist remains
   the orchestrator; there is no need to launch the upstream agent runner.
3. Record components, flowsheet connections, cases, input units and provenance.
   Label each value given, assumed or calculated with its actual source. Save
   baseline inputs before edits. The bundled mixer is a synthetic analytical
   example: 100 kg/h ethanol plus 300 kg/h water should produce 400 kg/h at 25%
   ethanol by mass. It establishes mass conservation, not mixing heat or volume.
4. Validate inputs, calculate with the supported model, and inspect stream and
   balance findings. Identify missing model coverage and any balance residuals.
   A successful propagation is not evidence of a thermodynamic flowsheet solve.
   For numerical simulation, check backend readiness and supported compounds,
   units and property packages first. Keep the generated simulation-run JSON:
   it records convergence, provenance, inputs and energy-closure limitations.
   Check total/component balances and mole-fraction sums against the stated
   study tolerances independently of convergence. A converged shortcut-column
   result can still miss strict mass/composition criteria. Report such a case
   as a qualified model result; do not silently normalize it or call it validated.
5. Generate diagrams from the same inputs and render PNG/SVG. Pass generated
   process XML paths explicitly to `render`; its default selection covers P&IDs
   only, and `--png` writes PNG instead of SVG. Run without `--png` for SVG. Preserve source YAML
   and DEXPI XML for edits. Save stream and validation JSON plus a Markdown report
   in the project's `build/` folder using the normal file tools. Follow
   references/reporting.md (source checkout: `skills/science/process-engineering/cheme-as-code/references/reporting.md`) for interpretation and delivery.
   Before delivering diagrams in chat, run `sci cheme --project PROJECT_DIR --chat-diagrams`.
   Display the resulting `BFD-chat.png`, `PFD-chat.png` and available
   `PFD-streams.png`: focused, enlarged exports from the same vector drawings.
   Keep full-sheet engineering diagrams as downloads. Inspect label spacing;
   dense multi-unit flowsheets may still need upstream `render --tiles` detail views.
6. For a requested comparison, preserve baseline and candidate cases or folders,
   apply the same model and criteria, and compare like quantities with the same
   units. Seek permission before starting an optimization beyond the requested
   calculation. Report the supported best candidate and unresolved requirements.

## Pitfalls

- Do not infer kinetics, conversion, separations, costs or utilities from a
  reaction equation alone. Missing information is `Not Available`.
- A valid schema or passing drawing check does not demonstrate engineering
  feasibility, plant safety, regulatory compliance or experimental validation.
- A conceptual process library entry is reference material with its own evidence
  status; cite its revision and attribution before reusing it.
- Generated engineering diagrams and balances do not replace human design review
  or an accepted HAZOP. Never fabricate sign-offs to advance a design stage.
- Preserve existing project edits; do not use upstream `--force` to overwrite them
  without the user's authorization. Keep raw logs out of the chat explanation.
- If `sci cheme` is absent, report the installation mismatch. Do not silently
  substitute hand-drawn diagrams or manual calculations and attribute them to
  ChemE-as-Code. Native package calculations remain the source of process results.
- The Viewer binds localhost by default. For an SSH user, explain port forwarding
  and provide the browser URL; the remote server cannot open the user's browser.
  Start a Viewer only for requested interactive viewing and stop test servers.

## Verification

Check exit codes, validation findings, numerical residuals, model applicability
and output files. View generated images with `vision_analyze` when available;
report unavailable visual inspection honestly. Include a purpose and plain-language
interpretation beside every result, and label predictions awaiting confirmation
`Experimental validation pending`. Deliver the images with `MEDIA:` references
and attach the saved report so the user can inspect both the design and evidence.
