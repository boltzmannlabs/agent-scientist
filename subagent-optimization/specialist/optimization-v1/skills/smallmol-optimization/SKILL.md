---
name: smallmol-optimization
description: Carry out a delegated molecular-optimization investigation using observed candidate results to select supported parent–library actions, preserve task constraints, and return an evidence-backed selection or stopping decision.
---

# Molecular optimization investigation

Own the scientific investigation within the assignment. Use the host's current
capability contract, calculated evidence and execution path. The assignment fixes
the original reference, property objectives, parent eligibility, final-success
rules, available libraries and resources. A separate specialist role does not
grant new scientific capabilities or spending authority.

This entrypoint and the selected CReM module are already injected into the current
specialist context. Do not reread either with `skill_view`; load another conditional
reference only when its information is needed.

When delegated from the main agent with a task-file path and `smallmol_campaign`
available, use the selected [main-agent bridge procedure](references/main-agent-bridge.md).
Fetch the checked evidence packet through that tool, apply the structured decision
through the same tool, and return its actual receipt to the main agent. The host
still owns scientific execution. A task file alone is not a campaign snapshot.

## Read the current state

Start each episode from the supplied campaign snapshot and input digest. Inspect
the complete task, pending/uncertain work, previous decisions and calculated
candidate summaries before choosing an action. Use `leadopt_campaign` only for
the host-permitted read operations. Actual receipts and observations are recorded
by the host; do not create or overwrite calculated evidence yourself.

For CReM, use [the already supplied tool-specific guide](references/crem.md) before
preparing a generation request; do not fetch it again. For incomplete/conflicting evidence or a resumed job, read
[evidence and continuation](references/evidence-and-resume.md). External references
inform this procedure; [source attribution](references/sources.md) explains their
limited reuse. Do not load unrelated tool instructions.

## Choose an informative action

1. Identify the current limiting objective and distinguish final targets from
   nonnegotiable parent/structure restrictions. An unfinished property target does
   not automatically make every observed molecule an inadmissible parent.
2. Use calculated constraint gaps, QED, original-reference similarity, diversity
   and attempted-action summaries. Do not reconstruct descriptor calculations
   from molecular strings in prose. Missing calculations are missing evidence.
3. Compare refining a promising neighborhood with exploring a different one.
   Consider feasible candidates and informative trade-offs rather than selecting
   only the largest single score. Pareto membership does not waive a hard rule.
4. Choose an admitted exact parent form and library, citing observed evidence.
   State the question, the expected informative result and what observation would
   change the next decision. Hypotheses are not calibrated probabilities or
   established chemical mechanisms.
5. Check the action ledger. Library reuse with another parent can be informative.
   Repeating identical parent/library/objective/tool settings needs an explicit
   supported reason, such as a genuinely stochastic repeat; lost context is not
   a reason. Use the supplied deterministic reference as a real alternative.

The original task reference remains the assessment anchor after every reseeding.
Record immediate-parent lineage separately. Similarity is not proof of preserved
scaffold, target activity or synthesizability. A structural difference is not
automatically an isolated causal transformation.

## Execute, observe and adapt

Follow `capability_contract.execution_mode`. In `host_mediated` mode, return
`status="action_requested"` with `chosen_action.kind="generate"` and the actual
parent ID, library ID and supplied action key. The qualified host executes that
scientific request through the normal connector and resumes the same investigator
with actual observations. This supports separate scientific/scoring interpreters;
the main agent does not re-plan the investigation. Do not call scientific execution
tools or invent a pending job in this mode. A blocked or planning-only proposal
must not be promoted into dispatch. Respect cumulative remaining submissions.

Prepare only documented inputs through the existing connector. Preserve the
selected property models and bounds. Respect the host's admission result and
the assignment's approved experiment identities. Never invent model IDs or
worker-managed fields to make a request pass.

After submission, retain the exact returned job identity. Return `waiting` while
science is queued, running, or awaiting host artifact assessment. The host can
monitor without repeated model reasoning and resume this logical assignment when
new evidence arrives. A timeout does not cancel an accepted remote job.

After complete evidence is imported, update the scientific decision using both
helpful and negative outcomes. Distinguish no products, duplicates, poor progress,
missing predictions and conflicting predictions. None establishes global
infeasibility or permission to relax the task.

## Finish the episode

Return the assignment's structured outcome, bound to its identity and digest.
Distinguish action_requested, waiting, completed, stopped and blocked. Use actual candidate and
evidence IDs. Success requires one candidate jointly satisfying every final rule;
rank infeasible trade-offs separately. State no qualifying selection when that is
the outcome. Explain whether work ended through success, exhausted allowance,
no new admissible candidates, no justified next action, or a concrete dependency.

Report raw provider predictions as predictions. Do not invent physical units,
uncertainty, model revisions, experiments or unobserved internal evaluation counts.
Summaries and recommendations must remain traceable to retained observations.
