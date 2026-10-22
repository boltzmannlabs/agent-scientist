# Enzyme tools: use, evidence and result interpretation

These five tools use the existing authorized Boltzmann connector, not direct HTTP
calls or a second credential system. Catalog visibility is not authorization.
Use the active profile's approved key, selected workflows and upload receipts.
All five have documented callable contracts; historical failures do not impose
a permanent local execution block. Disclose recorded uncertainties and obtain
approval for a new attempt. Never duplicate an accepted or pending job.

## Enzyme DeepAllo

Domain: **Protein Engineering → Enzyme Generation**. Exact job: `deepallo`.
Predicts up to three allosteric pockets on a selected protein chain. Load the
[generated enzyme module](modules/protein-enzyme-generation.md) for the request.
The input is one uploaded PDB, exactly one model, with the case-sensitive selected
chain and more than 10 standard residues with CA. Ambiguous alternate locations
are invalid. Pocket predictions do not establish experimentally demonstrated allostery.

The October 22 reference test completed and returned a CSV with three predictions.
Observed columns: `rank`, `pocket_id`, `probability`, `chain_id`,
`residue_numbers`, `residue_count`. Inspect actual counts; “up to three” does not
promise three for every input. Earlier HTTP 403 was account entitlement, not a
payload defect; the subsequently authorized test succeeded.

## EnzyControl

Domain: **Protein Engineering → Enzyme Generation**. Exact job: `enzycontrol`.
Generates enzyme **backbones** conditioned on the selected chain, motif residue
labels and substrate SMILES. Required fields and bounds are in the
[generated enzyme module](modules/protein-enzyme-generation.md).
Residue labels have no chain prefix and may include insertion codes. The chain
must contain 2–2000 standard residues, finite N/CA/C coordinates, the selected
motifs and at least one non-motif residue. The substrate has at most 128 atoms
including hydrogens; checking that limit requires a chemistry-aware validator.

The initial handoff called `seed` optional because the local worker can generate
one. The supplied FastAPI snapshot requires it: obtain a user-approved integer
seed, do not silently choose one. `n_samples` is optional with worker default 1.
The frontend message “Substrate is required” for the chain field is a label error;
the actual field is still `chain_id`.

The supplied CALB/1TCA reference uses a benchmark substrate pairing, not a ligand
crystallographically present in that structure. The local reference used storage
and status substitutes and is not a production golden output. The October 22
platform test returned ten backbone PDBs, `summary.csv`, `residue_mapping.csv`
and `manifest.json`. Check requested count against both archive members and
summary rows. Scaffold amino-acid labels are placeholders, not designed sequences.
Neither backbone generation nor completion establishes folding, side-chain
design, substrate activity or experimental enzyme function.

## Catalytic Geometry

Domain: **Protein Engineering → Protein Toolbox**. Exact job: `Catalytic_Geometry`.
Measures or validates reaction-specific, evidence-linked structural geometry.
Read the [generated toolbox module](modules/protein-toolbox.md) and the complete
[template/binding/mapping guide](modules/catalytic-geometry-template.md).
The file contract contains the full schemas for all geometry check types,
atom references, evidence labels, binding roles and candidate mappings.

Upload the structures and each required JSON separately. The supplied FastAPI
requires both `reaction_template` and `template_binding` storage-path strings,
even though local code supports optional binding and inline templates. Never
fabricate dummy roles to satisfy that API requirement.

The local runtime supports CSV and JSON candidate mapping. **The Node route
rejected CSV with HTTP 400, “Mapping file must be a .json file”.** Use JSON on
this connector route. A conversion must preserve candidate IDs, mapping keys,
chain IDs, integer residue numbers and insertion codes exactly, reject duplicate
mapping keys, and be reviewed before upload. Do not silently change the data.
The documented input-source enum and both execution modes remain available.

The developer bundle's template is explicitly a **user-defined geometry-
preservation engineering check**, not an experimentally established catalytic
criterion. Its local prior run used the older `rules_path` interface; do not
send that field on the current API. The live reference test completed with 20
passed candidates, 40 passed checks and no invalid candidates after the reviewed
CSV-to-JSON conversion. These counts are observations, not universal thresholds
or a reason to infer catalytic activity, kinetics or substrate scope.

Inspect `candidate_summary.csv`, `geometry_measurements.csv`,
`invalid_candidates.csv`, the template/binding/rules used, `evidence_report.json`
and `manifest.json`. Distinguish measured, passed, rejected and invalid candidates.

