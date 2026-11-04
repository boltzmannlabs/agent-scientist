# Proposed molecular-investigation specialist

Tracking: [agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33).
Original research: [science-environments#89](https://github.com/boltzmannlabs/science-environments/issues/89).
Date: 2026-11-03. Status: local development definition and advisory adapter implemented;
actual LLM reasoning and scientific benefit untested. See [implementation](../specialist/README.md).

## One responsibility

Given an unfinished task, compatible observations and a finite approved library
menu, choose one **untried** library to investigate an evidence-backed local
analogue hypothesis. Explain supporting pairs, counterexamples, uncertainty and
what observation would change the recommendation. A valid response can abstain.

The scientific unit is an observed chemical transformation in a declared context,
not a molecule's aggregate score or a job's completed status. The current code
implements a simple transfer heuristic to compare against; it is not this
specialist's complete scientific reasoning.

This direction requires at least two scientifically meaningful, approved library
choices. Libraries may be broad chemistry sources; target-specific activity is a
separate evaluation problem. The role neither curates a library per target nor
assumes parsed-set differences alone make useful experimental alternatives.

## Candidate ideas and current choice

| Idea | Scientific question | Current boundary |
| --- | --- | --- |
| Context-conditioned edit transfer | Where does an observed edit pattern support another local investigation? | Preferred role; needs qualified parent/site/context annotations and relevant library cards. |
| Hypothesis-discriminating analogue panels | Which observation separates transferable effects from context-specific or combination effects? | Useful later, but current library choice cannot guarantee exact matched products/sites. |
| Adaptive allocation across chemical regions | Where should the next generation effort go? | Only meaningful with actual region controls, comparable evidence and honest internal-compute accounting. |

CReM provides a concrete public library input. This is a candidate initial
workflow for the specialist study, not a revision of the existing DRD2 campaign
or permission to submit jobs. Changing Graph GA steps alone lacked a sufficiently
specific scientific decision. Expensive-score acquisition is not justified for
the cheap deterministic DRD2/QED assessor; assess all valid returned proposals.

## Responsibility and execution

| Component | Ownership |
| --- | --- |
| Main agent | Overall task, clarification/authorisation, acceptance, native connector execution, recovery and final report |
| Environment/helpers | Durable state, exact comparisons, deduplication/provenance, compatible evidence summaries and resource records |
| Specialist | Assigned scientific hypothesis and one evidence-linked next-investigation recommendation |
| Independent evaluator | Frozen outcome/rule checks, cost/quality comparison and scientific review; never the specialist's own critic |

Do not let the main and specialist independently submit competing investigations.
No routing instruction or response schema establishes a native permission sandbox.

## Proposed input contract

Reuse existing task/evidence records rather than introducing another scientific
submission schema or campaign database. Supply:

1. Exact original reference/form, objectives, hard constraints, fixed assessor,
   stopping rules and genuinely agreed resource allowance, including unknowns.
2. Candidate structures and compatible unrounded observations with IDs, units,
   method/version/context, validity and missing/censored evidence explicitly.
3. Qualified parent-child/site mappings, isolated versus simultaneous edits,
   supporting pairs and counterexamples under a versioned family definition.
4. Approved immutable library assets, reviewed fragment/context capability cards,
   actual availability and verified action controls. Record overlaps and known
   material identities; library labels alone are not chemical evidence.
5. Previous investigations, decisions, pending/unknown attempts and current task
   state. Archived/frozen development cases cannot become live assignments.

Keep fixed instructions concise. Retrieve exact supporting records by ID as
needed; omitted history is retrievable, not absent evidence. Deterministic code
prepares tables and arithmetic; the role must not spend model calls reproducing
those operations. Unchanged evidence should reuse prior advice.

## Proposed output contract

- Disposition: recommend an investigation, request information, stop or skip.
- Selected approved untried library ID/content version, when justified.
- Scientific question, working hypothesis and credible competing interpretation.
- Supporting and contradicting observation/pair IDs; unresolved information.
- Why this investigation is preferable to the simple baseline or alternatives.
- Expected informative observation and outcome-dependent next decision.
- Assumptions, costs/unknowns and a task-consistent stopping reason.

Do not require a fabricated hypothesis or executable action for skip/defer/stop.
No invented model IDs, payload fields, uncertainty intervals or measured potency.
No relaxation of original constraints or substitution of generation reward for
the task assessor. Qualification always uses the original reference.

If the intended edit family is absent from generated products, report that the
proposed chemical hypothesis was not tested. Do not reinterpret any returned
structure as a successful controlled experiment merely because the job completed.

## Invocation and no-go conditions

Invoke only when a real scientific choice remains. Skip already successful,
closed/frozen or unchanged tasks, arithmetic-only work and choices fully owned
by the optimiser. Main handles ordinary execution errors and ambiguous-job
reconciliation. Defer when controls, annotation quality or critical evidence are
missing. Exhausting the approved menu does not prove chemical infeasibility.

## Evaluation proposal

Predeclare the task/library cohort, original-reference rules, stopping/resource
accounting, exposure, complete-output handling, evaluator and meaningful benefit.
Keep scientific tools, environment support, helper access and model settings
matched initially. Compare fixed-order/simple-policy baseline, current main,
equally guided main, and identical guidance delegated. Count all parent/child
work and unsuccessful starts. Model/profile routing is a separate later factor.

Measure task success and resources to first qualifying analogue, with actual
internal row/model costs where available. Equal jobs are not equal compute.
Known archived episodes and artificial fixtures are development material; they
cannot establish protected-holdout performance or molecular improvement.

If the guided main or simple code matches the specialist at lower cost, retain
the simpler implementation. Separate delegation is an experimental choice.

## Dependencies before scientific use

- Internally checked actual transformation annotations and library capability cards
  when the selected policy makes edit-specific claims;
  numerical support thresholds, if used, must be prospectively agreed.
- Real approved, versioned library CSVs and normalized/material identities;
  input-to-fragment coverage and actual product enrichment need checking.
- Qualified model bundle, units, service behaviour, execution costs and native
  child tool permissions; public/worker field presence is not live proof.

The local bundle adds a saved-specialist definition and host-side handoff checks.
It does not establish scientific model improvements, successful training, a
completed molecular benchmark or meaningful use across arbitrary targets.

## First executable study

The [conditional pilot](../pilot/PROTOCOL.md) starts with one common CReM library
and one optional follow-up library decision per arm. It uses complete fixed-assessor
observations and keeps edit attribution unknown unless separately established.
It therefore does not require invented pair annotations to run. We perform the
internal development checks with the user; no external SME dependency is imposed.

The initial capability is choosing the next informative library after an
unfinished lead-optimization attempt. Later capabilities can include deciding
which candidate region to investigate or when evidence warrants stopping, but
each needs a measurable decision and a comparison first. De novo generation
would need its own task contract and policy; it is not implemented by renaming
this lead-optimization workflow.
