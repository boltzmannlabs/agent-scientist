# Recipe naming from actual composition

Assign a clear, distinct name to every proposed recipe before saving it. Use:

**<Active(s) and pure-active concentration(s), with basis> <Formulation type> — <Distinguishing ingredient system>**

Use the actual saved ingredients, active fractions and formulation class; do not
invent components or infer properties. Include meaningful grade, supplier or
process distinctions only when supplied and needed to tell candidates apart.
Keep names within the current package field limits. If a full mixture name is too
long, shorten common ingredient descriptions while keeping each active and its
concentration unambiguous; give the full ingredient table underneath.

## Concentration and formulation

- Use pure-active loading, not the percentage of technical material. A 20% w/w
  product made from 95% technical is named 20% w/w, even though the technical
  ingredient occupies 21.0526% of the recipe. Put the 95% assay in the ingredient
  table or a distinguishing grade suffix where useful.
- State the concentration basis: % w/w, g/kg, g/L, or another supplied basis.
  Do not convert mass-based loading to g/L without appropriate density data.
- For mixtures, include every active's concentration with its name. For nutrients
  preserve the declared nutrient/oxide basis; do not invent an active equivalent.
- Include the actual formulation type (SC, EC, EW, OD, WG, WP or another declared
  category). Do not infer formulation type from an ingredient name alone.
- If identity, target or type is unknown, label that portion unspecified/provisional
  and obtain essential information before treating it as a complete saved recipe.

## Distinguishing candidates

Choose a neutral suffix that identifies the main compositional difference:

- dispersant/wetting-agent system;
- solvent/vehicle system;
- carrier, encapsulating matrix or binder;
- a changed grade/assay, supplied supplier or relevant dosage of an ingredient.

Examples for two supplied tebuconazole compositions:

- **Tebuconazole 20% w/w SC — Lignosulfonate / Alcohol ethoxylate**
- **Tebuconazole 20% w/w SC — Naphthalene sulfonate condensate / DOSS**

Use DOSS only if the actual ingredient is dioctyl sulfosuccinate, and explain the
abbreviation in the ingredient table. These examples are not required ingredients
or assumptions for other formulations. If only xanthan level differs, use a suffix
such as **Xanthan 0.15%** versus **Xanthan 0.20%**, on its stated basis. If only the
physical search setting differs, retain the recipe's name and distinguish the
scenario/settings; do not pretend the ingredient recipe changed.

Avoid unsupported names such as "high performance", "best", "stable", "premium"
or "low cost" unless the stated evidence supports that exact claim. Prefer the
neutral composition descriptor even when a ranking is available.

## Saved identity and presentation

Supply the descriptive `name` through the documented recipe-creation/variant
interface. Where a generic batch generator cannot accept separate names, create
the explicitly specified candidates individually using the existing manual recipe
operation. Check names in saved results before showing the recipe-choice question.
Do not add unsupported API fields or rewrite private storage directly.

Use the SAME descriptive name in chat, native recipe options, scenario mappings,
Run Summary, generation tables, plots, cost comparisons and final reports. Keep
V0/V1 and optional A/B as short secondary labels. Example:
**V1 (A) — Tebuconazole 20% w/w SC — Lignosulfonate / Alcohol ethoxylate**.

For existing saved recipes with generic names, show a composition-derived display
name alongside the original saved name/ID. Preserve their stored identities and
historical run links; do not create duplicate recipes merely to change a label or
silently rename old experimental records. An explicit rename request should use a
supported metadata operation, if available, with no changes to composition.
