<!-- canonical-contracts:start -->
> Request fields and catalog status: `../tool-contracts.v1.json`.
> File rules: `../file-input-contracts.v1.json`. Limits: `../input-limits.v1.json`.
> Missing detailed file rules mean partial validation, not a submission ban.
> Known invalid inputs and explicitly blocked tools still stop. Historical output
> verification is separate from request readiness; report uncertainty honestly.
<!-- canonical-contracts:end -->

# Virtual Screening

Domain: Small Molecule Design

This module was selected by the server. Use only the exact contracts below.

## 33. Butina Clustering
Cluster a SMILES library by whole-molecule or Murcko-scaffold fingerprints and
optionally configure sampling and dimensionality reduction.

| Field | Value |
|---|---|
| **job_name** | `Butina_Clustering` |
| **backend task** | `butina` |
| **validation status** | **Verified working** |
| **accepted input** | uploaded `.csv` with a `SMILES` column |
| **observed terminal status** | `Success` |

### Inputs

All six fields are compulsory.

| Parameter | Type | Required | Exact values and meaning |
|---|---|---|---|
| `Path` | platform path string | yes | Uploaded CSV containing `SMILES`. Capital `P` is required. |
| `model` | string enum | yes | `Butina` or `Murcko-Butina`. |
| `DimReduce` | string enum | yes | API schema values `PCA` or `TSNE`; the UI may display `tSNE`. Only `PCA` is live-proven in the current evidence. |
| `sampling_type` | string enum | yes | `Random` or `Min-Max`. It is still sent when `sampling` is `no`. |
| `cutoff` | number | yes | Clustering cutoff. `0.4` is end-to-end verified; `-1` is newly submission-accepted as an automatic/default sentinel, but its terminal semantics are not yet verified. |
| `sampling` | string enum | yes | Exact lowercase string `yes` or `no`, not a boolean. |

Maintainer correction: use exact API value `Min-Max`. This spelling correction
supersedes the earlier sampling-option notes; it is not a new live-test result.

```python
uploaded_library_path = file_upload(local_smiles_csv)

job_name = "Butina_Clustering"
experiment_name = "Butina clustering"
experiment_data = {
    "Path": uploaded_library_path,
    "model": "Butina",
    "DimReduce": "PCA",
    "sampling_type": "Random",
    "cutoff": 0.4,
    "sampling": "no",
}
```

For a diverse library, `0.4` can produce many singleton clusters; use a
different cutoff only when scientifically justified. Do not silently replace a
user-specified cutoff with the newly accepted `-1` sentinel.

### Output instructions

The verified terminal result exposes a list-shaped
`OutputData.outputFilePath`; download each link and identify `butina.csv`.
The live artifact contained 7,543 rows with exact columns:

```text
ID,ClusterID,SMILES
```

This live artifact supersedes the older product-sheet claim
`SMILES,Labels`. `ClusterID` values are zero-based integers and need not be
contiguous in input order. Preserve `ID` and `SMILES` for joining results back
to the source library. Report molecule count, distinct cluster count, singleton
count, and largest-cluster size from the actual CSV.

### Evidence

- The all-experiments schema confirms the six compulsory fields and their
  enum values.
- An earlier canary reached terminal `Success`; `butina.csv` downloaded and
  parsed as 7,543 rows with `ID,ClusterID,SMILES`.
- The newest payload using `sampling="yes"`, `sampling_type="Random"`, and
  `cutoff=-1` returned HTTP 200. Only submission is proven for that variant.

## 34. K-Means Clustering

| Field | Value |
|-------|-------|
| **job_name** | `K_Means_Clustering` |

**Inputs:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `Path` | string | yes | S3 path to CSV (upload first) — capital P |
| `Features` | string | yes | `"descriptors"` or `"fingerprints"` |
| `DimReduce` | string | yes | `"PCA"` or `"tSNE"` |
| `no_of_cluster` | int | yes | Number of clusters |

