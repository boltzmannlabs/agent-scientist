# Agent Choice for formulation questions

Offer **Agent Choice** in every formulation question with multiple alternatives,
including mode, scenario, recipe, parameter review, navigation, Edit and Run.
Apply this rule before older examples that show fixed button lists. It governs
formulation workflow questions, not external security/credential/approval dialogs.

## Display

Use the model skill helper's `question` action to wrap a question/choices object,
or its already decorated scenario selectors. Send question, choices and
multi_select to native clarify, retaining helper metadata in the pending draft.
Never exceed four buttons. Up to three manual choices fit beside Agent Choice.
With four manual choices the helper displays two, More choices, Agent Choice;
More choices opens more_selector, and Back to choices restores the first screen.
All original actions remain reachable. For larger lists, show numbered options
and allow typed selection through Other alongside Agent Choice and Previous.
Use action_selector for the parent menu, not the raw canonical actions list.
Use edit_actions for Edit. Keep recipe/deletion pickers single-select.

## Resolve delegation

Selecting Agent Choice explicitly delegates the CURRENT question. Assess the
original objective, hard constraints, known recipe/input data, model applicability,
existing results and the actual options. Choose the most suitable valid option,
briefly state the option and reason, then continue that option's workflow without
asking the user to make the same selection again. Subsequent questions also offer
Agent Choice; whole-workflow delegation requires an explicit user request.

Prefer options that satisfy hard constraints, then the stated objective and
practical feasibility. Use existing measurements or saved results for rankings;
do not invent prices, measurements, material properties or claimed improvements.
A model-selection decision can use known model scope without running simulations
before Run. For recipe comparisons, All eligible recipes may be appropriate when
all are relevant and within scope; it is not a universal default.

At Run, Agent Choice can choose Run without review when inputs are resolved,
schema-valid and within the requested execution scope. Otherwise choose Edit to
resolve the setup. The delegated Run choice authorizes execution; do not repeat
the same question for manual approval. At a parameter question it can accept
valid displayed defaults as explicit exploratory assumptions and record them.
It cannot fabricate essential missing facts. Ask only for indispensable missing
facts when no grounded choice can proceed, and explain that blocker.

For deletion or bulk confirmation, consider the user's stated cleanup goal and
actual IDs. Do not select destructive cleanup solely because it is cheap or a
button is focused. Prefer Keep/Previous when no justified deletion target exists.
An explicit delegated cleanup goal may resolve a deletion, preserving the existing
scope, confirmation protocol and undo safeguards. Never extend this delegation to
purchasing, deployment, contacting suppliers or modifying unrelated records.

## Persist and report

Each decision records question, actual options, selected option(s), reason, inputs
and constraints used, assumptions and affected scenario/recipe IDs. In a draft,
use `record-decision` with expected_revision, answer="Agent Choice",
outcome="submitted", and decision={question, options, selected_option, reason,
inputs_used, assumptions, scenario_ids, recipe_ids}. Update the revision from its
response before another mutation. Agent Choice alone is not a resolved selection:
recipe/run resolvers return agent_choice without changing data or running physics.
After recording, pass the concrete selected option to the ordinary resolver/action.
Before a mode-specific draft exists, keep the same ledger in the conversation's
pending setup and transfer it into the draft when created. Retain the ledger when
exporting; do not claim the numerical engine generated the reasoning. If the
package PDF does not accept the decision ledger, include its table in the chat
results and provide a companion JSON/CSV; verify before claiming it is in the PDF.

Run Summary and detailed final results must include an **Agent decisions** table:
Question | Agent-selected option | Why it fits the objective/inputs | Assumptions.
Keep direct user choices distinguishable. Do not present Agent Choice itself as
the selected model/recipe or as evidence of experimental validation.
