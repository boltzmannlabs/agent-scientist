# Lipophilicity model-score decision pilot

This is a **new objective**, selected by the user: use the supported platform
`Lipophilicity` model with score range **0–3**. It does not resume or relabel the
earlier model-free/DRD2 attempt. Those records remain unchanged. This document
specializes [PROTOCOL.md](PROTOCOL.md); its former DRD2 activity criterion is
replaced by the rules below.

## Exact objective and qualification

The existing connector receives exactly this optimization selection:

```json
{"global_models":[{"name":"Lipophilicity","min_threshold":0,"max_threshold":3}]}
```

Do not invent model paths, custom model IDs or worker-managed `attribute` fields.
The original reference, unspecified stereochemistry and checked libraries remain
fixed. Success requires one valid, distinct, nonreference candidate jointly meeting:

- Platform `Lipophilicity` score **0 ≤ score ≤ 3**.
- Local RDKit QED **strictly greater than 0.800452829768805**.
- Original-reference Morgan count-radius-2 similarity **strictly greater than 0.7**.

A real completed `Property_Prediction` job using `global_models=["Lipophilicity"]`
returned **−8.72** for the identity-verified original reference. The private
qualification, input CSV and downloaded output CSV are hash-bound. The builder
checks the actual one-row structures and reported value; it does not run a
classifier or submit another prediction. Hosted QED was rounded to `0.8`; the
local unrounded QED baseline is retained instead.

Physical units and the platform model/weight revision are **unverified**. Call this
a platform model score, not measured logP/logD or experimental lipophilicity. RDKit
logP is not a replacement. The assessor independently checks supplied provider
predictions, identities, local QED and similarity. Its code is independent of the
agent's recommendation; it is **not an independent predictor or experimental
validation**. Missing property values cannot become successful candidates.

## Freeze, routing and accounting

`build_property_protocol(..., generation_parameters=selection)` in
`pilot/property_protocol.py` returns a JSON-ready protocol for `PilotRun.create`.
The exact explicit selection above is required; omissions and changed selections
are rejected. Freeze it in a fresh private run directory before new candidate
outcomes. It reuses structural/library admission from the earlier builder, replaces
its evaluator/rules/interpretation, and removes classifier scoring artifacts from
this objective's active scientific pins. Legacy validation dependencies may still
be read and hash-checked; no DRD2 inference is performed. The new assessor
implementation and baseline evidence are pinned.

Keep the three arms, shared `mixed_reference` batch, one-follow-up horizon,
same guidance and evidence, named native specialist requirement, and full cost
accounting. Stop before any arm when the common batch succeeds. Missing native
specialist invocation is a routing failure, not a completed specialist comparison.
Model/provider verification does not establish complete inference-setting or
fresh-session equivalence. Findings are descriptive development observations;
there is no protected holdout or causal specialist-gain claim.

The user approved only this concrete generic parser warning:
`SMILES: smiles semantics are not verified by the generic CSV parser.`
The protocol records it separately for each exact library SHA. Structural audits
remain mandatory. This does not authorize ignoring other warnings/errors, changing
a library, bypassing authorization or inferring scientific validity from parsing.

The read-only account experiment listing returned
`No experiments found for this user and job_name`. That response supplies no job
ID and does not justify resubmitting an uncertain prior request. Preserve original
receipts and reconcile original attempts. A new objective uses a distinct fresh
run; no automatic live calls, profile changes, installs or Git publication occur
when building this protocol.
