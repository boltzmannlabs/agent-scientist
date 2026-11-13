# Vina live-readiness test — submission outcome unknown

Tracking: agent-scientist#33. Date: 11 November 2026.
Status: **live submission attempted; outcome unknown; no docking results observed**.

This describes the original attempt only. A later separate job completed and now
provides [two-ligand readiness evidence](feedback-vina-readiness-success-20261111.md).
That later success does not resolve this attempt's acceptance history.

## Authorized test and actual execution

The user requested live testing. The bounded first test used the existing `ankith`
profile, native wrappers and verified 1A9U observed protein PDB, with exactly two
inputs: SB2 reference control and the previously supplied e072 lead. Original
campaigns and profile configuration were not edited.

The prospective settings were a 23 Å cubic box centered at
(3.707500, 15.850000, 28.973000), derived from native SB2 bounds plus 5 Å padding
per side; `exhaustivness="8"`; `upload_sdf="True"`; retain all poses; select CSV
pose 0/SDF pose 1 without substitution. No molecular-improvement comparison,
Solubility cutoff, generation, optimizer, retry or top-up was authorized by this
test protocol.

| Operation | Observed outcome |
| --- | --- |
| Input review | Source hashes matched. Protein chain A had 2,833 finite-coordinate atoms and no hetero-ligand records. Both exact submitted SMILES parsed and connectivity-checked in existing RDKit2026.03.6. |
| Native validation | Zero errors. PDB review and unavailable SDK-RDKit checks were resolved by the recorded local review. The historical Vina worker-failure notice was also retained and reviewed under this explicit live-test authorization. |
| Uploads | Both inputs uploaded successfully; returned file hashes matched. |
| Native submission | Exactly one request at 2026-11-11T07:30:24.350855+00:00. Returned unknown outcome, no document ID and `safe_to_retry=false`. |
| Docking/pose evaluation | No results observed; readiness not established. |
| Charges | Unknown. |

Native diagnostic:

> Service request failed without a usable diagnostic; job outcome is unknown.

This does not establish acceptance, nonacceptance, a worker failure, a billing
problem or a specific HTTP status. Two successful uploads do not establish
submission entitlement or scientific-tool readiness.

## Original attempt and continuation

- Experiment: `p38-vina-readiness-20261111-v1`.
- Job: `Vina_basic_docking`.
- Local attempt handle: `cbec7b7e3dc8447ca7a9a94d0bd8eb7b` — not a platform job ID.
- The native local ledger confirms state `unknown`, `doc_id=null` and both linked
  uploaded receipts. No receipt was altered to invent an accepted job.

The native status/log interfaces require a real platform identifier and cannot
search by experiment name. Reconcile the exact experiment in the owning
dashboard/backend. If it exists, recover and monitor its original document ID.
An empty dashboard alone does not prove nonacceptance; do not automatically
submit a replacement.

Private evidence is retained under
`~/.local/state/smallmol-feedback-policy/vina-live-readiness-20261111-v1/`:
protocol/input hashes, ligand join manifest, local validation/review records,
both original upload receipts, submission intent and original response, native
transport evidence, `run_outcome.json`, `report.md`, artifact hashes and a prepared
`backend_reconciliation.txt` message. No external message was sent.

The feasibility critic independently confirmed the receipt semantics and lack
of a supported native lookup without a document ID. Solubility checkpoint units
and deployed resolution remain separate unresolved setup facts. No scientific
improvement, independent evaluation or specialist-benefit claim is made.
