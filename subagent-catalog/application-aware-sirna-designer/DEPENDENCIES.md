# Setup-first dependency guide

## What can be provisioned

Core (Python3.12+ stdlib), optional QA (Python3.13.7 observed), RN.Ai/RNAiSpline/analysis (Python3.13.7 observed), OligoFormer (Python3.8.20 observed), and ViennaRNA2.7.2/bowtie2.5.5 conda bio-tools are separate profiles. Direct observed package pins live in dependencies.json and matching requirements files. They are not a full transitive lock, publisher attestation or promise that all public wheels exist. The analysis matplotlib build has a distribution-specific +dfsg1 suffix and may require authorized local wheels; do not silently replace it. Native source, checkpoints, RNA-FM, frozen gate files, exact reference/index/table versions and a valid fixture remain external assets.

This package deliberately does not include proprietary/no-license code or model assets. RN.Ai code/checkpoint have historically reported Apache-2.0 terms; verify current acquired terms. OligoFormer research restrictions, no-license RNAiSpline/SiaRNA and separate structural/model licenses require case-specific approval. Past permission on another profile is not current authorization. Do not automatically accept licenses or train a replacement. SiaRNA/ENsiRNA/BERT-siRNA are blocked by documented prerequisites, so there is no pretend complete install recipe for them.

## Safe sequence

1. Scope and provider first. Prefer a matching authorized Boltzmann contract. A remote route does not need every local model installed. The manifest's optional Boltzmann declaration invokes SCI's reviewed setup; the leaf cannot manage credentials. No new external MCP is required for core functionality. API context retrieval may be delegated back to the parent with explicit source-transfer permission.
2. Inventory only chosen trusted executable metadata with check_dependencies.py; import/checkpoint/native fixture/scientific applicability are distinct gates. The isolated -I probe excludes user-site/PYTHONPATH inheritance. Historical environments may depend on those paths and therefore fail the isolated probe; report the mismatch instead of hiding dependencies. Duplicate distribution metadata is retained. No metadata status certifies a clean native install.
3. Select an existing approved interpreter or have the parent provision the exact Python version. Never pip/conda install into SCI or an existing scientific environment. Use an approved fresh prefix, reviewed package index or approved offline wheelhouse, cache/temp root and cost/resource budget. The script pins selected direct requirements but does not download interpreters or asset licenses.
4. Generate and review the plan. Flags are interface controls, not an authorization source. The parent must actually approve software/source/egress/write scope. Commands run without a shell. Pip's inherited configuration and all PIP environment variables are cleared, then controlled local cache/config settings are applied; explicit reviewed index or wheelhouse only. Wheel-only installation fails instead of silently compiling unavailable packages. Inspect downloaded code and transitive dependencies under the parent's software policy. Index flags are not a network sandbox: the owning execution environment must enforce any offline/egress boundary.
5. Execute the reviewed plan once. The software script exclusively creates the prefix, retains real subprocess logs/exit status and records setup-receipt.json there. Partial/failed environments are retained for diagnosis and never silently reused or deleted. After metadata success, bind assets and verify a genuine approved scientific fixture before any target work.

## Commands from the package directory

The approved write root must already exist. Planning executes the explicitly selected trusted Python only for metadata; no installation or network occurs.

    "$APPROVED_CORE_PYTHON" -B scripts/setup_requirements.py --profile core --python "$APPROVED_CORE_PYTHON" --approved-root "$APPROVED_ENV_ROOT" --prefix "$APPROVED_ENV_ROOT/core-env"

After actual parent approval, add --execute --approve-install. Core uses --without-pip and installs no third-party dependencies.

For QA or a native Python profile choose --profile qa, rnai, rnaispline, oligoformer or analysis and the exact selected interpreter. Add --wheelhouse "$APPROVED_WHEELHOUSE" for offline installation. Alternatively supply both --allow-network and --index-url "$APPROVED_HTTPS_INDEX" after reviewing that source. Network/index flags and offline wheelhouse are mutually exclusive; no hidden public-index fallback is used. Prefix creation/network/package installation remains unrun until explicit approval.

Metadata checks:

    "$APPROVED_CORE_PYTHON" -B scripts/check_dependencies.py --profile qa --python "$APPROVED_QA_PYTHON"
    "$APPROVED_CORE_PYTHON" -B scripts/check_dependencies.py --profile rnai --python "$APPROVED_RNAI_PYTHON"

Conda bio-tools are a separate parent-reviewed command, not pip packages:

    "$APPROVED_CONDA" env create --prefix "$APPROVED_BIO_PREFIX" --file dependencies/environment-biotools.yml

Place conda cache/temp under approved roots and review configured channels and solver/platform compatibility. No conda solver/native environment reconstruction is claimed by recipe parsing. Probe each selected binary with its actual version/help and a trusted native fixture. RNAhybrid is intentionally excluded until its known broken stage is resolved and independently validated.

## Private bindings and assets

Copy dependencies/bindings.example.json outside the package, resolve real absolute paths and record actual SHA-256 values after authorized reads. Source IDs may point to reviewed source-entry/manifests; a single file hash does not verify an entire repository or fixture. Include code revision, applicable weights, references, chemistry/context and licenses in the actual run provenance. No unpickle/model loading is done by the asset checker.

    "$APPROVED_CORE_PYTHON" -B scripts/check_bindings.py "$PRIVATE_BINDINGS" --profile rnai
    "$APPROVED_CORE_PYTHON" -B scripts/check_bindings.py "$PRIVATE_BINDINGS" --profile rnai --verify-assets --read-root "$APPROVED_ASSET_ROOT"

Repeat --read-root only for approved roots. Symlink escape and out-of-root paths fail. Empty templates block native work. Integrity and metadata outputs always say model_readiness_verified=false: the parent must observe/review actual fixture execution and applicability. Install only what the requested endpoints require; all remaining assets remain explicitly NOT_RUN/BLOCKED, not silently passed.
