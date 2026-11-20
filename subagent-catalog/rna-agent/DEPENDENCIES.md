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

The schema-v2 manifest declares four child packages and compatible versions. SCI's normal package installer
reviews and binds each child in the selected owning profile; no private installer or manual definition edit is
needed. Child capabilities stay scoped to their own reviewed packages. Missing scientific dependencies remain
explicit blockers for the affected mode even when optional program setup is deferred during installation.

## Verification commands (from the package directory)

    python3 -B tests/test_contract.py
    python3 -B scripts/route_request.py --text "design siRNA for human KRAS"
    python3 -B scripts/dependency_plan.py --verify
    python3 -B scripts/validate_package.py --sci-source <sci-checkout> --sci-python <sci-python>
