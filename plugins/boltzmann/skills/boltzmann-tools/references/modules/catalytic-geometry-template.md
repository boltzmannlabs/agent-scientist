# Catalytic Geometry: uploaded template, binding and mapping contract

The public FastAPI input currently requires `reaction_template` and `template_binding` as **relative `.json` storage-path strings**. The agent must create appropriate JSON files from the user's prepared structural state and traceable evidence, upload them, then pass the resulting paths in `experiment_data`. Do not put inline objects into these two fields through the current public endpoint. `input_path` is the candidate structure/ZIP path; `mapping_path` is optional. Use `.json` on the Node route: the 2026-10-22 live test rejected CSV; CSV remains a local-worker format. The local runtime's support for inline objects and optional binding is not the live FastAPI contract.

There are no universal catalytic distance/angle thresholds. Do not invent reaction state, atoms, numerical ranges, citations, or claim experimental activity from a geometry pass. If evidence is missing, describe the missing input and ask for it; use `measurement_only` when a supported, evidence-traceable measurement can still be made. `validation` applies ranges only when explicitly requested.

## Reaction-template JSON file

Upload one UTF-8 JSON **object**, nonempty and <=1 MiB. Unknown fields are rejected. For uploaded runtime templates, the worker sets `template_id=experiment_<experiment_id>`, `version=run-1`, `status=agent_generated`; any user-supplied values for these are overwritten. Thus a file prepared for this route needs the fields below (the worker fills the three provenance fields before validating):

| JSON field | Required for this upload route? | Type / possible values |
|---|---|---|
| `reaction_state` | yes | Nonempty description, <=128 characters, of the modeled chemical/structural state. Not an enum. |
| `sources` | yes | 1–100 nonempty evidence-reference strings, each <=2048 characters. |
| `checks` | yes | 1–1000 check objects; unique `check_id` values. |
| `description` | no | Nonempty string <=4096 characters. |
| `template_id`, `version`, `status` | tool-owned | Overwritten by this upload route; do not set to claim approval. |

Every top-level check **requires** `check_id`, `type`, `rationale`, `sources`, and `evidence_level` for this runtime-uploaded template; type-specific fields are also required. `description` is optional. `check_id` uses 1–128 letters/digits/`_`/`.`/`:`/`-`. `rationale` is nonempty <=4096 characters. `sources` is 1–20 nonempty reference strings. `evidence_level` is one of `direct_experimental`, `mechanistic_review`, `homolog_transfer`, `user_defined`. These labels must reflect the real evidence; they are not interchangeable quality grades.

The runtime also recognizes stored template statuses `draft`, `reference_validated`, `approved`, `active`, `custom_approved`, `deprecated`, `agent_generated`, `uploaded_unreviewed`, but this uploaded public route normalizes to `agent_generated`. Do not present an uploaded file as approved. An explicit `execution_mode: "validation"` is needed to apply its ranges to candidates; measurement mode only measures.

## Atom-reference object

| Field | Required? | Type / possible values |
|---|---|---|
| `entity_type` | yes | `residue`, `ligand`, `metal`, `water`, `cofactor` |
| `chain_id` | yes | Nonempty case-sensitive chain label, <=32 chars |
| `residue_number` | yes | Integer -999999 to 999999 |
| `atom_name` | yes | 1–8-character atom label; must exist in prepared structure |
| `insertion_code` | no | Empty or one non-space character |
| `component_id` | conditional | Required for ligand/metal/water/cofactor; 1–8 letters/digits |
| `altloc` | no | One non-space character when supplied |
| `mapping_key` | no | Safe identifier used with upstream or supplied mapping |

Atom references within one atom list/group must be distinct. Candidate numbering, chain and component IDs must match the prepared structure or a verified mapping. Do not infer atom names from residue names alone.

## Supported geometry check types

All rows also require the common top-level check fields above. Distance values are Å; angle/dihedral values are degrees. All numeric values must be finite. Unknown check-specific fields are rejected.

