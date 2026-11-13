# Agriculture Properties

Domain: **Small Molecule Design → QSPR Modelling**. Exact Node job name:
`global_agriculture_properties`. This owner-documented contract is **enabled** at the user's
explicit request on 2026-11-12. Direct submission is **verified as accepted/queued** from the user notebook; completion and returned outputs remain **unverified**.
The canonical request and file contracts are installed; the original handoff and activation
record are in `contract_sources/agriculture-properties/contract-draft.json` relative to the
plugin root. Existing Boltzmann authorization, profile permissions and validation still apply.

The owner supplied this contract on 2026-11-12. It predicts agricultural and environmental
endpoints from a single SMILES string or an uploaded CSV. For multiple molecules use CSV, not a SMILES array. Select one or more of
the 14 exact IDs below, or scalar `all`. The documented result is one uploaded
`predictions.csv`, one row per molecule, selected predictions and molecular descriptors.

## Backend and observed deployment

| Item | Value |
|---|---|
| Worker task | `agriculture_properties` |
| Diagnostic collection | `Agriculture_Properties` (owner supplied; no live record lookup yet) |
| GPU | Not required |
| RAM | 4 GB |
| CPU cores | Not supplied |
| Deployed worker endpoint | `/v5/tools/Agriculture_properties` |
| Worker-required runtime fields | `experiment_id`, `user_id`, **`tokenid`** |

