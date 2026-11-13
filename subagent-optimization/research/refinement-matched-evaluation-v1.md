# Matched refinement evaluation — draft contract v1

Tracking: agent-scientist#33. Status: **proposed evaluation design; not frozen or
authorized for execution**. Prepared 12 November 2026. This document neither
renews the completed p38 pilot nor requests new scientific jobs.

## Goal, alternatives and selected design

Goal: test whether delegating the next small-molecule refinement decision to the
specialist improves complete eligible-panel quality under the same scientific
tools, information and observable service allowances as a capable base agent.
Record execution overhead and context use separately.

The [proposed scientific-reasoning addendum](scientific-reasoning-contract-v1.md)
records evidence typing, uncertainty-to-decision consequences, computational
versus experimental feedback and visible multi-objective trade-offs. It is for
equal application to future arms before freezing; it does not change the issued
shared-preparation task or add endpoints, submissions or selection rules.

More sampling without a comparator tests search opportunity. Another request to
the same final scorer does not establish independent scientific validation.
A base-versus-specialist comparison can test the stated delegation question,
provided knowledge, execution safeguards and scientific opportunities are shared.
Choose that comparison, initially on one optimization workflow.

Use a **shared initial evidence packet**, followed by one independently chosen
continuation per arm and the same final-assessment rule. This restricts the
comparison to continuation decisions and reduces duplicated setup while retaining
actual new generation and assessment. Without a matched aggregate reasoning
budget it evaluates the configured delegation workflow, including extra context/
reasoning resources; it does not isolate a specialist reasoning effect.
It is not a from-scratch tool-discovery benchmark. A later broader
workflow-planning test needs its own contract.

The first proposed test is **one matched pilot pair**, for protocol qualification
and a descriptive outcome. It cannot establish general superiority. Any larger
study needs a prospectively fixed case/repeat count and analysis, informed by
variance and desired uncertainty rather than selecting repetitions after wins.

## Treatment and strong comparator

| Item | BASE_WITH_GUIDANCE | BASE_PLUS_SPECIALIST |
| --- | --- | --- |
| Scientific decision maker | Main agent, no delegation | `smallmol-design`, delegated by the main agent |
| Model/provider | Same pinned model/provider | Same; no stronger specialist model |
| Scientific knowledge | Shared task, decision guide, selected skills/modules and helper code | Same scientific content |
| Tools | Native CReM, Property_Prediction, fixed Vina; shared local helpers | Same tools and helpers |
| Starting observations | Identical shared initial packet | Identical shared initial packet |
| Scientific opportunities | Same continuation/final maxima | Same maxima |
| Decisions | May inspect chemistry, compare libraries/parents, adapt or STOP | Same choices |
| Output | Same ten-slot panel and records | Same contract; parent does not quietly replace the specialist's decisions |

The baseline receives the useful scientific guidance; specialist-only domain
knowledge would confound an architectural/delegation comparison. Do not weaken
the baseline by forbidding feedback, pose inspection or reusable scripts.
Separate histories and output directories support separation but do not by
themselves prevent cross-arm access.

Use new conversations with equivalent approved profile configurations and live
scientific access, frozen contract snapshots, methods, assets and service settings. Record
extra automatically supplied guidance and model/context usage. Exact historical
message-byte identity is not required; a material information advantage must be
resolved before a matched interpretation. Neither arm sees the other arm's decisions or products
before both results are frozen. Critiques happen after both arms finish.

The assisted arm's parent is an **operational relay only** before commitment.
It may pass the assignment, preserve receipts, relay failures and enforce scope,
but must not suggest molecules, advise parent/library choices or revise the
specialist's scientific decision. Safety/resource stops remain allowed. Record
all parent/child model use. Scientific steering by the parent is a protocol
deviation, not an unreported change to the treatment.

### Access isolation

Before launch, qualify an existing sandbox or separate execution-account boundary
that actually covers file, terminal/Python and artifact access. Each arm receives
only the common packet, frozen helper copies and its own outputs/history. Disable
shared conversation-memory injection. Do not expose other-arm receipts, job
listings, mutable helpers or operator/reviewer directories. Common assets must
be read-only. Verify the boundary with benign marker-file/history checks, not
additional scientific jobs.

