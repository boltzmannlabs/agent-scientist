---
name: formulation-results
description: Explain and report formulation optimization results.
version: "1.4.0"
author: Gopi Krishna, Agent Scientist
license: MIT
platforms: [linux, macos, windows]
metadata:
  sci:
    category: science
    tags: [formulation, optimization, results, simulations, cost, reporting]
    related_skills: [agri-formulation-workflow, agri-models-and-design, agri-evidence-and-data]
---

# Formulation Results and Interpretation

Turn formulation optimization work into a traceable, understandable decision. Apply to any formulation type or product category. Discover available models, data and package operations at runtime; never assume one product, chemistry, metric, recipe structure or fixed number of simulations.

## Core rules

- Begin with a plain-language statement of the objective, constraints, target specifications and evaluation criteria. Resolve ambiguities that change feasibility or ranking.
- Preserve the user's baseline as V0. Record recipe identity, ingredient composition, grade/source, concentration, quantity and units, batch basis, process and known cost/performance. Unknown fields remain “not provided”; do not fabricate them.
- Give each saved recipe a stable generation label (V0, V1, V2…). Never imply chronological superiority. Keep generation labels linked to exact recipe IDs and revisions.
- Select every relevant simulation from the problem objectives and criteria, using current model catalogues and domain fit. Do not run every available model indiscriminately. Mark unavailable, unsupported, blocked and unassessed criteria clearly.
- Give every recipe a composition-based name: active(s), pure-active concentration
  and basis, formulation type, and distinguishing ingredient system. Follow the
  workflow skill's `references/recipe-naming.md`. Use that same name in tables,
  selectors, charts and reports, alongside generation labels and exact saved IDs.
- Every simulation result must map to the exact formulation name, generation, recipe ID/revision, model, scenario/run ID, inputs, shared conditions and evidence/assumption provenance.
- Explain each result before or alongside its numbers and interpret it immediately afterward. Use the required six-part interpretation below for every simulation and reported result. Do not provide naked numbers, raw objects or execution logs.
- Distinguish measured experimental results, user-supplied values, literature data, model predictions and assumptions. A simulation awaiting confirmation is not a failure. Use “Experimental validation pending” or “To be experimentally confirmed.”
- Use constructive, neutral wording. Explain predicted benefit and potential significance without asserting that an unverified improvement is real. A candidate is not unsuitable solely because experiments have not been run.
- Do not call a candidate failed unless it violates a stated numerical/specification constraint in the evaluated model or has a documented technical failure. Describe model-based constraint misses as “did not meet the modeled target” and clarify their predictive status. If no target exists, say “not assessed against a target.”
- Treat absence of data as unresolved, not zero or failure. Never claim a global optimum outside the evaluated search space.

## Procedure

1. **Frame the decision.** State objective, constraints, target values/ranges, metric direction, units, baseline/reference, and decision priority in simple language. Separate hard constraints from preferences. Show what remains unclear.
2. **Establish V0.** Retrieve the saved baseline and show every ingredient, grade/source, concentration and quantity on a stated mass/volume basis. Include manufacturing process and known baseline simulation and cost records. Label unavailable baseline fields. Do not invent baseline performance.
3. **Plan evaluation coverage.** Build an objective-to-simulation matrix: criterion, relevant model/test, output metric/unit, applicability and input needs. Ask for essential missing information. Ask permission before assumptions that can change recipe ranking. Routine model defaults may be used only where the user or platform authorizes them, and must be labeled.
4. **Generate and track versions.** Assign V1… in evaluation order. For each generation, capture recipe ID/revision and all ingredient names, grade/source, concentration, mass/volume quantity, total basis, and changed-from-previous description. Keep failed, incomplete and archived candidates visible with their status and reason.
5. **Run and map simulations.** Use comparable conditions for baseline and candidates. Save exact input parameters, units, assumptions, model version, run/scenario ID and output values. Verify each run is linked to the intended saved recipe. Never infer recipe identity from a display name alone.
6. **Evaluate costs.** Where prices and production assumptions exist, compare each grade, supplier and quantity, substitutions, raw-material contribution, total raw-material cost and manufacturing/packaging/logistics/overhead/tax costs separately. State currency and cost basis (e.g. per kg saleable product). Show savings against V0. Missing price or cost terms stay unresolved; do not call a raw-material subtotal total production cost.
7. **Interpret and rank.** Apply stated hard constraints and target criteria to model outputs. Rank feasible evaluated candidates by the user's priorities, then show cost-effective alternatives and Pareto trade-offs where useful. Keep model prediction separate from experimental confirmation. Explain uncertainty and search coverage.
8. **Recommend next steps.** Identify best overall and best cost-effective evaluated candidates when the data supports that distinction. State what would change the recommendation, unresolved risks, and a practical experiment/measurement plan to validate promising predictions.
9. **Create the report.** Provide a concise chat summary and, when supported/requested, a professional PDF plus machine-readable tables. Check units, labels, generation mapping, interpretation and evidence status before delivery.