**Output CSV columns:** `ID, ClusterID, SMILES` (only 3 columns)

---

## 35. Similarity Screening

| Field | Value |
|-------|-------|
| **job_name** | `Similarity_Screening` |

**Inputs:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `ref_smile` | string | yes | Reference SMILES |
| `lib_mols_path` | string | yes | S3 path to CSV (upload first) |
| `screen_threshold` | number | yes | Similarity threshold; use roughly 0.6+ for close analogues or 0.3–0.5 for scaffold hopping |

**Input CSV columns:** `SMILES`

**Output key:** `sim_screen_data_path` (NOT `outputFilePath`)

**Output CSV columns:** `Tanimoto_Similarity, Ref_Smile, SMILES` plus descriptors
and any pass-through library columns. Descriptor columns may be duplicated as
identical `_x`/`_y` pairs; read either copy.

---

## 36. Pharmacophore Screening

The receptor workflow was live-verified but cost 200 credits in the observed
run. Confirm that cost with the user before submitting.

| Field | Value |
|-------|-------|
| **job_name** | `Pharmacophore_Screening` |

**Inputs:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `hypothesis_path` | string | yes | S3 path to hypothesis file (from phcore_gen) |
| `library` | string | yes | S3 path to CSV (upload first) |
| `min_features` | int | yes | Minimum features to match |

**Input CSV columns:** `SMILES, NAMES`

The verified result uses `OutputData.outputFilePath` as a list. Rank hits by
`RMSD` ascending; use the numeric feature `count` because the observed
`features_matched` strings were placeholders.

---

## 37. Substructure Screening

| Field | Value |
|-------|-------|
| **job_name** | `Substructure_Screening` |

**Inputs:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `library_path` | string | yes | S3 path to CSV (upload first) |
| `substructures_path` | string | yes | S3 path to CSV (upload first) |
| `method` | string | yes | `"graph_matcher"` or `"rdkit"` |
| `task` | string | yes | `"toxic"` or `"substructure"` |
| `screening_type` | string | yes | `"in"` or `"out"` |

**Output CSV columns:** `Tanimoto_Similarity, Ref_Smile, SMILES, LABELS, Message`

---

## 38. Novelty Check
Compare an uploaded SMILES library against a selected reference collection by
exact identity or molecular similarity.

| Field | Value |
|---|---|
| **job_name** | `Novelty` |
| **backend task** | `novelty` |
| **validation status** | **Verified working for ChEMBL identity; Enamine submission verified** |
| **accepted input** | uploaded `.csv` with a `SMILES` column |
| **observed terminal status** | `Success` for the verified ChEMBL run |

### Inputs

Send all four fields. Although the threshold affects similarity searches, the
frontend schema requires a numeric value for identity searches too.

| Parameter | Type | Required | Exact values and meaning |
|---|---|---|---|
| `path` | platform path string | yes | Uploaded CSV containing a case-sensitive `SMILES` column. |
| `library` | string enum | yes | Exact value `ChEMBL`, `SureChEMBL`, or `Enamine`. |
| `STRUCTURE_SEARCH` | string enum | yes | Exact API value `Identical` or `Similarity`. |
| `threshold` | number | yes | Similarity cutoff for `Similarity`; still send a numeric value for `Identical`, conventionally `0`. |

The UI label **Identity** maps to API value `Identical`. Never submit
`"STRUCTURE_SEARCH": "Identity"`. The screenshot confirms all three library
choices and both UI search choices; the all-experiments schema confirms their
payload values. An older BoltChem note lists only ChEMBL and SureChEMBL, but
the newer schema plus an HTTP-200 Enamine submission supersede that stale list.

```python
uploaded_library_path = file_upload(local_smiles_csv)

job_name = "Novelty"
experiment_name = "Novelty identity screen against Enamine"
experiment_data = {
    "path": uploaded_library_path,
    "library": "Enamine",
    "STRUCTURE_SEARCH": "Identical",
    "threshold": 0.35,
}
```

