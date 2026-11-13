# SB202190 development pair — comparison review

Reviewed 13 November 2026. Tracking: agent-scientist#33.
Status: **both arms frozen; no demonstrated specialist selection advantage**.
This review did not submit, redock, regenerate, retry or edit either arm.

## Outcome

Both arms recorded the same CReM parent/library action, returned the same 176
molecular identities, selected the same 40 forms and committed the same ordered
eight generated identities plus two null slots. Their common property values and
native search scores agree. This is a **molecular-selection decision tie**.

The specialist delivered eight verified final measurements; BASE delivered none
because its final service request failed. That is an observed delivery/coverage
difference in this pair, not evidence of better scientific choices or general
execution reliability. Both complete-panel means remain null. Do not substitute
BASE search values for missing final observations or compare the specialist's
eight-result diagnostic mean as if both complete panels had been assessed.

| Observation | BASE_WITH_GUIDANCE | BASE_PLUS_SPECIALIST |
| --- | ---: | ---: |
| New scientific submission attempts | 4 | 4 |
| Continuation unique molecular identities | 176 | 176 |
| New outcome-blind assessed identities | 40 | 40 |
| Newly jointly eligible candidates | 5 | 5 |
| Continuation eligible search mean, diagnostic n=5 | -8.1478 | -8.1478 |
| Committed generated identities / ten slots | 8 / 10 | 8 / 10 |
| Verified eligible final coverage | 0 / 10 | 8 / 10 |
| Complete-panel final mean | null | null |
| Final native request | Confirmed terminal failure | Success |
| New Vina ligand attempts, including failed inputs | 17 | 17 |

The chosen parent was the eligible high-QED tetrahydropyridinyl form and the
library was `hetero_rich_sources.csv`. Both decisions explicitly traded weaker
parent docking for QED headroom, while acknowledging source composition cannot
prove product-level improvement. Both had three shared initial successes and
five new successes. All five new scores were less favorable than all three
initial scores. None of the eight generated forms scored lower than original
SB202190 (-8.888). These are computational predictions with native units absent,
not experimental affinity or a causal verdict about the best alternative action.

## Verification and evidence

Source directories, both under the active profile's workspace:

- `08_results/p38_refinement_matched/arms/BASE_WITH_GUIDANCE_20261112T122201397716Z/`
- `08_results/p38_refinement_matched/arms/BASE_PLUS_SPECIALIST_20261112T125119465804Z/`

The parent read back all **101 BASE** and **140 specialist** inventory members,
checked hashes/byte counts and reproduced the seeded subset. It compared ordered
identity pools, assessed QED/Crippen/PAMPA values, selected search score maps and
panel commitments. All **82 shared packet members** remained hash-matching.
The panel commitment digest is the same in both arms:
`b578335c50ad56fe720d8f7e47ab972e7603e1860271cb66297b2372393f43ce`.

A separate critic checked the pair's actual artifacts. It confirmed equal native
search score maps across all 70 pose rows, the same seven selected search scores
and byte-identical final input CSVs. Selected search coordinates match across
arms. Precommit timestamps precede relevant submission reservations. Original
shared/arm/kit artifacts remain unchanged. Machine-readable comparison evidence
is in [sb202190-development-pair-review.json](sb202190-development-pair-review.json).

Reporting schemas differ: BASE names the continuation search phase
`continuation_search` and metric `vina_score`; the specialist uses `search` and
`vina`. Review mapped these explicitly to the same documented native Vina
quantity and its own artifacts; originals were not rewritten. The BASE final
records stay failed/null.

Molecular identity equality does not mean all raw outputs are byte-identical.
Sixteen optimizer PAMPA annotation cells differ between generation outputs.
Common PAMPA assessments and exact-form eligibility agree; the specialist common
CSV lacks a NAMES column but retains usable identity mapping. No rounding-based
optimizer annotation replaces common assessment.

BASE's preserved final diagnostic reports JSONDecodeError in SDF storage upload,
with confirmed terminal failure and no final artifacts. This does not establish
whether underlying scoring finished or that a molecule caused the error. The
specialist's final request returned scores and coordinates identical to earlier
search for all ten submitted ligands, including references. Fresh submission is
evidenced; independent recomputation versus caching is unresolved.

The specialist omitted regenerable cached bytecode from its local kit copy,
with the omission recorded. Functional common source snapshots match; this is
not a different scientific decision method. Its UI label of failed/incomplete
reflects incomplete evaluation: authorized execution completed, but only eight
eligible generated slots were available.

## Limits and development consequence

This one deliberately selected within-family case used procedural separation,
not enforced file isolation or proven approval/context/aggregate model-compute
parity. Reports record no cross-arm outcome use; file/manifest checks cannot prove
absence of context leakage. Preserve those limitations rather than infer either
independent reasoning or contamination from matching choices alone.

Both agents demonstrated evidence-linked reasoning and reusable execution, but
this pair supplies no marginal molecular-selection benefit from delegation.
One service failure does not repair that missing evidence. A specialist can
still have organizational/context value; this study did not establish it through
measured total model cost or context savings.

Close this pair without a retry or larger replacement batch. The next proposed
development goal is a concrete improvement to the decision procedure, tested
first across frozen contrasting evidence packets with prospective criteria and
trace capture. Check responsiveness to joint deficits, counterevidence and
uncertainty, not just plausible explanations or change for its own sake.
Such offline checks establish component behavior, not new molecular performance;
future scientific benefit still needs a prospectively frozen live evaluation.
Do not weaken the capable baseline or simply give the specialist more scientific
calls to manufacture an advantage.

No new live scientific work, profile change, Git operation or modification of
frozen scientific evidence was authorized or performed by this review.
