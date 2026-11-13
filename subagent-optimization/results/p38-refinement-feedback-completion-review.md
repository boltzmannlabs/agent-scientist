# p38 refinement feedback — completion review

Reviewed 12 November 2026. Tracking: agent-scientist#33.
Status: **bounded integration complete; no specialist-superiority result**.

Source: `sa-0-1ce61f20`, ankith workspace
`08_results/p38_refinement_feedback/continuation_sa-0-1ce61f20/`, continuing
`sa-0-d12ee796`. The original and continuation artifacts remain unchanged.

## What completed

The user-run specialist executed the remaining generation, common PAMPA, search
Vina and final Vina jobs successfully. Cumulative seven-submission and
80-candidate-assessment caps were respected. Ten generated identities were
committed and assessed alongside both controls. No pending job or further
scientific authorization remains in this pilot.

The feedback action kept e072 and changed the source library from mixed to
hetero-rich. This exercised the intended outer decision loop using existing
CReM, Property_Prediction and Vina tools. No predictor or optimizer model was
trained or modified. The result establishes execution of the bounded workflow
and feedback experiment, not effectiveness across other tasks.

## Verified measurements and interpretation

| Metric over assessed candidates | Initial | Follow-up |
| --- | ---: | ---: |
| Assessed identities | 40 | 40 |
| Jointly eligible | 16 (40%) | 13 (32.5%) |
| Mean Crippen LogP | 4.47363 | 3.68763 |
| Mean QED | 0.47641 | 0.40183 |
| Mean heavy atoms | 34.7 | 35.7 |
| Mean TPSA | 94.19575 | 121.54375 |
| QED-only / LogP-only / both failures | 10 / 1 / 13 | 20 / 1 / 6 |
| Standalone top-ten search mean, native Vina Score | -8.6369 | -8.4734 |

Lower native Score is preferred. The follow-up's standalone top-ten mean worsened
by **0.1635**, and joint eligibility fell **7.5 percentage points**. Lower LogP
was observed; improved overall eligibility and smaller products were not.
Additional polarity/size accompanied poorer mean QED. These are descriptive
observations, not a causal decomposition of QED or validated biological effects.

The combined 29-candidate eligible pool yielded a ten-slot panel with five
initial and five follow-up identities. Its final mean was **-8.9749**, median
**-8.8990**, sample SD **0.42406956**, range **[-9.748, -8.470]**. All ten meet the
PAMPA class-1, QED and Crippen conditions. All ten are numerically more favorable
than the same-batch e072 control (-8.216), and two than SB2 (-9.234).

The retained mean is 0.3380 more favorable than the initial top-ten search mean.
That is not evidence of a feedback-policy advantage: the retained pool grew from
16 to 29 eligible scored identities. The best candidate remained from the first
batch. Both source and emitted pools overlap; two follow-up finalists, including
the strongest one, had already been emitted but not assessed in the initial batch.
Their later assessment was allowed by the frozen task, but cannot establish that
the new library uniquely generated those successes.

## Separate read-only critique and checks

A separate critic independently reproduced both seeded subsets, the disjoint
40+40 assessed identities, 29-candidate ranking, endpoint eligibility, final
statistics and cumulative accounting. It verified all 160 continuation hashes
and 61 original hashes and found no integrity blocker.

The parent independently verified the 160 continuation manifest hashes, ten
unique endpoint identities, eligibility, phase composition and statistics.
This is independent artifact/decision review, not independent redocking,
experimental evaluation or confirmation of the deployed model's accuracy.

All final scores and selected-pose coordinate multisets matched search results
exactly. A fresh native final request is evidenced; deterministic recomputation
versus internal reuse/caching is unresolved. Identical outputs alone prove
neither explanation. Native score units, worker/model revisions and full cost
are unavailable. Preserve those limitations rather than inferring energy units
or repeatedly submitting the same calculations.

## Resources and status

Cumulative use: seven scientific submissions, 80 distinct new candidate
assessment slots, 84 common PAMPA inputs and 45 Vina ligand attempts. Reported
amounts total 12 in unspecified units; missing PAMPA amounts prevent a complete
cost total. No new scientific execution, profile edit or Git operation occurred
in this review. The source run reports are preserved rather than overwritten.

The local approval workaround and corrected skill selection allowed this
continuation to complete without a new reported refusal. That does not establish
a framework approval-routing fix. The policy remains a user-selected broad
profile override.

## Next decision

The fixed development goal remains improving decisions with the same scientific
tools. Options considered:

1. Increase sampling again: can improve selected scores through greater search
   opportunity, but does not answer the specialist-benefit question.
2. Repeat the same final request: does not establish independent validation and
   cannot resolve caching versus deterministic execution by itself.
3. Freeze a matched base-agent versus specialist-assisted evaluation on the same
   optimization workflow: directly tests the stated question.

Choose option 3 as the next evaluation design. Keep tools, model access, source
options, scientific knowledge, controls, observable allowances, selection helpers
and endpoint rules equivalent. Give the base agent permission to reason and adapt;
do not weaken its workflow artificially. Include specialist/parent context and
model costs where available; report unknowns rather than equal-compute claims.

Use prospectively fixed lead/replicate blocks or shared starting evidence, with
unseen future outcomes isolated. This completed case is development data; do not
tune on it and then call its reuse an untouched benchmark. Primary endpoints
should include complete-panel native-score quality and complete eligibility/
coverage, with per-run failures, usable yield and resource use preserved.

Before that test, refine the decision contract to assess the dominant joint
constraint deficit. Source LogP alone was insufficient here: QED losses and
actual product size/polarity must inform hypotheses. Adding new tools or claiming
a universally better library is not supported by this pilot. No next experiment
is authorized by this review alone.
