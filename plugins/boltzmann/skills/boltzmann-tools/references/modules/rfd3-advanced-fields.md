# Enzyme RFD3: complete optional-field guide

The five core required fields are `input_path`, `motif_residues`, `ligand`, `min_length` and `max_length`. See [enzyme-generation.md](protein-enzyme-generation.md) for top-level request fields. `advanced_settings_enabled` is the **string** `"true"` to apply `advanced_settings`; omitted/`"false"` disables it. All fields below are **optional**. Omit fields not selected by the user. FastAPI accepts many JSON `null` values, but empty strings are **not** valid numbers at its boundary. Do not send `cfg_features` or `symmetry` as user overrides in this release.

## `advanced_settings` fields

| Field | Required? | Type and accepted nonempty values | Omitted behavior / cautions |
|---|---|---|---|
| `contig` | no | String of native contig segments, e.g. `40-45,A108,40-45,A139`; motif IDs/ranges must match input | No indexed composition override. Do not invent residue numbering. |
| `select_fixed_atoms` | no | Map from motif residue/component code to `ALL`, `TIP`, `BKBN`, or comma-separated atom names; alternatively literal string `"true"` or `"false"` | Defaults to all motif/ligand atoms fixed, or motif backbone if redesigning side chains. `"true"` fixes all; `"false"` uses defaults. |
| `select_unfixed_sequence` | no | Residue selection string/map; string `"true"` or `"false"` accepted | Preserve motif identities by default. |
| `select_buried` | no | Residue selection string or string-valued map | No burial condition. Boolean/flag input is not accepted. |
| `select_partially_buried` | no | Residue selection string or string-valued map | No partial-burial condition. |
| `select_exposed` | no | Residue selection string or string-valued map | No exposure condition. |
| `select_hbond_donor` | no | Atom-selection map with string keys/values | No donor conditioning. |
| `select_hbond_acceptor` | no | Atom-selection map with string keys/values | No acceptor conditioning. |
| `select_hotspots` | no | Residue selection string/map, e.g. `"A152"`; string `"true"` or `"false"` accepted | No hotspot condition; hotspot-origin strategy needs meaningful hotspots. |
| `redesign_motif_sidechains` | no | Literal string `"true"` or `"false"` | Defaults false. |
| `ori_token` | no | Exactly three finite numbers `[x,y,z]`; zeros valid | Native origin strategy/default if omitted. Do not combine with `infer_ori_strategy`. |
| `infer_ori_strategy` | no | `"com"` or `"hotspots"` | Native centering if omitted; `"hotspots"` requires suitable hotspot selection. |
| `plddt_enhanced` | no | Literal string `"true"` or `"false"` | Native default is enabled. |
| `is_non_loopy` | no | Literal string `"true"` or `"false"` | Native default unset; explicit `"false"` has meaning. |
| `partial_t` | no | Finite number >0 | Omitted means normal scaffolding; supplied means partial diffusion and preserves input protein length. Must leave >=2 noise levels with `num_timesteps`. |
| `allow_ligand_on_existing_chain` | no | Literal string `"true"` or `"false"` | Defaults false. |
| `geometry_constraints` | no | Array of `distance`/`angle` rule objects described below | No extra output geometry checks. |
| `diffusion_batch_size` | no | Integer 1–2 | Derived/default; when both batch controls supplied, product must equal `n_samples`. |
| `n_batches` | no | Positive integer | Derived/default; must divide `n_samples` when paired/derived. |
| `inference_sampler` | no | Object with fields below | Native sampler defaults. |

Empty `{}` selections mean no selection. Optional blanks may be normalized by Yup, but callers should omit them. The native model validates structural selections and incompatible combinations; schema validity is not a promise that a design will pass quality checks.

## `advanced_settings.inference_sampler` fields

Every sampler field is optional. Do not force all native defaults into a request unless explicitly selected. The live FastAPI model lists these 15 fields; local runtime/Yup enforce the narrower supported values and bounds shown here.

| Field | Required? | Accepted values when supplied | Native default / note |
|---|---|---|---|
| `num_timesteps` | no | Integer 2–500 | 200 |
| `n_recycle` | no | Integer **1–5** | Checkpoint default; `0` caused native `KeyError: 'X_L'` and is now rejected by tool/Yup. |
| `step_scale` | no | Finite number >0 | 1.5 |
| `noise_scale` | no | Finite number >0 | 1.003 |
| `p` | no | Finite number >0 | 7 |
| `kind` | no | `"default"` only | Symmetry sampler unavailable. |
| `use_classifier_free_guidance` | no | Literal string `"true"`/`"false"` | False. |
| `cfg_t_max` | no | Finite number >=0 | None. |
| `cfg_scale` | no | Finite number >=0 | 1.5. |
| `center_option` | no | `"all"`, `"motif"`, `"diffuse"` | `all`. |
| `s_trans` | no | Finite number >=0 | 1.0. |
| `allow_realignment` | no | Literal string `"true"`/`"false"` | False. |
| `gamma_0` | no | Finite number >=0 | 0.6. |
| `gamma_min` | no | Finite number >=0 | 1.0. |
| `s_jitter_origin` | no | Finite number >=0 | 0.0. |

## `geometry_constraints` rules

Each rule **requires** exactly `type`, `atoms`, `min`, `max`. `type` is `"distance"` or `"angle"`. A distance has **exactly 2** atom references; an angle has **exactly 3**, with the middle atom as vertex. Each atom reference requires `atom` plus **exactly one** of `residue` or `ligand`. `residue` must name a selected motif (for example `A108`); `ligand` must name a selected component (for example `NAI`). Atom names must occur in the input and are case-sensitive. Empty unused selectors can be normalized by the updated tool, but canonical agent-generated JSON should omit them. Repeated atom references within one rule are invalid.

`min` and `max` are finite, nonnegative numbers with `min <= max`. For an angle, `max <= 180` degrees. Distance is in Å. Broad ranges may be syntactically valid but scientifically meaningless; choose values from the user's specific structural/chemical evidence.

```json
{
  "type": "distance",
  "atoms": [
    {"residue": "A108", "atom": "ND2"},
    {"ligand": "NAI", "atom": "REPLACE_WITH_VERIFIED_ATOM"}
  ],
  "min": "REPLACE_WITH_EVIDENCE_BASED_MINIMUM",
  "max": "REPLACE_WITH_EVIDENCE_BASED_MAXIMUM"
}
```

The example is a **shape illustration only**, not a valid scientific check or submit-ready threshold. Replace atom and bounds using verified input structure and reaction evidence.

## Result interpretation

The updated worker retries only explicitly quality-rejected generated structures. If retries exhaust, it can still report a completed job and upload the ZIP. Passing candidates, if any, are under `designs/`; rejected, review-only structures are under `rejected/round_N/`, with reasons in `rejections.json` and summary counts/status in `manifest.json`. A completed archive with `quality_status: "rejected"` contains **no passing designs**. Native inference errors, malformed/unparseable structures, gross corruption, upload failures and input errors remain failures; they are not converted to quality rejections.
