# Application-aware guide RNA designer

Portable SCI leaf-specialist source package, following the manifest/instructions/skills/references/tests contribution structure. It routes thirteen CRISPR application classes and encodes scientific prerequisite, permission, endpoint-compatibility and completed-only benchmark policies. Host permissions are not enforced by a prompt or these helper scripts. It does not bundle scientific models or guarantee design quality.

Package revision 1.3.0. This revision adds benchmark-informed model retention, explicit research-only alternatives, a complete third packaged skill, setup planning and CBE/RFcombined runtime profiles. It does not claim a universally improved predictive model or bundle scientific weights.

## Contents

- manifest.yaml: exact tool/skill declarations, optional native Python/R executable bindings and execution limits.
- dependencies.json: machine-readable core/native dependency catalog and external scientific asset requirements.
- DEPENDENCIES.md: approved setup instructions, limitations and metadata verification commands.
- requirements.txt: standard-library-only core; no third-party core pip requirements.
- dependencies/: separate version-pinned Python profiles, conda environment recipes and R package inventory.
- instructions.md: parent handoff, safety/provider discipline, scientific execution and reporting.
- skills/application-aware-grna-workflow/: complete original procedural skill.
- references/: modality map, evidence boundaries, parent handoff and run-record JSON schema.
- scripts/request_contract.py: inert metadata preflight, not scientific inference.
- scripts/harness_audit.py: offline v2 record consistency, opt-in artifact checks, optional schema/raster QA.
- scripts/validate_package.py: current-version local fixtures/schema/dependency validation; no live-agent installation.
- skills/reproducible-scientific-harness/: execution and comparison evidence discipline transferred from the chat harness, without mixing CRISPR and siRNA backends.
- tests/: synthetic metadata fixtures and honest local/integrated test evidence.

## Install and use

In a SCI session supporting portable specialist packages:

    /subagent package install "<package-dir>"

Choose the current owning profile and review tools, execution permissions, optional interpreter and sources. This is a local installation command, not a shell command. Then start a fresh conversation:

    /new
    /subagent run application-aware-grna-designer AUDIT the approved artifact manifest. Parent will supply read permissions, output root, native environments and exact scope.

A live specialist definition is created only by reviewed installation. Saving this package does NOT install/enable it or modify the current session. This package deliberately has automatic=false. No credential, runtime state or scientific tool installation is copied. Recipient model/provider and any connectors need their own configuration and authorization. The manifest includes no external scientific connector; if provider policy requires one, the specialist must hand back to the parent rather than bypass it.

## Dependency setup

Read [DEPENDENCIES.md](DEPENDENCIES.md) and [dependencies.json](dependencies.json) before selecting native tools. SCI uses the optional program declarations in manifest.yaml to review installed executable bindings; it does not automatically run the pip/conda recipes. Install only an approved profile into a separate new environment and verify it using scripts/check_dependencies.py. Observed pins are not a clean-install or model-readiness guarantee.

## Scientific setup

Parent-approved native CRISPR workflows may require separate Python/R versions, original published software/weights, genome/transcript/chromatin references, frozen task contracts and measured-label evaluation data. A generic Python executable supports only the inert package fixtures. Successful package checks or imports do not establish model readiness. The recipient must supply those assets explicitly. No implicit installs, heuristic replacement scores or guessed biological inputs.

The specialist covers routing across knockout, therapeutic research, variant correction, base/prime editing, CRISPRi/a, epigenome, Cas13, diagnostics, pooled libraries, plant and microbial tasks. Some routes are disabled/review-only or need unimplemented native adapters. No new guide is created by the packaged tests. Pathogen design is review-only and clinical advice/safety claims are excluded.

## Tests and validation scope

Run from the package directory using an approved Python executable:

    python3 -B tests/test_contract.py
    python3 -B scripts/request_contract.py tests/synthetic_request.json

The second command runs the supplied synthetic audit-metadata request; it makes no source reads or scientific predictions. Fixture tests check request gating only, not a model, efficacy, ranking, native tool readiness, LLM adherence or biomedical safety. tests/validation.json distinguishes local checks from pending integrated/runtime testing. No scientific results are invented to make a fixture pass.

For the added harness QA, use the approved optional harness interpreter:

    "$APPROVED_HARNESS_PYTHON" -B tests/test_dependencies.py
    "$APPROVED_HARNESS_PYTHON" -B tests/test_harness.py
    "$APPROVED_HARNESS_PYTHON" -B scripts/harness_audit.py tests/synthetic_harness_record.json --validate-schema
    "$APPROVED_HARNESS_PYTHON" -B scripts/validate_package.py --sci-source "$APPROVED_SCI_SOURCE" --sci-python "$APPROVED_SCI_PYTHON"

