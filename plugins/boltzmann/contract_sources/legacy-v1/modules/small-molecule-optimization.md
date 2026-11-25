<!-- canonical-contracts:start -->
> Request fields and catalog status: `../../../skills/boltzmann-tools/references/tool-contracts.v1.json`.
> File rules: `../../../skills/boltzmann-tools/references/file-input-contracts.v1.json`. Limits: `../../../skills/boltzmann-tools/references/input-limits.v1.json`.
> Missing detailed file rules mean partial validation, not a submission ban.
> Known invalid inputs and explicitly blocked tools still stop. Historical output
> verification is separate from request readiness; report uncertainty honestly.
<!-- canonical-contracts:end -->

# Molecule Optimization

Current requirement correction (2026-11-23): MCTS, Mars Plus, Graph GA and
Fragment-Based Optimization require at least one `global_models` entry.
Both global-model threshold bounds must be numeric; empty strings were rejected
by live service validation on 2026-11-23. `custom_models` remains optional.
Current executable definitions are in
`skills/boltzmann-tools/references/tool-contracts.v1.json` at the plugin root;
other legacy snapshots preserve historical evidence.

Domain: Small Molecule Design

This module was selected by the server. Use only the exact contracts below.

## 40. Lead Generation — Reinvent

| Field | Value |
|-------|-------|
| **job_name** | `Lead_Generation_Reinvent` |
| **watch_time** | ~120s |

**Inputs:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `n_mols` | int | yes | Number of molecules |
| `n_steps` | int | yes | Number of RL steps |
| `data_path` | string | yes | S3 path to CSV (upload first) |
| `name` | string | yes | Experiment name |
| `dataType` | string | yes | `"csv"` (required when finetune=false) |
| `reward` | string | no | Default: `"MWS"` |
| `model_path` | string | no | Pretrained model path |
| `finetune` | string | no | Default: `"false"` |
| `tar_seq` | string | no | Target sequence |
| `off_tar_seqs` | list[string] | no | Off-target sequences |
| `global_models` | list | yes | At least one model |
| `custom_models` | list | yes | At least one model (id must be valid MongoDB ObjectId) |

**Input CSV columns:** `SMILES`

---

## 41. Lead Generation — Augmented

| Field | Value |
|-------|-------|
| **job_name** | `Lead_Generation_Augmented` |
| **watch_time** | ~120s |

**Inputs:**

| Parameter | Type | Required | Notes |
|-----------|------|----------|-------|
| `method` | string | no | Default: `"smiles_aug_mem"` |
| `no_of_molecules` | int | yes | Number of molecules |
| `steps` | int | yes | Number of steps |
| `data_path` | string | yes | S3 path to CSV (upload first) |
| `name` | string | yes | Experiment name |
| `dataType` | string | yes | `"csv"` (required when finetune=false) |
| `global_models` | list | yes | At least one model |
| `custom_models` | list | yes | At least one model |

---

## Lead Optimization MCTS

Optimize a reference molecule with Monte Carlo tree search.

| Field | Value |
|---|---|
| **job_name** | `Lead_Optimization_Mcts` |
| **historical evidence status** | Documented from the supplied platform schema; output not live-verified |

**Inputs:**

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `n_mols` | integer | yes | Number of molecules to generate during lead optimization. |
| `hit_smile` | string | yes | Reference molecule SMILES used as the starting point. |
| `global_models` | list[object] | yes | At least one global property model is required. Selected property models in `{name, min_threshold, max_threshold}` form. Use only names from the list below. |
| `custom_models` | list[object] | no | Custom property models in `{id, min_threshold, max_threshold}` form. |

`experimentName` is required at the top level and is not part of
`experimentData`. Do not rename `hit_smile` to `smiles`.

```python
data = {
    "experimentData": {
        "n_mols": 50,
        "hit_smile": "CN(C)C(=O)C1CC1C(=O)NCc1nc(-c2cccc(Br)c2)no1",
        "global_models": [
            {
                "name": "CaCo2 permeability",
                "min_threshold": 0,
                "max_threshold": 1,
            }
        ],
    },
    "job_name": "Lead_Optimization_Mcts",
    "experimentName": "prime",
}
```

## Mars Plus

Generate and optimize molecules from a starting SMILES string.

| Field | Value |
|---|---|
| **job_name** | `Lead_Generation_Mars_Plus` |
| **historical evidence status** | Documented from the supplied platform schema; output not live-verified |

**Inputs:**

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `smiles` | string | yes | Starting molecule SMILES. |
| `n_mols` | integer | yes | Number of molecules to generate. |
| `n_steps` | integer | yes | Number of optimization steps. |
| `global_models` | list[object] | yes | At least one global property model is required. Selected property models in `{name, min_threshold, max_threshold}` form. Use only names from the list below. |
| `custom_models` | list[object] | no | Custom property models in `{id, min_threshold, max_threshold}` form. |

