# p38α — first bounded refinement and feedback pilot

Tracking: agent-scientist#33. Status: **specified; not executed**.
Purpose: exercise one complete optimization/assessment/feedback episode using
existing tools. Test whether the specialist makes an auditable, chemistry-aware
follow-up choice. This is development, not a base-versus-specialist benchmark.

Design choice: a larger one-shot batch would test search opportunity; a multi-tool
portfolio would also introduce unqualified route differences. Start with CReM
and one conditional feedback action to isolate the parent/library decision.
The two batches and 40 assessed candidates per batch are operational pilot caps,
not scientifically optimal settings or a guarantee of enough eligible molecules.
Later comparisons must give the base agent the same choices and allowances.

## Objective and eligibility

Explore new analogues of the supplied e072 lead for more favorable **native
Vina Score**, while retaining **PAMPA class 1**, **RDKit QED ≥ 0.5** and **RDKit
Crippen LogP 0–5 inclusive**. Lower native Vina Score is preferred. Do not mix
this endpoint with historical Smina values or infer experimental affinity.

Starting lead e072:
`CCC(C)(C)NC(=O)C(F)(F)c1cccc(NC(=O)Cc2cncnc2)c1`

Matched SB2 reference control, never a generation parent:
`C[S@](=O)c1ccc(-c2nc(-c3ccc(F)cc3)c(-c3ccncc3)[nH]2)cc1`

Both have already returned PAMPA class 1. The objective is docking-quality
exploration while preserving eligibility, not correcting a demonstrated PAMPA
deficit. No additional similarity cutoff or protected-core promise is imposed.
Report actual structural changes and similarity descriptively with their method.

## Fixed inputs and reusable readiness

Use the existing full observed 1A9U chain-A protein, not the old SBG pocket:

`/home/boltzmann13/.sci/profiles/ankith/workspace/08_results/target_conditioned_de_novo_design/p38_baseline_20261105T072302Z/inputs/derived/receptor_observed_A.pdb`

SHA-256: `54c71aeb21d1d528b9475a5d3f76014269ca5bb6de51f5ce07ced4c9a95f43e1`.
It contains 2,833 protein atoms and 351 observed residues. Preserve missing
regions and the original preparation limitations. Native SB2 coordinates:
`control_native.sdf` in the same directory, SHA-256
`db111b838854ff3658487d6c05b8e7f0dea8eaa682183ae6d4d7b3f00ebc9a34`.

Use `Vina_basic_docking` with center (3.707500, 15.850000, 28.973000), full
cubic side 23 Å, public `max_radius_size="23"`, `exhaustivness="8"`, and
`upload_sdf="True"`. Use the documented `processed_pdb` upload reference and
`smiles` upload reference. Vina ligand CSV headers are exactly `SMILES,NAMES`.

Completed technical checks, read only when needed:

- Vina job `6af4406cfe20edb9107da5fa`: successful pose/identity associations;
  report in the profile's `workspace/outputs/p38-vina-confirmed-resubmission-20261111T101601790587Z/`.
- PAMPA job `6af455a44bcdd4891fc0f85f`: both inputs class 1; report in
  `workspace/outputs/pampa-readiness-20261111T114615850213Z/`.

These are readiness evidence, not pilot candidate measurements. Do not repeat
readiness jobs, inspect historical generated pools, or reconcile/resubmit the
separate earlier UNKNOWN Vina request. Its unresolved billing remains disclosed.
Unavailable worker revisions or HTTP404 diagnostic logs alone are not blockers.

## Available actions and public request semantics

Use the active profile's native Boltzmann tools; inspect the current optimization,
QSPR and toolbox contracts. This pilot admits only:

1. `Fragment_Based_Optimization`: inline `ref_mol`, uploaded CSV `library_path`,
   `global_models=[{"name":"PAMPA","min_threshold":0.5,"max_threshold":1}]`.
   These are the source-supported proposed score bounds for this route, not
   common-assessor label bounds or a guarantee of deployed filtering. Inspect
   returned annotations and retain their actual meaning/precision separately.
   No supported number-of-molecules or steps control exists here; do not add one.
2. `Property_Prediction`: uploaded SMILES CSV and `global_models=["PAMPA"]`,
   without uncertainty/explainability requests. It returned **binary labels** in
   readiness. A successful class 1 passes; class 0 fails. Neither is a probability.
3. `Vina_basic_docking` with the fixed settings above. Keep every returned pose
   and failure record. Select CSV pose 0 / SDF pose 1 as in readiness; a missing
   selected pose is unavailable, not permission to choose a different pose.
   `Pose=-1,Score=100` is a failure sentinel, never a favorable observation.

