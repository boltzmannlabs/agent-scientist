# Automatic baseline and cost/performance optimization

Use this protocol inside an explicitly requested automatic optimization campaign.
For recipe creation, the workflow skill's required DESIGN / AI + PHYSICS DESIGN /
NOT NOW question takes precedence after showing saved recipes. Do not silently
start this campaign or replace the selector with a vague simulation offer.
Selected modes review inputs and wait for Run. Automatic execution does not
authorize inventing missing chemistry, prices, properties or experimental outcomes.

For requested/selected AI + Physics Design, the model skill's
`references/ai-physics-inputs.md` takes precedence: collect staged input answers,
show the setup and wait for Run. Automatic execution in this reference applies
outside that mode.

## Establish the reference and evaluation contract

Save the user's baseline unchanged. Record project/recipe/revision, exact chemical
identities, format, batch, pure-active targets and application basis. If none was
provided, create and identify a proposed baseline; request essential missing
identity/targets rather than silently choosing a different product.

Extract objectives and evaluation criteria with units and direction. Minimize total
cost per kg saleable product subject to every mandatory limit AND noninferiority
versus the baseline. For lower-is-better metrics require candidate <= baseline;
for higher-is-better require candidate >= baseline. Use a nonzero tolerance only
when the user provides it. Viscosity, pH and other target bands require their
actual bounds, not an assumption that higher/lower is always better. If the baseline
fails a new target, alternatives still must meet that target; report extra cost
honestly if improvement is required. Preserve all user constraints.

Keep test temperature, storage horizon, dilution, flow/equipment, active identity,
engine version and units comparable. A cheaper recipe with a lower pure-active
loading or a different assay condition is not a fair improvement. Use the same
batch/currency/production basis, or establish a separate explicitly normalized
comparison. The worker does not automatically convert currencies.

## Resolve essential cost blockers before the search

Inspect the baseline's ingredient prices and production assumptions first. When
required quotes/values are missing and cannot be retrieved from a permitted source,
call native `clarify` now. Ask for quotes or permission to use a clearly labelled
scenario; if the user already says prices are unknown and estimates/research are
forbidden, offer to provide quotes or defer cost optimization. Do not replace the
input question with a speculative variant campaign, symbolic cheapest recipe or
"supply prices later" in the final answer. Cancellation stops the cost branch,
retains the baseline and records the blocker; it does not silently assume prices.
Run independent fully specified baseline checks only as appropriate to the request.

## Build the grade/supplier/material search space

For every allowed material option record chemical identity, grade/code, supplier,
lot, assay/purity, relevant specification/TDS/COA properties, price currency/unit,
quantity tier, date/source, freight and availability/approval restrictions. Retain
unknown values explicitly. Use uploaded quotes or actually retrieved public sources;
mark estimates as estimates. Research does not authorize contacting suppliers,
placing orders or representing a listing as a firm current quote.

Store supplier/lot/grade_source on the saved ingredient. Put its grade/code in the
candidate label and comparison manifest's grades mapping; do not invent unsupported
recipe fields. These are separate fields: descriptions such as "98% technical,
Supplier B" in a label do not populate ingredient.supplier. For example an active
row can contain `{"name":"Tebuconazole technical","role":"active","pct":20.4081632653061,"purity_pct":98,"supplier":"Supplier B","grade_source":"User-supplied hypothetical scenario"}`.
Retrieve and check the saved rows: preserve every supplied supplier/source and do
not proceed with a blank supplier column when that information was provided.
Supplier ownership is ingredient-specific. An active supplied by Supplier A does
not establish that "Dispersant A" or water comes from that supplier. Do not copy
supplier/lot information across ingredients or infer it from A/B product labels;
leave unknown fields empty and show "not specified". Even a declared synthetic
example authorizes only its stated supplier assumptions. Verify each populated
supplier against its exact user/source assignment before comparing.
Keep the same chemical active name across assay variants so studies
can compare it. When assay changes, recompute technical mass to preserve each pure
active target, rebalance the vehicle and validate with recipes/manual. New ingredient
identities, suppliers or grades require saved alternative recipes; recipes/variant
only edits the existing ingredient percentages.

