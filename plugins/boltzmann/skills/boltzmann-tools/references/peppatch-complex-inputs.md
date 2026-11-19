# PepPatch input preparation and output interpretation

## PepPatch preparation and results

Use exact job name `Pep_Patch` and the existing single `input_path` file field.
There are no new request fields, analysis switches, chemistry overrides, or
output-path fields. Upload once, submit the returned authorized platform path,
retain the job ID, and poll that ID rather than resubmitting a pending job.

```json
{
  "job_name": "Pep_Patch",
  "experiment_data": {"input_path": "<returned platform PDB or ZIP path>"}
}
```

This is a request shape, not a runnable sample. Normal authorization, cost and
partial-validation approval policies are unchanged. Never set best-effort
approval automatically or bypass a known input error. No client-side RDKit,
Open Babel, PDB2PQR or other chemistry installation is required for this handoff.

### Choose the input mode

- Protein only: supply one prepared, single-model PDB, either raw or as the sole
  PDB in a ZIP. No manifest is needed. This preserves the legacy protein-only
  path and its residue-scale hydrophobicity method.
- Protein plus ligand: supply one ZIP containing exactly one single-model PDB
  and root `peppatch_manifest.json`. Bind every nonstandard non-HOH residue to
  reviewed reference chemistry. A PDB residue name, including generic `LIG`,
  is not evidence of chemical identity. Never silently remove a ligand to obtain
  a protein-only result.

Nested PDB paths and directory entries are allowed; this is not a batch mode.
Only the sole PDB, optional root manifest and directories are accepted. Do not
include reference SDFs, extra JSON, restraint CIFs, notes, or multiple poses.
Use relative POSIX member paths with exact case; traversal, absolute/Windows
paths, duplicate/case-colliding members, symlinks and encryption are rejected.
Current worker resource safeguards are 50 MiB input/total expanded bytes,
64 ZIP members including directories, and 1 MiB manifest bytes. These are
resource safeguards, not molecular quality thresholds or billing estimates.

### Complex manifest

The worker schema is copied unchanged into
`file-input-contracts.v1.json` at
`tools.Pep_Patch.files.input_path.zip_manifest_schema`.
The following is the tested public 1STP/biotin example: it belongs to the
prepared 1STP structure with BTN A300 identifier-only renamed to LIG B1.
Its graph and mapping come from CCD BTN, not the generic name LIG. Use the
matching example ZIP from the operator handoff. Never copy this biotin
definition into a different molecule's request.

```json
{
  "schema": "peppatch-complex-input.v1",
  "structure": "complex.pdb",
  "ligands": [
    {
      "chain_id": "B",
      "residue_number": 1,
      "insertion_code": "",
      "component_id": "LIG",
      "smiles": "O=C(O)CCCC[C@@H]1SC[C@@H]2NC(=O)N[C@@H]21",
      "atom_mapping": {
        "C11": 1, "O11": 0, "O12": 2, "C10": 3, "C9": 4,
        "C8": 5, "C7": 6, "C2": 7, "S1": 8, "C6": 9,
        "C5": 10, "N1": 11, "C3": 12, "O3": 13, "N2": 14, "C4": 15
      },
      "chemistry_source": "RCSB CCD BTN https://files.rcsb.org/ligands/download/BTN.cif; reference graph and ideal stereochemistry; complex RCSB 1STP, ligand identifier-only renamed to B:LIG1"
    }
  ]
}
```

`structure` must exactly match the sole PDB member. Each ligand selector is the
original `(chain_id, residue_number, insertion_code, component_id)`; numbering
is PDB numbering, not a zero-based residue index. Blank chain and insertion
values are `""`; `insertion_code` is required even when empty. Bind each ligand
occurrence separately, with no missing, duplicate or unmatched selectors.
An empty `ligands` list is valid syntax for a protein-only ZIP, not permission
to ignore nonstandard residues.

`atom_mapping` keys are all original PDB heavy-atom names, without hydrogen
names, extras or omissions. Values are unique zero-based atom indices from the
worker's RDKit interpretation of the exact supplied SMILES, not PDB serials,
alphabetical atom order, or indices from a different reference representation.
The map must cover the reference graph exactly once and match element identities.
Obtain a provenance-matched reference and map; do not invent them from the pose.
The schema allows at most 32 bindings and 512 mapped heavy atoms per ligand.
JSON booleans are not integer indices or residue numbers. Duplicate JSON keys
are invalid, and `chemistry_source` must identify the reviewed reference source.

### Client checks versus worker validation

The client reuses bounded ZIP integrity, JSON schema and structure inspection.
When the existing structure parser is available, it checks single-model input,
unambiguous identities, exact selectors, complete PDB heavy-atom-name mapping,
and unique contiguous zero-based indices. Missing parser coverage remains
explicitly unchecked under the existing partial-validation policy.

These are syntax/identity checks, not chemical validation. The client does not
parse the SMILES graph, establish reference atom count or mapped elements,
verify mapped bond lengths or stereochemistry against coordinates, assign
protonation/charges/radii, or execute native surface analyses. A syntactically
acceptable SMILES string can still be invalid chemistry. Complex checks therefore disclose worker-side
chemical validation as incomplete locally; existing approval policy applies.
Approval never overrides known invalid syntax, unsafe archives or bad selectors.

