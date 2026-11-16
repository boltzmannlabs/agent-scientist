# Scenario editor — Design and AI + Physics Design

Use this interaction for explicitly requested manual setup/review and for every
requested/selected AI + Physics Design session. For AI + Physics, first follow
`references/ai-physics-inputs.md` to collect the initial setup through questions.
Automatic formulation evaluation follows the workflow skill and does not enter this
editor or wait for its Run question. In this manual flow, use the interaction after
either mode is selected. Initial recipe authoring and
direct standalone calculation prompts do not enter this editor. Use native
`clarify` for choices and edits; the scientific package performs calculations.

## Parent menu

Retrieve the recipe summary and model inventory, then promptly propose a small
relevant set of scenarios, without executing them. Before presenting action
options, show a compact recommendation table: scenario, what it checks, and one
brief reason tied to the formulation and the user's goal. Keep recommendation
claims within the catalogue model limits: do not present aqueous dilution as
emulsion/dispersion prediction or ideal settling as a suspensibility test. Physical
properties remain inputs, not predictions from excipient identities. Reuse recommendations
already shown after recipe generation instead of giving a second long explanation.
They remain suggestions: do not re-add a scenario the user deleted. Do not reconstruct the entire
simulation history or reason through search feasibility before showing the menu.
Before the first parent menu, only retrieve the recipe summary and model
inventory. Fetch an exact previous result later, only for a specific Add/Edit
section. If several historical inputs disagree, let the user choose rather than
reconstructing every run. Give each a
stable short ID (S1, S2, …) and a brief two-to-five-word name. Keep numeric
conditions and criteria in their fields, not appended to scenario names. Show only this summary:

| ID | Scenario | Model | Recipes | Status |
|---|---|---|---|---|
| S1 | Pumping | Rheology | A, B | Review required |
| S2 | Storage settling | Suspension | A, B | Review required |

Before showing that table, create actual draft entries for every recommended
row using `scripts/scenario_draft.py` (stdlib-only metadata helper, run through
terminal). Suggestions are unreviewed configuration entries, not calculated
results. Never show S1/S2 and later claim there are no scenarios to delete merely
because they were recommendations. Render the table from the helper's saved list,
not a separate imaginary list. Delete and Edit always use that same list.

Read `references/draft-commands.md` for the helper protocol. If resuming an older
conversation whose displayed rows were never saved, reconstruct those displayed
rows as review-required entries with their selected recipe IDs before asking
which to delete. Do not regenerate already deleted suggestions.

Then ask exactly one parent question:
**What would you like to do with these scenarios?**
Choices: **Add scenario**, **Delete scenario**, **Edit scenario**, **Run scenarios**.
Pass these four choices in that order as plain strings in `choices`, never
objects with label/description fields. Use the question exactly as written;
do not rename Run to mean starting input review. Run opens the single review-choice question described below, including for
unreviewed rows; do not force the user through Edit first.
Keep these same four actions even when the list is empty. Do not substitute Undo
for Run or add a fifth button; Undo/Cancel remain typed navigation commands; Previous belongs to input steps.
If Run is selected with an empty list, explain that a scenario must be added and
show this same menu again without executing anything.

After adding, deleting, or editing, update the summary and ask this same parent
question again. Never interpret completion of an edit or add as a request to run.
A user can type Back, Cancel, Undo deletion, or a particular scenario ID. A skipped
or cancelled question never runs calculations. Preserve existing recipes/results.

## Add scenario — one stage at a time