Freeze the actual contracts and local RDKit version in the new output directory
before submitting. Use existing scientific Python where available; do not change
profile or connector sources. There is no requirement to recover private model
weights or exact historical injected-message bytes. A substantive change to
input, score or label semantics must be resolved or reported, not silently mixed.

The three candidate source libraries in [library_manifest.json](library_manifest.json)
are permitted exploratory inputs **when the user authorizes this task**. They
each contain 20 source molecules, not a promise of 20 generated candidates.
The original CSVs and their attribution remain unchanged. Earlier fragment
lookup counts used a different lead and do not establish e072 applicability.
Local structural admission is not experimental validation or SME endorsement.

## Allowances and stopping

| Operation | Maximum native submission attempts | Maximum input identities per attempt |
| --- | ---: | ---: |
| CReM generation | 2: initial plus conditional follow-up | One parent, one listed library |
| Common PAMPA assessment | 2 | 40 new candidates plus e072 and SB2 |
| Search Vina | 2 | At most those 40 candidates plus e072 and SB2 |
| Fresh final Vina | 1, reserved | 10 committed candidates plus e072 and SB2 |

Totals: **7 scientific submission attempts**, **80 new candidate assessment
slots**, **84 common PAMPA input attempts**, **96 Vina ligand attempts**.
Failures and ambiguous acceptance consume allowances. No retries, replacement
batches or top-ups. Uploads/status/downloads are recorded but are not scientific
submissions. Reuse a verified upload only if the native connector permits it.
On UNKNOWN submission acceptance, stop new scientific submissions and preserve
the original receipt for reconciliation; do not infer rejection from a dashboard.
Do not impose an unsupported backend attempt cap: CReM's hidden enumeration,
inference workload, pose count, cost and deployed version may remain unknown.

Use a two-hour pilot submission/monitoring window from first scientific
submission. Stop starting work when it expires; preserve any accepted job ID and
return WAITING/INCOMPLETE with exact continuation state. Do not assume that a
remote job was cancelled. Later status checks, downloads and local analysis of
already accepted jobs are permitted after this cutoff; they do not authorize
further submissions or restart the window. No currency/credit ceiling is supplied; report actual
provider amounts and unknown units without inventing a cost. The user-run prompt
authorizes possible service charges within these observable submission limits.
CLI interruption does not reset the clock, counters or final reserve.

## Execute, assess, then choose a follow-up

1. Verify fixed input/library hashes and source-only admission. Create a separate
   output directory and durable ledger before execution. Review the lead's actual
   structural features. Compare the listed library options and choose the first
   parent/library action with a hypothesis, alternatives and counterevidence.
   A mixed library is an available exploratory default, not a proven optimum.
2. Submit the initial CReM request once. Preserve its receipt, native job ID,
   statuses and full original output. Enumerate valid connected, canonical
   isomeric identities without standardizing away chemistry. Preserve specified
   stereochemistry and flag unspecified centers; do not enumerate new states.
   Record invalid rows, duplicates, lead/control recoveries and parent recoveries.
3. **Before reading generator property values or calculating candidate quality
   metrics**, commit an assessment subset of at most 40 new nonreference unique
   identities. Use `assessment_subset` from `prototype/feedback_policy/feedback_policy.py`
   with sorted canonical identities, allowance 40 and seed **1101**. Record the
   selection input, output and digest. Unselected outputs remain unassessed, not
   failures. Do not use a property/docking-selected subset or replace failures.
   Use identity-only parsing/summaries until commitment; preserve the complete
   raw file without displaying its prediction columns to select the subset.
4. For that subset, calculate QED and Crippen LogP locally under one frozen
   RDKit implementation; run one common PAMPA batch including both references.
   Join by verified identity, retaining raw labels and errors. Rounded generator
   predictions do not replace this common assay. Missing/nonfinite values,
   explicit inference errors or unresolved identity/semantics are unavailable,
   not negative or positive predictions. Keep successful binary labels separate
   from native optimizer scores. Inspect zero-valued records for failure evidence;
   never decide from zero alone. Dock only confirmed jointly eligible candidates,
   plus both references, in one search batch. If no candidate passes, do not run
   an extra control-only docking batch merely to use the allowance.
   Preserve contradictory repeated common PAMPA labels for an identical form
   and assessment context. Mark its eligibility unresolved; do not select the
   favorable label, overwrite a failure, or submit a tie-breaking assessment.
