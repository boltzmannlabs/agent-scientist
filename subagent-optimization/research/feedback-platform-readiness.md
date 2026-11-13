# Feedback workflow — platform qualification evidence

Date: 11 November 2026. Tracking: agent-scientist#33.
Status: **two-ligand Vina interface readiness demonstrated by a later completed
job; Solubility/model and comparison setup remain unresolved**. Earlier unknown
submission attempts remain separate reconciliation/accounting records.

## What is established

The offline host adapter imports the recorded baseline with explicit identity,
phase and measurement mappings. It preserved all 99 candidate registry entries
and 660 measurement rows. Its historical state remains frozen and no allowances
are restored. These records contain QED/Crippen and Smina, not the new Solubility
endpoint or platform Vina. See the
[integration record](../results/feedback-policy-v2-observation-integration.md).

The selected local Solubility artifact's SHA-256 was recomputed and matches
`a62b102639e5df62a3361496193b1a9190db7c462b20e13d7af552b60234c289`.
It was hashed as bytes, not loaded. The saved prior inspection describes a bare
HGB estimator with 1,477 inputs. Neither this identity check nor the catalogue's
`LogS` alias establishes its training-target units or transformation.

## Solubility qualification remains unresolved

| Requirement | Existing evidence and exact limitation |
| --- | --- |
| Target definition tied to the selected checkpoint | No inspected model card/training record ties its target column, concentration units, logarithm/sign or inverse transform to this SHA. `logS >= -4` remains conditional and was not applied. |
| Same deployed model in CReM and GA | Local resolvers choose the first existing model-store/NFS candidate. The inspected code does not verify this artifact's SHA at resolution; actual deployed choices remain unverified. |
| Actual feature/transform pipeline | Standalone bundle and CReM inference use different transform handling. Successful standalone inference would not qualify the deployed route. |
| Active property objective | GA may continue after predictor loading/inference errors; an accepted request alone does not prove property-guided optimization. |
| Comparable reported precision | Inspected CReM rounds to two decimals; GA rounds to four. Fix a common assessment/precision rule before threshold decisions, especially at the boundary. |

Names, plausible prediction ranges and UI defaults cannot resolve these questions.
These are setup facts to resolve once, not repeated information requests inside
every specialist episode. Existing evidence can satisfy them; no particular
private debug endpoint or message-byte identity is required.

## Basic Vina: source-defined behavior

The inspected `v5/Toolbox/flex_docking/basic_docking.py` and
`utilities/rigid_validation.py` support a prospective result mapping:

| Item | Inspected source behavior |
| --- | --- |
| Public input | Follow the narrower SDK contract: uploaded receptor PDB and CSV containing exactly `SMILES,NAMES`; explicit box fields; string `exhaustivness`. |
| Box size | `max_radius_size` becomes each full cubic side length, not a radius. |
| Ligand preparation | Add hydrogens; ETKDGv3 seed 42; optional UFF up to 500 iterations; Meeko. Positive UFF return values are accepted, so success does not prove convergence. This differs from the earlier MMFF/Smina setup. |
| Docking | Vina scoring, source seed 42, up to ten poses. The engine is reused across the ordered batch; per-ligand order independence is not established. |
| Identity mapping | `Ligand_no` is one-based input-record ordinal. Cross-check original SMILES/names through the retained input manifest; do not join by output row order. |
| Pose mapping | CSV `Pose=0` corresponds to SDF pose number 1. Preserve all poses and apply a prospectively selected pose rule. |
| Failure | `Pose=-1,Score=100` is a failure row, not a finite usable score. Overall job completion can mean only some ligands succeeded. Missing interaction analysis is distinct from docking failure. |

The new adapter implements these identity/pose/failure rules but defaults to
unqualified measurements. Source inspection cannot confirm which worker revision
is deployed. The later completed job below supplies an actual matched control
check and pose/score association evidence. Deployed software/seed provenance and
explicit score-unit labels remain unavailable.
Historical Smina values cannot provide that validation. DiffDock confidence stays
separate from the primary Vina energy endpoint.

## Authorized live attempt — 11 November, 07:30 UTC

Both exact reviewed inputs uploaded successfully through the existing `ankith`
profile and native connector. Exactly one `Vina_basic_docking` submission request
was made for SB2 control and the e072 lead, with a prospectively frozen 23 Å cubic
box, exhaustiveness 8 and all requested poses retained. No Solubility cutoff or
optimizer was used.

The native response returned `status=unknown`, no `doc_id`, and
`safe_to_retry=false`, without a usable service diagnostic. The local attempt and
its two upload receipts remain protected. No docking outcome or charge was
observed; acceptance and billing remain unknown. There was no resubmission.

The native interfaces cannot search by experiment name, and the local attempt
handle is not a platform job ID. Dashboard/backend reconciliation is needed for
`p38-vina-readiness-20261111-v1`; recover the original document ID before polling,
or establish nonacceptance before considering another submission. See the
[live-attempt record](../results/feedback-vina-live-readiness-20261111.md).

## Later completed job — current technical readiness

Actual document ID `6af4406cfe20edb9107da5fa` has a separately saved native
terminal Success record and twenty verified CSV/JSON/SDF poses: ten per ligand.
The fixed selected SB2 and e072 native scores are -9.234 and -8.216; control
heavy-atom RMSD is 0.51234 Å without alignment in the original receptor frame.
Saved identity, stereochemistry, finite-coordinate and score-association checks
pass. A read-only critic verified the three raw-artifact hashes and reviewed the
validation code/results.

This establishes the tested two-ligand technical interface and observed result
mapping. It does not establish biological binding, optimizer improvement,
specialist advantage or general service reliability. Deployed version, seed,
preparation provenance and explicit score-unit labels remain unavailable.

The successful job is separate from the original unknown attempt, even though
the experiment labels match. Use its readiness evidence without another docking
submission; retain the original acceptance/billing issue separately. See
[completed readiness evidence](../results/feedback-vina-readiness-success-20261111.md).

## Source trail

Paths below are local source dependencies, not bundled or deployed by this work:

- `Ankith/model_inspection/admet_25_gpm/inspection_report.json`: prior artifact inspection.
- `BOLTCHEM-FEATURES/v5/QSPR Modelling/prop_inference_new/prop_inference_new/proppred/global_model_catalog.json`: catalogue mapping without target-unit provenance.
- `v5/Molecule Optimzation/crem/prop_inference_new/bpp_main.py:205`: reported precision.
- `v5/Molecule Optimzation/Graph_GA/scoring_funcs/score_mpo.py:204`: reported precision; predictor-error handling is separate from scientific success.
- CReM/GA `property_model_paths.py`: first-existing-path resolution.
- `v5/Toolbox/flex_docking/basic_docking.py:408`: ligand failure rows; line 762 onward: zero-based CSV poses.
- `v5/Toolbox/flex_docking/utilities/rigid_validation.py:188`: grid interpretation; line 712 onward: size/2 containment.
- Agent Scientist `plugins/boltzmann/skills/boltzmann-tools/references/modules/small-molecule-toolbox.md`: public request/file contracts.

Three critic reviews covered scientific endpoint evidence, source feasibility and
evaluation/import integrity. They support the stated boundaries, not live
qualification or evidence of better molecules.