1. **Choose model.** Read `catalogue/models` and show all currently available keys in a
   compact numbered list grouped by purpose, with each model's readable title
   and key (for example, “Rheology & pumping — rheology”). Follow with a free-text `clarify`
   asking for the model number or name, with no `choices` array at this stage.
   Do not replace this with two recommended buttons. Native clarify displays at most four
   choices: never pass a 21-choice array or silently limit the catalogue to four.
   The inventory includes physical models and analysis workflows. Sensitivity,
   robustness and inverse design need a supported base model and additional
   configuration; combined-active response needs two actives in a selected recipe.
   In AI + Physics mode, an eligible physical key such as rheology may be the
   search base; do not label it evaluation-only merely because its key is not
   inverse_design. If inverse_design is chosen, ask for its supported base model
   unless already explicit in the request. Explain requirements only when relevant. Do not pretend every key can
   be inserted into the engine's ordinary design/study comparison.
2. **Choose recipes.** Use the helper's `recipes` command with the actual eligible
   saved recipe IDs/names. Show its numbered list and pass its `selector` unchanged
   to native `clarify`: **multi_select: false**. All eligible recipes is a single
   radio choice: Enter confirms it, with no checkbox or Space action required.
   With one/two recipes, direct individual choices and Previous also appear;
   larger sets use All eligible recipes / Choose recipes / Previous. Choose recipes
   opens the helper's free-text number/ID question. Do not use checkbox selection.
   Resolve the submitted answer with the helper and use its exact `recipe_ids`.
   Show the selected recipe names, retain them in the pending Add/Edit and advance
   to shared conditions. Empty/`[]`/unanswered input keeps this same step pending;
   re-show the single-choice selector and explain Enter once. Do not abandon Add
   after a retry count, interpret an empty answer as All, or regenerate the model.
   Previous returns to model selection; explicit cancellation preserves the saved
   draft and exits without adding a partial scenario. Ask for an individual active
   only when a selected recipe makes it ambiguous.
3. **Shared conditions.** Read the chosen model schema. Show the first related
   group of shared fields with current/proposed values, units and origins. Ask
   **Keep values**, **Change values**, **Previous**, or **Skip — use defaults**
   when every unanswered field has a valid displayed default. Accept free-text
   changes too. Skip accepts defaults for this group only; it does not run anything.
   Use small groups, usually at most four fields per question. Cover all shared
   groups before moving on. Do not show recipe-property inputs in this stage.
4. **Recipe-specific properties.** For each selected recipe in turn, show its
   relevant material/property fields, values, units and origins. Ask to keep or
   change that recipe's values, in small related groups, with the same Previous
   and Skip controls as shared conditions. Offer copying reviewed
   values to other selected recipes only when the user chooses it. Do not infer
   viscosity or other physical properties from ingredient names. Show “No separate
   recipe-specific fields” and continue when the model has none; do not invent any.
5. **Search settings (AI + Physics only).** For a supported search scenario,
   collect search variables and bounds/scales, then objectives/constraints, then
   evaluation count and seed in separate groups. Keep fixed conditions separate
   from search variables. Auxiliary evaluation-only scenarios are allowed but an
   AI + Physics run needs at least one valid search configuration. Sensitivity,
   robustness and inverse-design keys use their actual nested schemas, not a
   second wrapper around an already configured analysis.
6. **Criteria.** Show the selected model's output metrics. Let the user supply
   acceptance bounds/objectives or choose **No acceptance limits**. Offer Previous and a Skip action only when it clearly
   means no additional acceptance limits; it must not drop a constraint supplied
   by the user. A criterion
   without a bound is not a specification pass. Do not silently invent thresholds.
7. **Finish adding.** Show a compact scenario summary, mark it Ready only when
   all necessary sections are reviewed/valid, save the draft, and return to the
   parent menu. Do not run it.

If a reply changes another section but does not answer the current field group,
record that requested change and ask the unresolved group again. Do not infer
Keep for unaddressed fields. A clear Keep answer applies only to displayed fields.

Defaults and agent assumptions must be visibly proposed before the relevant
Keep answer. Merely selecting a mode or allowing assumptions in the initial
prompt does not approve all unseen fields. Preserve user-provided values.

## Previous, Skip and All

