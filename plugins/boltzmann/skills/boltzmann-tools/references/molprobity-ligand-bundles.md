# MolProbity custom-ligand input bundles

The request is unchanged: exact routing `job_name: Mol_Probity`, uploaded ZIP in
`input_path`, existing `execution_mode` and validation-only `quality_thresholds`.
Do not add a `ligand_dictionary` or `restraints_path` API field. Ordinary single
structures and ordinary structure ZIPs remain supported.

## Preparation

For an unsupported noncovalent substrate, obtain a chemistry-reviewed restraint
CIF plus a verified reference SMILES and exact atom mapping. Do not infer bond
orders, protonation or ideal restraint targets from the tested pose. Do not
invent dictionaries, remove ligands to make validation succeed, or strip stereo
labels to bypass unsupported cases. A dictionary generator needs separate
reviewed molecular inputs; this connector does not generate dictionaries.

```text
complexes.zip
├── ligand_manifest.json
├── structures/parent_complex.pdb
└── restraints/LIG.cif
```

The manifest must be UTF-8 JSON at the exact ZIP root. Its complete machine
schema is `tools.Mol_Probity.files.input_path.zip_manifest_schema` in
`file-input-contracts.v1.json`, using protocol `molprobity-ligand-bundle.v1`.

| Field | Required | Meaning |
|---|---|---|
| `schema` | yes | Literal `molprobity-ligand-bundle.v1`. |
| `structures` | yes | Nonempty array of candidate entries. |
| `structures[].path` | yes | Exact canonical relative ZIP member path to a supported structure. |
| `structures[].ligands` | yes | Custom dictionary bindings; `[]` means no custom dictionary. |
| `ligands[].dictionary` | yes | Relative `.cif` dictionary member, never a candidate structure. |
| `ligands[].sha256` | yes | Actual lowercase SHA-256 of the dictionary's original bytes. |
| `ligands[].component_id` | yes | Exact uppercase component code; protected polymer/water components cannot be replaced. |
| `ligands[].chain_id` | yes | Exact case-sensitive chain label in the candidate. |
| `ligands[].residue_number` | yes | Integer residue number in the candidate. |
| `ligands[].insertion_code` | no | Exact insertion code; default empty string. |
| `ligands[].smiles` | yes | Reviewed nonempty heavy-atom reference SMILES. |
| `ligands[].atom_mapping` | yes | Each heavy-atom name mapped bijectively to its zero-based RDKit reference-SMILES atom index. |

Each custom component instance must be explicitly bound by chain, residue and
insertion code. One candidate cannot use conflicting dictionary hashes for the
same component; different candidates remain independently bound. Candidate IDs
come from sanitized basenames, so different paths must not collide. Every
structure/dictionary CIF must be declared; their roles must not overlap.

## Limits and local coverage

The canonical limits are under `tools.Mol_Probity.ligand_bundle` in
`input-limits.v1.json`: manifest and each dictionary <=1 MiB, <=64 dictionary
paths, <=256 bindings per candidate, <=2048 dictionary atoms, <=1000 total ZIP
entries (including auxiliary files), <=50 MiB per structure, <=2 GiB expanded
archive and <=200 compression ratio. Connector inspection budgets may be smaller
and must be disclosed as incomplete inspection, not invented scientific limits.

Local preflight checks manifest shape/version, duplicate JSON keys, finite JSON,
safe/member paths, declared roles, dictionary hashes, unique selectors and IDs,
and bounded CIF syntax/atom counts when Gemmi is available. With RDKit available,
it checks reference syntax/index coverage and rejects specified stereo/isotopes.
Bound structure checks cover models, exact components/residues, heavy-atom names,
alternate locations and explicit binding of all instances.

Local checks do **not** establish dictionary/reference connectivity and bond-order
agreement, formal charges/hydrogen counts, CCTBX energy types, restraint coverage
and target quality, experimental protonation or assay relevance. The worker must
validate these. Missing parsers and remaining checks require explicit best-effort
approval; approval cannot bypass known-invalid input.

Version 1 does not support specified stereo/isotopic ligands, stereospecific
dictionary restraints, custom covalent links, link/modification/global-energy
dictionaries or polymer/water replacement. Some restrictions require the worker's
CCTBX path and remain unchecked locally. There is no protein-only fallback for
an invalid bound complex.

## Results and deployment boundary

Keep the existing summary table, invalid/outlier tables, raw reports and complete
results ZIP. Measurement-only status remains `measured`, never `passed`.
When custom dictionaries were used, also retain optional
`ligand_dictionaries_used.json` and `restraints_used/<sha256>.cif` provenance.
Their absence is normal for ordinary inputs; do not fabricate them.

Worker-local release tests are not a live Node integration check. Backend owners
must confirm ZIP forwarding and billing count **declared structures only**, not
dictionary CIFs, and deploy the correct worker image. A pushed tag does not update
running pods. Confirm these before promising platform-wide bundle support.
MolProbity structural metrics and dictionary provenance do not prove binding or
catalytic activity.
