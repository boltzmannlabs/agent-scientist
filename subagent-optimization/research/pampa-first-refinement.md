# First refinement case — PAMPA replacement

Tracking: agent-scientist#33. Status: **user-run bounded refinement and feedback
integration completed; separate read-only review completed; specialist benefit
not established**.
The user ran Property_Prediction job 6af455a44bcdd4891fc0f85f. Both inputs return
class 1, without probability scores. The subsequent refinement case completed
as sa-0-1ce61f20, with 7 cumulative submissions, 80 assessed candidates and a
complete ten-slot final panel. See the
[completion review](../results/p38-refinement-feedback-completion-review.md).
The library change lowered mean LogP but worsened mean QED, eligible yield and
standalone follow-up top-ten quality. Pooled panel gains are confounded by more
search opportunities. The role/approval setup changes are documented separately.

## Property and objective

Use the exact platform selector **PAMPA**, a GROVER classification endpoint.
The intended endpoint is high passive membrane permeability. The reference TDC
PAMPA_NCATS definition assigns class 1 to high permeability and class 0 to
low-to-moderate permeability. It is not measured intestinal absorption or oral
bioavailability. [TDC ADME documentation](https://tdcommons.ai/single_pred_tasks/adme/#pampa-permeability-ncats).

The inspected GROVER code produces a sigmoid class-1 score and binary class
at score >= 0.5. Both CReM and Graph GA wrappers prefer the probability column.
The pilot's common-assessor eligibility rule is now **PAMPA class = 1**, matching
the observed Property_Prediction export. The source computes that label using
its internal 0.5 score boundary. Raw 1.0 labels are not probabilities of exactly
one, calibrated confidence, measured permeability or absorption percentages.

Use the same Property_Prediction label assessment for both comparison arms.
Optimizer-native probabilities remain separate measurements with their own
method/output identity. Do not merge them into the common label field or claim
cross-route numerical equivalence. Since e072 and SB2 already pass, no PAMPA
deficit was observed; the first refinement question is docking quality while
preserving class 1, QED and Crippen eligibility.

Retain QED >= 0.5 and RDKit Crippen LogP 0–5. Use the common platform Vina
endpoint for docking quality. Keep the supplied e072 lead, SB2 control and target
context unchanged. The completed two-ligand Vina job supplies technical readiness
evidence; older Smina scores are not numerically interchangeable.

Final selection remains feasibility first, then native Vina ranking: ten distinct
generated nonreference identities committed before final assessment, with missing
slots/failures preserved. Both approaches get the same helpers, inputs, actions,
evaluator and declared allowances.

## Why PAMPA

Both critics selected PAMPA over the alternatives. HIA/Bioavailability had less
explicit positive-class annotations in inspected sources; GIA is regression;
Clearance/Half Life require additional unit/endpoint/direction choices.

PAMPA is listed in the current catalogue and public schemas. Critic CSV joins
found no label differences in inspected exact-SMILES overlaps between local raw
PAMPA_NCATS records and overall, cleaned and training collections. This supports
label preservation in those records, not proof of the deployed training dataset.

## Route-specific request semantics

| Route | Proposed selector/bounds | Meaning and limit |
| --- | --- | --- |
| CReM | PAMPA, min 0.5, max 1 | Prospective favorable-score window. CReM generates variants before predictions; outer assessment enforces eligibility and selects subsequent parents/libraries. Confirm deployed bounds/filter handling. |
| Graph GA | PAMPA, min 0, max 0.5 | Its classifier reward gives a step bonus at p >= max_threshold. This sets the step at 0.5; it is not an acceptance interval or continuous probability-maximization reward. |
| Property_Prediction | global_models: ["PAMPA"] | Names are strings; this request has no thresholds. Use for the first readiness test. |

Sending max_threshold=1 to GA would reward only scores reaching 1. The offline
component now supports separately frozen route model selections. In label mode
external eligibility is 1..1 and the GA score boundary remains separately 0.5.
Labels and scores have explicit output-kind identities. Old Solubility settings
remain supported; the saved specialist/profile is unchanged.

## User-run live check

The [readiness assignment](pampa-readiness-prompt.md) is complete; retain it as a
historical record and do not rerun it merely to reproduce the same labels. See
[the result summary](../results/pampa-label-readiness-20261111.md). The following
bounded optimization/assessment/feedback episode is also complete. The next
evaluation needs its own prospective comparison contract; do not repeat either
the readiness jobs or the completed continuation automatically.

The first [user-run integration task](../specialist/feedback-v2/evaluation/p38-integration-v1/TASK.md)
now specifies CReM → common PAMPA/RDKit/Vina assessment → a justified follow-up or
STOP → committed final panel. It permits at most two generations and seven
scientific submission attempts in total. The three existing candidate source
libraries passed a new local representation audit; e072-specific fragment
coverage and scientific usefulness remain untested. Follow the
[specialist review steps](../specialist/feedback-v2/SETUP.md) before using the
execution prompt. At the user's later request, the existing role's instructions
and modules were added in ankith, saved and enabled; the later frozen-panel
skill addition was separately authorized. That bounded test is now complete.
Do not rerun its original prompt or automatically restore its exhausted limits.

For subsequent tool outputs, establish output type: score, class or both. Keep raw outputs
and native loading/inference evidence where available. Both source adapters can
replace missing predictions with zero; a returned zero alone cannot establish
either successful inference or a failed molecule.

Preserve native class and rounded score separately. An exact rounded boundary
value alone cannot settle the unrounded side: use a verified native class or
available precision evidence, otherwise retain unresolved eligibility. Do not
shift the threshold afterward or retry for a favorable outcome.

The exact-ID diagnostic returned HTTP404 without JSON. Record unavailable
runtime head/checkpoint trace as a limitation, not a recurring blocker for this
source-interpreted development case. Record deployment identity when available.
Cross-route numerical parity,
predictive accuracy and scientific benefit still require separate evidence.

## Sources and software evidence

- Local QSPR global_model_catalog.json: PAMPA classification/GROVER.
- Native small-molecule-optimization.md and small-molecule-qspr.md: selectors/request shapes.
- Route grover_mtl_infer.py: named PAMPA head, sigmoid and class boundary.
- Route DL inference wrappers: probability-column preference.
- Graph GA score_mpo.py: classification step at max_threshold.

No models were loaded or remote jobs submitted during selection. The PAMPA-mode
offline tests establish mechanics only, not measured permeability or better
molecule discovery.
