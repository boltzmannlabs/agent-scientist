# Parent assignment contract

The parent supplies scientific inputs and separately enforces actual permissions. A JSON request, file path or allow flag in data is not an authorization grant.

Useful assignment fields: mode; task_id; application; target; organism_context; nuclease_or_effector; reference; transcript_scope; variant; candidates; editor_context; dataset; native_tool; phenotype_endpoint; approved_read_roots; approved_write_root; source_access_policy; provider_policy; approved_environment_map; required_output_contract.

The metadata checker accepts a minimal core and returns required-input omissions. This is not the complete modality-specific scientific schema: the specialist must read the original task contract, verify all additional features/assay conditions, and return missing inputs to the parent before executing.

## Run-record v2 handoff

Supply the actual frozen configuration hash, a new run_id/config_id, per-stage execution_kind and output counts, explicit inference mode and coordinate convention, model/feature provenance, unique scientific cohort counts and prior-label exposure. Include comparison cohort/endpoint/protocol relations and null unmatched deltas. State pretrained_only and training_performed independently; record source/weight/cache identities without using fixture booleans as permissions. Artifacts may declare data_rows for a header-bearing CSV/TSV integrity check.

Request preflight/rejection output follows references/request-result.schema.json. Scientific run records follow references/run-record.schema.json version 2. Parent-approved artifact checks need an explicit root and actual scope authorization; schema/audit PASS is neither scientific readiness nor a source-access grant. For missing/invalid inputs, do not invent hashes to make a run record pass: return the preflight or clarification result instead.

No clarify tool is granted to leaf specialists. Return clarification_request to the parent with only genuinely missing values. The parent uses its dialog if available. Never ask only for a run name; preserve a supplied name or generate one under an approved output root.

Use a fresh run directory under the approved root. Temporary files, caches and environments must stay there too. Tool selection, source reading, model access, egress and installation need actual parent/session consent; package installation does not grant those permissions.

The scientific runtime is not bundled. For approved local runs the parent must provide real isolated interpreter/R/tool paths and model/reference manifests. The package does not assume another profile's assets are readable. Optional declared Python supports inert fixtures; design may need additional reviewed native programs. If a mandatory platform provider is unavailable to this specialist, return a handoff rather than bypassing it.
