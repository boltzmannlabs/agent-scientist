---
name: agri-formulation-workflow
description: Evaluate and cost-optimize agricultural formulations.
version: "2.5.0"
author: Gopi Krishna, Agent Scientist
license: MIT
platforms: [linux, macos, windows]
metadata:
  sci:
    category: science
    tags: [agriculture, formulations, recipes, design, cost, suppliers]
    related_skills: [agri-models-and-design, agri-evidence-and-data, formulation-results]
---

# Agricultural Formulation Workflow Skill

Coordinate formulation development with the installed scientific library. For a
user-provided formulation problem, offer Design / AI + Physics after recipe
creation. Within an authorized evaluation, select relevant simulations, compare
iterations with the baseline, and minimize total production
cost subject to maintaining or improving the required performance. Numerical
scenarios depend on supplied material evidence and are not product validation.

## When to Use

Use for agricultural formulation problems, baseline improvements, recipe variants,
raw-material grades, supplier alternatives, ingredient combinations, performance
comparisons and cost optimization. Answer conceptual questions without launching
an unrelated campaign. Honor explicit limits such as recipes-only or cost-only.

## Prerequisites

Agent Scientist installs `sci-agriformulations` directly; no plugin activation or
science-service API key is needed. Load `agri-models-and-design` with `skill_view`
for model selection and `agri-evidence-and-data` for quotes, sources or measurements.
The package is deterministic; Agent Scientist is its only LLM coordinator.

## How to Run

Use `terminal` with `sci --run-module agri_tool --request-file PATH`. Create a
private JSON data file, then invoke the launcher directly. Use this same file
interface for the scenario draft helper. Do not pipe into Python or construct
inline interpreter code for routine metadata: it triggers the native scanner.
Keep security checks and normal approval policy enabled. Use `terminal` for BOTH
creating private JSON data AND running the package. Do not call `write_file`,
`patch` or `edit_file` for any catalogue request, recipe request, comparison manifest
or draft: those tools display file-edit cards with internal paths even in quiet mode.
Use ordinary shell output redirection to a private request file within the terminal
operation, followed by the package call. Use file tools normally for requested
source edits or deliverable documents.

A request is one JSON object with `operation`, `action`, optional `model`,
`project_id`, `request_id` and `payload`. Discover `catalogue/operations`, then the
relevant catalogue action (`recipes`, `design`, `data`, `cost`, `research`,
`project`). An empty catalogue action plus `model` returns its schema. Preserve
saved identities; reuse a request ID only for an identical retry.

The launcher resolves the active profile's workspace and reuses its older
integration store when present. Use `--workspace` only for a deliberately chosen
alternate store. Remote execution must have the package and that store available.

## Quick Reference

| Need | Existing package action |
|---|---|
| Exact baseline or changed material/grade/supplier recipe | `recipes/manual` |
| Bounded composition candidates | `recipes/create` |
| Distinct ingredient families | `recipes/portfolio` |
| Same ingredient identities with revised percentages | `recipes/variant` |
| Comparable scenarios with specifications | `design/study` |
| Supported physical parameter search | `design/optimize`, followed by full replay |
| Other relevant model/analysis cases | `simulate/run` or `simulate/batch` |
| Full production cost scenarios | `cost/estimate` or `cost/batch` |
| Baseline/cost/performance selection and grade tables | `cost/compare` |
| Evidence and calibrated observations | `research`, `data` |
| Save/read back/export | `project/get`, `project/result`, `project/export` |

`manual`, `create` and `portfolio` validate AND save. They can create the project
when `project_id` is absent; retain its returned ID. The allowed ingredient roles
are active, carrier, matrix, solvent, surfactant, dispersant, binder, filler,
coating, stabilizer and other. Do not invent roles or API fields.

## Agent Choice in every option question

Read [references/agent-choice.md](references/agent-choice.md) for all formulation
questions with alternatives. Include Agent Choice, preserve manual options through
the helper's overflow selectors, resolve a delegated choice from objectives and
known inputs, and record its option/reason for the final results. This takes
precedence over older fixed button examples, including the three-mode selector.

## Composition-based recipe names

Give every recipe a descriptive name before saving and use it throughout recipe
selection, scenarios, comparisons, charts and reports. Read
[references/recipe-naming.md](references/recipe-naming.md) for the naming rules.
Use active identity + pure-active concentration/basis + formulation type + the
main distinguishing composition. A/B and V0/V1 labels supplement the name; they
never replace it. Verify the saved name, composition and ID agree before display.

## Required mode choice for every optimization request