The current same-profile unrestricted terminal is not proof of isolation. If the
runtime cannot enforce these boundaries, label the exercise a procedurally
separated development comparison, not an isolated matched benchmark. Actual
cross-arm outcome access or a material information advantage invalidates the
matched scientific interpretation; disclosure alone does not repair it. Preserve
deviations and results rather than silently replacing a pair.

## Case selection and packet preparation

The completed p38/e072 run is **development evidence**, not an untouched holdout.
It informed the revised decision guide and cannot be used to claim an unbiased
new benchmark merely by hiding its report from the next agent.

The [SB202190 case](../specialist/feedback-v2/evaluation/matched-v1/case-sb202190-v1/README.md)
now has a completed shared initial packet and [separate artifact review](../results/sb202190-shared-packet-review.md).
It is a deliberately selected within-family case, not a scaffold holdout. Its
new [development-pair kit](../specialist/feedback-v2/evaluation/matched-v1/case-sb202190-v1/arms-v1/README.md)
explicitly chooses procedural separation in the existing profile, with approval
and isolation limitations disclosed. It does not claim the stronger controlled
setup described here. No service permission follows from this design document.

**13 November completion update:** both development arms are now frozen and
[separately reviewed](../results/sb202190-development-pair-review.md). They chose
the same action, selected the same 40 new identities and committed the same eight
generated forms plus two null slots. BASE's final request failed; the specialist
delivered eight valid final results. Neither has a complete-panel mean, and no
specialist selection benefit was demonstrated. No retry or further scientific
continuation is authorized by that review.

Before live testing, the operator must choose and freeze a justified starting
lead/case, provenance, target/control identities and inputs. Select from a
documented, outcome-blind source/rule, not from whichever previous output scored
best. Use fresh outcomes for the matched pilot; preserve a reused development
case only as a separately labelled regression exercise.

The shared packet must be materialized and checked **before** either agent is
given an execution assignment. It includes:

- Lead SMILES, fixed target/scoring inputs and native control coordinates, with
  identity/chain/preparation records and known uncertainties.
- Common eligibility/quality definitions, tool contracts and documented public
  parameters; actual approved source CSVs and provenance/content hashes.
- One initial mixed-library CReM batch; a committed outcome-blind subset of up
  to 40 new identities; common PAMPA/local descriptors and eligible-candidate
  Vina results, plus both reference controls.
- Full returned artifacts, poses and failure records, rather than just a small
  summary that makes structural review impossible. Compact summaries link to them.
- Common local parsing/accounting/selection helpers; actual remaining counters,
  existing native IDs and explicit setup/partial-validation authorization.

Do not make agents retrieve unavailable private model provenance or manufacture
missing packet files. Unavailable deployed revisions, costs or native seeds are
recorded limitations unless a required scientific interpretation is unresolved.
The draft is not runnable until the case and complete packet are frozen. No
additional readiness jobs or arbitrary compound selections are authorized here.

Shared preparation has a fixed per-stage attempt allowance. Failed/ambiguous
native attempts count; partial or negative outcomes remain in the common packet.
Do not regenerate, change the case or rebuild a packet because its results are
unattractive. UNKNOWN acceptance pauses both arms pending reconciliation. A
skipped stage is not falsely counted as completed work. Technical input repairs
before observing outcomes are distinct from outcome-driven replacement.

## Fixed scientific contract

For this proposed first comparison, retain the tested endpoint definitions:

- Common `Property_Prediction` **PAMPA class 1**; optimizer annotations remain
  separate and do not replace the common binary assessment.
- Local RDKit **QED ≥ 0.5**, **Crippen LogP 0–5 inclusive** under one common
  frozen implementation. Hosted Lipophilicity is a different method.
- Lower-is-better **native Vina Score**, under identical target preparation,
  box, public exhaustiveness settings and selected-pose mapping. Preserve the
  native unit; do not assign one if the service omits it.

Keep the original lead and reference control separate from generated candidates.
Generated recoveries of either do not fill panel slots. Control measurements are
reported separately and do not impose an invented success cutoff. Unspecified
stereo is preserved and flagged; no unbudgeted state enumeration or rescoring.