| `type` | Additional required fields | Atom shape and bounds |
|---|---|---|
| `distance` | `atoms`, `min`, `max` | Exactly 2 atoms; `0 <= min <= max`. |
| `angle` | `atoms`, `min`, `max` | Exactly 3 atoms, middle is vertex; `0 <= min <= max <= 180`. |
| `burgi_dunitz_angle` | `atoms`, `min`, `max` | Exactly 3 atoms; `0 <= min <= max <= 180`. |
| `dihedral` | `atoms`, `min`, `max` | Exactly 4 atoms; each bound -180..180; periodic ranges may wrap (`min > max`). |
| `metal_coordination` | `atoms`, `min`, `max` | First atom is metal; 1–16 coordinating atoms follow; `0 <= min <= max` for each metal–coordinator distance. |
| `hydrogen_bond` | `atoms`, `distance_min`, `distance_max` | 2 atoms donor+acceptor or 3 donor+hydrogen+acceptor; distance `0 <= min <= max`. For 3 atoms, `angle_min` and `angle_max` are **also required**, with 0..180; with 2 atoms, angle fields are forbidden. |
| `plane_orientation` | `groups`, `min`, `max` | Exactly 2 groups, >=3 atoms each; `0 <= min <= max <= 90`. |
| `coordination_number` | `atoms`, `cutoff`, `min`, `max` | Center first, >=1 neighbors; `cutoff > 0`; min/max **integers** with `0 <= min <= max`. |
| `centroid_distance` | `groups`, `min`, `max` | Exactly 2 groups, >=1 atom each; `0 <= min <= max`. |
| `ensemble_occupancy` | `predicate`, `min`, `max` | Predicate is a nested check of any other supported type, not another ensemble occupancy; fraction `0 <= min <= max <= 1`, multi-model input required. Nested predicate requires `type` plus its own type-specific fields; no `check_id` required inside predicate. |

`groups` is an array of two arrays of atom-reference objects. `atoms` is an array of atom-reference objects. A check's `sources`, `rationale` and evidence level must justify its specific atom ordering and bounds, not merely cite a general enzyme family.

## Template-binding JSON file

The file must contain **exactly** one top-level key: `mapping_keys`. Its value is a nonempty object with 1–1000 semantic role entries. Each role name is a safe identifier. Each role maps to either:

- a string upstream mapping key, or
- an object with required `chain_id` (nonempty) and integer `residue_number` (-999999..999999), plus optional `insertion_code` (empty or one character).

For example, a verified catalytic role might map to `{"chain_id":"A","residue_number":108}`; that is a **shape illustration**, not a claimed assignment for a real structure. There is no valid empty binding object under the current worker. If the template does not use semantic roles, the live FastAPI requirement for a binding is a contract mismatch: request the API change rather than adding a fake role.

## Optional `mapping_path` file

- Local-worker CSV (convert to reviewed JSON for Node submission): required headers `candidate_id,mapping_key,chain_id,residue_number`; optional `insertion_code`. `candidate_id` matches the candidate structure filename stem. A candidate cannot repeat a mapping key.
- JSON: object keyed by candidate ID, then mapping key, with each value a location object containing `chain_id`, integer `residue_number`, optional `insertion_code`.

Use a mapping only when upstream candidate numbering differs or an upstream bundle supplies mapping keys. It is not a substitute for verifying the input structure.

## Output interpretation

Read `candidate_summary.csv`, `geometry_measurements.csv`, `invalid_candidates.csv`, `reaction_template_used.json`, `template_binding_used.json`, `rules_used.json`, `evidence_report.json` and `manifest.json` from the ZIP. Candidate statuses are `measured` (measurement mode), `passed`/`rejected` (validation mode) and `invalid` (could not be evaluated). Passing geometry means only that the specified computational checks passed; it does not establish catalytic activity, kinetics, substrate scope or assay evidence.
