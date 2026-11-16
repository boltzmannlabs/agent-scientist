---
name: agri-models-and-design
description: Run physical scenarios and constrained design searches.
version: "2.5.0"
author: Gopi Krishna, Agent Scientist
license: MIT
platforms: [linux, macos, windows]
metadata:
  sci:
    category: science
    tags: [simulation, physics, sensitivity, optimization]
    related_skills: [agri-formulation-workflow, agri-evidence-and-data]
---

# Agricultural Models and Design Skill

Select the implemented model appropriate to the decision, declare its inputs, and
interpret numerical results within its assumptions. The 21 catalogue entries
include physical models, empirical screens and analyses; they are not 21 validated
composition-to-performance predictors.

## When to Use

Use for physical scenarios, release, storage, dilution, handling, sensitivity,
robustness, recipe comparisons and constrained inverse design.

## Prerequisites

Use the installed `sci-agriformulations` library through `terminal` and the
`sci --run-module agri_tool --request-file PATH` command. Load the workflow skill for
request-file and profile-workspace conventions. Load the workflow skill through
`skill_view` for automatic formulation optimization and baseline/grade/supplier costing. A selected recipe and
individual active must belong to the project when the action requires them.

## How to Run

Use `operation="catalogue", action="operations"` for the operation inventory,
or `action="models"` for model keys. Use `operation="catalogue"` with `action=""`
and the relevant `model` key to read the exact current
schema, bounds, defaults, units, output metrics and limitations. Defaults are
assumptions, not measured properties. Call `operation="simulate"` with that model
and the discovered payload in a request file. Batch only the models needed for the user's decision.

The request shape for a direct single-model calculation is:

```json
{"operation":"simulate","action":"run","model":"rheology","project_id":"saved-project-id","payload":{"recipe_id":"saved-recipe-id","active_name":"exact saved active name","inputs":{}}}
```

Replace IDs/name and populate `inputs` from the selected model schema. Use supplied,
measured/fitted or previously confirmed inputs. User-authorized exploratory defaults
remain explicit assumptions; automatic execution is not permission to invent material
properties. In a manual review, submit the confirmed setup values.
Use this request shape directly rather than searching old scratch files for it.

## Quick Reference

| Decision | Model keys |
|---|---|
| Release mechanism/timing | `kinetics`, `geometry_release`, `finite_bath`, `swelling_release` |
| Chemical storage/package | `stability`, `packaging` |
| Suspension/flow/solubility | `suspension`, `rheology`, `solubility` |
| Liquid/dry dilution arithmetic | `dilution`, `powder_dilution` |
| Dose/flight/deposit | `dosage`, `spray`, `spreading`, `rainfastness` |
| Processing | `manufacturing` |
| Two-active reference/soil screen | `mixture_response`, `soil_fate` |
| Parameter analysis/search | `sensitivity`, `robustness`, `inverse_design` |

## Optimization entry point

For every formulation optimization request, first follow the workflow's required
mode choice using this helper's `mode-choice` command. Offer Design Study, AI +
Physics Design, Not now and Agent Choice before solving or collecting setup inputs.
Existing saved recipes and requests for "automatic optimization" do not bypass it.
Only an already explicit mode selection or explicit mode delegation skips repeating
that question. Do not automatically select inverse_design merely from "optimize".

## After recipe creation

Follow the workflow skill's required post-recipe choice: show saved recipe tables
and scenario recommendations, then ask DESIGN / AI + PHYSICS DESIGN / NOT NOW
through native `clarify`. Do not replace these options with a prose offer or run
scenarios before selection. Both selected modes review inputs before Run; a mode
already specified in the prompt goes directly to that review.

## AI + Physics Design input questions

Whenever AI + Physics Design is requested or selected, load
[references/ai-physics-inputs.md](references/ai-physics-inputs.md) and follow its
staged native `clarify` questions before any simulation, feasibility calculation
or optimization. This takes precedence over automatic execution for that mode,
even when the initial prompt supplies values or permits assumptions. Show supplied
values for review instead of asking the user to retype them. Selecting the mode
alone does not confirm recipe selection, inputs or search bounds.