Maintain a cursor and the user's answers in the pending draft. **Previous** returns
to the actual previous input question with its saved values, not to the parent
menu. At the first Add question it returns to the parent without committing a
partial scenario. On returning forward, reuse answers unless the user changes
them; invalidate only fields affected by a changed model or recipe selection.
**Back to scenarios** remains a separate typed command for leaving the wizard.

Offer **Skip — use defaults** on numeric/parameter groups with valid displayed
catalogue defaults. It fills only unanswered fields and preserves user-provided
or previously confirmed values; do not reset them silently. State “Skipped; shown
defaults kept” once, record the assumed origin, mark the group reviewed, and move
to the next input question. In an Edit operation, Skip leaves existing values
unchanged. If no valid default exists (identity, unavailable measurements, missing
base model or incompatible bounds), explain that the field cannot be skipped and
ask for it; do not invent one. The user can still go Previous or cancel.

An answered Skip choice, or a deliberately skipped input with outcome=submitted,
can keep displayed defaults in an eligible input group. Cancel, timeout, unavailable
UI, unanswered questions, and a skipped mode/recipe/run decision do not authorize
selection or execution. Skip is never an alternative to Run.

Offer **All** where it has a clear finite scope: eligible recipes, the displayed
scenarios for deletion, or all Ready scenarios for execution. For long lists use
All / Choose items / Previous, then a numbered free-text chooser. For choosing a
model, All means only the displayed context-specific recommended set if that option
is explicitly offered; do not interpret it as every available model. Each added model
still passes through its own input wizard. All never includes deleted entries or
silently bypasses a model's prerequisites. Do not silently omit incomplete entries
from a requested all-scenarios run: explain which need review.

For every eligible numeric/parameter group, including a group revisited through
Previous, use the same four labels: **Keep values / Change values / Previous /
Skip — use defaults**. Do not replace Skip with a differently named default
button or drop it simply because the group was visited already. Omit Skip only
when no valid default is available, and explain why.

Do not combine five or more buttons: native clarify shows only four. Use a
separate selection step rather than losing Previous, Skip or an item to truncation.

## Delete scenario

1. List the actual saved draft. If empty, say there is nothing to delete and return
   to the parent menu. Otherwise pass the helper's `delete_selector` as ONE
   native clarify question. Show current IDs/names above it. All must not be the
   first or recommended option.
2. A direct scenario choice or typed IDs selects only those IDs. Every deletion
   question uses `multi_select: false`: highlighting one scenario and pressing
   Enter must select it. Do not substitute checkbox selection for these buttons.
   With three scenarios, the helper lists all three directly and a More options
   button. More options opens the helper's `delete_more_selector`; All remains a
   deliberate choice there. With longer lists, Choose a scenario or Choose multiple
   scenarios opens `delete_id_selector`, a single free-text question for IDs from
   the displayed list. Multiple deletion uses typed IDs such as `S1, S3`, not
   checkboxes. Previous returns to the preceding selector. No parallel bulk-action
   question is used. Never ask
   “Which scenarios?” and “Or a bulk action?” in the same clarify call.
3. An empty list `[]`, blank answer, null, skipped/unanswered status, Previous or
   Cancel means no deletion. Say “No scenarios removed” and return to the parent.
   Never turn an empty selection into All or use a different question's default
   answer to authorize deletion. A leftover bulk answer in an older multi-question
   response is not a valid selection in this flow.
4. For a proper subset, call helper delete with exactly the selected IDs and
   current revision. No extra confirmation is needed. Show removed IDs and the
   remaining list returned by the helper, then return to the parent.
5. All (or a selection covering every scenario) requires the helper's separate
   `bulk_delete_confirmation` question. Its FIRST/default choice is Keep scenarios;
   Delete all N scenarios is a deliberate second choice. Only that exact explicit
   confirmation permits `confirm_all: true` on the delete command. Do not invent
   the flag to bypass an error. An empty, skipped or cancelled confirmation keeps
   the draft unchanged. Selecting a lone remaining scenario directly needs no
   bulk confirmation; explicitly choosing All still does.