Explore allowed grade × supplier × ingredient-family × proportion/process choices,
including meaningful joint combinations. Use bounded generation or explicit
recipes/portfolio for distinct families, then supported parameter searches inside
those candidates. Do not optimize only one coefficient and call it joint raw-material
optimization. Respect compatibility, ingredient/grade approval, composition bounds,
processing limits and availability constraints. Keep a ledger of evaluated, rejected,
blocked and unevaluated combinations. For continuous spaces use a declared finite
search and report its bounds, seed, evaluations and coverage, never a global optimum.

Material substitutions must use matching measured properties or an applicable
validated composition-property mapping to establish performance effects. The
physical optimizer changes physical inputs, not supplier identities or dispersant
doses. Without material-specific evidence, run permitted exploratory scenarios,
label them conditional and ask for the essential evidence needed to confirm a
substitution. Identical assumed viscosity for all suppliers does not prove equal
performance. Do not fabricate a grade-to-property relationship to finish the task.

## Select and execute all relevant calculations

Discover current catalogue models and schemas. Map every stated objective/criterion
to an applicable model, exact output metric, native unit and necessary dependencies.
Preserve this relevance/coverage matrix. A representative mapping is:

| Objective | Candidate models, subject to formulation/domain fit |
|---|---|
| Transfer/pour/pump | rheology; manufacturing if milling/energy is part of the problem |
| Physical storage stability | suspension; solubility when dissolved-phase saturation matters |
| Chemical shelf life/package | stability; packaging when moisture/barrier exposure matters |
| Aqueous dilution/concentration | dilution or powder_dilution; solubility where applicable |
| Release timing/extent | kinetics or the relevant geometry/finite-bath/swelling model |
| Spray/deposition/rain exposure | spray, spreading, rainfastness; dosage only on a valid mass basis |
| Soil persistence | soil_fate with its screening limitations |
| Two-active response | mixture_response only with the necessary two-active/reference data |
| Uncertainty or constrained search | sensitivity, robustness, inverse_design when the objective needs them |

This is not a fixed two-model shortcut. Add every applicable check needed by the
problem, including coupled storage/release/dose effects when relevant. Do not run
unrelated models or all 21 blindly. Unsupported efficacy, emulsion stability or
other criteria stay unresolved with their required evidence; an unrelated model
must not stand in for them. Legacy campaigns are not automatic default simulations.

Use supplied inputs, applicable saved/fitted observations and previously confirmed
values. For essential missing properties, prices, criteria or assumption permission,
ask focused native clarify questions. Continue fully specified relevant work and
resume automatically once blockers are answered. Do not ask for mode selection or
an additional Run confirmation in this automatic path. If the user explicitly
requests manual review, follow the separate editor and its Run authorization.

Evaluate the baseline and each feasible iteration under the common criteria.
Use design/study where supported (up to eight candidates and four scenarios per
study); split larger comparisons without changing their intended coverage.
Special analysis keys use their actual dedicated schemas. Candidate overrides may
vary only catalogue candidate_parameters; hold shared test conditions fixed.
After a physical search, replay the shortlisted inputs as ordinary model scenarios
and rerun the full relevant comparison, not just the optimized metric. Preserve
engine fingerprints, actual run IDs and failures. Never omit an unevaluated
mandatory criterion from a claimed feasible winner.

## Cost the actual recipes

Use cost/estimate or cost/batch; a batch accepts up to 24 scenarios. Prices must
match exact saved ingredient names. Use the cost result's final_cost_per_saleable_kg,
not the known-material subtotal, as total production cost. Include stated yield,
processing, packaging, fixed batch costs, overhead, freight and taxes. Ask for
essential missing cost assumptions; zero must be an explicit scenario value.
Use supplied technical masses without a second purity correction. The comparator
shows price per pure kg for grade comparisons, but does not apply that value again
to the recipe total. Do not confuse per-kg and per-litre cost.

Keep price-estimate low/base/high ranges and production assumptions. A price
interval is not a statistical confidence interval. Do not combine quotes at
incompatible quantity, date, currency or delivery terms without an explicit basis.
Grade-wise savings must include the changed technical amount as well as unit price.

## Deterministic baseline comparison