The worker verifies the supplied reference graph, state, element mapping and
pose stereochemistry before native preparation. Current support is standard
protein plus fully specified noncovalently bound organic ligands. Do not promise
support for arbitrary metals, covalent/LINK or inter-component CONECT links,
disconnected graphs, isotopes, radicals, unspecified/mismatched stereochemistry,
or enhanced relative/mixture stereochemistry. Supply one fully specified state.
Do not neutralize, erase stereo, invent a reference or alter the bound pose to
make an unsupported case pass.

Complex preparation also rejects reuse of a protein chain ID after `TER`, and
simultaneous blank (`""`) and underscore (`"_"`) chain IDs because these collide
in native PQR chain labeling. Such inputs require a separately reviewed copy
with distinct explicit chain labels and a recorded identity mapping; do not
silently merge chain segments or relabel the original.

The worker rejects coincident mapped bond endpoints and mapped bond lengths
greater than `1.3 * (Rcovalent(atom1) + Rcovalent(atom2))`, using RDKit's default
connectivity `covFactor=1.3` and element covalent radii. This is an input/mapping
sanity guard against physically impossible reference connectivity in the pose,
not an ideal-bond-length test, universal scientific cutoff, or biological quality
gate. It runs in the worker; no client chemistry dependency is required.

### Preparation and methods

Complex profile: `peppatch-complex-crippen-peoepb.v1`.

- Protein state/charges: native PDB2PQR AMBER default state, without explicit
  pH titration or heavy-atom optimization. Do not describe this as a specified-pH
  protonation calculation.
- Ligand state: exactly the supplied reference-SMILES formal charges, hydrogen
  counts and stereochemistry; no silent neutralization or pH-based state change.
  Native preparation uses Open Babel MOL2 typing and PDB2PQR PEOE_PB charges.
- The worker checks original heavy-atom coordinates. Added hydrogens and only
  native terminal OXT heavy-atom completion are allowed and reported. Generated
  H/OXT positions are preparation assumptions, not experimental observations.
- Both components use one Wildman-Crippen atomic fragment hydrophobicity method
  on the joint prepared complex surface; H contributions are grouped onto the
  bonded heavy atom. The pinned official compiled parameter table and complete
  SMARTS matching avoid native match-cap omissions/fallback errors.

The legacy protein-only hydrophobic residue scale and the complex atomic profile
are different methods. Read the recorded profile before comparing scores; do
not treat them as calibrated equivalents. The worker analyzes the supplied joint
assembly, not per-chain isolated surfaces, and does not expand a biological assembly.
HOH water atoms are excluded explicitly.

### Result ZIP: unchanged key and CSV names

The worker's primary artifact remains the ZIP in `datainfo.outputFilePath`.
Use terminal status and the existing signed-artifact downloader; do not invent
new `hydrophobic_csv_path`, `electrostatic_csv_path` or metadata response fields.
Download and inspect the whole ZIP, then inspect:

- `electrostatic_patches.csv`: positive/negative APBS electrostatic-potential
  patches, with potential units recorded as `kT/e`; this is electrical charge
  potential, not hydrophobicity.
- `hydrophobic_patches.csv`: hydrophobic/hydrophilic surface descriptors using
  the recorded input-mode profile, not an affinity or activity score.
- `analysis_metadata.json`, `analysis_report.md`, `hydrophobic_profile.json`
  and `residue_mapping.csv`: overall/per-analysis statuses, methods, units,
  settings, original chain/residue/insertion identities and input preservation.
- For prepared complexes, `preparation_metadata.json` and
  `prepared_atom_parameters.csv`: coverage, added atoms, charge/radius/state
  provenance and prepared-atom identities/coordinates.
- For prepared complexes, `prepared_complex.pdb` and `complex_parameters.pqr`: the actual prepared
  complex coordinates and APBS charge/radius input, supporting audits of atom
  coverage against `prepared_atom_parameters.csv` and the preparation metadata.
  PQR uses internal residue numbering; use the identity maps to recover original
  selectors. These are complex support files, not new CSV previews or new API
  result keys. Inspect available native preparation/APBS logs on failure.

The two root CSV previews remain `electrostatic_patches.csv` and
`hydrophobic_patches.csv`; additional support files do not replace either result.

Both CSV area columns are in square angstroms. Preserve `main_residue_original`
and explicit chain/residue/insertion columns rather than relabeling historical
global numbering. A header-only CSV can mean zero qualifying patches; distinguish
that from an absent/failed analysis using metadata. A retained ZIP or one valid
CSV does not establish full success: require both analysis statuses completed.
Report actual errors/unsupported chemistry honestly. No biological quality gate
is applied, and neither descriptor proves measured logP, binding affinity,
catalytic activity, aggregation behavior or free energy.

### Verification boundary

Operator-reported local worker verification on 2026-11-12 covered public native
1STP/BTN and 1HSG/MK1 complexes (generic selectors `B:LIG1` and `C:LIG1`) and
a synthetic two-ligand complex; both analyses passed for each. Independent
native-source CALB baseline verification, including the reported OpenMP (OMP)
checks, found exact byte-for-byte equivalence of both legacy CSVs. These are
fixture/configuration-specific local worker results, not a claim that every
ligand is supported or that the candidate image has been adopted by the hosted
backend.
This Agent Scientist handoff itself makes no paid submission and does not prove
Node ZIP forwarding, ZIP credit accounting or live deployment adoption.
