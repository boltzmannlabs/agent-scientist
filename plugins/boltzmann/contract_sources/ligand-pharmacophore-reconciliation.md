# Ligand-based pharmacophore hypothesis — 2026-10-26

This record explains restoration of `ligand_pharmacophore` to the executable
catalog. No scientific job was submitted and no live artifact recovery was tested.
The exact job identifier is sourced, not constructed from the tool's display name.

## Evidence and decisions

- `legacy-v1/clarification-public-evidence.v1.json`, `ligand_pharmacophore`:
  seven scientific payload fields, numeric wire types, file inputs, feature labels
  and diagnostic collection `pharmacophorehypoligand`. Its form field `job_name`
  is labelled Experiment Name; the connector keeps that user label in the
  separate `experiment_name` envelope, not in the scientific payload.
- `legacy-v1/boltchem_tools.md`, Tool 9: recorded accepted submission envelope
  using the same exact job and seven scientific fields; training/validation CSVs
  with `SMILES` headers; fraction range 0–1 and minimum/maximum relationship.
  Its examples and reported test outcomes are historical evidence, not new tests.
- Public frontend `https://app.boltzmann.co/static/js/main.5b329b08.js`, inspected
  2026-10-26: the result-view dispatcher recognizes `ligand_pharmacophore` alongside
  `pharmacophorehypoligand`. This confirms a frontend identifier association,
  not current submission acceptance, entitlement or backend availability.
- `lig_phcore` is a historical route/internal-task label. It is not substituted
  for the recorded submission job name. Receptor-based `Pharmacophore_Hypothesis`
  remains a distinct tool with a distinct payload.

The archived UI options omit `hb donor`, but the recorded accepted payload
includes it. Retain that sourced option with an explicit review warning rather
than deleting a documented choice or claiming fresh verification. All attempts
require acknowledgement of the historical worker/output risk through the
existing partial-validation approval mechanism; this is not a permanent ban.

Only documented bounds are enforced. Observed counts and suggested batch sizes
are not promoted into invented hard limits. CSV validation checks the recorded
header, nonempty required values and basic structure; it does not certify SMILES
chemistry, set suitability or current extra-column acceptance.

## Output and cost uncertainty

The archived record reports 25-credit charges and missing objects at the returned
`zip_files` / `default_hypothesis` references despite terminal Success. Do not
present this as today's price or a proven ongoing outage. Preserve all returned
links; refresh a failed/expired link for the same job when appropriate; inspect
downloads and report missing artifacts accurately. Never duplicate a submission
to recover a missing artifact, or claim that result-field names prove files exist.

Historical storage paths are not distributable sample files or authorization.
No scientific fixtures, private paths, credentials or experimental results are
added by this change. Test CSVs contain harmless parser fixtures only.

The three runtime JSON definitions and generated module now own the executable
contract. The pre-standardization audit remains a dated historical snapshot;
its missing-entry list must not override the current catalog.
