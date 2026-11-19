# Application-aware siRNA designer

Portable SCI leaf-specialist package, version 1.0.0. It updates the design/evaluation/benchmark workflow around the retained siRNA harness, not the underlying model weights. The older sirna-design-specialist folder is preserved separately. This package uses the current installed SCI portable schema, disabled automatic matching and complete custom skill folders.

## Layout

manifest.yaml declares exact tools, three packaged skills, optional reviewed programs and Boltzmann integration. instructions.md is the leaf contract. dependencies.json, DEPENDENCIES.md and dependencies contain setup profiles and private-binding templates. scripts contains working setup/probe/request/asset/record/validation utilities. references contains newly authored policies, source pointers, eleven task routes and historical evidence summaries, not original datasets or restricted code. tests contains inert metadata inputs, expected results, software tests and actual local evidence.

The supplied manifest.yaml is JSON-compatible YAML 1.2, so the core validator can read it without a YAML dependency. Keep that subset when editing, or deliberately update the core loader. This is accepted by the installed SCI manifest validator.

## Install in SCI

From a SCI conversation with portable-specialist support:

    /subagent package install "<this package directory>"

Choose the owning profile and review powerful execution tools, optional executables, the Boltzmann integration and references. This is a SCI slash command, not a shell subcommand. Then start a fresh conversation with /new. Saving this package does not install/enable it in a live profile or grant provider/model permissions. Automatic matching is false. Model/provider setup remains recipient-owned.

Examples (parent supplies actual approved roots and inputs):

    /subagent run application-aware-sirna-designer SETUP the approved local route; report a dependency/asset plan before any downloads or scientific work.
    /subagent run application-aware-sirna-designer DESIGN under the supplied human noninfectious-research brief, exact transcript and approved harness bindings; stop for missing prerequisites.
    /subagent run application-aware-sirna-designer EVALUATE only the requested properties on the approved supplied candidates.
    /subagent run application-aware-sirna-designer BENCHMARK the frozen approved measured cohort; distinguish previous label exposure and unmatched published protocols.

## Setup before science

Read DEPENDENCIES.md. The worker selects a provider and minimum required profiles first. Plans do not install anything. The executable setup script creates a fresh isolated Python environment only with explicit execution/install approval; non-core installs also require an approved wheelhouse or explicit network/index choice. It does not install Python interpreters, scientific model source/weights, references or licenses. Missing runtime versions/assets require parent-approved acquisition or existing bindings. Model-specific native fixtures must pass after setup and before scoring.

Core tools need Python3.12+ only. Optional QA, RN.Ai, RNAiSpline, OligoFormer and analysis environments have separately observed direct pins. Bio-tools have a separate conda recipe. CPU/GPU/ABI and storage must be verified for the actual chosen backend; no hardware guarantee is inferred from old runs. The setup script never installs into an existing prefix or the SCI runtime/package.

## Local verification

    "$APPROVED_CORE_PYTHON" -B scripts/request_contract.py tests/sample_request.json
    "$APPROVED_CORE_PYTHON" -B scripts/validate_package.py
    "$APPROVED_QA_PYTHON" -B scripts/harness_audit.py tests/synthetic_record.json --validate-schema
    "$APPROVED_QA_PYTHON" -B scripts/validate_package.py --sci-source "$APPROVED_SCI_SOURCE" --sci-python "$APPROVED_SCI_PYTHON"

The last command uses the installed SCI interpreter and its selected committed dependencies only for SDK checks; it does not bootstrap, synchronize or repair SCI. Validation evidence distinguishes core/software checks, actual isolated core setup, optional metadata probes, strict SDK checking, live agent integration and native scientific execution. See tests/validation.json and tests/PROVENANCE.sha256. A core-only run explicitly skips optional QA/SDK checks when absent; those are not reported as passes. Run outputs and bindings stay outside this package.

## Scope, costs and limits

Supported design scope is noninfectious human siRNA research. Plant/pest/pathogen and infection-enabling applications are not activated. Clinical prescriptions, safety assurance and experimental success claims are excluded. LLM calls, platform jobs, downloads, GPUs and indices can incur cost; source upload, charges, license acceptance and execution each need the parent's actual approval. No generic install command grants these rights.

RN.Ai remains the historically retained incumbent, not a universal best model. Core19's small retrospective improvement did not generalize in other-target selection; RNAiSpline/OligoFormer did not beat it on the latest executed cohort. SiaRNA, ENsiRNA and BERT-siRNA were blocked by specific feature/asset/checkpoint prerequisites, not proven inferior. No published-protocol superiority was demonstrated. Read references/historical-evidence.json. These are prior run summaries, not predictions executed by installing this agent.

Immune motifs, seed viability, alignment heuristics, drug-site recovery and reporter physics have limited endpoints; none establishes clinical safety, potency or full application completion. Chemically unmodified cores are not clinical formulations. Novel checkpoints or context changes need a new validated run, not relabeling old evidence. Exact commands must be verified against the bound local adapters; historical campaign drivers are not portable generic design commands.

Only newly authored code/docs and MIT harness utilities are bundled. No third-party weights, datasets, model code, genome indices, credentials or historical source permission grants are redistributed. Native environment reconstruction, licenses, source compatibility and genuine scientific fixtures are separate acceptance criteria. Terminal/execute_code are not a sandbox; owning-profile policy must enforce source and write/egress boundaries. No external MCP or arbitrary plugin is automatically installed; context retrieval can be handed to the parent. New custom skills are complete procedural bundles, not concealed model implementations.