Before any formulation optimization, ask DESIGN STUDY / AI + PHYSICS DESIGN /
NOT NOW / Agent Choice via native `clarify`. This includes existing recipes and
requests to optimize, optimise, improve stability, reduce cost, compare alternatives
or find the best formulation. Read
[references/mode-selection.md](references/mode-selection.md) and use the model
skill helper's `mode-choice` selector. Do not infer the mode from "optimize",
"automatic", "run everything", "fully specified" or supplied parameter values.
Ask this BEFORE pricing/property/setup questions or any simulations/search/cost
campaign. Read-only baseline/catalogue discovery and a brief problem/recipe summary
are allowed first. Do not regenerate existing recipes to reach the mode question.
Only an explicitly selected mode, an answer to this selector, or explicit delegation
of the mode decision resolves it. A direct, named standalone calculation is distinct
from a formulation optimization request. This rule supersedes automatic routing.

## After saving recipes — required next-mode choice

After creating/saving requested recipes, show their actual composition tables,
batch and pure-active balance with the evidence status. Briefly suggest relevant
scenarios (recommendations only). Then, in the SAME turn, call native `clarify`
with one question: **How would you like to evaluate these recipes?**
Use these plain-string choices:

- **DESIGN — Evaluate recipes under selected physical conditions**
- **AI + PHYSICS DESIGN — Search physical parameter ranges, then evaluate shortlisted settings**
- **NOT NOW — Recipes only**
- **Agent Choice**

Emphasize the two mode names in the preceding message; the question UI uses plain
strings. Show recipes BEFORE opening the question. Do not finish with a full
technical report or a vague "If you want, I can run simulations" offer instead of
this selector. Missing prices/properties are collected after mode selection;
they are not reasons to suppress the two options. Mass-balance validation is not
a performance study. Avoid unevidenced labels like "higher-performance recipe".

A generic request to create recipes does not authorize automatic evaluation.
Await the selected mode. DESIGN opens `references/design-setup.md` in the model
skill; AI + PHYSICS DESIGN opens `references/ai-physics-inputs.md`. Both collect
and review the selected setup and wait for Run. NOT NOW/cancel preserves recipes
and runs no simulation. If the prompt already explicitly selects a mode, proceed
to that mode's input questions without asking the mode again. An explicit stop,
"no follow-up questions" or declined evaluation remains respected. An explicitly
requested direct standalone calculation does not enter this recipe-creation flow.
On resuming saved recipes awaiting evaluation, reuse their IDs and show the same
choice; do not regenerate them.

## AI + Physics Design input review

When the user requests or selects AI + Physics Design (including AI+Physics),
load the model skill's `references/ai-physics-inputs.md`. Collect and confirm
inputs through staged native `clarify` questions before calculations. This mode
requires user review of recipes, scenarios, conditions, properties, targets and
search settings, followed by an explicit Run action. The automatic-execution
instructions below apply outside this requested/selected mode. Preserve values
already supplied and show them for review; do not silently fill unseen defaults.

## Automatic Workflow

Read [references/cost-performance-optimization.md](references/cost-performance-optimization.md)
inside the chosen mode after setup and execution authorization. The word
"optimization" never bypasses mode selection, including in an automatic request.
Select the mode first (or resolve explicit Agent Choice delegation), collect its
inputs, and follow Run / Run without review / Edit. Once execution is authorized,
coordinate the relevant simulations and comparison without repeated Run prompts.

Automatically run every applicable scenario needed to assess the stated objectives,
criteria and coupled dependencies. Select from the current catalogue; do not run
all 21 entries indiscriminately. Preserve a relevance/coverage table including
unsupported, missing-input, skipped and failed cases. Run fully specified relevant
cases while identifying essential blockers in the others.

Use supplied values, applicable measured fits and confirmed saved inputs. Do not
invent active identity, supplier quotes, grade properties, criteria or unit
conversions. Ask focused `clarify` questions only for essential missing data or
permission to use exploratory assumptions. Automatic execution does not authorize
unseen material-property defaults. User-authorized catalogue assumptions are
labelled and retained; routine numerical controls such as seeds remain explicit.
Before generating a cost-optimization campaign, inspect baseline and candidate
price coverage. If prices or required production assumptions are missing and no
permitted source can resolve them, use the native `clarify` tool immediately to
request the missing quotes/values or permission for a labelled cost scenario.
A final-message request such as "supply prices later" does not replace that input
question. If the user says prices are unknown or forbids estimates/research, ask
whether to provide quotes or defer the cost branch; never create a speculative
variant grid or conditional cost winner in place of the question. On cancellation,
keep the saved baseline, mark cost optimization blocked and stop that branch.
Fully specified independent baseline checks may still run when requested.
After mode selection and the Run choice authorize execution, continue the
selected scope without another redundant Run question. An explicit stop/cancel remains stopped until the user resumes it.

## Manual Design Review

Use the scenario editor after DESIGN or AI + PHYSICS DESIGN is selected, or when
the user explicitly requests interactive scenario selection or setup review.
Then load the model skill's `references/design-setup.md`. In this selected-mode flow,
show the actual recipes before the mode question; defaults stay proposals until
reviewed and calculations wait for Run. Keep its Add/Delete/Edit/Run parent loop,
Previous/Skip navigation and selective-deletion safeguards. Optimization requests
enter the chosen mode after the required mode decision.