## MolProbity

Domain: **Protein Engineering → Protein Toolbox**. Exact job: `Mol_Probity`.
Measures structure-quality metrics or applies only user-selected quality gates.
Use the [generated toolbox module](modules/protein-toolbox.md).
One structure, gzip structure, or ZIP is accepted by the documented file contract.

Default/`measurement_only`: omit `quality_thresholds` entirely. Do not send
the frontend's all-zero defaults. `validation`: supply a nonempty inline object
or an uploaded JSON file containing only chosen thresholds. All eleven supported
threshold names, numeric/integer types and bounds are in the request schema;
none is a universal recommended cutoff. Inline objects do not require an upload.

The October 22 reference submission was accepted, but the last recorded status
was pending without output. Do not present it as a completed test or submit a
replacement for that pending job. Use its saved job ID in the private test ledger;
production identifiers are intentionally not distributed with the skill.
No verified output schema is invented. Inspect returned artifacts and quality
metrics when available; structural quality does not establish function or binding.

## Enzyme RFD3

Domain: **Protein Engineering → Enzyme Generation**. Exact job: **`Enzyme_RFD3`**.
Generates enzyme scaffolds from a prepared motif/ligand-containing structure.
Load the [generated enzyme module](modules/protein-enzyme-generation.md) and the
[complete advanced-fields guide](modules/rfd3-advanced-fields.md).
All supplied advanced selectors, sampler settings, numeric bounds, string flags,
geometry fields and cross-field constraints are retained. Ligands are selected
CCD component codes present in the structure, not SMILES.

Use literal strings `"true"`/`"false"` for the documented flag fields, not JSON
booleans. The supplied updated API/runtime documentation permits distance **and
angle** constraints, superseding the older distance-only frontend snapshot.
Only include advanced settings when enabled; omit unused numeric fields instead
of blank strings. `task_name`, when present, is `rfd3`; it is not the routing name.

The supplied local 1MG5-derived reference had one rejected round and one accepted
design. Local file/status substitutes and stochastic outputs are not production
golden results. The impossible-geometry control was rejected locally. Do not
expect byte-identical outputs or identical per-candidate decisions in live runs.

The October 22 Node submission **used `job_name: Enzyme_RFD3` and was accepted**.
The worker later reported `RFD3 failed during input validation: job_name is
required and must be a nonempty string`. The cause remains unverified. Preserve
the exact routing name; do not insert a guessed inner `job_name`, bypass Node,
or claim that the failure was repaired by catalog integration. This is a
historical service failure, not a missing-contract block. Explain it before a
new user-approved attempt, and reconcile any ambiguous submission before retrying.

A completed ZIP can contain only rejected designs. Inspect `manifest.json`,
`rejections.json`, `designs/` and `rejected/round_N/`; report accepted and rejected
counts separately. `quality_status: rejected` is not a successful design.
Input, inference, corruption and upload failures remain failures. Geometry
preservation and scaffold generation do not establish catalytic activity.

## Shared submission and verification rules

Use `boltzmann_upload` for local inputs, then
`boltzmann_submit(job_name=..., experiment_name=..., experiment_data=...)`.
The Node wire envelope uses `job_name`, `experimentName`, `experimentData`.
Node supplies authenticated `user_id`/`tokenid` and creates `experiment_id`;
these do not belong in the scientific payload. Never put a key in documentation,
examples, model context or arbitrary requests code. Upload placeholders in
recorded examples are not valid platform paths.

Retain returned `docId` and the **same exact job name** for polling/fetching.
Do not retry ambiguous submissions. HTTP 200 means accepted, not completed or
scientifically correct. File-size/shape checks cannot establish atom identity,
chemical validity, biological function or account entitlement. Existing explicit
best-effort approval covers disclosed specialized checks; it never bypasses
authentication, profile restrictions, malformed payloads or unsafe archives.

Full supplied request/file/limit definitions are incorporated into the three
canonical contracts. Developer provenance records, the supplied API snapshot,
sanitized bundle calls/local reports, bundle README and source/member SHA-256
hashes are retained under `contract_sources/enzyme-tools-2026-10-22/` in the
plugin repository. Raw credentials, notebooks, live identifiers, signed URLs,
local absolute paths and bulk result archives are not distributable defaults.
