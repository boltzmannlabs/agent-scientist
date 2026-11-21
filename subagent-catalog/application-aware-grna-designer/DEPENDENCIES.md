# Dependencies and reviewed setup

## Core vs scientific execution

requirements.txt contains no third-party packages because the package fixtures/request preflight are standard-library-only. Use Python 3.12 or newer for these checks. Existing SCI/model-provider setup is separate; never pip-install this dependency collection into SCI's runtime.

dependencies.json is the machine-readable catalog. It separates observed native environments and external assets. requirements files contain directly observed version pins, not solver-verified full transitive locks. A version being installed on the originating machine does NOT prove availability from a public index, portability or a clean reconstruction on another machine.

## Agent Scientist package installer

manifest.yaml is authoritative for SCI's installer. Optional program declarations let the user select and separately authorize version checks for installed Python/R executables. SCI does not automatically install these pip/conda/R files, does not run shell bootstrap scripts, and does not acquire scientific weights or genomes from this catalog. Optional program setup can be deferred. Link the actual matching executable after preparing a reviewed environment.

The core python3 version probe checks the Python3 family; scripts/check_dependencies.py additionally enforces the core minimum version. Backend probes identify their version families; the dependency checker reports exact observed-version matches separately. Package/runtime readiness and scientific readiness are different.

## Separate profiles

| Profile | Observed interpreter | Main use | Setup files |
| --- | --- | --- | --- |
| harness | Python3.13.7 observed; core audit supports 3.12+ | Optional offline schema/manifest/raster QA, not model scoring | dependencies/environment-harness.yml and requirements-harness.txt |
| analysis | Python3.12.14 | Metric/report calculations | dependencies/environment-analysis.yml and requirements-analysis.txt |
| rs3 | Python3.8.20 | Native RS3 | dependencies/environment-rs3.yml and requirements-rs3.txt |
| crispron | Python3.9.23 | TF2.14.1/Keras2.14 CRISPRon | dependencies/environment-crispron.yml and requirements-crispron.txt |
| editing | Python3.10.21 | PRIDICT2/DeepPrime | dependencies/environment-editing.yml,requirements-editing.txt,requirements-torch-cpu.txt |
| behive | Python3.7.12 | Legacy BE-Hive efficiency model | dependencies/environment-behive.yml and requirements-behive.txt |
| crispria | Python2.7.15 | Legacy source-import environment only | requirements-crispria.txt; no clean conda recipe claimed |
| r_native | R4.5.3 | Native CFD/RFcombined/crisprDesign/crisprScore | dependencies/r-packages.csv; not a complete renv lock |

Keep legacy environments isolated. Their version-pinned packages may be unsupported or have security issues; use only with reviewed trusted data/code, not as general-purpose internet environments. Do not upgrade serialized-model runtimes silently to satisfy a solver.

## Optional harness QA

The harness profile records Python3.13.7, jsonschema4.19.2, PyYAML6.0.3, packaging26.3 and Pillow11.3.0 observed in an existing approved interpreter. These pins were checked without installing anything. The observed environment exposes duplicate PyYAML/packaging distribution metadata; the checker resolves each effective version with the selected interpreter's own metadata lookup and reports all visible conflicting versions. This is explicitly not a clean reconstruction or module/model-readiness guarantee.

    python3 -B scripts/check_dependencies.py --profile harness --python "$APPROVED_HARNESS_PYTHON"

Use the separate installed SCI runtime for optional strict SDK validation. Its bare managed Python may need the install's selected dependency generation; sci_schema_probe.py reads that selection with the installed implementation, checks Python ABI compatibility and adds its existing site-packages only inside the child process. It does not run SCI bootstrap/sync/recovery, install dependencies or change profile settings. Do not add SCI's internal dependencies to the scientific QA requirements merely to import its SDK. Unknown installed SDK layouts must be reviewed rather than repaired with an upstream SCI install.

## Example setup (requires approval; not executed by this package)

From the dependencies directory, choose only the profile you need. Use an explicitly approved fresh environment prefix rather than an in-use environment:

    conda env create --prefix "$APPROVED_ENV_PREFIX" --file environment-rs3.yml

The corresponding requirements-rs3.txt must remain beside that YAML. Conda/pip cache and temporary paths must be placed under the approved write root. Solver or unavailable-wheel failures are setup failures, not permission to modify model features or substitute another model.

