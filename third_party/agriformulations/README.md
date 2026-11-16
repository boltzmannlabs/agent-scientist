# Bundled AgriFormulations wheel

`sci_agriformulations-1.3.0-py3-none-any.whl` is installed by Agent Scientist's
normal dependency setup. `pyproject.toml` declares the exact version and a local
wheel source; `uv.lock` records the resolved dependencies. No plugin, separate
activation, package registry or Boltzmann science service is required.

The three agricultural skills under `skills/science/agri-*`, together with
`skills/science/formulation-results`, guide recipes, automatic
objective-based model selection, grade/supplier/material cost optimization, 21 model
keys, fitting/data, research and results. The catalogue also exposes an initial
analytical wettability entry; it remains pending scientific verification. Design /
AI + Physics is offered after recipe creation.
Normal installation/update seeds them through the existing bundled-skill sync.
Users' existing skill opt-outs and user-edited skills retain normal Sci behavior.
Start a new conversation after installation or update.

## Availability across profiles

The formulation package is a shared installation dependency. All four bundled
skills (`agri-formulation-workflow`, `agri-models-and-design`,
`agri-evidence-and-data`, `formulation-results`) are available by default in every
normally created profile. Existing profiles receive bundled updates through the
normal all-profile skill sync during `sci update`. Creating a profile does not
require a separate formulation package installation or plugin activation.
Profiles retain separate projects, drafts and results. Explicit skill disabling
and `--no-skills` creation remain intentional user overrides. Start a new chat
after skill updates so cached conversations load the new instructions.

## Running the package

Ask Sci a formulation question. The agent reads the relevant skill, writes one
JSON request file, and uses the existing `terminal` tool:

```sh
sci --run-module agri_tool --request-file /absolute/path/request.json
```

This launcher selects Sci's installed Python. An initial request can be:

```json
{"operation":"catalogue","action":"operations","payload":{}}
```

After recipe creation, the agent shows saved recipes and recommended scenarios,
then asks DESIGN / AI + PHYSICS DESIGN / NOT NOW through native clarification.
Both selected modes collect reviewed inputs before Run; missing prices do not
suppress the choice. An explicitly selected mode goes straight to input review.

Inside explicitly requested automatic campaigns, the agent chooses and
runs every applicable simulation needed by its objectives and criteria. It compares
grade, supplier, ingredient-combination and parameter alternatives with the saved
baseline, and minimizes total production cost subject to maintaining or improving
required performance. It asks only for essential missing inputs or assumption
permission; no mandatory mode-choice or Run menu interrupts this automatic path.
Unsupported material-property mappings, missing quotes and unassessed criteria
remain visible and cannot establish a proven product improvement.

The existing `cost/compare` package action joins actual saved recipes, cost records
and simulation IDs. It enforces the same active loading/batch/currency/test basis,
keeps failed or incomplete iterations, computes grade contributions, cost savings,
performance deltas and Pareto options, and retains the cheapest feasible evaluated
option including the unchanged baseline. It saves a comparison identity and returns
JSON/CSV artifacts. PDF/ZIP exports include a dedicated baseline/grade/performance
section, a cost chart and machine-readable comparisons. Cost estimates depend on
supplied prices/production assumptions; the physical optimizer does not infer
supplier or ingredient effects.

The Design / AI + Physics scenario editor opens after the mode selection or an
explicit request for interactive selection/review. Its Add/Delete/Edit/Run loop,
reviewed defaults, Previous/Skip and selective deletion still apply in that opt-in
flow. Single deletion uses arrow keys and Enter; multiple deletion uses typed IDs.
Internal file paths and routine backend narration are omitted in either flow.
See the workflow skill's `references/cost-performance-optimization.md` for the
automatic protocol and the models skill's `references/design-setup.md` for manual review.

For a quiet local chat, the existing Sci display preferences can be set to:

```yaml
display:
  tool_progress: "off"
  show_reasoning: false
```

Per-platform preferences under `display.platforms` override these values. Keep
interim assistant messages enabled so parameter tables preceding clarification
questions remain visible. These are profile display preferences, not wheel
installation side effects. Interactive questions and relevant errors remain
available; internal metadata uses terminal I/O to avoid mandatory file-edit cards.

In manual review, saved recipe tables appear before the mode question. Interactive non-streaming
CLI chats keep assistant context visible even with routine tool progress hidden.
A stdlib metadata helper in the models skill saves proposed scenarios before
showing the menu, so displayed recommendations are selectable draft entries.
Delete asks for a scenario and preserves the others; it never deletes scientific
results. Restart Sci after updating the CLI/skills to load these changes.