## Automatic Objective-Based Evaluation

For a user-provided formulation problem, load the workflow skill and its
`references/cost-performance-optimization.md` with `skill_view`. Automatically map
all stated objectives and evaluation criteria to applicable catalogue models and
execute baseline/candidate comparisons. Include necessary coupled dependencies;
record unsupported, missing-input and failed criteria. Do not reduce a broad problem
to rheology/settling by habit or run unrelated models merely to cover all 21 keys.

The workflow skill coordinates grades, suppliers, ingredient combinations and
composition bounds alongside supported physical searches. Use matching measured
properties or an applicable validated mapping for material effects. The inverse
optimizer itself searches physical parameters; it has no supplier or ingredient
identity objective. After any search or substitution, replay all relevant baseline
checks and compute production cost for the actual saved recipe. Use the workflow's
comparison helper for cost savings, feasibility and trade-offs.

Automatic coordination is an execution behavior AFTER mode selection, setup and
the user's Run choice. It does not bypass the mode question for any optimization
request. Ask for essential inputs in the selected mode and preserve explicit limits.

## Agent Choice

Every option-based formulation question includes Agent Choice. Load the workflow
skill's `references/agent-choice.md`. Use helper-decorated selectors and
`action_selector`, rather than sending raw action lists. A delegated choice is
resolved to an actual option from objectives/inputs, recorded with its reason,
and continued without re-asking that question. Record decisions in the draft via
record-decision; include them in final results.

## Run and Edit review

In the scenario editor, Run opens one question: **Run without review / Go to Edit
for review**. Use the helper's run selector; this supersedes older rules that
blocked unreviewed scenarios or treated parent Run as immediate execution.
Without-review accepts valid displayed defaults but still requires essential
inputs and schema checks. Edit provides **Edit section / Confirm review / Previous**;
Confirm review saves Ready status and ends Edit, returning to the parent without
executing. Follow `references/design-setup.md` for this flow.

## Recipe selection

Show composition-based recipe names from the workflow skill's naming convention
alongside short labels and saved IDs; do not show only A/B or "Recipe 1/2".

For Add/Edit and AI + Physics recipe questions, use the draft helper's `recipes`
selector with `multi_select: false`. All eligible recipes is a direct choice,
not a checkbox. Resolve the explicit answer to saved IDs; an empty response keeps
this step pending, with no arbitrary retry limit or lost Add configuration.
See `references/draft-commands.md` for the selection command.

## Manual Design Review

When a mode is selected after recipe creation or an optimization request, or the user asks for interactive setup or
scenario selection, load `references/design-setup.md`. That selected-mode
editor retains the Add/Delete/Edit/Run parent menu, staged fields, Previous/Skip,
reviewed defaults and explicit Run. Initial recipes are shown before its mode
question. Completed Add/Delete/Edit operations return to the parent without running.
Deletion uses radio choices for up to three scenarios; multiple deletion collects
typed IDs. Empty selection removes nothing; All needs separate Keep-first confirmation.
Use the metadata helper's --request-file interface; do not pipe into Python.
After the selected setup and Run choice, execute the authorized objective-based scope.

## Procedure

1. Specify the output decision and its units before choosing models. Discover
   schema and output metrics rather than inventing field names.
2. Attach the exact recipe/active identity and provide explicit property inputs.
   For `active_name`, copy `recipe.active_components[].name` verbatim, including
   a supplied-grade label such as "technical" if present. The project's brief
   label is not the simulation selector when it differs from that recipe field.
   Check whether the model uses the active fraction or merely links the recipe
   for traceability. Ingredient names do not determine viscosity, diffusivity,
   partitioning, degradation or interfacial behavior.