For `Similarity`, require a user-provided or scientifically justified threshold
between 0 and 1. Do not silently reuse `0.35` merely because it was accepted in
the Enamine identity submission; identity mode does not establish similarity
threshold behavior.

### Output instructions

The verified ChEMBL identity result uses the tool-specific envelope:

```python
result["OutputData"]["similarity_summary"]["path"]
result["OutputData"]["similarity_summary"]["download_link"]
```

Do not assume `outputFilePath`. The downloaded
`identical_output_data.csv` preserved all 40 input rows and contained:

```text
SMILES,ACTIVITY,details
```

`ACTIVITY` was an input-column pass-through, not a novelty score. Other input
columns may similarly pass through. `details` is a Python-literal list rather
than JSON; parse it safely with `ast.literal_eval`, never `eval`. Each observed
hit dictionary contained `chembl_id`, `SMILES`, and `Score`. Report hit count,
top reference identifier, and score per molecule. The verified run contained
no novel/no-hit molecule, so treat empty-`details` interpretation as requiring
sanity checking rather than claiming that branch is proven.

The Enamine identity payload is submission-verified only because result lookup
was unavailable during this update. Do not describe its terminal output as
verified until the document reaches a terminal state and its artifact is
inspected.

### Evidence

- The all-experiments schema confirms `ChEMBL`, `SureChEMBL`, and `Enamine`,
  and maps search payload values to `Identical` and `Similarity`.
- The supplied screenshot independently confirms the three screen choices and
  the UI labels `Identity` and `Similarity`.
- An earlier ChEMBL/`Identical` canary completed end to end; its 40-row artifact
  was downloaded and inspected.
- The newest Enamine/`Identical` payload returned HTTP 200. Current network
  restrictions prevented a fresh result fetch, so that new variant remains
  submission-verified rather than terminal-verified.

## 60. QSPR Screening
Screen an uploaded molecule library against selected property or ADMET filters.

| Field | Value |
|---|---|
| **job_name** | `QSPR_Screening` |
| **Mongo diagnostics collection** | `reward-based-screening` (verified sample record); pair with the returned experiment ID. |
| **backend task** | `screening` |
| **validation status** | **Verified working** |
| **accepted input** | uploaded `.csv` with a `SMILES` column |
| **observed terminal status** | `Success` |

### Inputs

| Parameter | Type | Required | Validation and meaning |
|---|---|---|---|
| `path` | platform path string | yes | Uploaded CSV containing a case-sensitive `SMILES` column. Use lowercase `path`. |
| `filters` | list of objects | yes for fixed-filter screening | Each item uses the exact keys `value` and `type`. Do not use `prop_name`, `label`, or a display label as the payload object. |
| `custom_models` | list of objects | no | May be omitted or sent as `[]`; both forms have produced HTTP 200. A selected custom model requires `id`, `min_threshold`, and `max_threshold` according to the validation schema, but that non-empty branch is not live-verified here. |

The latest accepted submission omitted `custom_models`, correcting an older
contract that called the field universally required. Include `custom_models:
[]` when composing a stable explicit payload, but do not reject a payload only
because the empty field is omitted.

The only exact fixed-filter objects currently proven from payload sources are:

```python
{"value": "BBB", "type": "Permeable"}
{"value": "BBB", "type": "Impermeable"}
{"value": "Bioavailability", "type": "Bioavailable"}
```

The UI exposes many more labels, including CYP, clearance, half-life,
lipophilicity, permeability, protein-binding, solubility, toxicity, Tox21,
biodegradability, endocrine, eye-corrosion, and genotoxicity endpoints. A label
alone does not prove its exact `value`/`type` pair. Preserve the pair emitted by
the UI or another validated source; never derive payload capitalization or
spelling from the visible label. Do not request mutually contradictory states
for the same property unless the user explicitly wants both result classes.

