# Feedback-policy v2 — recorded observations and native result mapping

Date: 11 November 2026. Tracking: agent-scientist#33.
Status: **offline integration implemented and tested; no live workflow executed**.

## Delivered and verified

The [adapter](../prototype/feedback_policy/README.md) now provides:

- Explicit host canonical-isomeric-SMILES/measurement joins with source hashes,
  raw records, phase separation and missing/conflict statuses.
- Basic Vina input CSV preparation with exact public columns and an ordered join
  manifest, plus source-defined native result import preserving every pose.
- Explicit `Pose=-1,Score=100` failure handling; CSV/SDF pose correspondence;
  declared pose selection without substitution; unqualified defaults.
- A historical replay CLI with bounded manifest/member containment and hash
  checks, separate outputs, and frozen/no-execution state.

Executed from `prototype/feedback_policy/`:

```bash
python3 -B -m unittest -q test_feedback_policy test_observations
```

**56 tests passed, zero failures/errors.** This includes the existing 36 policy
tests and 20 adapter/integration tests. Synthetic archive tests cover tampered
members, a manifest symlink outside the bundle, frozen replay and unchanged inputs.

## Actual recorded-data import

Imported the completed base-guidance p38 archive, not the specialist output.
No historical panel was re-ranked or rejudged under the new criteria.

| Record | Preserved count |
| --- | ---: |
| Candidate registry | 99 |
| Search measurements | 594 |
| Final measurements | 60 |
| Control measurements | 6 |
| All measurements | 660 |

All original observations and rounded generator annotations remain available.
The projection uses the precise recorded QED/Crippen values. Search QED/Crippen
coverage is 99 each; final coverage is ten each. There are zero Solubility or
platform-Vina observations; historical Smina stays separately labelled.

The three imported manifest members and the manifest itself were checked again
after import and remained unchanged. This was not a revalidation of all 823
source artifacts or independent verification of molecular/pose semantics.
The archived task returns STOP with no action cards or restored allowances.

Private import receipts and observations are saved under:
`~/.local/state/smallmol-feedback-policy/p38-baseline-import-20261111-v2/`.
The source-evidence snapshot is
`~/.local/state/smallmol-feedback-policy/platform-source-evidence-20261111-v1.json`.
Generated/private evidence is not added to the repository.

## Review and remaining boundary

The evaluation critic found a manifest-containment gap; it was fixed and covered
by regression/integration tests. The feasibility critic confirmed native
identity/pose/failure mapping and clarified that canonical identity must be
isomeric SMILES. The scientific critic found no checkpoint-tied evidence of the
selected model's physical units. See
[platform readiness](../research/feedback-platform-readiness.md).

Model unit/transform and deployed-resolution evidence, an authorized common Vina
control qualification, live allowances, and the matched comparison contract
remain prerequisites for scientific execution. No predictions, remote jobs,
profile changes or Git operations were performed in this integration work.
