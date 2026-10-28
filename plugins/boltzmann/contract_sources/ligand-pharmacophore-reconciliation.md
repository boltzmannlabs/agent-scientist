# Ligand-based pharmacophore hypothesis — 2026-10-26

This record explains restoration of `ligand_pharmacophore` to the executable
catalog and the later validation-file correction. The initial restoration itself
submitted no scientific job; the correction uses subsequent observed diagnostics.
The exact job identifier is sourced, not constructed from the tool's display name.

## Evidence and decisions

- `legacy-v1/clarification-public-evidence.v1.json`, `ligand_pharmacophore`:
  seven scientific payload fields, numeric wire types, file inputs, feature labels
  and diagnostic collection `pharmacophorehypoligand`. Its form field `job_name`
  is labelled Experiment Name; the connector keeps that user label in the
  separate `experiment_name` envelope, not in the scientific payload.
- `legacy-v1/boltchem_tools.md`, Tool 9: recorded accepted submission envelope
  using the same exact job and seven scientific fields; fraction range 0–1 and
  minimum/maximum relationship. Its SMILES-only procedure is incomplete for
  validation CSVs and is superseded by the correction below.
  Its examples and reported test outcomes are historical evidence, not new tests.
- Public frontend `https://app.boltzmann.co/static/js/main.5b329b08.js`, inspected
  2026-10-26: the result-view dispatcher recognizes `ligand_pharmacophore` alongside
  `pharmacophorehypoligand`. This confirms a frontend identifier association,
  not current submission acceptance, entitlement or backend availability.
- `lig_phcore` is a historical route/internal-task label. It is not substituted
  for the recorded submission job name. Receptor-based `Pharmacophore_Hypothesis`
  remains a distinct tool with a distinct payload.

The inspected public frontend feature list and recorded accepted payload both
include `hb donor`; the older archived list was incomplete. Retain this supported
choice without presenting the archived omission as a current UI limitation.
Scientific uncertainties and historical output risk still require review through
the normal partial-validation approval mechanism; this is not a permanent ban.

Only documented bounds are enforced. Observed counts and suggested batch sizes
are not promoted into invented hard limits. CSV validation checks the recorded
header, nonempty required values and basic structure; it does not certify SMILES
chemistry, set suitability or current extra-column acceptance.

## Validation CSV correction

The public frontend required-field registry associates
`PharmacophoreHypothesis-Ligand validation` with `["SMILES","LABELS"]`.
Its ligand-based input help describes `active` / `inactive` text classes, but
inconsistently spells the header singular `LABEL`. The backend diagnostic
`Missing required column(s): LABELS in validation.csv` confirms the plural header.
Adding this column with approved textual classes resolved the demonstrated
submission blocker; the corrected request reached service-reported Success.
This does not establish biological validity or guarantee downloadable artifacts.

The corrected canonical file rule requires `SMILES,LABELS` and uses a scalar
JSON schema in `values.LABELS` to enforce exact `active` / `inactive` strings.
The generic CSV inspector reuses the existing schema validator for such cells;
it never rewrites labels or SMILES. Missing labels are invalid before upload,
even when partial-validation approval is supplied. Training still requires only
`SMILES`. Artificial labels require explicit smoke-test approval.

The generated module is derived from these canonical definitions. Regression
coverage exercises missing/wrong-case headers, empty or undocumented classes,
valid class values, preserved input bytes, upload/submit gates and profile-scoped
receipts. The rule change invalidates old affected upload receipts; revalidate
and upload before a separately approved new submission, never replay an
accepted job to test this repair.

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