```python
uploaded_library_path = file_upload(local_smiles_csv)

job_name = "QSPR_Screening"
experiment_name = "QSPR screening - BBB and bioavailability"
experiment_data = {
    "path": uploaded_library_path,
    "filters": [
        {"value": "BBB", "type": "Permeable"},
        {"value": "Bioavailability", "type": "Bioavailable"},
    ],
    "custom_models": [],
}
```

Before uploading, parse the CSV, require a non-empty `SMILES` column, and
validate every non-empty SMILES value. Do not place raw CSV content or a local
filesystem path in `path`.

### Output instructions

The verified terminal result uses:

```python
result["OutputData"]["filtered_data"]["path"]
result["OutputData"]["filtered_data"]["download_link"]
```

The verified `filtered_data.csv` preserved 40 input rows and contained:

```text
SMILES,ACTIVITY,Mol_wt,LogP,numHacceptors,numHdonors,TPSA,QED,SA,LogS,
BBB,Bioavailability
```

Input columns can pass through, descriptors are appended, and each selected
filter adds a verdict column named for its `value`. In the verified sample all
40 molecules passed, so that run does not prove whether failing molecules are
dropped or retained. Report actual input/output row counts and verdict counts
from the artifact rather than assuming either behavior.

### Evidence

- The all-experiments schema confirms the CSV path, `{value, type}` filter
  objects, and `{id, min_threshold, max_threshold}` custom-model shape.
- An earlier end-to-end canary reached terminal `Success`; its artifact was
  downloaded and parsed as the 40-row CSV described above.
- The newest test payload used two `{value, type}` filters, omitted
  `custom_models`, and returned HTTP 200, proving that omission is accepted.
- API-style filter keys such as `prop_name` and `label` previously caused HTTP
  400; use the UI-style keys exactly.


---

## Verified BoltChem contract overlay (2026-09-08)

The following section is the current verified BoltChem contract for this module. It overrides conflicting legacy text above. Do not submit until its required fields, exact enums, file headers, and validation rules pass.

### Clustering and Screening Tools

# Butina clustering
Tool display name: Butina
Frontend route/screen:
Exact form fields: "Path","model","DimReduce","sampling_type","cutoff","sampling"
Required fields:"Path","model","DimReduce","sampling_type","cutoff","sampling"
fields details and options:
[Path:CSV file path of ligands for clustering.With column name as SMILES,
model:[Butina,Murcko-Butina] ,
DimReduce: [PCa, tSNE],
sampling_type:[Random,Min-Max],
cutoff:float,Similarity threshold for molecules within each cluster.(0 to 1)
sampling:[yes,no]
]
Optional fields:null
Allowed choices and exact spelling:
Sample input file:/path/to/approved-input-or-output
Required file format:csv
Required column names:SMILES
Sample output file:/path/to/approved-input-or-output
output file column names: ID,ClusterID,SMILES
Actual backend/network payload:
data = {
        "experimentData": {
            "Path": "CURRENT_USER_UPLOAD_PATH",
            "model": "Butina",
            "DimReduce": "PCA",
            "sampling_type": "Random",
            "cutoff": 0.4,
            "sampling": "yes"
        },
        "job_name": "Butina_Clustering",
        "experimentName": "Butina_Clustering_test"
    }
Exact backend job name, if visible:Butina_Clustering
Known validation or failure messages:

# Kmean clustering
Tool display name:Kmean clustering
Frontend route/screen:
Exact form fields:Path, Features, DimReduce, no_of_cluster
Required fields:Path, Features, DimReduce, no_of_cluster
field details and options:
Path:CSV file path of ligands for clustering.With column name as SMILES
Features:[descriptors,fingerprints],
DimReduce:[PCA,tSNE]
no_of_cluster:integer(Number of clusters to be created.)
Optional fields:null
Allowed choices and exact spelling:
Sample input file:/path/to/approved-input-or-output
Required file format:csv
Required column names:SMILES
Sample output file:/path/to/approved-input-or-output
output column names: ID,ClusterID,SMILES
Actual backend/network payload:
data = {
        "experimentData": {
            "Path": "CURRENT_USER_UPLOAD_PATH",
            "Features": "descriptors",
            "DimReduce": "PCA",
            "no_of_cluster": "4"
        },
        "job_name": "K_Means_Clustering",
        "experimentName": "K_Means_Clustering_test"
    }