Allowed generation is `Fragment_Based_Optimization`: parent `ref_mol`, uploaded
`library_path`, and the same admitted PAMPA selection/bounds as the tested route.
Each arm can select among the same frozen source libraries and eligible parents,
or stop generation. No undeclared edit mask, internal step count or output cap.
Graph GA and additional tools remain outside this first comparison.

An allowed follow-up parent is the original lead or an assessed generated
identity with confirmed, unconflicted joint eligibility in the shared/own evidence.
The reference control is never a generation parent. If no allowed parent exists,
STOP generation; do not invent a different parent-selection rule mid-pair.

The [common decision guide](../specialist/feedback-v2/evaluation/matched-v1/COMMON_GUIDE.md)
requires joint-constraint diagnosis: QED-only, LogP-only,
overlapping and PAMPA/missing-data failures; product size, flexibility, polarity,
alerts when actually calculated, and observed parent–product changes. A source's
mean LogP is not evidence that its products will repair QED or be smaller.
Treat descriptor correlations as hypotheses, not causal effects. Give that guide
to both arms and freeze it before future outcomes; do not tune it between arms.

## Observable allowances and repeated identities

Each arm carries the same **actual** shared-initial attempts/selected slots,
with maxima of three logical submissions and 40 candidate-assessment slots.
The shared preparation is physically run once; skipped/failed stages remain
explicit rather than being fabricated completed submissions.
Per arm, permit at most four additional native submissions:

| Continuation stage | Maximum submissions | Maximum inputs |
| --- | ---: | ---: |
| CReM follow-up | 1 | One allowed parent and one listed library |
| Common PAMPA | 1 | 40 newly assessed identities plus original lead/control |
| Search Vina | 1 | Eligible selected identities, up to 40, plus both controls |
| Final Vina | 1 reserved | Up to ten committed candidates plus both controls |

Per-arm cumulative maxima: **7 logical submissions, 80 new-candidate assessment
slots, 84 common PAMPA inputs and 96 Vina ligand attempts**. These are ceilings,
not compulsory spending. Failures and ambiguous attempts consume allowances;
there are no replacements, top-ups or favorable-score retries. UNKNOWN acceptance
stops new submissions pending reconciliation. Unused capacity is reported.

The maximum physical service count for a complete new pair is **11**:
three shared jobs plus four per arm. This is a proposed allocation, not spending
authorization. Hosted billing units and hidden enumeration/inference remain
unknown when not exposed; equal logical allowances are not equal total compute.
Mark shared receipts explicitly. Attribute their logical use equally to arms,
but count the shared physical service/billing event only once in the pair's
actual total; do not double-count a charge merely because both ledgers reference it.

Retain the tested two-hour per-arm submission window from its first new reserved
submission; waiting/interruption does not reset it. Final capacity is reserved.
Collect accepted jobs after cutoff by their original IDs, but do not start the
next stage after cutoff. Report resulting incompleteness. Record queue times;
the same wall-time ceiling does not equal the same worker-compute allocation.

Commit at most 40 valid new identities before reading optimizer property values
or calculating outcomes, using the same sorted-canonical sampling helper and
predeclared block seed. For the first pilot use seed 1101 for the shared initial
subset and 1102 for both continuation subsets. These control external sampling,
not a nonexistent CReM seed parameter.

Exclude previously assessed identities and references. A previously unassessed
initial emission can enter only when actually emitted in that arm's follow-up,
as in the completed task. Preserve and report this overlap. Classify finalists
already present in the initial unassessed pool separately from identities absent
from that pool; do not attribute all later successes uniquely to a source change.

Use frozen strict connected canonical isomeric identity, without silent
neutralization, tautomerization or stereo changes. Retain all emissions,
invalids, duplicates, reference/parent recoveries and subset input/output/digest.
Measurements require the declared method/output kind and successful finite
values. Common PAMPA labels must be 0 or 1. Missing/error records cannot
establish eligibility; contradictory repeated labels are unresolved, never
settled by selecting the favorable row. Preserve evidence distinguishing an
explicit predictor failure from a genuine zero-valued class.

