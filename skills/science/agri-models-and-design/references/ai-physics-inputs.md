# AI + Physics Design — guided input review

Apply whenever the user requests or selects AI + Physics Design. Use native
`clarify` questions, one stage at a time. Before execution, read the existing
`references/design-setup.md` and `references/draft-commands.md` for persistence,
review flags, navigation and Run checks. This input review overrides automatic
execution for this mode only.

## Question sequence

1. **Objective and targets.** Briefly restate what the user wants to improve and
   what must stay fixed. Show supplied targets with units and direction. Ask for
   confirmation or changes; collect missing targets in a separate focused question.
   If no acceptance limits are requested, record that choice and avoid pass claims.
2. **Baseline and recipes.** Show saved recipe names, generation/IDs, batch basis
   and composition. Ask which is the baseline, then which alternatives to include.
   Offer All eligible recipes where appropriate. Preserve pure-active loading and
   ask about any permitted composition/grade/supplier changes. Never infer a recipe
   selection from an unrelated answer or select all without an answer.
3. **Scenarios to evaluate.** Recommend a small relevant set with one plain-language
   reason each. Ask the user to keep or change the proposed set. Save recommended
   rows as actual Review required draft entries before showing them. Permit adding,
   editing or deleting scenarios through the existing editor. Discover the current
   catalogue; do not assume a fixed number of models or require all models.
4. **Shared test conditions.** For each scenario, ask about related groups such as
   temperature, duration, dilution, equipment and substrate. Usually show no more
   than four related fields at once, with units and the source of every value.
5. **Recipe-specific properties.** Ask for each recipe's relevant viscosity,
   surface/interfacial tension, degradation or other model properties separately
   from shared conditions. Show supplied/measured/saved values first. Explain an
   unfamiliar input with one short sentence about what it controls. Ingredient
   names and percentages do not establish these properties. Unknown essential
   properties require a value, applicable measured fit, explicitly accepted
   exploratory assumption, or deferral of that scenario.
6. **Search variables and bounds.** Ask which supported properties may change and
   which remain fixed. Collect lower/upper bounds, units and linear/log scale in
   small groups. Then confirm objective metrics, mandatory constraints, evaluation
   budget and seed. Explain the budget as the number of model evaluations. Do not
   treat a proposed bound as reviewed. Validate bounds against the current schema;
   ask for correction if invalid rather than clamping. Material grade/supplier or
   ingredient alternatives need separately saved recipes and supporting properties;
   the physical optimizer cannot invent a composition-to-property relationship.
7. **Costs, when requested.** Ask about quote sources and exact material prices,
   currency/basis and production assumptions in separate groups. Show existing
   values for review. If missing, offer to supply them or defer the cost branch;
   never replace missing costs with zero or silently drop the requested objective.
8. **Setup summary and Run.** Show selected recipes and scenarios, reviewed shared
   and recipe-specific values, targets, variable bounds, fixed values, budget and
   assumptions. Mark incomplete sections clearly. Return to the existing
   Add/Delete/Edit/Run parent menu. Only Run scenarios authorizes calculation of
   the displayed Ready scope; editing or finishing an input group does not run it.
   Incomplete scenarios must be resolved or explicitly deferred before the chosen
   scope can run. No extra confirmation after a valid Run is needed.

## Clear question format

Use a short stage title, current selection, and compact field/value/unit/source
rows before one question. Use native `clarify` with `choices` as plain strings;
never send objects as choices. Respect its four-choice limit.

For a related parameter group use **Keep values / Change values / Previous /
Skip — use defaults** where valid displayed defaults exist. Keep applies only to
shown values. Skip fills only unanswered eligible fields using shown defaults,
records the assumed origin, and preserves explicit values. Omit Skip and explain
why for essential identity, unknown properties, absent quotes or invalid bounds.
Previous restores the preceding question and its saved answers. Cancellation or
an empty/unavailable answer preserves the draft and authorizes no computation.

Example screen (illustrative fields; use the actual selected model):

**Pumping — shared conditions**

| Field | Value | Source |
|---|---|---|
| Pipe length | 5 m | Proposed catalogue default |
| Pipe radius | 10 mm | Supplied by you |
| Flow rate | 5 L/min | Proposed catalogue default |

Question: “Keep these pumping conditions or change them?”
Choices: Keep values / Change values / Previous / Skip — use defaults.

Do not dump raw JSON, unexplained API keys, command lines or internal paths.
Do not ask every parameter in a single question. Do not repeatedly ask the user
for already supplied values: show and confirm them. No simulation, optimizer,
sensitivity sweep or scratch feasibility calculation is allowed before Run.
Read-only schema queries, draft edits and unit validation are allowed.

After running, follow `formulation-results`: Run Summary first, baseline → candidate
changes, predicted improvements, then the detailed report and validation needs.