The final command also uses the separate installed SCI runtime for strict package-schema checks. It saves current-version validation evidence, complete check logs and a verified relative-path checksum inventory under tests/. It does not install the specialist, register tools, call an LLM or run a scientific model. Without an approved SCI source, local QA can run but strict SCI validation remains explicitly NOT_RUN.

Historical version 1.2.0 passed the 8 original metadata request fixtures, 35 synthetic/software harness tests, actual preflight/audit CLIs, core/harness metadata probes and installed SCI schema checks. Six environment recipes parsed; no clean environment reconstruction or model inference was performed. Earlier validation remains archived under tests/history/validation-v1.1.0.json and is not reasserted as current-version behavioral evidence. See CHANGELOG.md and references/harness-integration.md for migration and evidence boundaries.

Installation and runtime tests through an actual configured model still need separate execution. LLM inference can incur provider cost; native reference downloads can be large; platform jobs need their own authorization/cost approval. The package itself performs no external operation when merely validated.

## Permissions and portability

Only declared built-in tools are requested. Terminal/execute_code are powerful host capabilities, not a sandbox; the owning session must enforce source/egress/write boundaries. All original sources stay read-only, and all run/cache/environment writes require an approved destination. No permission from another profile or directory is inherited. Leaf specialists cannot ask clarify or manage credentials/configuration; missing inputs go to the parent. Contribution review and any redistribution of added datasets remain separate responsibilities.

New authored package material is MIT. External papers/software retain their own terms; citation pointers do not grant redistribution or execution rights.

## Version1.3 benchmark-informed behavior

Read APPLICATIONS.md for applications/readiness, TOOLS_AND_SERVICES.md for exact tool/skill/MCP/plugin requirements and costs, and DEPENDENCIES.md for runtime profiles. The completed historical benchmarks favor retaining native PRIDICT2/DeepPrime ensembles and BEHive/RFcombined references. RS3 full-pool refit is opt-in research, not an automatic upgrade. Native CBE is a separate research endpoint, not a proven BEHive replacement.

The requested starter layout is present: manifest.yaml, instructions.md, README.md, complete skills/ folders, tests/sample.csv, tests/expected.json and tests/validation.json. Sixteen CSV metadata cases exercise model/context/label/opt-in policies; they contain no guide sequences or invented scientific outcomes. Existing eight request fixtures and historical validation evidence are retained.

Metadata-only examples from this package directory:

    "$APPROVED_QA_PYTHON" -B scripts/model_policy.py tests/policy_request.json
    "$APPROVED_QA_PYTHON" -B tests/test_model_policy.py
    "$APPROVED_QA_PYTHON" -B scripts/setup_plan.py --profile cbe --write-root "$APPROVED_WRITE_ROOT" --prefix "$APPROVED_NEW_CBE_PREFIX"
    "$APPROVED_QA_PYTHON" -B scripts/check_dependencies.py --profile cbe --python "$APPROVED_CBE_PYTHON"
    "$APPROVED_QA_PYTHON" -B scripts/check_dependencies.py --profile rfcombined --rscript "$APPROVED_RF_RSCRIPT"

The plan prints commands without running them. A metadata match is not a native readiness pass. Before scientific execution the parent must approve actual setup, supply original assets and inputs, verify native fixtures and enforce safety/provider/source-sharing boundaries. No additional MCP/plugin is needed for offline checks; selected remote scientific providers remain parent-owned handoffs.

Use tests/validation.json as the actual current-version evidence, not this prose or prior-version live behavior. Current package checks do not install/enable the agent, reconstruct every environment, run all scientific backends or establish improved experimental performance. Earlier package revision was backed up before this edit; tests/history/ retains earlier validation records.

Current-runtime QA option: when the approved existing SDK interpreter matches sdk_qa rather than the historical harness profile, run:

    "$APPROVED_SDK_PYTHON" -B scripts/validate_package.py --qa-profile sdk_qa --sci-source "$APPROVED_SCI_SOURCE" --sci-python "$APPROVED_SDK_PYTHON" --cbe-python "$APPROVED_CBE_PYTHON" --cbe-rnafold "$APPROVED_CBE_RNAFOLD" --rfcombined-rscript "$APPROVED_RF_RSCRIPT"

Only pass executable options for programs you have approved. This invokes read-only metadata/version probes, never native inference or installation. The source reader uses the installed SDK's existing YAML parser when PyYAML is absent. Exact current test counts and outcomes remain in tests/validation.json.
