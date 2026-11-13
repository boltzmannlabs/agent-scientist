# First refinement case — current selection and historical proposal

Tracking: agent-scientist#33. Current property: **PAMPA**, selected at the user's
request to replace Solubility. See [the active case](pampa-first-refinement.md)
and [completed readiness assignment](pampa-readiness-prompt.md). The user-run
test returned two source-supported positive labels; see
[the result](../results/pampa-label-readiness-20261111.md). The subsequent bounded
feedback integration is now complete and separately reviewed, without a
specialist-benefit claim; see the
[completion review](../results/p38-refinement-feedback-completion-review.md).

The remaining document preserves the **superseded conditional Solubility
proposal** and its evidence. Its -4 cutoff and normalization anchors are not
active parameters for the PAMPA case.

## Selected property and rationale

Select the Boltzmann property named **Solubility** for the first hosted-model
constraint guiding refinement. Use a qualified Boltzmann Vina route as the
proposed primary docking evaluator, with the existing QED/Crippen checks.
The exact Vina variant/settings remain to be selected and qualified. This adds a prospective constraint
to a NEW development case; it does not reinterpret the completed campaigns.

Options considered:

| Property | Assessment |
| --- | --- |
| Solubility — selected | Adds an aqueous-solubility dimension beyond QED/Crippen, provides continuous feedback and has a desirable increasing direction compatible with the inspected GA regression reward. |
| Lipophilicity | The existing local LogP constraint already covers a related dimension, although the hosted endpoint may differ. Its earlier output interpretation is unresolved. A desired bounded window also does not match the GA worker's monotonically increasing regression reward. |
| Toxicity classifiers | Potentially useful later. Positive-class meaning and desired direction must be established; the inspected GA classifier rewards predictions above a threshold, which is not automatically appropriate for reducing risk. |

This selection concerns the task's suitability, not a claim that the chosen
predictor has already been scientifically validated or is superior to all others.
Solubility adds a task endpoint; it is not independent confirmation of chemical
quality, since descriptor information can overlap with QED/LogP-related features.

## Scientific target

Provided the deployed output is confirmed to be log10 aqueous solubility in
mol/L, set the proposed eligibility criterion to **predicted logS >= -4**.
At the boundary S = 10^-4 mol/L = 100 micromolar. There is no invented upper
eligibility bound: better predicted solubility must not be rejected for exceeding
a UI default.

The AqSolDB primary paper defines LogS in mol/L and discusses -4 as a qualitative
class boundary. SwissADME independently uses a molar logS class boundary at -4.
Qualitative labels differ between sources. We choose the numerical boundary as
an explicit development criterion, not a universal drug-quality, assay or clinical
requirement. No pH, temperature, intrinsic/apparent endpoint or experimental
measurement is assumed for this Boltzmann model without provenance.