3. For comparisons, keep test temperature, duration, equipment and other shared
   conditions fixed within each scenario. Vary only declared candidate-property
   parameters. Different assumptions can distinguish hypotheses, not demonstrate
   a measured ingredient effect.
4. Use study/workflow evaluation through `operation="design"` study/workflow actions to evaluate
   candidates, acceptance bounds and objectives. Inspect completeness, signed
   specification margins and the Pareto front. No acceptance limits means
   specification satisfaction is unassessed.
5. Use bounded physical search through the design optimization action or
   `model="inverse_design"`. Supply a physical base model, fixed inputs, bounded
   variables, objectives and constraints. Shortlisted settings are directly
   simulator-evaluated; the GP guides search and is not an experimental model.
   A finite unsuccessful search does not prove physical impossibility.
6. Use `sensitivity` to examine one-at-a-time effects about a stated baseline.
   Ranks depend on supplied ranges and exclude interactions. Use `robustness`
   only with justified distributions/correlations; sampled pass probability is
   conditional on those assumptions.
7. Inspect model-domain failures and unavailable metrics rather than silently
   deleting them. Retrieve saved exact inputs before revising. After any grade, supplier, ingredient, composition or optimized property change,
   rerun the complete relevant comparison against the unchanged baseline. Keep
   the same criteria and shared conditions; changes need evidence or explicit assumptions.

## Chat Result Format

Respect the active chat surface: use Markdown tables where they render; in the
plain CLI use aligned columns or labeled sections, as Sci's platform guidance
requires. Keep the same values, units, criteria and warnings in either layout.

Summarize calculations in readable Markdown tables, never by pasting the raw
worker object. Include scenario/recipe identity, model, metric, value and units;
show a criterion and pass/fail only when the user or study actually supplied it.
Mark unassessed criteria as “not assessed.” Keep partial/failed cases, important
assumptions and limitations visible. For a design study, compare candidates
side by side with baseline deltas. For cost optimization include actual total
production cost, grade/supplier contributions, savings, trade-offs and failed
iterations through the workflow comparator. Report returned Pareto status without
implying experimental validation. Include saved IDs for follow-up and offer PDF/ZIP for detail.

For requested end-to-end cases, discover the corresponding design catalogue
example. `design/complete` accepts compact explicit material families, computes
technical-active and balancing masses, and runs declared scenarios.
`design/develop` creates a child project and runs release, chemical retention and
storage-adjusted hypothetical dose for each individual active. These actions
preserve their declared scope; use `design/study` when specification criteria
and Pareto comparison are required. Use `design/experiments` only when the user
requests a measurement plan; it does not execute laboratory work.

## Pitfalls

- D and particle length are confounded through D/L² from release alone. The
  optimizer refuses searching both together without an independent fixed value.
- Available-active mass balance is not biological uptake, efficacy or a field-use
  recommendation. Treat the target as hypothetical unless applicable evidence exists.
- Chemical retention does not establish physical shelf life. Settling screens do
  not predict flocculation, sediment cake or redispersibility.
- `dilution` assumes an aqueous screen. For EC/OD/EW it does not predict actual
  precipitation, emulsion stability or oil/water partitioning. Use
  `powder_dilution` for dry product g/L, not a liquid density conversion.
- Rheology pumping pressure is a nominal-shear screen, not equipment qualification.
- Spray displacement is not a validated drift footprint; soil fate is a simplified
  screening balance, not an environmental risk assessment.
- Mixture-response output is a Bliss/Loewe reference, not automatically measured
  synergy. Fixed-ratio products cover a line, not a complete independent-dose grid.
- Keep fitted-range/extrapolation gates and source/runtime identities. A direct
  simulator replay is a consistency check, not independent experimental validation.
- GP interpolation spread, sensitivity envelopes and supplied price bounds are
  different from calibrated empirical confidence intervals.

## Verification

Check units, physical limits, active identity and saved recipe version. Cite exact
metrics with their assumptions. Preserve rejected cases, distinguish specification
pass from product validation, and report what each calculation cannot resolve.
