# Shared initial packet — SB202190 / p38α

Status: **proposed bounded preparation; execute only when explicitly assigned**.
Tracking: agent-scientist#33. This task prepares common inputs for a later
comparison. It is neither comparison arm, an authorization to run both arms,
nor a continuation of the completed e072 pilot.

## Fixed question and inputs

Prepare initial evidence for exploring new SB202190 analogues with lower native
Vina Score while retaining common PAMPA class 1, RDKit QED ≥ 0.5 and Crippen
LogP 0–5 inclusive. Scores are predictions; preserve native units or their absence.
Do not substitute Smina or another predictor.

Read this directory's README.md, local_case_review.json and
proposed_references.csv. Use exactly its declared SB202190 molecular form and
SB2 control. Both appear in common PAMPA and any eligible-candidate search batch;
neither is a generated-candidate slot. Do not use e072 or archived generated
compounds. Do not inspect other experiment outcomes or candidate registries.
The case audit already checked prior identities; it provides no prior scores.

Verify the five reusable asset hashes listed in local_case_review.json. The
full observed 1A9U chain-A receptor and native SB2 SDF remain unchanged. Preserve
the receptor's existing missing-region/preparation limitations. SB202190 has no
native pose in 1A9U; do not calculate a native-pose RMSD for it.

Use the frozen local environment:
`/home/boltzmann13/drug_discovery_ml/ml_env/bin/python` (RDKit 2025.09.6).
Use existing pure helpers under `prototype/feedback_policy/`, recording copies
and hashes in the output. Do not import an old campaign's mutable runner/state.
Resolve routine local processing within scope; never change the profile,
connector, scientific objective, libraries or source assets to get a better result.

## Finite operations

Use the active profile's native Boltzmann tools and inspect their current public
optimization, QSPR and toolbox contracts. Save relevant snapshots. Do not build
a second HTTP client or require inaccessible private worker/model provenance.

| Stage | Maximum submission attempts | Fixed scope |
| --- | ---: | --- |
| Initial CReM | 1 | SB202190 parent and existing `mixed_reference.csv` only |
| Common PAMPA | 1 | Up to 40 selected new identities plus SB202190 and SB2 |
| Search Vina | 1 | Only jointly eligible selected identities, plus SB202190 and SB2 |

Maximum total: **3 submission attempts, 40 new candidate-assessment slots,
42 common PAMPA input attempts and 42 Vina ligand attempts**. These include
failed or ambiguously accepted attempts. Uploads/status/downloads are recorded
separately. No top-up, retries, follow-up generation, final panel, alternative
library or controls-only scientific batch. Hidden enumeration/pose work and
currency cost are not capped by these observable limits; report them as unknown
where the service does not expose them.

Use a two-hour submission window from the first durable scientific reservation.
Record the start/deadline before submitting; interruption does not reset either.
No next-stage submission after that deadline. Read-only collection of an accepted
job by its actual ID and local analysis remain allowed afterwards. If collection
cannot finish, return WAITING with its receipt and exact continuation state.
Do not claim local interruption cancels remote work.

No monetary ceiling is supplied. Service amounts and any absent units remain
explicit. This task grants no service permission without the user's assignment.

## Execution and interpretation

1. Create a fresh directory under
   `08_results/p38_refinement_matched/shared_sb202190_<timestamp>/` in the active
   profile workspace. Verify references/assets and copy the task, case review,
   common guide and relevant helper source into a record of this preparation.
   Before any native submission, durably reserve its stage/inputs and save the
   exact request digest. Retain native receipts and actual IDs. On UNKNOWN
   acceptance stop new submissions; never guess IDs or submit a replacement.

2. Submit `Fragment_Based_Optimization` once with the exact lead `ref_mol`,
   uploaded mixed-library `library_path` and
   `global_models=[{"name":"PAMPA","min_threshold":0.5,"max_threshold":1}]`.
   CReM enumerates products and annotates predictions; do not claim an internal
   Vina objective or add unsupported count/steps/radius/seed/atom-mask controls.
   Keep the full raw output and all invalids, duplicates and reference recoveries.

