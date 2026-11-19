# Dependencies — rna-model-discovery

Core tooling (request_contract.py, validate_spec.py, registry.py, validate_package.py) is standard-library Python
(>=3.12). The optional `python_core` program binding in the manifest records an approved interpreter; scripts also
run with the system python3.

- **No package installs are performed by this specialist.** All search, clone and fetch activity is parent-authorized
  egress at run time and recorded in the run's evidence.
- **jsonschema** is optional: validate_spec.py uses it for strict Draft 2020-12 checks when importable and falls back
  to the built-in structural checker otherwise; the fallback's verdict is recorded as `builtin-structural`.
- The shared registry is a parent-owned JSON file; both rna-model-discovery and rna-model-execution carry identical
  copies of scripts/registry.py (state ladder enforced in code).

Verification commands (from the package directory):

    python3 -B scripts/request_contract.py tests/cases-request.json   # any single request fixture
    python3 -B scripts/validate_spec.py tests/synthetic_spec.json
    python3 -B scripts/registry.py init /tmp/reg.json && python3 -B scripts/registry.py validate /tmp/reg.json
    python3 -B scripts/validate_package.py --sci-source <sci-checkout> --sci-python <sci-python>
