# Dependencies — rna-agent (orchestrator)

Core tooling (route_request.py, dependency_plan.py, registry.py, validate_package.py) is standard-library Python
(>=3.12). The optional `python_core` program binding records an approved interpreter; scripts also run with the
system python3.

- **No installs are performed by this specialist.** Dependency setup means: plan (matrix + PLAN_ONLY proposals) and
  verify (read-only host probes). Bindings happen through the leaf package install review; recipes run only under
  parent approval into fresh prefixes.
- Host verification probes `--version` on PATH binaries and interpreter families across PATH and conda env roots;
  probes execute code only in the sense of version banners, and every probe is read-only.
- The shared registry CLI (scripts/registry.py) and registry schema are byte-identical copies with rna-model-discovery
  and rna-model-execution; keep the three in sync (the package test asserts identity with the discovery copy).

## Children wiring

SCI package schema v1 rejects manifests declaring `children`, so this package deliberately omits them. After
installing this package, run the parent-side installer (`rna-agent/install_rna_agent.py` in the repository) to wire
`children` into the saved definition (a legitimate definition-level edit, revision-guarded) and to verify that every
routed leaf is installed and enabled.

## Verification commands (from the package directory)

    python3 -B tests/test_contract.py
    python3 -B scripts/route_request.py --text "design siRNA for human KRAS"
    python3 -B scripts/dependency_plan.py --verify
    python3 -B scripts/validate_package.py --sci-source <sci-checkout> --sci-python <sci-python>