For Vina retain all raw rows/poses and select CSV pose 0 / SDF pose 1. Require
unambiguous input-to-pose identity/stereo mapping, finite coordinates and agreement
among score/pose artifacts from that **same native request**. Final scores are not
required to equal earlier search scores. `Pose=-1,Score=100` is failed/null. Missing
or ambiguous selected poses are not replaced with another pose. Apply the same
validity checks to search and final results.

## Shared execution and model-resource accounting

Both arms use the same existing native upload/submit/status/download operations
and common local data/accounting helpers. Do not give only one arm identity
validation, recovery, budget tracking or a better evaluator. Do not create a
parallel HTTP client or new scientific model to conduct the comparison.

Each executing agent must durably reserve stage/input allowances and request/
identity digests before native submission, then retain receipts, actual IDs and
results. Shared helpers assist this accounting; the offline policy's pure
functions are not host submission gates. Do not claim backend-enforced limits
unless enforcement is separately demonstrated.

Before launch, qualify local execution and relevant skill/module access in both
arms. The current subagent auto-approval override does not automatically give
the main agent an equivalent approval path. Record each effective policy and
ensure the same authorized work can execute; any policy/permission block is an
execution outcome, not proof of inferior molecular decision making. Do not
bypass a refusal, weaken checks silently or require operator intervention in
only one arm while calling the runs operationally matched.

Concretely, the base currently has the main CLI's smart approval path, while the
specialist has the broad `subagent_auto_approve: true` fallback. Sharing a profile
does not make them equivalent, and a harmless local check cannot guarantee later
smart-review outcomes. Resolve supported operational parity before a controlled
launch, or label the exercise operationally asymmetric/descriptive. Do not credit
that asymmetry as superior chemical reasoning. Both arms need common
`boltzmann:tools` and `frozen-panel-molecular-design` guidance plus relevant modules.

Pin model/provider and host iteration settings. Record total parent-plus-child
API calls, tokens, wall time and costs where available, including review overhead
separately. Native model counters may be unavailable; report unknowns rather
than zero. Scientific-opportunity matching alone does not establish equal LLM
compute or improved model efficiency. A stricter reasoning-budget study needs
observable, enforceable total budgets before making that claim.

## Endpoint and comparison rules

Both arms retain a ten-slot panel selected from eligible assessed new identities:
ascending successful native search Score, ties by canonical identity. Commit
identities/hashes before final submission. Missing slots and failed final
measurements remain missing; no outcome-driven replacement. Reuse exact-form
common property/descriptor records under the same frozen context, with provenance.

### Partial-stage and stopping rules

All permitted next stages remain conditional on the submission window, remaining
allowances and absence of an unresolved refusal/acceptance block.

| Condition | Frozen response |
| --- | --- |
| Follow-up generation fails or yields no assessable new identities | Retain shared initial candidates. No replacement/top-up generation; commit an allowed final panel from available evidence. |
| Some PAMPA/descriptors are missing or conflicting | Affected identities remain unresolved; their selected slots are spent. Dock only confirmed eligible identities. |
| No generated follow-up identity qualifies | Skip follow-up search; no extra control-only search. Retain shared initial observations. |
| Search results/pose mappings are partial or failed | Retain valid successes and failures; do not substitute unselected identities. |
| Fewer than ten eligible scored identities exist | Commit available identities plus explicit unfilled slots. No extra generation/reassessment. |
| No generated identity can be committed | Skip final submission; retain ten unfilled slots and null complete-panel quality. |
| A committed final record fails or lacks a valid pose | Preserve commitment and missingness. No endpoint replacement. |
| Submission acceptance is UNKNOWN | Stop new submissions for affected work; reconcile through documented read-only mechanisms, never guessed IDs or replacement calls. |
| Window expires or a new refusal occurs | Stop new submissions. Collect accepted work as permitted; report pending/censored state if collection cannot finish. |

Before either arm starts, freeze a symmetric collection cutoff or explicit
operator-interruption rule and its supported checkpoint/cancellation mechanism.
Record actual terminal/interruption times; the rule must not depend on which arm
is winning. A local collection cutoff does not prove remote cancellation. Do not
reopen an arm after observing the other result.

