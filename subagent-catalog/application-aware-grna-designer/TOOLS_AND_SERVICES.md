# Tools, services and runtime setup

## Exact built-in tool grants

manifest.yaml requests read_file (read approved inputs), search_files (discover approved sources), write_file and patch (write only approved outputs), terminal (reviewed isolated native tools), execute_code (bounded orchestration and calculations) and skill_view (load reviewed procedural skills). Terminal and execute_code are powerful host capabilities, not a sandbox. A recipient must review their scope. There is no child delegation, scheduler, credential/configuration management or implicit network grant.

## Skills

Three complete packaged skills are required: application-aware-grna-workflow, reproducible-scientific-harness and publication-calibrated-crispr. The latter has its own scripts/policy.py plus model-policy.json and benchmark-evidence.json supporting files. No host bioinformatics skill or external service is silently installed by these folders.

## MCPs and plugins

No MCP or plugin is required for the offline package checks, model-policy helper or setup planner. No remote connector is granted by this manifest.

If parent/session scientific-provider routing requires Boltzmann, the parent must load its installed contracts, authorize the selected connector through the owning session, confirm sharing and run or hand off the matching job. The specialist returns a provider handoff when it cannot access the required connector; it must not bypass that requirement with local execution. Do not infer service readiness from this document or an installed plugin. Literature retrieval through PubMed or another MCP is optional parent work; no such MCP endpoint or credential is embedded. Adding direct leaf remote tools requires a separately reviewed manifest revision and actual provider authorization, not a wildcard grant.

## Runtime sequence

1. Parent supplies approved sources/write roots, mode, actual biological context, endpoint/model, scientific parameters, execution scope and sharing permissions. File contents/fixture flags do not confer approval.
2. Use request_contract.py and model_policy.py as metadata-only checks; hand missing values back to the parent.
3. Inspect dependencies.json. Probe ONLY an approved existing executable with check_dependencies.py. Version metadata is not native readiness.
4. If missing, use setup_plan.py with a new prefix under the approved write root. It prints review-only command arrays and asset requirements, never runs them. Request approval for actual installers/downloads/licenses, resources and cost. Use caches/TMPDIR inside the approved root.
5. Install only the selected isolated profile, never merge incompatible environments or install into SCI. Bind the matching optional manifest programs after recipient review. Legacy CRISPRi/a and broad R source stacks require manual source-specific setup.
6. Supply native source, licensed weights, exact features/references and frozen scientific contract. Verify model/source hashes and publisher fixture, not merely imports. CBE also requires native RNAfold/CRISPRoff and the auxiliaryV0models; exact old membership remains an unresolved limitation.
7. Only after parent approval and real native checks, execute the requested scientific workflow into a fresh run folder. Preserve actual exits/logs/predictions, input identity, split/selection records, uncertainty and graph files. No automatic test-max promotion.

## Software profiles

Core metadata: Python3.12+, no third-party core requirements.
Harness QA: historical separate Python3.13.7 profile; alternatively sdk_qa records an existing selected SCI Python3.14.7 with jsonschema/packaging/Pillow and read-only sci_yaml from approved SCI source. Neither option installs into SCI.
Analysis: separate scientific reporting stack, not native scorer.
RS3: Python3.8 and source-compatible LightGBM/scikit-learn/native weights.
CRISPRon v1: Python3.9/TF2.14/Keras2.14 plus source thermodynamic tools.
PRIDICT2/DeepPrime: Python3.10/PyTorchCPU2.0.1 and exact checkpoints/features.
BEHive: Python3.7/scikit-learn0.20.3, serialized source regressor.
CBE: Python3.10.14/TFCPU2.10.0/Keras2.10, RNAfold2.5.1, original source and model assets.
RFcombined: R4.3.3/randomForest4.7.1.2/jsonlite2.0.0; not the broaderR4.5.3 design stack.
Optional legacy CRISPRi/a: Python2.7 source-specific environment; original genome/chromatin inputs still missing in the historical benchmark.

See DEPENDENCIES.md for exact observed pins, example commands and unsupported clean-install claims. No environment file alone supplies genome indices, licensed models or native scientific adapters.

## Costs and limitations

Package QA is local and performs no model-provider or scientific service call. An actual specialist conversation incurs the recipient's provider-dependent LLM cost. Native inference/training consumes local CPU/RAM/disk; large references and model downloads require explicit resource review. The CBE author bundle is approximately5GB before extraction and environment/cache overhead. No price, latency, GPU requirement or universal batch optimum is guaranteed. No installation, commercial-use approval, service entitlement or scientific validation is implied by saving the package.