## Procedure

1. Establish the active/nutrient identity, formulation class, pure-active targets,
   batch and application basis, objectives, evaluation criteria and any restrictions.
   Resolve only essential missing facts. Generate a project name instead of asking.
2. Save the supplied baseline unchanged and display its validated composition.
   If no baseline was supplied, establish an explicit reference recipe and label
   it a proposed baseline. Do not invent baseline performance or prices.
3. Build alternatives across material grades, allowed suppliers, ingredient
   identities/combinations, proportions and supported physical/process parameters.
   Recalculate supplied-grade masses when assay changes, keeping pure-active
   targets and mass balance fixed. Save distinct recipe versions and quote sources.
   Populate each provided supplier in the ingredient's `supplier` field and source
   in `grade_source` (and `lot` when known). A supplier name in a recipe label or
   grade description does not replace those structured fields. Check the saved
   ingredients before running and correct omissions by saving the complete recipe.
   Record a supplier only for the exact ingredient the user/source assigns it to.
   Never propagate the active's supplier to additives, infer it from names such as
   "Dispersant A", or invent a supplier to fill the table. Leave unprovided supplier
   and lot fields empty and display "not specified". Synthetic prices/properties
   authorize only the stated assumptions, not additional supplier identities.
4. Select relevant models from objectives and criteria, evaluate the baseline,
   then apply the same test conditions and criteria to all iterations. Use
   candidate-specific measured properties or valid mappings; identical assumed
   inputs cannot demonstrate ingredient or supplier equivalence.
5. Run supported physical searches as needed; evaluate their shortlisted settings
   across the complete relevant comparison. Composition/grade/supplier search is
   a coordinated candidate search, not a capability of the physical optimizer.
6. Cost every iteration using actual supplied-grade masses and common currency,
   batch, production basis and stated yield, processing, packaging, freight,
   overhead and tax assumptions. Missing costs remain missing, not zero.
7. Use `cost/compare` as documented in the reference. It joins saved recipes,
   cost records and scenario IDs, enforces
   baseline/criterion comparability, computes savings and performance deltas,
   and selects the lowest-cost fully assessed feasible scenario, including the
   baseline. Preserve all excluded/unresolved iterations and their reasons.
8. Return the best evaluated formulation, grade/supplier cost comparison, every
   iteration's baseline deltas and performance trade-offs. Qualify the result by
   evidence and search coverage; do not claim a global optimum or product pass.

## Chat Result Format

Load `formulation-results` for the mandatory six-part interpretation, generation-wise reporting, evidence language and professional report template. Use it for any formulation category; the agricultural protocol supplies the package-specific execution details.

Present structured tables or aligned columns appropriate to the chat surface.
Never paste raw JSON/objects, commands, source/request/draft paths, or backend
lookup narration. Use short progress messages about the scientific decision.
Requested downloads may show readable artifact links.

- **Baseline and winner:** full saved ingredient composition, grade, supplier,
  purity, percent, mass, batch basis and pure-active loading.
- **Grade/supplier costs:** supplied unit price and source/date, purity-adjusted
  unit price where meaningful, quantity used, material contribution and total
  saleable-product cost on the same currency/basis. Flag missing/unverified quotes.
- **All iterations:** changed grades/suppliers/materials/parameters, total cost,
  savings versus baseline, relevant metrics, criterion margins/status, failures
  and exclusions. No unsuccessful iteration disappears from the record.
- **Trade-offs and recommendation:** explain cheaper-but-failing alternatives,
  cost/performance Pareto options, the selected candidate or retained baseline,
  remaining uncertainty and necessary validation. No feasible option means report
  that outcome rather than relaxing a constraint silently.
- **Evidence and files:** keep assumption/measurement/price provenance and exact
  recipe, scenario, study and cost links. Export PDF/ZIP supporting results when
  requested, plus comparison JSON and iteration/grade/performance CSV files.

## Pitfalls

- Ingredient identity or a higher assay does not determine physical performance.
  Preserve chemistry, compatibility and measured-domain gates during substitution.
- Cost supplied technical masses once; do not apply purity correction again.
- A lower total with missing prices or unsupported performance is not a proven saving.
- `partial`, `cancelled`, `needs_input` and `error` remain distinct from completion.
- Changed recipes and prices create new versions. Preserve the original baseline.
- Interpret model scope correctly; an aqueous screen is not emulsion stability,
  ideal settling is not a suspensibility assay, and calculated available-active
  mass is not demonstrated efficacy or a field-use recommendation.
- Use the installed package and existing skills, not a former plugin coordinator
  or additional LLMs in the calculation path.

## Verification

Retrieve saved results and confirm baseline identity, mass/purity balance, common
comparison basis, complete relevant-model coverage, full cost coverage, criterion
satisfaction and traceable sources. Every reported number must come from saved
library results or the deterministic comparison artifacts. Distinguish best
among evaluated scenarios from experimentally demonstrated product performance.