- [AqSolDB, Scientific Data 2019](https://www.nature.com/articles/s41597-019-0151-1)
- [SwissADME, Scientific Reports 2017](https://www.nature.com/articles/srep42717)

## Candidate model and evidence limits

Current local catalogue candidate:

- Public property name: `Solubility`.
- Storage identifier: `boltchem/admet_25/gpm_models_25/Solubility_hgb_reg_mordred_2d_3d_v4.pkl`.
- Catalogue: HGB regression with Mordred 2D/3D features.
- Two local copies have SHA-256 `a62b102639e5df62a3361496193b1a9190db7c462b20e13d7af552b60234c289` and size 3,368,598 bytes.
- A saved inspection report describes a bare HistGradientBoostingRegressor with
  1,477 inputs. This review did not load or execute the model.

The older Mermaid catalogue instead names an ExtraTrees Solubility model. Neither
model naming, the `LogS` slug, an empty transform field nor observed label ranges
proves the active checkpoint's target units. The inspected local bare artifact
report provides no unit/target-transform model card. We have not certified that
CReM and Graph GA resolve the same model revision.

Before using -4 as a physical threshold, verify the active model resolution in
both routes, its training-label definition and inverse-target transformation.
Reuse existing model documentation/qualification evidence where available. This
is an operator-level setup check, not a request for every child to inspect private
metadata. If the scale is different, convert from verified provenance or revise
the case before runs; do not relabel arbitrary predictions as log mol/L.

## How this property guides the tools

CReM generates parent/library variants before property prediction in the inspected
worker. The outer policy uses actual Solubility predictions for eligibility and
subsequent parent/library selection. Merely attaching predictions is insufficient.
The common evaluator also measures QED, Crippen LogP and the selected Vina score. Library changes
are hypotheses; actual product changes must be verified.

Graph GA uses the selected model inside its MPO. In the inspected scorer, the
regression contribution is:

`0.2 * (prediction - min_threshold) / (max_threshold - min_threshold)`

This is added to the existing similarity-based score, with its other existing
terms/penalties. It is not clipped and is not a hard interval filter. Therefore
the scientific eligibility condition must be enforced separately.

If log mol/L output and the same deployed scoring behavior are confirmed, propose
normalization anchors of -6 and -4: the former maps to zero and the latter to one
before the 0.2 weighting. These correspond to published solubility-class boundaries;
they are a proposed scaling convention, not proven optimal weights. Values above
-4 continue to earn more reward in this source. Do not claim that max_threshold
caps predictions or excludes more soluble molecules. These request values have
not been submitted. The exact CReM request representation is also not qualified.
The unclipped term can encourage extreme predictions; qualification should examine
raw prediction distributions and available applicability evidence. A higher model
score alone does not establish a more credible soluble molecule. Do not silently
clip scores or add exclusions after inspecting comparison results.

An accepted GA job is insufficient evidence that the intended property objective
was active: source loading/prediction failures can leave other score terms in
use. Require available objective-loading evidence and finite intended property
outputs; otherwise retain the run as objective unresolved. Native source outputs
are rounded to four decimals. Qualification must establish a common prediction
method and precision rule for both routes, including threshold-borderline cases;
do not silently change the cutoff or invent an uncertainty margin. If the chosen
precision cannot resolve eligibility, obtain an authorized common measurement or
retain an unresolved status.
The inspected CReM consumer rounds predictions to two decimals, so native CReM
and GA outputs do not even have the same reported precision. A printed value at
the cutoff cannot establish the unrounded prediction's side of the boundary.
The common assessment/precision rule remains a live-qualification requirement.

## Proposed shared development starting point

Use the previously generated p38 candidate **e072** as a supplied reference lead
in a NEW lead-refinement task, not as a newly discovered solution:

`CCC(C)(C)NC(=O)C(F)(F)c1cccc(NC(=O)Cc2cncnc2)c1`

Reason: it has an established computational input/provenance trail and no detected
unspecified tetrahedral centers in the prior checks, reducing one avoidable
representation complication. Its actual Solubility prediction is NOT_MEASURED
here. Do not choose or alter the target after learning that prediction. If it
already meets the minimum, quality improvement while retaining eligibility remains
the question; do not tighten the threshold to manufacture a failure.

Keep the supplied lead separate from the original 1A9U/SB2 site control. Reuse
verified target-coordinate inputs where appropriate; do not assume the earlier
Smina receptor adapter, search settings or score values apply to platform Vina.
Both base and policy runs
receive identical lead information; no other historical candidate outcomes are
supplied. This is development data and cannot be represented as a protected holdout.

Proposed common conditions: QED >= 0.5, Crippen LogP 0–5 inclusive, plus verified
predicted logS >= -4. Preserve the proposed ten-slot quality/completeness/compliance
reporting. The proposed common rule is feasibility first, then ascending native
Vina score among eligible, unique new identities; exact ties use canonical
identity. Keep the input lead and SB2 out of the designed panel and retain their
recoveries separately. Commit ten slots before fresh final assessment; preserve
unfilled or failed slots without replacement. Both approaches receive the same
selection helper. The complete rule, assessment-subset allocation and proposed
bottleneck-to-action preferences are in
[feedback-policy-v2.md](feedback-policy-v2.md). They remain proposals for approval,
not changes to the old unfiltered-panel task.

This is a functional constrained-refinement development case. If the initial lead
fails the verified Solubility constraint, the feedback policy can test feasibility
repair. If it already passes, test docking improvement while retaining feasibility.
Neither outcome justifies changing the target after observing its value. A later
deficient starting case can test repair separately.

## Platform docking evaluator — corrected 11 November 2026

Smina was a locally installed evaluator for the earlier case study. It is not
being presented as a Boltzmann platform tool or required for this new workflow.
The old Smina campaigns, measurements and frozen specifications remain unchanged.

The current local connector contract lists:

| Job | Appropriate role in this proposal |
| --- | --- |
| `Vina_basic_docking` | First evaluator candidate for the known 1A9U site and rigid-receptor comparison; current operational readiness still needs verification. |
| `Vina_Flexible_Docking` | A separately justified receptor-flexibility investigation with explicitly selected residues; not an automatic better score or replacement baseline. |
| `Vina_Score_only_docking` | Score supplied poses; this is not a new pose search. |
| `Diffdock` | Alternative pose prediction/blind docking. Confidence is a pose-confidence output, not Vina energy or binding affinity. |

Choose one Vina variant and freeze its scientific preparation, search region,
supported settings, pose selection and aggregation for both comparison arms.
The proposed primary is the complete ten-slot mean native Vina docking score,
lower preferred under the usual energy convention; confirm producer sign/units
from actual outputs before evaluation. Keep any derived transform explicit.
DiffDock confidence, flexible-docking scores and score-only results occupy
separate method-labelled fields and cannot be silently pooled into this metric.

The platform contract expects a processed receptor PDB, explicit box fields and
supported string-valued exhaustivness. Do not copy the old Smina value 9,
autobox_add=10 or PDBQT adapter as equivalent platform inputs. Confirm the meaning
of max_radius_size when defining the new search region. The newer local basic
worker passes it as the full cubic box side length; deployed equivalence remains
to be verified. Pose numbering, failure sentinels and preparation are now recorded
in [feedback-platform-readiness.md](feedback-platform-readiness.md), with an
offline source-defined adapter available.

This requires a new matched base/policy comparison using the selected platform
evaluator. Do not compare the new Vina mean numerically against the old Smina mean
as evidence of specialist improvement or paper-score reproduction. A related
scoring-function lineage does not establish numerical equivalence.

Contract source: local Agent Scientist
`plugins/boltzmann/skills/boltzmann-tools/references/modules/small-molecule-toolbox.md`.
DiffDock interpretation: [official FAQ](https://github.com/gcorso/DiffDock#faq).

## Remaining steps, without new execution permission

1. Settle the common logical contract: feasibility/quality priority, panel rule,
   bottleneck preferences, accounting and response to missing evidence. Develop
   and test the offline decision component using recorded/synthetic observations
   and explicit unavailable-capability states. Backend qualification need not
   block that code.
2. Separately qualify the Solubility endpoint in both routes and one platform
   Vina evaluator before scientific use, through existing evidence or a separately
   authorized bounded check. Reuse the resulting host configuration across arms.
3. Before live comparison, freeze route profiles, numerical observable allowances,
   assessment allocation, stopping/final reserves, repeats and a minimum useful
   gain/uncertainty rule. Count failed attempts; report unknown internal work.
4. Test policy value first with the same base model, facts, tools and helpers.
   Study delegation/context efficiency and unseen cases later. Functional tests
   alone cannot establish molecular improvement.

A tie or loss remains a result. No arbitrary score improvement, model performance,
new candidate measurement or deployment readiness is fabricated by this proposal.

## Local sources examined

- `BOLTCHEM-FEATURES/v5/QSPR Modelling/prop_inference_new/prop_inference_new/proppred/global_model_catalog.json`: candidate model record.
- `BOLTCHEM-FEATURES/v5/QSPR Modelling/prop_inference_new/scripts/validate_global_sklearn_inference.py`: `LogS` metadata label, not unit certification.
- `BOLTCHEM-FEATURES/v5/Molecule Optimzation/mermaid/config/gpm_models_info.json`: conflicting older model record/defaults.
- `Ankith/model_inspection/admet_25_gpm/inspection_report.json`: existing artifact inspection and hash.
- `Ankith/solubility_external_bundle/prop_inference_new/proppred/ml/infer.py`: saved-artifact target-transform handling.
- `BOLTCHEM-FEATURES/v5/Molecule Optimzation/Graph_GA/scoring_funcs/score_mpo.py`: regression normalization and classification direction.
- Existing p38 base and specialist reports: shared lead provenance and prior descriptor/stereochemistry observations only.

No models were loaded, predictions made, scientific jobs submitted, frozen runs
modified, or Git operations performed during this selection.
Independent source/selection critique accepted this as an evidence-based planning
proposal. It did not certify deployed model units or authorize model execution.