Use the installed package's `cost/compare` action. It reads saved records from the
owning project, not LLM-written metric values, and saves the comparison in the project.
It returns JSON plus iteration, grade/supplier and performance CSV artifacts. It does
not run simulations or alter recipes. Use the same package launcher as other actions:

```sh
sci --run-module agri_tool --request-file "$REQUEST"
```

Write a JSON request with operation=cost, action=compare, the owning project_id,
and the manifest below as payload. Use the same selected workspace as other calls.
No interpreter pipeline or inline Python is required. This extends the existing
package operation; no new model tool, plugin or remote service is needed.
Keep internal paths out of chat.

Use the existing response identities directly rather than writing ad hoc parsing
or summary programs. The response envelope's project_id owns the work. Saved recipe
IDs are in result.recipes[].recipe_id; a single simulate result is the saved record
in result, with scenario_id and result.metrics inside that record. A cost estimate
has result.cost_id. Full project readback is result.document, and project/result
readback is result.record. cost/compare joins and summarizes the metrics itself;
there is no need to reconstruct scalar outputs from curves or scrape old scratch
files. Prefer batch actions where their documented shape covers the requested work.

The request links every evaluated iteration to its real saved recipe, cost and
scenario IDs. Scenario IDs in runs are the manifest's scenario labels, not model
names unless those labels happen to match. Multiple criteria can share a run.
Example (replace identities with actual records and add all relevant scenarios):

```json
{
  "baseline": {"id":"B0","recipe_id":"R-baseline","cost_id":"cost-baseline","runs":{"flow":"s-baseline"},"grades":{"Exact active name":"95% technical"}},
  "candidates": [
    {"id":"I1","label":"Alternative grade and supplier","recipe_id":"R-alternative","cost_id":"cost-alternative","runs":{"flow":"s-alternative"},"grades":{"Exact active name":"98% technical"},"changes":["assay","supplier","dispersant combination"]}
  ],
  "scenarios": [
    {"id":"flow","model":"rheology","varying_inputs":["yield_stress_pa","consistency_pa_sn","flow_index"],"criteria":[
      {"metric":"pressure_bar","unit":"bar","goal":"minimize","maximum":1.0,"tolerance":0},
      {"metric":"viscosity_at_100_s_pa_s","unit":"Pa s","goal":"range","minimum":0.3,"maximum":0.8}
    ]}
  ]
}
```

The comparator rejects cross-recipe/currency/active mismatches, unrecognized metrics
and varying test-condition fields. Missing cost/metrics/runs, changed engine or
shared conditions, changed pure-active/batch/format basis, and failed criteria
exclude an iteration from recommendation. The unchanged baseline participates in
selection, so an expensive alternative cannot displace an adequate cheaper baseline.
An absent baseline cost prevents a savings-based recommendation. Ties retain the
baseline. Selection is lowest cost among fully assessed feasible evaluated scenarios;
Pareto IDs also show non-dominated cost/performance trade-offs. All numerical
predictions remain conditional on their evidence. No software flag proves product
performance, supplier equivalence or experimental validation.

Read the saved comparison and JSON/CSVs and present the actual values. The files preserve all iteration
IDs, saved result links, status/reasons, cost ranges, savings, metric deltas and
material/price provenance. The worker PDF includes dedicated baseline/iteration/grade/performance tables and a
cost comparison chart. The ZIP includes the comparison JSON/CSVs, PDF and scientific
records. Retain the comparison_id for readback through project/result.

## Deliver the decision

1. Display baseline versus best evaluated full recipe, with each material's grade,
   supplier, purity, percent and mass on the same batch/active basis.
2. Show grade-wise/supplier-wise raw material contributions and total saleable-product
   cost, absolute/percent savings, price ranges and source/date/quantity qualifications.
3. Show every iteration against the baseline: changed materials/parameters, each
   relevant performance metric, criterion status, margins/deltas and failures.
4. Explain the Pareto options and cheaper rejected alternatives. Recommend the lowest
   cost option meeting all criteria and noninferiority, or keep the baseline if it
   wins. If none qualifies, say so and identify the blocking evidence/constraints.
5. Separate measured, quoted, assumed and simulated inputs. A conditional scenario
   winner must be labelled conditional, with the tests/data needed to confirm it.