Controls remain outside generated slots. Missing control deltas stay null and
are reported separately. A malformed/mismapped control or evidence of an altered
target/scoring context makes quality comparison unqualified; retain raw candidate
scores as diagnostics. A numerical control-score difference alone is not proof
of drift or invalidity; report it without inventing a tolerance. Freeze the
target/control validity rule before launch.

The primary outcome has two ordered components:

1. **Confirmed final eligible coverage** out of ten slots.
2. **Complete ten-slot mean native Score**, only when all ten slots are valid,
   eligible and measured. Lower is numerically preferred.

Coverage counts committed generated identities with confirmed mandatory
eligibility and valid final measurements/poses. Higher coverage is a coverage
advantage, not a complete-panel score win.

Do not convert missingness to an arbitrary docking penalty or average only
successful slots as the complete-panel result. For each pair report coverage
first; compare quality only when both panels are complete. If both are incomplete
with equal coverage, do not manufacture a quality winner from partial means.

For complete pairs report `specialist mean − base mean`: negative is a numerical
specialist advantage, zero a tie and positive a numerical disadvantage. Keep
per-arm and paired outcomes, not just an across-run winning shortlist. No
practical-effect threshold or physical-affinity interpretation is invented.

### Cross-arm overlap and score differences

Do not share follow-up predictions, docking results or decisions between arms.
Preserve each arm's own requests/observations/spending when identities overlap;
do not opportunistically deduplicate one arm's work after seeing the other's
outcomes. Keep the planned two per-arm final jobs. Report action, candidate and
panel overlap explicitly.

Identical panels constitute a molecular-selection tie. Different final scores
for identical committed identities are observed evaluator variation, not superior
molecular selection. For partially overlapping panels also report shared versus
arm-exclusive contributions; no post-hoc rescore or winner-dependent aggregation.

Secondary outcomes: joint eligible yield over all attempted selected identities,
failure bins, new/overlapping chemistry, contribution to the retained panel,
same-batch control differences, actual service use, elapsed time and model/context
overhead. A better best molecule alone does not establish better complete-panel
quality; improved pooled quality alone does not establish a mechanistic effect.

Fresh final requests use the same native evaluator for both arms. Preserve
scores/pose comparisons and any evidence of identical outputs, cache use or
unknown seeds. A fresh request is not automatically independent computation.
Keep experimental binding and biological efficacy NOT_MEASURED.

## Decision standard and completion

The one-pair pilot can show a comparative observation and operational feasibility.
It cannot establish reliable specialist superiority. General improvement requires
prospectively repeated cases, consistent benefit with failure/coverage reporting,
and resource/context evidence appropriate to the claim. Identical decisions or
results are a valid tie, not a reason to enlarge only the specialist's budget.

Freeze both results before arranging a separate read-only critique. Review must
not add scientific calculations, choose replacement endpoints or alter either
arm. Preserve failures, interruptions and incomplete comparisons. Any unresolved
execution-policy asymmetry is disclosed and limits scientific attribution.

Before issuing controlled-study prompts, resolve and freeze: the next case/lead and
provenance, complete common packet, common decision/helper versions, operational
approval parity, model settings, arm order and the complete allowance ledger.
Arm order must be chosen prospectively and recorded; one pair cannot remove
service-time effects. Do not send this draft to an execution agent as a runnable
task or silently renew the completed pilot.

The first development-pair kit uses the declared procedural/asymmetric mode
rather than claiming these controlled-study conditions were achieved. Its
case-specific actual initial Vina use is five inputs, so at most 54 new inputs
per arm yields 59 cumulative (within the generic 96 ceiling). Unused initial
capacity cannot be transferred. Both arms receive the same common helper fixes.

## Design review record

Separate evaluation and execution critics reviewed this draft. Corrections
defined the parent's operational-only role, realistic access/approval parity,
shared-preparation accounting, allowed parents, phase/failure/pose rules,
overlap/tie interpretation and limits on causal claims. A final evaluation
reread found no remaining critical design contradiction. Score-artifact agreement
was clarified as within the same request; final and search values need not match.
The common guide and allowance arithmetic were checked. This review does not
freeze the missing case/packet or establish operational isolation/readiness.
