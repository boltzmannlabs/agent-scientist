# Mode selection before formulation optimization

For a request to optimize/optimise a formulation, reduce its cost, improve a
specified performance, compare candidates or find a better formulation, use native
clarify to ask the mode BEFORE any simulation, search, cost campaign or setup-data
questions. This includes saved recipes and requests described as automatic.
Read-only recipe/catalogue retrieval is allowed before the question; explain the
objective and baseline briefly. Do not force another recipe-creation stage.

Use the model skill helper: `mode-choice --request-file PATH` with `{}` to obtain
the complete selector. No draft is required. Send its question/choices/multi_select
to native clarify. It provides four choices:

- DESIGN STUDY — compare saved candidates at selected conditions.
- AI + PHYSICS DESIGN — search supported ranges, then compare shortlisted settings.
- NOT NOW — preserve recipes and stop evaluation.
- Agent Choice — choose a suitable mode from the goal and supplied evidence.

Resolve the actual answer/outcome through mode-choice. Only selected with mode
`design` or `ai_physics` enters setup. `agent_choice` means resolve delegation
according to references/agent-choice.md, record the actual mode/reason and continue
without asking the user to select that mode again. Empty/cancelled/unsubmitted or
not_now starts no evaluation. Unknown input is not automatic authorization.

Choosing a mode does not itself authorize simulations: collect its clear input
questions and use the existing Run without review / Go to Edit / Agent Choice flow.
Missing quotes/properties are addressed after mode choice, not instead of it.

Do not repeat the question if the current request explicitly says Design Study,
Design mode or AI + Physics Design, or a mode is already selected for the continuing
run. Explicit requests to let the agent choose the mode can be resolved directly
with the selection and rationale recorded. Generic "optimize automatically" is
not an explicit mode selection or delegation. A direct named standalone calculation
(e.g. a specified single-model simulation) retains its direct path; it is not a
formulation optimization campaign.

Regression examples that MUST ask the mode first:
- “Optimize my saved SC recipes for cost and storage stability.”
- “Automatically find a cheaper formulation using the supplied inputs.”
- “Improve these two recipes; keep the same active loading.”

Explicit choices that proceed to setup without asking again:
- “Use Design Study to compare these recipes.”
- “Use AI + Physics Design with the saved formulation.”
- “Choose the design mode for me based on this problem.”