The public [deployed OpenAPI](https://boltchemapis.boltzmann.co/openapi.json), inspected
2026-11-12, additionally requires `tokenid`, which was absent from the owner's runtime-field
list. All three fields belong to Node orchestration/authentication. Never invent identifiers,
copy a token into `experiment_data`, or call the worker directly to bypass the Node route.
SCI already generates a readable experiment name when omitted; report the returned name.

An authorized staged connector probe used two harmless molecules (`CCO`, `CC(=O)O`) and
`water_half_life` / `ready_biodegradability`, with no runtime fields in the scientific payload.
The returned message was **Internal server error**, with no job ID and an unknown outcome.
An earlier MCP client call lost its response after request dispatch; its server outcome is
also unknown. Both attempt records are retained. There were no further submissions after
the explicit server error in that probe. Those historical attempts remain unresolved.
Do not blindly retry either attempt.

The error does not establish whether Node routing, runtime-field injection, or another
service component failed in those attempts. A later notebook response rejected a SMILES
array with HTTP 400: `smiles must be a string type`. The corrected direct payload below
returned **HTTP 200**, **queued**, and docId `6af59f71042419d6c2a5ed85` (25 credits),
as recorded in the user notebook execution 6. This confirms acceptance without client-supplied
runtime identifiers, not completed computation or independent verification of their injection.
CSV mode and prediction outputs remain unverified. Poll the existing job rather than duplicating it.

## Backend repair and historical result-retrieval error

On 2026-11-13 the tool owner reported that the backend issue was fixed.
The tool remains enabled: accept new user-authorized requests through the normal
submit → status → download workflow. The earlier missing-output error is historical,
not a permanent execution restriction or a reason to refuse a new request.

A read-only check of existing job `6af5af253fb9b718021334e2` on 2026-11-13
returned an authorization denial: `You don't have permission to perform this action`.
This did not verify the backend repair, job completion or predictions. Use the
owning profile's authorized credential; do not switch credentials or providers
silently, bypass permissions, or resubmit an existing job.

Historical job `6af5a5e2e1fce9fa279f8f35` returned
`Output path not found in metadata` on 2026-11-12. If that error actually recurs,
report the current job ID and retrieval blocker, and stop that attempt. Do not
start recovery scripts, guess endpoints, or read credential files. A later
explicit status check can recover the same job after a service repair.

## Public inputs

Use exactly one nonempty molecule-input mode: `smiles` or uploaded `input_csv`.
For direct input, `smiles` must be a string and `input_csv` must be present as `""`.
For CSV input, supply the uploaded reference in `input_csv`; omit `smiles` or set it to `""`.
Arrays and null molecule inputs are not accepted by this connector contract. The scalar property
`all` is allowed; an array containing `all` is not. The one-or-more requirement is enforced
with `minItems: 1` for property arrays, clarifying the owner's otherwise empty-array-permitting
schema. No numeric batch or runtime limits were supplied.

```json
{
  "type": "object",
  "properties": {
    "smiles": {
      "type": "string",
      "x-input-kind": "value",
      "description": "One SMILES string, never an array. For direct input supply a nonempty string and input_csv as an empty string. For CSV input omit smiles or use an empty string."
    },
    "input_csv": {
      "type": "string",
      "x-input-kind": "file",
      "x-allow-empty": true,
      "description": "Required field. Send an empty string for direct SMILES input; for CSV mode send the uploaded storage reference. CSV requires uppercase SMILES; optional ID and extra columns are accepted."
    },
    "properties": {
      "type": [
        "string",
        "array"
      ],
      "x-input-kind": "value",
      "description": "One supported property ID, a nonempty list of supported IDs, or the scalar string all. Do not replace IDs with display names or use all inside an array.",
      "anyOf": [
        {
          "type": "string",
          "enum": [
            "fish_nic_cpann",
            "fathead_epa",
            "daphnia_epa",
            "earthworm_concert",
            "sludge_ec50",
            "water_half_life",
            "soil_half_life",
            "sediment_half_life",
            "algae_classification",
            "algae_ec50",
            "bcf_meylan",
            "ready_biodegradability",
            "bee_knn",
            "air_half_life_coral",
            "all"
          ]
        },
        {
          "type": "array",
          "minItems": 1,
          "items": {
            "type": "string",
            "enum": [
              "fish_nic_cpann",
              "fathead_epa",
              "daphnia_epa",
              "earthworm_concert",
              "sludge_ec50",
              "water_half_life",
              "soil_half_life",
              "sediment_half_life",
              "algae_classification",
              "algae_ec50",
              "bcf_meylan",
              "ready_biodegradability",
              "bee_knn",
              "air_half_life_coral"
            ]
          }
        }
      ]
    }
  },
  "required": [
    "properties",
    "input_csv"
  ],
  "oneOf": [
    {
      "required": [
        "smiles"
      ],
      "properties": {
        "smiles": {
          "type": "string",
          "minLength": 1
        },
        "input_csv": {
          "enum": [
            ""
          ]
        }
      }
    },
    {
      "required": [
        "input_csv"
      ],
      "properties": {
        "input_csv": {
          "type": "string",
          "minLength": 1
        },
        "smiles": {
          "enum": [
            ""
          ]
        }
      }
    }
  ],
  "additionalProperties": false
}
```

## Submission examples

The direct scientific payload matches the accepted notebook test. The CSV example is
owner-documented and not yet live-verified; its storage placeholder is not a usable file path.
For CSV mode, upload the user's file first and substitute its returned storage reference.
Do not submit `properties` alone: the molecule-input mode is also mandatory.

```json
[
  {
    "job_name": "global_agriculture_properties",
    "experiment_data": {
      "smiles": "CCO",
      "properties": [
        "water_half_life",
        "ready_biodegradability"
      ],
      "input_csv": ""
    }
  },
  {
    "job_name": "global_agriculture_properties",
    "experiment_data": {
      "input_csv": "<actual storage reference returned by upload>",
      "properties": "all",
      "smiles": ""
    }
  }
]
```

## File checks

```json
{
  "input_csv": {
    "formats": [
      "csv"
    ],
    "columns": [
      "SMILES"
    ],
    "values": {
      "SMILES": "smiles"
    },
    "extra_columns": true,
    "header_case_sensitive": true,
    "notes": "Uppercase SMILES required; uppercase ID optional. Additional columns are accepted but not used for prediction. ID generation/preservation, invalid-row behavior and output ordering have not been supplied."
  }
}
```

Uppercase `ID` is optional. Other columns may be supplied but are not used for prediction.
These file checks do not establish chemical/model applicability or scientific correctness.

## Result contract and interpretation

Expected columns:

```text
ID, SMILES, <selected property columns>, MolWt, QED, TPSA, HBD, HBA,
RotatableBonds, RingCount, AromaticRingCount, HeavyAtomCount, FractionCSP3, FormalCharge
```

Preserve raw values. Units, transformations, class definitions, failure sentinels, ID
generation/preservation, invalid-row behavior, output ordering and model versions were not
supplied. Do not infer physical thresholds, favorable score directions or environmental
safety from endpoint names or predictions. Inspect molecule identity coverage and counts;
do not assume IDs or row order survive unchanged.

To verify results, poll the accepted job using its retained docId, download predictions.csv, and
compare selected property columns and molecule identities. Test scalar/list selections and
`all` without treating HTTP acceptance as completed computation. Review any failed rows
honestly. The diagnostic collection is source-documented, not live-verified. Refresh status
for expired artifact links; never invent paths or reuse another user's references.