The library also exposes `from agri_tool import execute`, with a caller-owned
workspace path. It uses no LLM internally. Chat summaries contain readable
tables, assumptions and warnings. Exports contain a PDF and JSON/CSV/PNG/ZIP
artifacts. Numerical results depend on supplied assumptions and do not establish
experimental performance.

By default the command stores data in the active profile's
`agriformulations/workspace`. If the previous agricultural integration workspace
exists in that profile, it reuses it so saved projects and artifacts remain
available. `--workspace PATH` explicitly selects an independent store.

## Artifact and maintenance

The wheel is about 49.8 MB (47.5 MiB); its uncompressed contents are about 61 MB.
The package plus its dependency files measured 375.1 MiB in a fresh Linux
Python 3.14 environment. This is not the marginal increase for every Sci install:
some dependencies may already be present; runtime/cache/disk overhead varies.
Optional legacy Torch/XGBoost replay dependencies are not part of the default
installation. Historical resource archives remain available in the wheel.

The source project is maintained separately from this repository. To update it,
build a new versioned wheel, replace the bundled artifact, update the dependency
pin/source and `manifest.json`, run `sci pm lock`, and run the package/skill tests.
The repository contains the wheel, provenance metadata and usage documentation,
not a duplicate package source tree. Refer to `manifest.json` for its checksum.

## Current dev-branch review status

The integration branch is based on `dev` and tracks issue
[#88](https://github.com/boltzmannlabs/agent-scientist/issues/88).
Current-wheel verification in an isolated PM environment passed 151 formulation,
cost/draft and profile checks, plus 28 skill-authoring checks. Targeted CLI checks
passed 38 cases with one failure:
`test_native_design_surfaces.py::test_paired_surfaces_follow_the_profile_without_leaking_into_custom_skins`.
The same test fails on the clean `dev` base, so it is recorded as a pre-existing
baseline failure rather than a new regression.

Five initial wettability tests cover analytical limits and saved-run linkage.
They do not establish complete model validity: scientific domain review, finite
outputs across nonwetting cases, uncertainty propagation and broader optimization
benchmarks remain pending. PF-LBM and production CIPAC integration are not delivered
by this branch. Historical validation below describes prior local development
and is not a claim that every historical scenario was rerun on this branch.

## Validation

Current automatic-workflow coverage: 165 unique checks passed. The 163-check
regression covered all 21 model keys through the scientific workflow suite,
24 cost-comparison checks, 68 manual draft checks, profile isolation and skill
authoring. Two added acceptance cases cover an unaffordable performance improvement
and no feasible option; the complete 26-check cost suite passed. The final
skill-only recheck passed 25 checks. These are synthetic numerical tests, not product validation.

Three fresh configured-GLM cases passed: automatic five-recipe/ten-simulation
comparison with PDF/ZIP export; missing-price clarification with a stopped cost
branch; and explicit manual review with no simulation before Run. The final
saved results and PDF/ZIP data/chart contents were independently audited. Prices
and properties were hypothetical scenario inputs. Selected PDF pages were
visually checked; no new chat GUI pixel test is claimed.

The earlier installation/manual-editor checks below remain useful historical
coverage; their mandatory mode-choice behavior is now limited to explicit manual
review.

- Default dependency installation built through PM from this checkout and lock.
- 46 scientific workflow checks passed through Sci's canonical test runner.
- Built-in skill syncing/loading and profile A/B/A isolation passed (4 checks).
- Agricultural skill authoring checks passed (21 checks).
- Navigation/display regression checks passed (40 selected checks), plus a live
  GLM conversation covering recommendations, bold mode labels, All, Previous,
  default-preserving Skip, and no internal file paths/edit cards. Responses were
  scripted; graphical font sizing was not screenshot-tested.
- Real GLM setup-review tests passed for Design, AI + Physics Design and a direct
  standalone calculation. Edits were applied, both modes waited for confirmation,
  and the standalone calculation skipped the editor. Responses were scripted.
- Scenario Add/Delete/Edit/Run loops passed for both modes, including edited
  shared inputs, staged questions and no calculation before Run. Empty-list
  deletion/cancel also passed. Menu answers were scripted; advanced analysis
  keys were listed but not all exercised through the live editor.
- Existing saved GLM project exported through the native Sci launcher as PDF/ZIP.
- Fresh live GLM chat independently discovered the built-in skills, saved two
  recipes, asked the mode after saving them, and ran four scientific cases and a
  design study. A follow-up exported and verified PDF/ZIP. The mode selection was
  a scripted Design fixture; graphical UI interaction was not tested.

Tests: `tests/agriformulations/`, `tests/skills/test_agri_cost_optimization.py`,
`tests/skills/test_agri_formulations_skill.py` and `tests/skills/test_agri_scenario_draft.py`. Validation was performed on Linux;
Windows/macOS and Nix application builds were not executed in this change.