The helper rejects empty IDs, unknown IDs, stale revisions and unconfirmed bulk
clears without writing. Preserve scientific results and the last-deleted snapshot
for Undo. Single-scenario deletion must not clear other entries. Display the same
parent menu after completion or cancellation; do not auto-select Add or Run.

## Edit scenario

1. Show saved scenario IDs/names and ask which scenario to edit, with Previous.
   If arriving from Run's review choice, use its selected scope and ask which
   scenario in that scope to review; do not silently edit others.
2. Show that scenario's current recipe selection, conditions, properties, criteria
   and search settings with units and origins. Present ONE question using the
   helper's `edit_actions`: **Edit section / Confirm review / Previous**.
3. Edit section asks which section to change (recipes, shared conditions,
   recipe-specific properties, criteria, search settings, model/name). Use a
   numbered free-text section chooser for long lists. Show only the selected
   section's current values and ask for its edits. Keep the existing recipe
   selector and Previous/Skip rules. Validate changes against the current schema;
   never clamp invalid values. Show a brief before → after table and save the
   edited scenario with `status: review_required`. Return to the same Edit action
   question so the user can make another edit or finish.
4. **Confirm review** ends Edit. Resolve every selected scenario input from saved
   values and explicitly shown defaults, validate units/bounds and required search
   settings, and show a concise final setup. If essential values are unresolved,
   ask only for those fields instead of marking the row Ready. Then call helper
   `confirm-review` with the selected ID(s), current revision and
   `confirmation: "Confirm review"`. The helper persists Ready status. Return to
   the parent scenario list; confirming review does not execute physics.

Previous/cancel exits the current editing stage without confirming unresolved
values or running. Saved edits remain, but no unconfirmed edit is called Ready.
Changing a model or recipe invalidates affected setup sections and requires their
resolution before confirmation. Keep unchanged scenarios and recipes intact.

## Run scenarios

When the user selects **Run scenarios**, show a short scope/setup summary (scenario,
recipes, key conditions and supplied/default origins), then ask exactly ONE native
question from the helper's `run_selector`:
**Run these scenarios without review, or go to Edit for review?**
Choices: **Run without review / Go to Edit for review**, `multi_select: false`.
Do not automatically execute on the parent Run action and do not reject an
unreviewed row just because its review flag is unset.

- **Run without review:** explicit permission to use the displayed saved/proposed
  inputs and valid catalogue defaults without a field-by-field review. Preserve
  user values, resolve all selected model inputs, record default origins, validate
  recipe/active identity, units, constraints and search bounds, then execute the
  selected scope. No extra Run or confirmation question is required. Unknown
  essential identity/material evidence or invalid bounds still need a focused
  question; this option does not authorize fabricated properties or prices.
- **Go to Edit for review:** open Edit for the selected scope. Use the Edit section /
  Confirm review / Previous flow above. After confirmation return to the parent;
  the user can select Run and choose Run without review to execute the now-reviewed
  values. Do not automatically start a simulation when Edit is confirmed.
- Empty/skipped/cancelled input executes nothing and preserves the draft. An empty
  draft asks the user to add a scenario before showing this question. A named
  subset remains that subset; do not silently expand the run to other scenarios.

Use metadata-only `run-choice` to resolve the actual submitted answer. It returns
`run`, `edit`, `previous`, `cancelled` or `needs_input` with the exact scope and
never runs the solver or changes review flags. The old `can_run` field describes
reviewed readiness; it does not disable the user's Run-without-review choice.

Read-only catalogue/schema validation and unit conversion are allowed during
editing. Do not calculate predicted outputs or feasibility until Run: this also
prohibits scratch Python/terminal formulas for pressure, viscosity, release,
settling or constraint feasibility. An ad hoc calculation is still a calculation,
even if it is not saved as a package simulation. Propose bounds for review without
solving them first; evaluate their feasibility only after Run.