Exact backend job name, if visible:K_Means_Clustering
Known validation or failure messages:

# Pharmacophore screening
Tool display name:Pharmacophore Screening
Frontend route/screen:
Exact form fields:hypothesis_path, library, min_features
Required fields:hypothesis_path, library, min_features
Optional fields:null
Allowed choices and exact spelling:
No of file inputs required:2(hypothesis_path, library)
Sample input file:CURRENT_USER_UPLOAD_PATH,
CURRENT_USER_UPLOAD_PATH
Required file format:hypothesis_path:posp, library:csv
Required column names:SMILES,QED,SA,TPSA,NUM_HDONORS,NUM_HACCEPTORS,Molecular Weight
Sample output file:CURRENT_USER_UPLOAD_PATH
Actual backend/network payload:data = {
        "experimentData": {
            "hypothesis_path": "CURRENT_USER_UPLOAD_PATH",
            "library": "CURRENT_USER_UPLOAD_PATH",
            "min_features": "2"
        },
        "job_name": "Pharmacophore_Screening",
        "experimentName": "Pharmacophore_Screening_test"
    }
output payload:Status: 200
{'status': 'Success', 'OutputData': {'outputFilePath': [{'path': 'CURRENT_USER_UPLOAD_PATH, 'download_link': ['https://example.invalid/current-job-artifact {'path': 'CURRENT_USER_UPLOAD_PATH, 'download_link': ['https://example.invalid/current-job-artifact 'billing': [{'job_name': 'task-ph-screening-v4-tntdn', 'tool_name': 'ph_screening', 'node': 'boltzmann2', 'duration_seconds': 124, 'total_tool_runtime': 121, 'tool_lifetime_seconds': 124, 'rounded_minutes': 3, 'rate_per_hour': 20, 'amount': 1}]}
Exact backend job name, if visible:Pharmacophore_Screening
Known validation or failure messages:

# Similarity Screening
Tool display name:Similarity Screening
Frontend route/screen:
Exact form fields:ref_smile,ref_mols_path,lib_mols_path,screen_threshold
Required fields:ref_smile,lib_mols_path,screen_threshold
fields and details:
Reference SMILES*string
(A single SMILES of the reference molecule to compute similarity against.)
Reference Molecules CSV Path*string
(CSV file containing multiple reference molecules with a SMILES header.)

Library Molecules CSV Path*string
(Path to the input CSV file containing molecules to compute similarity with respect to the reference SMILES.)

Screening Threshold*integer
(Threshold for screening molecules in the library based on similarity with the reference SMILES.(0 to 1))
Optional fields:ref_mols_path
Allowed choices and exact spelling:
Sample input file:CURRENT_USER_UPLOAD_PATH
Required file format:csv
Required column names:SMILES
Sample output file:CURRENT_USER_UPLOAD_PATH
Actual backend/network payload:data = {
        "experimentData": {
            "ref_smile": "CCOC1=CC=C(C=C1)C(=O)N2CCC(CC2)NC(=O)C3=CC=CC=C3",
            "lib_mols_path": "CURRENT_USER_UPLOAD_PATH",
            "screen_threshold": "0.05"
        },
        "job_name": "Similarity_Screening",
        "experimentName": "prime"
    }
output_schema:Status: 200
{'status': 'Success', 'OutputData': {'sim_screen_data_path': {'path': 'CURRENT_USER_UPLOAD_PATH, 'download_link': ['https://example.invalid/current-job-artifact 'billing': [{'job_name': 'task-sim-screen-dll28', 'tool_name': 'sim_screen', 'node': 'boltzmann2', 'duration_seconds': 39, 'total_tool_runtime': 37, 'tool_lifetime_seconds': 39, 'rounded_minutes': 1, 'rate_per_hour': 20, 'amount': 1}]}
Exact backend job name, if visible:Similarity_Screening
Known validation or failure messages:
The fields ref_mols_path, ref_smile are interelated, when the user have only one reference smile then we use the field ref_smile and if the user have multiple then we make a csv of those smiles with column name as "SMILES" and we use the field ref_mols_path for that

# Substructure Screening
Tool display name:Substructure Screening
Frontend route/screen:
Exact form fields:library_path,substructures_path,method,task,screening_type
Required fields:library_path,substructures_path,method,task,screening_type
Fields and options:
library_path:CSV file path of the molecules to screen with respect to the substructure.
substructures_path:Substructures to use for screening: either a CSV file or a list of SMILES.
method:[graph_matcher,rdkit],
task:[toxic,substructure],
screening_type:[in,out]
Optional fields:null
Allowed choices and exact spelling:
Sample input file:CURRENT_USER_UPLOAD_PATH
Required file format:csv
Required column names:action_type,activity_comment,activity_id,activity_properties,assay_chembl_id,assay_description,assay_type,assay_variant_accession,assay_variant_mutation,bao_endpoint,bao_format,bao_label,canonical_smiles,data_validity_comment,data_validity_description,document_chembl_id,document_journal,document_year,ligand_efficiency,molecule_chembl_id,molecule_pref_name,parent_molecule_chembl_id,pchembl_value,potential_duplicate,qudt_units,record_id,relation,src_id,standard_flag,standard_relation,standard_text_value,standard_type,standard_units,standard_upper_value,standard_value,target_chembl_id,target_organism,target_pref_name,target_tax_id,text_value,toid,type,units,uo_units,upper_value,value,SMILES,Molecular Weight,ACTIVITY

Sample output file:
Actual backend/network payload:
data = {
        "experimentData": {
            "library_path": "CURRENT_USER_UPLOAD_PATH",
            "substructures_path": "C1C=CC=C(N)C=1",
            "method": "rdkit",
            "task": "substructure",
            "screening_type": "out"
        },
        "job_name": "Substructure_Screening",
        "experimentName": "Substructure_Screening_test"
    }
backend schema:
Exact backend job name, if visible:Substructure_Screening
Known validation or failure messages:

# QSPR Screening
Tool display name:QSPR Screening
Frontend route/screen:
Exact form fields:path,filters,global_models,custom_models
Required fields:path,filters
Optional fields:global_models,custom_models
`global_models` uses the fixed property-model choices shared by BoltChem tools.
`custom_models` uses threshold objects such as:
`[{"id":"ss","min_threshold":"11","max_threshold":"11"}]`.
fields and options:
path:Path to the CSV file or library containing ligands with a 'SMILES' column for screening.
 "filters": [
                {
                    "value": "BBB",
                    "type": "Permeable"
                },
                {
                    "value": "Bioavailability",
                    "type": "Bioavailable"
                },
                {
                    "value": "BBB",
                    "type": "Impermeable"
                },
                {
                    "value": "HIA",
                    "type": "Absorbed"
                },
                {
                    "value": "HIA",
                    "type": "Not absorbed"
                },
                {
                    "value": "Bioavailability",
                    "type": "Non Bioavailable"
                },
                {
                    "value": "PGP_inh",
                    "type": "inhibitor"
                },
                {
                    "value": "PGP_inh",
                    "type": "non-Inhibitor"
                },
                {
                    "value": "Cyp2c9_inh",
                    "type": "inhibitor"
                },
                {
                    "value": "Cyp2c9_inh",
                    "type": "non-Inhibitor"
                },
                {
                    "value": "Cyp2c19_inh",
                    "type": "inhibitor"
                },
                {
                    "value": "Cyp2c19_inh",
                    "type": "non-Inhibitor"
                },
                {
                    "value": "Cyp1a2_inh",
                    "type": "inhibitor"
                },
                {
                    "value": "Cyp1a2_inh",
                    "type": "non-Inhibitor"
                },
                {
                    "value": "Cyp3a4_inh",
                    "type": "inhibitor"
                },
                {
                    "value": "Cyp3a4_inh",
                    "type": "non-Inhibitor"
                },
                {
                    "value": "Cyp3a4_sub",
                    "type": "substrate"
                },
                {
                    "value": "Cyp3a4_sub",
                    "type": "non-substrate"
                },
                {
                    "value": "Cyp2d6_inh",
                    "type": "non-Inhibitor"
                },
                {
                    "value": "Cyp2d6_inh",
                    "type": "inhibitor"
                },
                {
                    "value": "Cyp2c9_sub",
                    "type": "substrate"
                },
                {
                    "value": "Cyp2c9_sub",
                    "type": "non-substrate"
                },
                {
                    "value": "Cyp2d6_sub",
                    "type": "substrate"
                },
                {
                    "value": "Cyp2d6_sub",
                    "type": "non-substrate"
                },
                {
                    "value": "Hydration_Free_Energy",
                    "type": "None"
                },
                {
                    "value": "CaCo2_permeability",
                    "type": "High"
                },
                {
                    "value": "CaCo2_permeability",
                    "type": "Low"
                },
                {
                    "value": "Clearance",
                    "type": "High"
                },
                {
                    "value": "Clearance",
                    "type": "Low"
                },
                {
                    "value": "Half_Life",
                    "type": "Long"
                },
                {
                    "value": "Half_Life",
                    "type": "Short"
                },
                {
                    "value": "Lipophilicity",
                    "type": "High"
                },
                {
                    "value": "Lipophilicity",
                    "type": "Low"
                },
                {
                    "value": "PAMPA",
                    "type": "High"
                },
                {
                    "value": "PAMPA",
                    "type": "Low"
                },
                {
                    "value": "hPPB",
                    "type": "High"
                },
                {
                    "value": "hPPB",
                    "type": "Low"
                },
                {
                    "value": "PPBR",
                    "type": "High"
                },
                {
                    "value": "PPBR",
                    "type": "Low"
                },
                {
                    "value": "Solubility",
                    "type": "Soluble"
                },
                {
                    "value": "Solubility",
                    "type": "Insoluble"
                },
                {
                    "value": "VDss",
                    "type": "None"
                },
                {
                    "value": "AMES",
                    "type": "Toxic"
                },
                {
                    "value": "AMES",
                    "type": "Non toxic"
                },
                {
                    "value": "Carcinogenicity",
                    "type": "Carcinogenic"
                },
                {
                    "value": "Carcinogenicity",
                    "type": "Non Carcinogenic"
                },
                {
                    "value": "DILI",
                    "type": "Toxic"
                },
                {
                    "value": "DILI",
                    "type": "Non toxic"
                },
                {
                    "value": "hERG",
                    "type": "Toxic"
                },
                {
                    "value": "hERG",
                    "type": "Non toxic"
                },
                {
                    "value": "LD50",
                    "type": "None"
                },
                {
                    "value": "Skin_Reaction",
                    "type": "No skin reaction"
                },
                {
                    "value": "Skin_Reaction",
                    "type": "Skin reaction"
                },
                {
                    "value": "GIA",
                    "type": "High"
                },
                {
                    "value": "GIA",
                    "type": "Low"
                },
                {
                    "value": "Biodegradability",
                    "type": "Biodegradable"
                },
                {
                    "value": "Biodegradability",
                    "type": "Non biodegradable"
                },
                {
                    "value": "Cyp2d9_inh",
                    "type": "inhibitor"
                },
                {
                    "value": "Cyp2d9_inh",
                    "type": "non-Inhibitor"
                },
                {
                    "value": "Cyp2d9_sub",
                    "type": "substrate"
                },
                {
                    "value": "Cyp2d9_sub",
                    "type": "non-substrate"
                },
                {
                    "value": "PGP_sub",
                    "type": "substrate"
                },
                {
                    "value": "PGP_sub",
                    "type": "non-substrate"
                },
                {
                    "value": "Endocrine_disrupting",
                    "type": "Endocrine disrupting"
                },
                {
                    "value": "Endocrine_disrupting",
                    "type": "Non endocrine disrupting"
                },
                {
                    "value": "Eye_corrosive",
                    "type": "Corrosive"
                },
                {
                    "value": "Eye_corrosive",
                    "type": "Non corrosive"
                },
                {
                    "value": "Genotoxicity",
                    "type": "Genotoxic"
                },
                {
                    "value": "Genotoxicity",
                    "type": "Non genotoxic"
                },
                {
                    "value": "ClinTox",
                    "type": "Toxic"
                },
                {
                    "value": "ClinTox",
                    "type": "Non toxic"
                },
                {
                    "value": "rPPB",
                    "type": "High"
                },
                {
                    "value": "rPPB",
                    "type": "Low"
                },
                {
                    "value": "Nephrotox_v3",
                    "type": "None"
                },
                {
                    "value": "NR-AR",
                    "type": "Active"
                },
                {
                    "value": "NR-AR",
                    "type": "Inactive"
                },
                {
                    "value": "NR-AR-LBD",
                    "type": "Active"
                },
                {
                    "value": "NR-AR-LBD",
                    "type": "Inactive"
                },
                {
                    "value": "NR-AhR",
                    "type": "Active"
                },
                {
                    "value": "NR-AhR",
                    "type": "Inactive"
                },
                {
                    "value": "NR-Aromatase",
                    "type": "Active"
                },
                {
                    "value": "NR-Aromatase",
                    "type": "Inactive"
                },
                {
                    "value": "NR-ER",
                    "type": "Active"
                },
                {
                    "value": "NR-ER",
                    "type": "Inactive"
                },
                {
                    "value": "NR-ER-LBD",
                    "type": "Active"
                },
                {
                    "value": "NR-ER-LBD",
                    "type": "Inactive"
                },
                {
                    "value": "NR-PPAR-gamma",
                    "type": "Active"
                },
                {
                    "value": "SR-ARE",
                    "type": "Active"
                },
                {
                    "value": "NR-PPAR-gamma",
                    "type": "Inactive"
                },
                {
                    "value": "SR-ARE",
                    "type": "Inactive"
                },
                {
                    "value": "SR-ATAD5",
                    "type": "Active"
                },
                {
                    "value": "SR-ATAD5",
                    "type": "Inactive"
                },
                {
                    "value": "SR-HSE",
                    "type": "Active"
                },
                {
                    "value": "SR-HSE",
                    "type": "Inactive"
                },
                {
                    "value": "SR-MMP",
                    "type": "Active"
                },
                {
                    "value": "SR-MMP",
                    "type": "Inactive"
                },
                {
                    "value": "SR-p53",
                    "type": "Active"
                },
                {
                    "value": "SR-p53",
                    "type": "Inactive"
                }
            ]
Optional fields:custom_models
  "custom_models": [
                {
                    "id": "",
                    "min_threshold": "",
                    "max_threshold": ""
                }]
Allowed choices and exact spelling:
Sample input file:CURRENT_USER_UPLOAD_PATH
Required file format:csv
Required column names:SMILES
Sample output file:
Actual backend/network payload:
data = {
        "experimentData": {
            "path": "CURRENT_USER_UPLOAD_PATH",


            "filters": [
                {
                    "value": "BBB",
                    "type": "Permeable"
                },
                {
                    "value": "Bioavailability",
                    "type": "Bioavailable"
                }
            ]
        },
        "job_name": "QSPR_Screening",
        "experimentName": "Sample experiment - QSPR Screening"
    }
Exact backend job name, if visible:QSPR_Screening
Known validation or failure messages:
