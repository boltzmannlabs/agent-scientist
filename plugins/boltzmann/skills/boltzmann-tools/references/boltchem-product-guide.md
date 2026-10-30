# BoltChem product descriptions and interpretation

Source: product descriptions and Binding Affinity Energy documentation supplied
by the project owner on 2026-10-15. This guide standardizes that supplied content;
it is not evidence of a successful API call or a replacement for request schemas.
Binding Affinity Energy's Node API route and payload fields were subsequently
supplied by the project owner on 2026-10-22.
Feature paths below are product navigation routes, not API endpoints.

## Create Dataset

Feature path: `/small-molecule/experiments/create-dataset`

Create a project-linked dataset of molecular structures and associated bioactivity
or assay measurements. Configure a dataset name, target gene, assay type and
measurement endpoint, such as IC50, then organize SMILES alongside their activity
values. Saved datasets are available in the dataset library and provide the
required training data for the platform's Custom Property Model workflow,
supporting regression or classification of molecular properties.

Existing connector job: `dataset_creation`. The current product UI labels the
required `scrap_id` value as **Gene/Protein Name** and sends that entered string
unchanged under the historical wire key. The other required fields are
`data_type` (`IC50`, `EC50`, or `Ki`) and `assay_type` (`Cell free`, `Cell based`,
or `Both`). Do not reinterpret `scrap_id` as a dataset, project, or upload ID, and
do not invent dataset-upload or project-ID fields.
Do not mix incompatible units, endpoints or assay conditions without an explicit,
reviewed data-preparation step.

## IC50

Feature path: `/small-molecule/experiments/ic50`

Predict inhibitory potency for compound–protein pairs from direct SMILES and
protein-sequence input or a CSV of paired inputs. Use individual predictions or
batch screening to prioritize compounds. The product documentation describes
predicted activity labels, pIC50 and IC50 in nanomolar units for each pair.
Higher pIC50 and lower IC50 indicate greater predicted inhibitory potency under
comparable conditions; they do not by themselves establish binding affinity or
experimental activity.

Existing connector job: `global_ic50`. Inspect the returned artifact before
claiming an activity label or any other output column is present. Retained
historical records identify `smiles`, `sequence`, `pIC50` and `IC50_nM`; the newly
supplied product description does not specify the activity-label column name.
Do not invent it. Preserve the job's current CSV contract; do not borrow the
Binding Affinity Energy header names below for IC50.

## Binding Affinity Energy

Feature path: `/small-molecule/experiments/binding-affinity-energy`

Predict a NESSO affinity score for compound–protein pairs from direct SMILES and
protein-sequence input or an uploaded CSV. Use the score to rank candidates for
the same target under a comparable prediction setup. According to the supplied
product documentation, lower scores indicate stronger predicted binding. Do not
assign physical energy units, convert the score to a dissociation constant, or
describe it as experimentally measured affinity without an explicit model/output
specification.

The connector job name is `global_binding_affinity`, routed through the existing
authorized `boltzmann_submit` operation. Its canonical request schema is in
`tool-contracts.v1.json`; do not map it to `global_ic50` or protein–protein
`Prodigy`. This is an owner-supplied contract, not a live-verified service result.

### Purpose and input workflow

Use this feature to evaluate a compound–protein pair or screen a CSV of pairs.
In the product UI, navigate to **Small Molecule Design → QSPR Modelling →
Binding Affinity Energy**, choose the project and enter an experiment name.

- **Upload:** supply a CSV containing `SMILES` and `SEQUENCE`, as specified in
  the supplied product documentation, with one intended compound–protein pair
  per row. Extra-column rules and accepted header aliases are not established.
- **Draw Molecule / direct input:** provide the compound's SMILES and the target
  protein's amino-acid sequence when a CSV is not supplied.
- For the connector, review one mode: direct `smiles` plus `sequence`, or
  `input_csv`. Upload CSV files with `boltzmann_upload` using this exact job name
  and `input_field="input_csv"`; use the returned storage path, not a local path
  or a placeholder. Omit fields for the unused mode; precedence if both modes
  are supplied is not established.
- Submit through `boltzmann_submit` with `job_name="global_binding_affinity"`,
  the reviewed `experiment_name` and those fields in `experiment_data`. Never put
  credentials or runtime user/experiment IDs in that payload. Keep the returned
  job ID for subsequent status/download operations; do not automatically retry
  an ambiguous submission.

