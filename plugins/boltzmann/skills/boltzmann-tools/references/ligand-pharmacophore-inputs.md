# Ligand pharmacophore input format and root cause

Use this guide before preparing or repairing `ligand_pharmacophore` inputs.
This is the ligand-based tool, not receptor-based `Pharmacophore_Hypothesis`.

## Correct file layout

- Training (`smiles_file`): CSV with the exact case-sensitive header `SMILES`.
- Validation (`validation_file`): CSV with exact case-sensitive headers
  `SMILES,LABELS`. Documented textual label values are `active` and `inactive`.
- Preserve the reviewed molecular strings and row assignments. Do not add labels
  to training merely because validation requires them, infer numerical 0/1
  encoding, impose an undocumented class balance, or invent batch-size limits.
- For a smoke test, obtain explicit approval for any artificial activity labels
  and mark their provenance in a sidecar manifest. They are constructed test
  classes, not measured biological activity; resulting validation metrics do not
  establish biological discrimination. For scientific validation, obtain a
  genuinely labeled, suitable dataset instead of guessing activities.

## Diagnose the original missing-column failure

When a SMILES-only validation file is submitted, preserve both diagnostic texts:

    message: Failed to calculate credits
    service_error: Missing required column(s): LABELS in validation.csv

The specific error identifies an absent validation-label column. A generic credit
message alone does not identify insufficient balance or an authorization error.
Valid SMILES and successful uploads do not establish a complete backend input.
For the diagnosed fixture, molecular parsing passed; adding the approved LABELS
column resolved this submission blocker without changing the structures or
scientific settings. Do not infer that all future credit-calculation errors have
this cause.

## Trace the description and validation defect

Use paths below relative to the Boltzmann plugin root in either installation.
Inspect current contents before deciding whether the defect remains present.

1. Historical source: `contract_sources/legacy-v1/boltchem_tools.md`, Tool 9,
   Sci Execution Instructions, says to build two CSVs with a `SMILES` header.
   Its validation-file table does not describe activity labels. This is an
   incomplete historical procedure, not a full validation-file specification.
2. Canonical file rule: in
   `skills/boltzmann-tools/references/file-input-contracts.v1.json`, inspect
   `tools.ligand_pharmacophore.files.validation_file`. The diagnosed rule declared
   only `columns: ["SMILES"]` and said SMILES was used for both CSVs. Its `source`
   pointed to that historical input table and execution step.
3. Generated tool description:
   `skills/boltzmann-tools/references/modules/small-molecule-pharmacophore-generation.md`
   originally reproduced the incomplete validation rule. The corrected canonical
   rule, regenerated module and updated reconciliation record now require
   SMILES,LABELS for validation. Repeating an omission across derived documents
   was not independent verification of the backend format.
4. Local preflight: `file_validation.py`, function `_csv`, checks the columns
   declared by the file rule. With only SMILES declared, a SMILES-only file can
   pass column checks and be uploaded after partial-validation approval. This is
   missing contract/preflight coverage, not evidence that the generic CSV parser
   malfunctioned or that approval overrode an invalid-file rejection.
5. Upstream help inconsistency: the public input description spells the header
   singular `LABEL`, with textual `active` / `inactive` classes. Its required-field
   registry associates `PharmacophoreHypothesis-Ligand validation` with
   `["SMILES","LABELS"]`. The explicit backend diagnostic and a successful
   artifact-producing corrected request agree with the plural `LABELS` header.

Report these as an incomplete historical/local contract plus inconsistent public
help text. Do not claim a backend computation bug or a particular historical
backend change: the evidence does not establish either. If the agent constructed
an input from the incomplete description, state that clearly rather than blaming
user-supplied data. Keep input repair, documentation repair and executable
contract repair distinct; updating this guide does not patch JSON or Python.

## Prepare and verify before submission

1. Load the current scientific module, this guide, file rules and input limits.
   Reconcile any disagreement before calling the fixture execution-ready.
2. Use current public metadata as read-only format evidence when needed. Discover
   the public application's `main.*.js` bundle from an established source; inspect
   bounded contexts for the input help and required-field registry. A source
   examined for this mismatch is
   `https://app.boltzmann.co/static/js/main.5b329b08.js`. Treat it as evidence,
   not an authenticated execution endpoint. Never copy browser credentials or
   call undocumented session-authenticated sample routes.
3. Parse every molecular string with RDKit and compare canonical identities for
   duplicates within and across splits; preserve source strings in the CSV.
   Distinct molecules alone do not establish independent biological validation.
   For feature checks use `from rdkit.Chem import ChemicalFeatures` and the
   appropriate documented feature factory, not a guessed import location.
4. Round-trip both CSVs with `csv.DictReader`. Check exact headers, nonempty
   required cells, original row counts and strings, and approved label values.
   Test that a SMILES-only validation fixture fails the explicit LABELS check.
   Save source identifiers, label provenance, checksums, parser version and
   limitations in a sidecar manifest rather than unapproved extra CSV columns.
5. Attempt normal connector validation. If it reports partial checks, explain
   the actual warnings and obtain explicit approval before using
   `allow_partial_validation=true`. RDKit validation does not clear that gate.
6. Preserve the original error separately from a corrected request. No returned
   job ID leaves job creation and billing unresolved; reconcile the earlier
   attempt through supported records or the user's dashboard before approving
   one corrected submission. After acceptance poll only the returned job ID.
7. Verify the runtime rule requires both validation columns and defines
   `values.LABELS` as a string schema with enum `["active","inactive"]`.
   The CSV inspector reuses the existing scalar-schema validator for these cells;
   it rejects missing, empty or undocumented classes before upload, even when
   partial-validation approval is supplied. Keep missing-header/class regression
   tests and native profile-scoped upload/submit tests. Regenerate module sheets
   with `contract_docs.py`, not hand edits. After deploying Python changes,
   start a fresh SCI session before using the validator. Contract changes can
   invalidate receipts: revalidate/re-upload before a separately approved new
   submission. Never replay an accepted job to test this repair.

## Verify outputs independently

Inspect the live response and download all returned artifacts. A usable response
can expose `zip_files`, `outputFilePath` (hypothesis CSV) and `default_hypothesis`.
Verify ZIP integrity and safe member paths before extraction. Parse the complete
CSV, resolve every referenced SDF/POSP in the archive, compare feature counts,
check finite coordinates and scores, chemically parse reference SDFs and compare
their identities with the reviewed training set. Determine the standalone default
POSP's actual archive match rather than assuming file order. Preserve repeated
features; selected categories need not all appear in each hypothesis.

Treat Success with missing or inaccessible artifacts as incomplete delivery.
Refresh status for the same job once and retry failed downloads when appropriate;
persistent 404s establish unavailable artifacts, not their cause. Conversely,
historical missing-object failures do not imply that new jobs lack outputs:
corrected requests have returned downloadable, verified CSV/ZIP/POSP artifacts.
Never resubmit compute to recover a missing download. Report artifact availability
separately from biological validity, calibrated score meaning and service charges.