## Agent decisions in results

Include a visible Agent decisions table in the Run Summary and detailed report:
question, actual agent-selected option, reason tied to the objective/inputs, and
assumptions. Read the workflow's `references/agent-choice.md`. Preserve the draft
ledger in report data; label choices as agent-selected rather than user-selected.
Do not report the literal Agent Choice button as a model, recipe or actual result.

## Required run summary before the detailed report

For every formulation optimization run, present a **Run Summary** before any detailed technical report or export. Include:

- Objective and target criteria in one plain-language sentence.
- Simulations performed, grouped by model, with the formulation generation and saved recipe/run IDs.
- Optimization steps and parameters compared, including grade/supplier/composition and process changes where applicable.
- Baseline versus selected candidate results, cost, target status and the best-performing evaluated outcome. State when no winner can be selected from available evidence.
- A parameter change ledger using these exact indicators and baseline-to-current values wherever available:

| Indicator | Meaning | Example |
|---|---|---|
| **Changed** | Parameter differs from baseline. | Viscosity: 1.4 → 1.1 Pa·s |
| **Improved** | Directional improvement against the stated objective/target. | Cost: $12 → $10/kg |
| **Unchanged** | Parameter retained its baseline value. | Temperature: 25 → 25 °C |
| **Needs validation** | Predicted improvement awaiting experiment. | Coverage: 62% → 70%; **Experimental validation pending** |

Indicators can be combined, such as **Changed · Improved · Needs validation**. Improvement must be defined against the user's objective or target, not inferred from a change alone. If a value was not measured or simulated, show “not assessed” rather than estimating it.

After this concise summary, provide the detailed report with simulation-wise interpretation, generation/cost tables, best formulation rationale, achieved modeled improvements, limitations and experimental validation requirements. The summary is not a replacement for detailed interpretation; all numerical findings remain explained in the detailed report.

## Mandatory interpretation for every simulation/result

Include all six elements in the same row, adjacent note or short paragraph:

1. **What was evaluated?** Purpose of the model/test.
2. **What do the results show?** Actual output values, trend and unit.
3. **What does this mean?** Plain-language consequence.
4. **Is it good or bad?** Compare with target, baseline or reference. If unavailable, say unassessed. Use neutral modeled-target language, not experimental pass/fail language.
5. **Why may it have happened?** Separate evidence-backed causal input changes from hypotheses. A correlation or model assumption is not proof.
6. **What next?** Next simulation, data request, formulation change or experimental validation.

A compact table can use columns `Evaluation / formulation`, `Result`, `Meaning and target comparison`, `Evidence and likely drivers`, `Next step`. Follow it with a clear prediction/validation qualifier. For lengthy cases, use one short interpretation block per simulation and per generation.

## Optimization handoff

A formulation optimization request first requires the workflow's Design Study /
AI + Physics Design / Not now / Agent Choice question, even with existing recipes.
Show a short objective/baseline summary, then ask; do not substitute an optimization
report or automatically run the search. Detailed reporting follows authorized work.

## Recipe creation handoff

When only recipes have just been created, show the saved compositions and a short
validation/evidence summary, then follow the workflow's native DESIGN / AI + PHYSICS
DESIGN / NOT NOW question. Do not let report formatting terminate the turn before
that question. A detailed optimization report follows actual evaluation. A requested
recipe document may still be delivered, but it does not replace the mode selector.

## Chat presentation