5. Make the first **feedback decision before another submission**. Summarize
   emission/unique/assessed/eligible counts, actual molecular changes, feature
   trade-offs, duplicate overlap, failures and pose evidence. Inspect leading and
   weaker assessed poses where available with explicit selection and mapping.
   Check gross geometry, placement and specified stereo; do not turn contact
   counts or absent clash flags into proof of binding. Compare eligible coverage
   and the retained pool's top-ten search mean; a best-score increase alone is
   not the complete-panel outcome. If fewer than ten exist, the full mean is null.
6. Choose **STOP** or one conditional follow-up. State: goal, evidence, options,
   selected parent/library and why, public payload, expected testable change,
   counterevidence and remaining allowances. The original e072 or an assessed
   generated candidate may be the parent only with an unconflicted, confirmed
   joint-eligibility record in this pilot; SB2 may not. Do not
   treat a library name as a demonstrated product change. A defensible exploratory
   change is allowed, but label its uncertainty. A repeat needs a stated question;
   “more molecules might score better” is insufficient justification by itself.
   Missing evidence does not require an automatic route switch. No Graph GA,
   other generator, receptor/site change or new scientific objective in this pilot.
7. If proceeding, apply the same steps to follow-up outputs, excluding all
   previously assessed identities/references, with subset seed **1102**. Previously
   unassessed first-batch identities may enter only if emitted in this follow-up;
   account for that overlap. No reassessment or replacement of previous failures.
   Verify whether the intended structural change actually occurred and record
   support, counterevidence, no new information and unresolved evidence separately.

The pure offline policy and observation helpers are available for reuse. Do not
feed synthetic fixture cards or self-invented qualification flags into them as
live facts. Native execution, admission and durable allowance accounting remain
the agent's responsibility; the component does not enforce backend budgets.

## Panel commitment and evaluation

From all assessed new, valid, jointly eligible candidates with successful search
Vina measurements, select up to ten by ascending native Score, ties by canonical
isomeric identity. Deduplicate and exclude original lead/control. Write ten slots
with explicit nulls if necessary, hashes and a timestamp **before final calls**.
Do not add candidates from old campaigns or from the unassessed pool.

If no generated identity can be committed, skip final submission, retain ten
unfilled slots and report no qualifying generated candidates. Otherwise run the
single fresh final Vina batch for committed identities and both controls.
Reuse the prior successful common PAMPA/QED/Crippen assessment only for the exact
same molecular identity under the frozen assessment context, with source pointers.
Any contradictory or changed method evidence leaves eligibility unresolved.
Do not call reused descriptors fresh. No endpoint replacement after commitment.

Keep the native Score and reported unit; if the unit is absent, state that rather
than imposing one. Compute final ten-slot mean, median, sample SD and range only
when all ten final scores and eligibility records are successful. Otherwise mark
the complete-panel result INCOMPLETE_EVALUATION, report coverage and null mean;
any partial statistics must be explicitly labelled. Separately report per-candidate
Score differences from same-batch e072/SB2, eligible yield, assessment failures,
search opportunities and resource use. Neither control occupies a generated slot.
Do not declare practical improvement from a tiny score difference, one pilot or
comparisons with historical Smina. No independent validation or biological claim.

## Deliverables and acceptance

Write beneath a new directory in the active profile's
`workspace/08_results/p38_refinement_feedback/`. Preserve source assets/readiness
records, frozen task inputs and the old UNKNOWN receipt. Retain raw artifacts,
upload/submission receipts, method settings, candidate ancestry and identity maps,
subset commitments, all returned poses/failures and a durable resource ledger.

Required concise outputs:

- `report.md`: executed workflow, initial and follow-up reasoning, actual chemistry,
  evidence that changes or weakens the recommendation, final coverage and stop reason.
- `candidate_registry.csv`, `measurements.csv`, `endpoint_panel.csv`,
  `summary_metrics.json`: phase/method-labelled values, null reasons, provenance,
  all ten slots and common-eligibility decisions. Retain raw precision.
- `decisions.jsonl`, `resource_ledger.csv`, `run_manifest.json`: goal, alternatives,
  selected action, public parameters, evidence paths, remaining counters and pending IDs.
- `artifact_manifest.csv`: paths and SHA-256 hashes, verified by read-back.

Integration acceptance requires actual generation, common assessment, feedback
decision and final assessment when eligible candidates exist, with identities,
limits and missingness preserved. A justified early STOP is valid decision behavior
but does not demonstrate an executed feedback improvement. A blocked or waiting
run is not completed scientific execution. Report workflow integration separately
from molecular quality. The parent performs a separate read-only critique after
the specialist; no additional scientific actions are implied.