Submit the exact values accepted through review or Run without review. An absent package field could introduce an
unseen default, so explicitly resolve all selected model inputs in the draft.
Shared fields are fixed for a scenario; recipe-specific overrides must respect
its declared `candidate_parameters`. If a user wants a normally shared condition
to differ, suggest separate named scenarios rather than inventing an invalid
override. Preserve the exact scenario-to-recipe mapping selected by the user.

For ordinary study comparisons, group only scenarios with identical recipe/active
sets and obey the current engine's scenario/candidate limits (currently four
scenarios and eight candidates per study). Split larger drafts into linked
studies without changing the configured evaluations. Do not take the union of
recipe selections and run unrequested combinations. Use simulation batches or
the dedicated analysis path for model keys excluded from ordinary studies. With
No acceptance limits, use an objective-only criterion where supported or a batch
without specification claims. AI + Physics searches only user-supplied or explicitly accepted variable bounds
and replays shortlisted values under the approved scope.

Report completed, partial and failed cases separately. Keep successful saved
results when a case fails; do not claim a failed case completed. Offer retry or
return to the editor without silently changing its inputs. After results, offer
PDF/ZIP exports and allow reopening this draft or switching mode with the same
recipes. Do not automatically start another run.

## Draft persistence and presentation

Persist a private JSON configuration draft in the active Sci profile's
`agriformulations/drafts/` directory (unique draft ID). This file is a configuration,
not evidence of computed results. Keep mode/project ID, stable scenario IDs,
model keys, selected recipe/active IDs, shared inputs, per-recipe inputs, input
origins, criteria, search configuration, reviewed sections and last deletion.
Include the mode in the draft identity. Switching modes creates a separate draft;
never overwrite the other mode's draft or its saved results. Reuse exact selections
only when the user requests it. Read the matching draft on resume. Save after each completed operation; use a pending copy for
an unfinished Add/Edit so Back cannot damage the saved scenario. A cancelled
question or context compression must not lose the draft or approve it.

Keep messages short and orderly. Use Markdown tables on supporting surfaces and
aligned columns in the plain CLI. Each screen has a short title, the current
selection or values, and one clear next question. Use schema field labels
(“Pipe length”, “Yield stress”) in the display; keep raw field keys in the saved
configuration, not as the primary table labels. For arrays, accept readable comma-separated values; for nested analyses ask for
named ranges, bounds or distributions in small groups and assemble JSON internally.
Do not narrate backend schema reads, source searches, draft/request file creation,
code paths, package internals, or historical solver behavior; present the current stage, the relevant values and the question.
Do not repeat every available model
outside Add/model selection, dump raw JSON, expose transport internals, use
unexplained parameter keys, or repeat long scientific disclaimers at every step.
Explain assumptions once per relevant group; retain them in the final results.

## Internal execution presentation

For internal requests, create a private JSON data file through `terminal`, then
invoke `sci --run-module agri_tool --request-file PRIVATE_REQUEST_PATH` directly.
For draft mutations, invoke the installed `scripts/scenario_draft.py` helper with
`--request-file PRIVATE_REQUEST_PATH` as described in `references/draft-commands.md`.
Do not pipe JSON into Python or construct inline interpreter code: this causes a
security approval prompt during ordinary setup. Preserve the normal scanner and
approval policy; use the file-based interface instead. Do not use
write_file/patch/edit_file tools for these internal files: the native UI preserves
file-edit cards even with routine tool progress off. Read current drafts before
updating them; use unique names and atomic replacement. These metadata operations
are allowed before Run; scientific calculations are not. Use file tools normally
when the user actually requests a source edit or document deliverable.

Keep user-facing text limited to recommendations, the current selection, the
current input group, concise progress, and results. Do not print commands or
internal paths. Offer report/data downloads with readable labels on supporting
surfaces. Give a real export path in the plain CLI only when needed to deliver a
requested file; never substitute internal code/draft/request paths for a report.
