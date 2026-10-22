# Agent-Scientist developer reference-test bundle

This bundle supplies concrete input fixtures and prior local reference artifacts for the three gaps raised by the developer review: EnzyControl, Catalytic Geometry, and RFD3. It is for contract/integration testing by the tool team. The local reference outputs are not production golden outputs, and successful computation is not experimental evidence of enzyme activity.

## Quick handoff

1. Upload the inputs listed below to the test user's storage and replace each `REPLACE_WITH_UPLOADED_PATH/...` value in the matching `*_call.json`.
2. Submit through the Agent-Scientist connector using the exact tool `job_name` in each example. Do not use the local reference paths as live platform paths.
3. Save the returned job/document ID, poll to completion, download the result, and compare the result structure/schema and status with the local reference artifacts. Because inference is stochastic, do not expect byte-identical structures or exact per-candidate pass/fail outcomes.
4. No credentials, user tokens, or production identifiers are included in these examples.

## Cases

### EnzyControl

- `enzycontrol/1TCA.pdb`: CALB structure, chain A. Motif labels 105, 187, 224 correspond to Ser105/Asp187/His224.
- `enzycontrol/enzycontrol_call.json`: submit example using the p-nitrophenyl butyrate SMILES and fixed seed 123.
- `enzycontrol/local_reference_benchmark.json` and `enzycontrol/local_reference_results.zip`: successful 10-sample *local* run (seed 123). It used local file-based storage/status substitutes, not production storage or database.

The substrate is a benchmark pairing, not a ligand crystallographically present in 1TCA. The structure and motif are validated against the local tool input validator. Generated backbones do not establish catalytic activity.

### Catalytic Geometry

- `catalytic_geometry/rfd3_catalytic_geometry_inputs.zip`: the exact previously prepared working input ZIP. It contains the reaction-template JSON, role-binding JSON, and candidate-mapping CSV. Its SHA-256 is `daeafb3da455478e2c6b1bbd147d5185e6fa7668c3b8ae20aae76719e6093e3f`.
- `catalytic_geometry/rfd3_20_results.zip`: the matching 20-candidate RFD3 CIF archive, including its residue mapping.
- `catalytic_geometry/catalytic_geometry_call.json`: live-call envelope; upload the files and replace the two required template/binding paths and the structure/mapping paths.
- `catalytic_geometry/local_reference_manifest.json` and `catalytic_geometry/local_reference_results.zip`: prior local output, 20 candidates measured, 20 passed, 0 rejected, 0 invalid.

Important interpretation: this template is explicitly a **prepared-scaffold geometry-preservation engineering check** for mapped Ser139/acetate geometry. Its distance and angle ranges are user-defined, not experimentally established catalytic criteria. A passing result means only that the supplied structure passed those supplied geometric checks. The local run used the local runner/older `rules_path` interface; the included call example follows the current live FastAPI contract (`reaction_template` and `template_binding` uploaded JSON paths, plus optional `mapping_path`).

### RFD3

- `rfd3/RFD3_M0255_1mg5.pdb`: input structure with the selected A108/A139/A152/A156 motif and NAI/ACT ligands.
- `rfd3/rfd3_call.json`: sanitized call fixture. It uses the same motif, ligand, contig, fixed atoms, geometry checks, and sampler settings as the prior all-fields local test, with `n_recycle: 1`; runtime user/token/experiment fields are omitted. Upload the PDB and replace its storage path before use.
- `rfd3/local_reference_report.json` and `rfd3/local_reference_results.zip`: prior local reference run. It requested one sample; round 1 was rejected for one backbone break and round 2 produced one accepted design. The reported distance was about 3.729 Å and angle about 173.346°, inside the user-specified intervals. The report's impossible-geometry control was rejected as expected.

This is a local prior run, not a production golden result. If the current RFD3 API rejects any field in the fixture, send the exact HTTP validation response and deployed schema/version to the tool team rather than silently changing the scientific inputs.

## What this bundle does not cover

It does not resolve MolProbity's existing job (fetch that job instead of duplicating it), or DeepAllo's HTTP 403 account entitlement. It does not submit jobs, install schemas, or prove production deployment readiness. The team should report exact accepted payloads, job IDs, output artifact paths, and any schema/runtime mismatch.