Start with the decision frame, then show V0 and the recommendation. Keep tables readable; split wide tables by purpose rather than omit fields. Define abbreviations and use consistent units. Put each interpretation directly next to its result. Avoid dense logs, unexplained acronyms, raw JSON and claims unsupported by saved records.

Use a generation comparison table with one row per ingredient per version, or a matrix with ingredient/grade and V0…Vn columns. Include concentration, quantity and change from prior version. State “unchanged” explicitly. A separate evolution table may summarize each version's rationale and trade-offs.

## Professional report structure

1. Title, date, project/product identity and evidence-status legend.
2. Executive summary: objective, key result, best evaluated candidate, cost change and validation status.
3. Problem definition: constraints, target specifications, criteria and decision priority.
4. Baseline V0: complete recipe, grade/source, quantity, process, performance and cost coverage.
5. Generation history: V0…Vn consolidated ingredient/grade/concentration/quantity table and change log.
6. Simulation coverage and recipe-to-run map.
7. Simulation-wise results, trends and mandatory interpretation blocks.
8. Cost breakdown and grade/supplier alternatives, including assumptions and savings.
9. Candidate ranking, target-versus-achieved and baseline-versus-best summary.
10. Uncertainty, missing information and limitations.
11. Recommendation and suggested experimental validation plan.
12. Appendices: units, complete inputs, run IDs, model versions and provenance.

Charts should answer a decision question: generation-wise metric trends, target-versus-achieved bands, baseline-versus-candidate cost, ingredient cost contributions and performance-cost trade-offs. Label axes, units, target bands, generation IDs and evidence status. Do not chart missing values as zero. If visual support is unavailable, provide a clear table and say so.

## Evidence and language

Use visible labels: `Measured`, `User-provided`, `Literature-reported`, `Model-predicted`, `Assumed`, `Unknown`. Cite source/date for literature and supplier data where available. A prediction may be promising, unfavorable relative to a modeled target, or inconclusive; none means experimentally confirmed. For any prediction awaiting confirmation, explicitly write **Experimental validation pending** or **To be experimentally confirmed**, describe the predicted benefit/significance, and recommend an appropriate test. Avoid “failed”, “unsuitable”, “proved”, or “validated” unless the corresponding evidence supports that exact claim.

## Validation checklist

Before presenting results, verify:

- V0 is identifiable and unchanged; generation IDs and exact recipe IDs are consistent.
- Every relevant objective has an applicable simulation or a clear unresolved reason.
- Every run maps to the correct recipe, inputs, assumptions, units and saved outputs.
- Every result has all six interpretation elements and a comparison reference.
- Cost basis/currency are consistent; raw materials and manufacturing costs are not conflated.
- Rankings apply the stated hard constraints and preserve unresolved candidates.
- Predicted results are not represented as experiments; missing evidence is not called failure.
- Recommendations state evidence, uncertainty, what may have caused the result and next validation step.
- Tables and charts contain no unexplained values, raw objects, hidden zeros or ambiguous labels.

## Compact example

**Decision:** Reduce material cost while keeping modeled viscosity within 0.8–1.2 Pa·s at 25 °C. V0 is the saved reference; the operating process and test temperature remain fixed.

| Generation | Formulation / recipe | Ingredient change | Modeled cost | Viscosity | Interpretation |
|---|---|---|---:|---:|---|
| V0 | Reference / R-100 | Grade A, 10 kg; additive X, 2 kg | $12/kg | 1.0 Pa·s | Baseline for comparison. |
| V1 | Candidate / R-101 | Grade B, 10 kg; additive X, 2 kg | $10/kg | 1.1 Pa·s | $2/kg lower in the supplied cost scenario; within the modeled target. |

**Rheology interpretation — R-100 → R-101:** What was evaluated: viscosity at 25 °C under the saved test conditions. Results: 1.0 → 1.1 Pa·s. Meaning: the model predicts a small viscosity increase alongside lower estimated cost. Target comparison: both values lie within 0.8–1.2 Pa·s; this is a modeled comparison, not an experiment. Why: the grade changed while the additive and conditions were held fixed; attributing the full change to grade requires validated grade-property data. Next: measure viscosity on a matched V0/V1 batch. **Experimental validation pending.**

This illustration is a reporting example only. Do not reuse its ingredients, values, currency, limits or causal explanation for a real project.