Do not silently generate all combinations of compounds and sequences. Preserve
the pairs supplied by the user. The connector checks CSV headers, row shape and
nonempty paired values, but does not establish scientific validity or backend
acceptance. Review partial-validation warnings before execution. No numeric input
limits, extra-column behavior, or diagnostic collection mapping are established
by the supplied handoff; do not invent them.

### Documented output table

Each row represents a submitted compound–protein pair. The following columns
come from the supplied documentation; confirm which are actually returned.

| Column | Meaning and interpretation |
|---|---|
| `smiles` | Input compound SMILES. |
| `sequence` | Input target-protein amino-acid sequence. |
| `binding_affinity` | Predicted NESSO affinity score; lower is stronger according to the product documentation. Units are not supplied. |
| `QED` | Quantitative Estimate of Drug-likeness, conventionally 0–1. Higher indicates a more favorable profile within this descriptor, not proven safety or efficacy. |
| `SA` | Synthetic Accessibility score. The supplied documentation describes a 1–10 scale, with lower values indicating easier estimated synthesis; it is not a verified synthetic route. |
| `TPSA` | Topological polar surface area, commonly reported in Å². Interpret with other properties; a single cutoff does not establish oral bioavailability. |
| `NUM_HDONORS` | Hydrogen-bond donor count. A physicochemical descriptor, not a direct permeability measurement. |
| `NUM_HACCEPTORS` | Hydrogen-bond acceptor count. A physicochemical descriptor, not a direct permeability measurement. |
| `Molecular Weight` | Molecular mass, documented in Da. Smaller is not universally better. |
| `LogP` | Lipophilicity descriptor. Interpret in context; lower is not always better, and LogP alone does not establish absorption. |

### Reporting checks and limitations

- Verify returned row counts and compound–protein pairing against the submitted
  inputs. Report rejected rows, missing values and partial outputs explicitly.
- Distinguish NESSO scores, docking scores, inhibitory potency and free-energy
  estimates; their scales are not interchangeable.
- Keep reported units and column names as returned. Do not invent energy units
  for `binding_affinity` or populate absent descriptor columns.
- Present predictions as computational estimates. Experimental confirmation,
  applicability-domain assessment and uncertainty remain separate questions.
- Drug-likeness guidelines are screening heuristics. Do not turn descriptor
  thresholds into submission limits or claims of oral bioavailability.

## Molecular Docking

Feature path: `/small-molecule/experiments/molecular-docking`

Explore predicted ligand–protein binding poses using AutoDock Vina or DiffDock.
Vina supports rigid-receptor docking, flexible docking with user-specified
receptor residues, and score-only evaluation of supplied poses. DiffDock supports
blind pose prediction without a predefined binding site. The product workflow
describes automated ligand/protein preparation and outputs including scores,
3D poses, interaction details and 2D interaction maps. Availability depends on
the selected mode and returned artifacts; docking predictions are not measured
binding affinities.

Existing connector jobs are distinct:

- `Vina_basic_docking`: basic Vina docking with a defined search region.
- `Vina_Flexible_Docking`: Vina docking with explicitly selected flexible residues.
  The Node submission API requires an uploaded ligand CSV path in `smiles`;
  a direct SMILES string is rejected. Exact CSV headers for this mode remain
  unconfirmed; do not assume basic docking's column requirements apply.
- `Vina_Score_only_docking`: evaluate supplied poses without claiming a new docking search.
- `Diffdock`: blind docking/pose prediction; do not reinterpret confidence as a
  Vina energy score.

Product-level automated preparation does not remove the connector's documented
input requirements. Preserve each mode's exact schema, including different
ligand input forms and string-flag casing. Retain historical worker-failure
warnings and approval requirements; this copy update does not verify recovery.
Only claim preparation steps or result artifacts supported by the actual run.

## FEP

Feature path: `/small-molecule/experiments/fep`

Estimate relative binding free-energy differences (ΔΔG) between congeneric
ligands for the same protein target. The described workflow combines alchemical
transformations with molecular-dynamics sampling of bound and solvated states
within a thermodynamic cycle. Use the estimates to compare analogues, interpret
structure–activity relationships and inform compound prioritization.

Results depend on system preparation, transformation choices and sampling
convergence. Report uncertainty and the service's stated units, reference ligand
and sign convention; do not infer these from the term ΔΔG alone or promise an
experimental potency improvement.

No executable connector job name, request schema or output schema for this FEP
feature is established in the current catalog. Do not substitute an unrelated
molecular-dynamics or energy-calculation job or infer an endpoint from its UI path.