`experimentName` is required at the top level and is not part of
`experimentData`.

```python
data = {
    "experimentData": {
        "smiles": "CC(=O)Oc1ccccc1C(=O)O",
        "n_mols": 10,
        "n_steps": 1,
        "global_models": [
            {
                "name": "CaCo2 permeability",
                "min_threshold": 0,
                "max_threshold": 1,
            }
        ],
    },
    "job_name": "Lead_Generation_Mars_Plus",
    "experimentName": "prime",
}
```

## Graph GA

Generate and optimize molecules with the graph genetic algorithm workflow.

| Field | Value |
|---|---|
| **job_name** | `Lead_Generation_Graph_GA` |
| **historical evidence status** | Documented from the supplied platform schema; output not live-verified |

**Inputs:**

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `smiles` | string | yes | User-supplied starting molecule SMILES. Validate it; do not reuse screenshot text. |
| `n_mols` | integer | yes | Number of molecules to generate. |
| `n_steps` | integer | yes | Number of optimization steps. |
| `global_models` | list[object] | yes | At least one global property model is required. Selected property models in `{name, min_threshold, max_threshold}` form. Use only names from the shared list below. |
| `custom_models` | list[object] | no | Custom property models in `{id, min_threshold, max_threshold}` form. |

`experimentName` is required at the top level and is not part of
`experimentData`.

```python
data = {
    "experimentData": {
        "smiles": validated_starting_smiles,
        "n_mols": requested_molecule_count,
        "n_steps": requested_optimization_steps,
        "global_models": [
            {
                "name": selected_model_name,
                "min_threshold": selected_numeric_minimum,
                "max_threshold": selected_numeric_maximum,
            }
        ],
    },
    "job_name": "Lead_Generation_Graph_GA",
    "experimentName": confirmed_experiment_name,
}
```

## Fragment-Based Optimization

Optimize a reference molecule using fragments derived from an uploaded SMILES
library. This is distinct from the removed Fragment-Based Generation workflow.

| Field | Value |
|---|---|
| **job_name** | `Fragment_Based_Optimization` |
| **historical evidence status** | Documented from the supplied platform schema; output not live-verified |

**Inputs:**

| Parameter | Type | Required | Notes |
|---|---|---|---|
| `ref_mol` | string | yes | User-supplied reference molecule SMILES. Validate it; do not reuse screenshot text. |
| `library_path` | string | yes | Platform storage path returned after uploading a CSV containing a `SMILES` header. |
| `global_models` | list[object] | yes | At least one global property model is required. Selected property models in `{name, min_threshold, max_threshold}` form. Use only names from the shared list below. |
| `custom_models` | list[object] | no | Custom property models in `{id, min_threshold, max_threshold}` form. |

`experimentName` is required at the top level and is not part of
`experimentData`. Validate and upload the CSV before submission; never send a
local path directly.

```python
data = {
    "experimentData": {
        "ref_mol": validated_reference_smiles,
        "library_path": uploaded_csv_storage_path,
        "global_models": [
            {
                "name": selected_model_name,
                "min_threshold": selected_numeric_minimum,
                "max_threshold": selected_numeric_maximum,
            }
        ],
    },
    "job_name": "Fragment_Based_Optimization",
    "experimentName": confirmed_experiment_name,
}
```

### Shared global property model names

Lead Optimization MCTS, Mars Plus, Graph GA, and Fragment-Based Optimization
use the same threshold-object model list:

```text
CaCo2 permeability, Half Life, Solubility, VDss, GIA,
Biodegradability, Cyp2d9 inh, Cyp2d9 sub, PGP sub,
Endocrine disrupting, Eye corrosive, Genotoxicity, Clearance,
Hydration Free Energy, LD50, Lipophilicity, PPBR, rPPB, hPPB,
Nephrotox_v3, BBB, Bioavailability, HIA, PAMPA, PGP_inh,
Cyp1a2 inh, Cyp2c9 inh, Cyp2c9 sub, Cyp2c19 inh, Cyp2d6 inh,
Cyp2d6 sub, Cyp3a4 inh, Cyp3a4 sub, AMES, Carcinogenicity,
DILI, hERG, Skin reaction, ClinTox, NR-AR, NR-AR-LBD, NR-AhR,
NR-Aromatase, NR-ER, NR-ER-LBD, NR-PPAR-gamma, SR-ARE,
SR-ATAD5, SR-HSE, SR-MMP, SR-p53
```

Each selected model object contains `name`, `min_threshold`, and
`max_threshold`. Both bounds must be numeric. Historical empty-string examples
were rejected by live service validation on 2026-11-23. The numeric 0–1 bounds
above are synthetic smoke-test settings, not recommended scientific defaults.
Preserve user-supplied bounds; ask for missing bounds rather than inventing them.

Neither supplied schema establishes an output contract. Poll the submitted job
and report only output keys and artifacts actually returned by the platform.
