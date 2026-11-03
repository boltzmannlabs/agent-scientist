# Initial workflow review: specialist decision scope

Tracking issue: [agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33).
Original tracking: [science-environments#89](https://github.com/boltzmannlabs/science-environments/issues/89).
Related environment: [science-environments#46](https://github.com/boltzmannlabs/science-environments/issues/46).
Date: 2026-11-02. Status: Research; specialist responsibility remains proposed.

## Purpose

Use the existing DRD2 case to understand the workflow and identify a useful
scientific decision before implementing one specialist. This review does not
select a new benchmark, change task rules, launch a model or submit science jobs.

## Existing workflow

| Stage | Existing responsibility | Possible specialist contribution |
| --- | --- | --- |
| Read task and baseline | Main agent reads the exact lead, evidence signatures and task protocol. | Receive these unchanged in its assignment. |
| Choose an investigation | Main agent chooses a proposal route and justified settings using available capabilities. | Analyse compatible prior results and recommend one supported next investigation. This is the hypothesis to test. |
| Execute | Existing native tools/connectors perform authorised work; the task also supplies a local assessor. | Return scientific advice within the agreed assignment. |
| Assess and record | Existing assessor calculates scores; environment records candidate evidence and supplies progress. | Interpret a scientific bottleneck using those observations; arithmetic remains with code. |
| Continue or stop | Main agent applies task stopping and selection rules. | Return a task-consistent recommendation, without changing the rules. |

The environment's `scientific_progress` exposes assessments, compatible evidence
coverage, baseline dependencies, decisions, attempts and resources. It explicitly
does not select the next scientific action. This creates a place to investigate a
policy, but the base agent already reasons about that choice; delegation must
demonstrate additional value.

## Task rules retained

The same candidate must improve both the pinned DRD2 classifier probability and
QED strictly over the baseline and have Morgan count-fingerprint similarity
strictly above 0.7. Return zero or one distinct nonbaseline candidate. Stop when
a valid candidate meets all conditions. The current protocol declares no numeric
candidate/submission/time caps. Any revised comparison needs a separately agreed
protocol; this review introduces no new limits or continued search after success.

Classifier probability is computational evidence, not measured receptor potency.

## Documented external controls

| Tool | Fields in the inspected local contract | Important boundary |
| --- | --- | --- |
| Graph GA | `smiles`, `n_mols`, `n_steps`, selected global/custom models and thresholds | At least one model selection is required. The listed global-model names do not include DRD2 or QED. Custom-only backend execution is explicitly unverified. |
| Mars Plus | `smiles`, `n_mols`, `n_steps`, global/custom model fields | A starting-molecule choice is documented. Live acceptance, reward behaviour and internal adaptation were not qualified here. |
| REINVENT | `n_mols`, `n_steps`, `finetune`, conditional data/model references and property selections | The inspected schema has no direct `smiles` field. Do not assume the starting-molecule interface or internal behaviour matches the other tools or upstream REINVENT4. |

Starting-molecule SMILES is different from a random-number seed. These fields
are possible external choices, not proof of end-to-end readiness. Counts and
optimisation steps do not establish matched scientific computation or account
for unknown internal work. A hosted generator's internal reward must remain
distinct from the fixed DRD2 task assessor.

## Existing evidence and comparison limits

The saved single-task review reports six proposals, five computational qualifiers,
one frozen selection and zero remote scientific submissions. That record supports
an execution walkthrough, not successful hosted-generator qualification or a
base-versus-specialist performance claim. Its first-success ceiling may make a
different prospectively selected task necessary for measuring search improvement.

The existing DRD2 protocol compares base without environment assistance against
an environment-assisted arm. That tests a different contribution. For the new
specialist comparison, hold environment support common and distinguish:

1. Current base agent.
2. Main agent with the proposed scientific guidance.
3. Same guidance delegated to one specialist.

Include a simple deterministic policy where appropriate. Initially keep the LLM,
scientific access and task settings matched; count parent and child reasoning.
Model/profile routing can be evaluated as a separate factor later.

## Next decision

Identify one task-permitted investigation whose choice depends on prior
observations and is genuinely controllable outside the chosen optimiser.
Document the inputs, rationale and evidence that would reverse that choice.
Check whether the optimiser already performs the same adaptation internally.

The first candidate is observation-conditioned selection of the next starting
molecule/branch or missing assessment. It is conditional, not the final agreed
specialist capability. If the tool already owns the choice, a simple policy
suffices, or the task ends before a useful decision occurs, revise or defer the
specialist rather than adding another controller.

## Evidence scope

This review inspected existing task documentation, saved run review, progress
source and the local canonical tool contract. Source paths and SHA-256 values
are recorded in [references.md](references.md). These working sources include
unpublished local changes and are not all present on BoltChem. No scientific
execution, native child launch or new benchmark was performed.
