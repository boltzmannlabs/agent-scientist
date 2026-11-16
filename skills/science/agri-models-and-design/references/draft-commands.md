# Saved scenario draft protocol

This helper protocol belongs to the opt-in manual scenario editor. It is not a
required gate for the automatic formulation/cost optimization workflow.

The stdlib-only `scripts/scenario_draft.py` helper keeps recommendations and
editable scenarios in the same saved list. Run it with the available Python
through `terminal`; it does not import the scientific engine or calculate results.
Resolve its path from this installed skill. Never print the helper/draft path in
chat. Write the mutation payload as a private JSON data file through `terminal`,
then pass `--request-file PRIVATE_REQUEST_PATH`. Invoke the installed helper script
directly. Do not pipe into Python, use inline Python code, or load JSON as code;
the native security scanner correctly requests approval for interpreter pipelines.
Keep scanning enabled; do not ask the user to approve a pipeline for routine draft I/O.
No visible file-edit card is needed for these private metadata files.

Commands take `ACTION --draft PRIVATE_DRAFT_PATH --request-file PRIVATE_REQUEST_PATH`.
For `list`, omit `--request-file`. The request file contains one JSON object.
The shell can write JSON with ordinary output redirection, followed by a separate
direct helper invocation; no pipeline is involved. For example, with resolved
private paths and the helper path supplied by this skill:

```sh
printf '%s' '{"expected_revision":1,"scenario_ids":["S1"]}' > "$REQUEST"
python3 "$HELPER" delete --draft "$DRAFT" --request-file "$REQUEST"
```

- **create**: request includes `project_id`, `mode` (`design` or `ai_physics`), and
  `scenarios`. Every displayed recommendation must be included before the first
  parent menu. Each entry has a stable `id` (`S1`), readable `name`, exact `model`
  key and `recipe_ids`. Extra proposed input metadata is preserved. Create marks
  entries review_required and refuses to overwrite an existing draft.
- **list**: no request body. Returns the actual scenarios, revision and four menu actions.
  Render this returned list in chat. Delete/Edit targets come from it. The returned
  delete_selector is one question; bulk_delete_confirmation is asked only after
  an explicit All selection.
  Use the selector templates unchanged with multi_select=false. Up to three
  scenarios are direct radio choices; Enter selects the highlighted scenario.
  For three rows, More options opens delete_more_selector. For longer lists,
  Choose a scenario / Choose multiple scenarios opens delete_id_selector; it has
  no choices array and collects typed IDs. Do not create a checkbox picker.
- **delete**: request includes `expected_revision` from list and `scenario_ids`,
  either a list of user-selected IDs or the literal `"all"` after an explicit All
  answer. A bulk clear (literal All or every ID in a multi-row draft) also requires
  confirm_all=true, obtained only after the separate user confirmation. Empty or
  unknown IDs, stale revisions and missing bulk confirmation leave the file
  unchanged. Output contains the remaining scenarios.
- **undo**: request includes `expected_revision`. Restores the last deletion.
- **upsert**: request includes `expected_revision` and a full `scenario` entry.
  Retain its ID for edits. For Add omit ID to allocate the next unused S-number.
  Extra metadata holds shared/per-recipe inputs, origins, search settings and
  reviewed sections. Set `status: "ready"` only after all required sections are
  reviewed; otherwise use `status: "review_required"`. Older `ready: true` entries
  without a status are normalized by the helper for compatibility.

After any mutation, use the returned list/revision. On a stale revision error,
list again and resolve the intended selection; never silently delete another row.
The helper locks each draft while reading, checking its revision and saving, so
two sessions cannot overwrite one another. A busy draft fails unchanged after a
bounded wait; list it again before retrying. Lock files are metadata, not scenarios.
There is no run command in this metadata helper. The agent checks readiness and
uses the scientific package only after the user's Run choice.

If an older session displayed recommendations without a draft, reconstruct those
exact displayed rows as review_required entries before offering deletion. Do not
show an empty list while S1/S2 still appear in the recommendation table. Save a
fresh draft per mode; previous scientific results are never targets of this helper.

## Recipe selection without checkboxes

Use `recipes --request-file PRIVATE_REQUEST_PATH` (no draft path required) before
Add/Edit recipe selection. Payload: `{"recipes":[{"recipe_id":"R-a","name":"Recipe A"},{"recipe_id":"R-b","name":"Recipe B"}]}`.
Render the returned numbered recipes and use `selector` unchanged in native
`clarify`. Send the same recipes plus `answer` from `user_response` and the actual
clarify `outcome` to resolve selection. `status=selected` returns exact saved
`recipe_ids`; retain them in the pending wizard and continue. Do not send the
question's default as an answer. This command never writes a draft or runs physics.
`needs_input` means keep asking the same step, without dropping the pending Add;
`previous` navigates back; `cancelled` exits without a mutation. Unknown IDs are
errors, not a reason to select All. `Choose recipes` returns a free-text selector
for comma/space-separated recipe numbers or IDs. Never use checkbox selection for
All or silently reset a confirmed selection.

The helper response wraps the question in `selector`: submit the WHOLE selector
object as one item of native clarify's `questions` array. Do not submit only its
`question` string, and do not omit its `choices`: that would create a free-text
question even though the screen describes radio choices. The structure is
`{"questions":[{"question":"Which recipes should this scenario include?","choices":["All eligible recipes","1 — <actual first recipe name>","2 — <actual second recipe name>","Previous"],"multi_select":false}]}`
for two recipes; copy actual labels from the helper rather than inventing IDs.
Check that the native question has the returned choices before sending it.

## Run choice and confirming Edit review

`run-choice --draft PATH --request-file REQUEST` is read-only. Include optional
`scenario_ids` (otherwise the displayed draft scope), actual `answer` and clarify
`outcome`. Send the returned selector as one complete native question, including
both choices. A `run` result authorizes the selected scope only after the agent
resolves and validates its input values; `edit` opens Edit. No answer or an
unsubmitted response never starts execution.

`confirm-review` is a mutation with `expected_revision`, `scenario_ids` and exact
`confirmation: "Confirm review"`. Before calling it, resolve inputs and check the
current model schema. Save edits via upsert as review_required first. Confirmation
rejects absent/unresolved inputs, marks only the selected rows Ready and returns
the parent list. It never executes physics. `edit_actions` supplies the Edit section /
Confirm review / Previous question. Display current values before that question.

## Agent Choice and overflow

All returned selectors include Agent Choice. Use action_selector for the parent,
and edit_actions for Edit. Canonical actions is not a button list. If a selector
has more_selector, More choices opens it and Back to choices restores the original
selector. Do not lose the overflow options. The question action (no draft needed)
wraps any question/choices object with the same rules. For long candidate lists
use numbered free-text selection with Agent Choice as a button, not a long array.

Agent Choice returns agent_choice from recipe/run resolvers, without selecting
anything or executing. Resolve it using the workflow's references/agent-choice.md;
record the concrete selection and reasoning with record-decision before continuing.
This mutation requires expected_revision, answer="Agent Choice", outcome="submitted"
and decision with question, options, selected_option and reason. It preserves
scenario contents and returns agent_decisions. It does not run physics. Transfer
pre-draft decisions when the selected-mode draft is created. Retain the complete
ledger in final report data and show its selections/reasons in the results.