For editing, the environment recipe installs the non-Torch requirements. Install the observed CPU Torch build separately using an explicitly approved CPU wheel index supplied in PYTORCH_CPU_INDEX:

    "$APPROVED_ENV_PREFIX/bin/python" -m pip install --index-url "$PYTORCH_CPU_INDEX" -r requirements-torch-cpu.txt

The source index must be reviewed independently; no credential/index value is embedded. Do not point the entire scientific requirements list at a CPU-wheel-only index. Exact CPU build compatibility and index availability have not been retested here.

CRISPRon also needs the original native thermodynamic tools; Python packages alone are insufficient. For legacy CRISPRi/a, the original setup encountered unavailable conda configparser4.0.2 and no pip; a verified pure-Python backport wheel was needed on that machine. Do not claim its requirements file alone solves all historical binary/solver constraints. The exact original chromatin/genome feature inputs are still necessary, and its source-import success was not a completed efficacy benchmark.

For R, use a separately approved matching R/CRAN/Bioconductor source environment, review dependency versions and original model-data packages, and compare against r-packages.csv. No generic install.packages call is supplied because it would not pin the required Bioconductor/development artifacts. Genome indices, native binaries and model weights remain external assets with their own versions/licenses/hashes.

## Verify a selected executable without installing

Using a trusted Python3.12+ interpreter from the package directory:

    python3 -B scripts/check_dependencies.py --profile core
    python3 -B scripts/check_dependencies.py --profile rs3 --python "$APPROVED_RS3_PYTHON"
    python3 -B scripts/check_dependencies.py --profile editing --python "$APPROVED_EDITING_PYTHON"
    python3 -B scripts/check_dependencies.py --profile r_native --rscript "$APPROVED_RSCRIPT"

Each selected-executable check executes a small reviewed metadata/version probe and therefore requires execution permission. It does not install packages, access a network, generate sequences, score models or resolve missing original references. The exact observed interpreter version is compared as well as selected distribution versions. A passing metadata check does not prove shared-library, feature, weight, assay or model readiness. Return discrepancies to the parent; do not edit scientific inputs to make setup pass.

## Version1.3 additional native profiles

cbe uses observed Python3.10.14, tensorflow-cpu2.10.0, Keras2.10.0, NumPy1.23.5, SciPy1.10.1, pandas2.2.2, Biopython1.79 and h5py3.16.0. requirements-cbe.txt is a selected observed-distribution inventory, not a transitive lock. environment-cbe.yml uses conda-forge plus bioconda for RNAfold/ViennaRNA2.5.1. Preserve its source version and native energy dictionary. Original pinned CBE source,25model directories, five auxiliaryV0checkpoints and matching labels remain external licensed assets. Do not confuse this environment with CRISPRonv1/TF2.14.

rfcombined uses observed R4.3.3, randomForest4.7.1.2 and jsonlite2.0.0. environment-rfcombined.yml and rfcombined-packages.csv describe this separate runtime, not the broaderR4.5.3 design stack. Original input features and transformations are mandatory; a successful R import does not regenerate them.

The setup planner prints a command list only:

    "$APPROVED_QA_PYTHON" -B scripts/setup_plan.py --profile cbe --write-root "$APPROVED_WRITE_ROOT" --prefix "$APPROVED_NEW_CBE_PREFIX"

It rejects an existing prefix or one outside the supplied root, but those path checks do not confer authorization or a sandbox. After reviewed installation, bind python_cbe, rnafold_cbe or rscript_rfcombined as applicable and run the metadata probes. Then execute the publisher fixture under separate scientific execution approval. No network/download/solver/install occurs during package validation. The newly added recipes have not been clean-rebuilt by this package update.

## Existing installed-SCI QA alternative

The original harness pins remain historical and are not silently changed to match another interpreter. A separate sdk_qa profile records the currently selected existing SCI Python3.14.7 with jsonschema4.26.0, packaging26.0 and Pillow12.3.0. PyYAML is absent there. For read-only package checks, validate_package.py can use the approved installed SCI source's sci_yaml parser when --sci-source is explicitly supplied. Select --qa-profile sdk_qa with that already installed matching interpreter; do not install these packages into SCI or run an upstream bootstrap. There is no clean solver recipe for this existing SDK layout. The normal standalone harness recipe remains separate.