3. Parse **identity fields only** until assessment-subset commitment. Under the
   declared RDKit implementation use strict connected canonical isomeric identity
   with `parseName=False`, `allowCXSMILES=False`, ordinary sanitization and
   explicit stereo preservation. Do not neutralize or tautomerize. Exclude both
   exact reference identities. Apply `assessment_subset` from
   `prototype/feedback_policy/feedback_policy.py` with allowance 40 and seed
   **1101** to the unique identities. Save input/output/digest and timestamp
   before displaying optimizer prediction columns or computing quality metrics.
   Retain fewer identities if fewer exist; never replace failed selected records.

4. Calculate QED and Crippen LogP for all selected identities and both references
   under RDKit 2025.09.6. Retain actual size, flexibility, polarity and unspecified
   stereo summaries without inventing new eligibility thresholds. Submit one
   `Property_Prediction` batch with `global_models=["PAMPA"]` and the current
   supported no-uncertainty/no-explainability settings. It reports binary labels,
   not calibrated probabilities. Join using verified exact identities. Distinguish
   explicit predictor failure from a legitimate class 0; missing/nonfinite or
   contradictory repeated labels are unresolved, not favorable results.

5. If any selected generated identity is confirmed jointly eligible, submit one
   `Vina_basic_docking` search batch for those identities and both references.
   Use CSV headers `SMILES,NAMES`, the fixed receptor upload, center
   **(3.707500, 15.850000, 28.973000)**, `max_radius_size="23"` (full cubic
   side 23 Å), `exhaustivness="8"` and `upload_sdf="True"`.
   Do not introduce local redocking. Retain every returned row/pose. Select CSV
   pose 0 / SDF pose 1; missing/ambiguous selected poses remain missing.
   `Pose=-1,Score=100` is failed/null, never a scored candidate. Verify graph,
   specified stereo, finite coordinates, input mapping and score agreement
   within that request. A missing control is retained as a limitation, not
   replaced. For SB2 only, retain native-frame control RMSD with documented atom
   mapping if calculable from these already-returned artifacts.

6. If no selected identity exists, skip both assessment submissions. If none
   passes joint eligibility, skip search. Retain failed/negative/partial evidence
   without changing lead, replacing a batch or silently fabricating completed
   stages. Record actual unused allowance. An unresolved tool refusal stops new
   calls; do not bypass it. Missing private model versions/404 diagnostic logs
   alone do not negate valid delivered observations.

7. Build a shared packet containing the initial candidate/measurement tables,
   all raw outputs/poses/failures, exact source references, tool snapshots and
   accounting. Report QED-only, LogP-only, overlapping, PAMPA and missing-data
   failures plus eligibility/assessment denominators and unassessed emissions.
   Describe observed chemistry; do not decide the future parent/library action
   for either arm. Do not create a final ranked endpoint panel or new reward.

## Output and stop

Save `report.md`, `packet_manifest.json`, `candidate_registry.csv`,
`measurements.csv`, subset commitment, `decisions.jsonl`, `resource_ledger.csv`,
reference/scorer manifests and linked native receipts/results. Record status,
scientific interpretation, model/provider and unavailable counters honestly.
Every metric/identity needs status and artifact provenance; nulls have reasons.
Use relative paths for packet contents and SHA-256 hashes; verify them by
read-back. Keep reusable source files and previous experiments unchanged.

State actual shared use (at most 3/40/42/42), accepted/pending IDs, failures,
elapsed times and provider amounts/unknown units. Keep a compact checkpoint and
full artifacts outside conversation context. No independent evaluation or
specialist-benefit claim follows from this preparation.

Stop after packet creation or a recorded blocker. No comparison-arm submission
is authorized. The later arm prompts and operational settings must be frozen
separately before either arm sees its execution assignment.
