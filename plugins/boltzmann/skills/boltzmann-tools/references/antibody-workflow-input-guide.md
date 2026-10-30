# Antibody workflow input guide

This manually maintained companion explains inputs discussed in
[Issue #14](https://github.com/boltzmannlabs/agent-scientist/issues/14).
Worker details below come from local copies of the Boltz2, PPIFlow, stabddg and
ab_qsar Docker sources reviewed on 2026-10-30. They describe inspected code;
they do not establish which image is deployed or prove a successful remote run.

Use this guide with the matching generated module and
[canonical request contracts](tool-contracts.v1.json). The connector still
enforces its installed schemas. If a worker requirement conflicts with a schema,
report the specific difference and reconcile the contract before submission.
Do not bypass validation, invent fields, or silently change the user's inputs.
Worker defaults below explain omitted values; they are not permission to choose
scientific parameters for the user.

## Boltz2: protein-only inputs and blank lists

Exact job: `Boltz2`. See [structure prediction](modules/protein-structure-prediction.md).

| Field | Meaning |
|---|---|
| `Protein_Sequences` | List of protein amino-acid sequences. Two proteins are two separate string entries in this list. |
| `DNA_Sequences` | List of DNA sequences, when DNA is part of the requested structure. |
| `RNA_Sequences` | List of RNA sequences, when RNA is part of the requested structure. |
| `SMILES` | List of ligand SMILES strings, when ligands are part of the requested structure. |

Protein-only requests do not need DNA, RNA or SMILES. Unused optional lists may
be omitted or supplied as `[]`. In the inspected wrapper, `clean_sequences`
also treats `['']` and `['   ']` as empty lists and removes blank entries from
mixed lists while preserving real entries. In JSON, use double quotes:
`"DNA_Sequences": [""]`. At least one protein, DNA or RNA sequence is required
by the worker; a SMILES-only request is insufficient for this wrapper.

Blank entries and invalid JSON are different problems. Close the protein list
before the next field. A fragment such as `"second sequence"[]` is malformed
JSON and cannot reach sequence validation. Do not copy terminal border characters
into a request.

## PPI Flow: select one mode

See [protein generative design](modules/protein-generative-design.md).
Choose the job and its matching `task_name` together:

| Job | `task_name` | Purpose |
|---|---|---|
| `ppiflowprotein` | `protein` | Generate protein binders against an uploaded target. |
| `ppiflowantibody` | `antibody` | Generate antibody CDR regions using an antigen and a heavy/light-chain framework. |
| `ppiflownanobody` | `nanobody` | Generate nanobody CDR regions using an antigen and a heavy-chain framework. |
| `ppiflowmonomer` | `monomer` | Generate standalone proteins, unconditionally or around a supplied motif. |

Use the fields for the selected mode. Mode-specific meanings and worker
requirements are described below; the generated module lists connector requirements.

### Protein mode

| Field | Meaning |
|---|---|
| `input_pdb` | Uploaded target or complex PDB containing the selected target chain. Required by the worker. |
| `target_chain` | Single chain identifier for the target in that PDB. Worker default: `A`. |
| `binder_chain` | Existing binder chain in the input complex, used to identify the interaction region when explicit hotspots are absent. The inspected worker requires this field or `specified_hotspots`. |
| `specified_hotspots` | Comma-separated target chain/residue identifiers, such as `A23,A24`. Use the uploaded target's residue numbers and selected target chain. The inspected validator rejects colon syntax such as `A:23`. |
| `samples_min_length` | Minimum generated binder length in amino-acid residues. Must be positive and no greater than `samples_max_length`. Worker default: `50`. |
| `samples_max_length` | Maximum generated binder length in amino-acid residues. Worker default: `100`. |
| `samples_per_target` | Positive integer count of designs requested for this target. Worker default: `5`. This is a request count, not a guarantee of successful outputs. |

### Antibody and nanobody modes

| Field | Meaning |
|---|---|
| `antigen_pdb` | Uploaded antigen PDB, separate from the framework file. Required by the worker. |
| `framework_pdb` | Uploaded framework scaffold with the CDR loops to be generated removed. Antibody mode uses heavy and light chains; nanobody mode uses a heavy chain only. See numbering notes below. Required by the worker. |
| `antigen_chain` | Single chain identifier for the antigen in `antigen_pdb`. Worker default: `A`. |
| `heavy_chain` | Single chain identifier for the heavy-chain framework in `framework_pdb`. Worker default: `H`. |
| `light_chain` | Antibody mode only: single chain identifier for the light-chain framework. It must differ from `heavy_chain`. Worker default: `L`. |
| `cdr_length` | Alternating comma-separated CDR names and inclusive length ranges. For example, `CDRH1,8-8` requests an eight-residue H1 loop. Ranges describe generated loop lengths, not residue positions to delete. |
| `samples_per_target` | Positive integer count of designs requested. Worker default: `5`. |
| `specified_hotspots` | Antigen residues to target, using the antigen PDB's chain and residue numbering, such as `A23,A24`. Required by the inspected worker in both modes, despite being optional in the current generated descriptions. |

The worker requires CDR names once each, in the following order. Missing or
blank `cdr_length` selects these worker defaults:

- Nanobody: `CDRH1,8-8,CDRH2,8-8,CDRH3,9-21`.
- Antibody: `CDRH1,5-12,CDRH2,4-17,CDRH3,5-26,CDRL1,5-12,CDRL2,3-10,CDRL3,4-13`.

The copied PPIFlow README specifies **IMGT numbering** for the framework and
removal of CDR loop residues. A normal consecutive-numbered Boltz2 prediction
is therefore not automatically a prepared framework scaffold. Identify the
heavy/light chains and their antibody numbering before preparing the framework;
retain the framework residue identifiers after removing the CDR residues. Keep
the antigen in its separate input file. Obtain the user's agreement before
altering their structure.

The inspected `sample_antibody_nanobody.py` locates gaps by discontinuities in
integer residue numbers. It assigns successive gaps to H1/H2/H3 or L1/L2/L3;
it does not verify IMGT annotations or interpret insertion codes as a complete
antibody-numbering scheme. Extra discontinuities, repeated integer IDs with
insertion codes, or renumbering away the intended gaps can misidentify loops.
Check the prepared scaffold's gap mapping explicitly. Supplying Kabat, Chothia
or arbitrary numbering does not trigger automatic conversion to IMGT.

### Monomer mode

| Field | Meaning |
|---|---|
| `generation_mode` | Connector selection: `unconditional` or `motif_scaffolding`. The canonical contract marks this as a selection field rather than a backend payload key. |
| `length_subset` | Requested sequence lengths for unconditional generation. The connector documents a string containing an integer list, such as `"[80, 100]"`; each length must be positive. |
| `motif_csv` | Uploaded motif-scaffolding CSV. The inspected worker requires nonempty `target`, `length`, `contig` and `motif_path` columns. Referenced motif files must also be available to the worker. |
| `motif_names` | Comma-separated motif names selecting entries for motif scaffolding. The inspected wrapper accepts a string. |
| `samples_num` | Positive integer sample-count setting for monomer generation. Worker default: `5`. |
| `samples_min_length`, `samples_max_length` | Currently required by the connector's monomer schema, but not used by the inspected monomer validator. They do not replace `length_subset` or `motif_csv`. |

The inspected worker requires exactly one of `length_subset` and `motif_csv`.
Its accepted `length_subset` types are broader than the connector's string
schema. Preserve the connector's documented type; do not treat worker support
for other types as permission to bypass the schema.

### Interpreting the reported output error

`sample_metrics.csv is missing pdb_name` is an output-validation error.
The `pdb_name` column associates a metrics row with its generated PDB. The
inspected antibody/nanobody producer now writes that column, but a failing
deployed run still needs its actual CSV and image version checked. Do not
invent PDB names or report success solely because a source copy contains the fix.

## Stability-Binding DDG: five scientific inputs

Exact job: `stability-binding-ddg`. See [protein optimization](modules/protein-optimization.md).

All five inputs below are needed by the inspected worker. In particular,
**`pdb_path` is required**, although the current canonical schema does not yet
include it in its required-field list.

| Field | Type | Required by worker | Meaning |
|---|---|---|---|
| `pdb_path` | string, uploaded file | yes | Uploaded `.pdb` structure of the docked protein–protein complex. Prepare the two interacting chains as `A` and `B`, matching this wrapper's interface convention. A sequence, SMILES string or PDB identifier alone is not a structure upload. |
| `sequence` | string | yes | Amino-acid sequence of the chain selected for mutation, using the 20 standard one-letter amino-acid codes. It must correspond to that chain in the supplied complex. |
| `chain` | string | yes | Chain to mutate: `A` or `B` for the expected two-chain complex. This identifier must exist in the PDB and match the supplied sequence. |
| `mutations` | array of strings | yes | One-based sequence positions or inclusive ranges at which variants will be generated, for example `["1", "2", "8-15"]`. Positions must fall within `sequence`. These select sites, not specific amino-acid substitutions. |
| `num_mutations` | string | yes | Positive number of sequence variants to generate, supplied as a string, such as `"10"`. It counts variants, not mutated positions per variant. |

The mutation generator chooses substitutions at the selected positions for
each variant. Preserve the user's chosen positions rather than inventing
substitutions. Check that the chain's structural residue numbering corresponds
to the one-based sequence positions used by this wrapper; antibody numbering
from a PPI Flow framework is not interchangeable with this convention.

The current connector allows integer mutation entries as well as strings, while
the inspected worker validates string entries. Use the string format when
preparing a new request and explain any needed conversion of existing inputs.

## Antibody Property Prediction: QSAR properties and numbering

Exact job: `Antibody_Prediction`. See [protein property prediction](modules/protein-property-prediction.md).

| Field | Meaning |
|---|---|
| `dataPath` | Uploaded CSV containing paired `Heavy_chain` and `Light_chain` sequences. The inspected reader requires both to be nonempty for each row. `Solubility_ESM` also requires a nonempty `seq_id` column. |
| `property_name` | The inspected worker expects a nonempty list of distinct property identifiers, for example `["CDR_Prediction"]`. Its registered options include `Thermal_Stability_Protbert`, `Thermal_Stability_ESM`, `Solubility_ESM`, `CDR_Prediction` and `Antigen_Antibody_binding`. See the binding limitation below. |
| `scheme` | Antibody numbering convention used to locate CDR regions, such as `imgt`, `kabat` or `chothia`. Required by the inspected validator for `CDR_Prediction` and the binding option. It is not an antigen epitope specification. |

`CDR_Prediction` identifies the three heavy-chain and three light-chain CDR
sequences using the selected numbering scheme. It does not generate a new
antibody or establish which antigen residues it binds.

An epitope is the antigen region recognized by an antibody. The inspected
binding dispatch passes `scheme` to a function parameter named `epitope`;
a separate `Epitope` input is not read by that dispatch. This is an unresolved
worker wiring discrepancy, not a reason to put antigen information in `scheme`
or promise a valid binding result.

The current connector declares `property_name` as a single string and requires
`scheme` for all property selections. That differs from the inspected worker's
list and conditional scheme requirement. Resolve this schema/worker mismatch
before submitting the affected QSAR request; this companion guide does not
change either implementation.

## Source review record

The observations above were checked against these files in the copied tool sources:

- Boltz2: `main.py` (`clean_sequences` and request preparation), `input_validation.py`.
- PPIFlow: `input_validation.py`, `README.md`, `sample_antibody_nanobody.py`.
- stabddg: `input_validation.py`, `generate_mutations.py`.
- ab_qsar: `input_validation.py`, `main.py`, `Antigen_binding/ab_aa_machine/Antigen_Antibody_binding.py`.

These external worker files are not bundled with Agent-Scientist. Verify the
deployed image and actual result artifacts when investigating a live run.
