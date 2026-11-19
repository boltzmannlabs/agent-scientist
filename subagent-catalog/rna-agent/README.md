# RNA-Agent (orchestrator package)

Portable SCI package for the RNA design orchestrator: deterministic table-backed routing of RNA requirements to the
approved leaf specialists, delegation-directive control, and leaf dependency planning + host verification. Same
structure and discipline as the leaf packages (manifest/instructions/skills/references/scripts/tests).

## What it controls

- **Routing**: scripts/route_request.py + references/routing-table.json are the single source of truth (mechanism
  first; ambiguity → one structured ASK; not-covered classes reported; gap verbs dominate design mentions). The
  orchestrator's LLM routing is backed by this deterministic classifier and records any disagreement.
- **Delegation**: emits ready-to-execute DELEGATION DIRECTIVEs (references/delegation-contract.md) — package-installed
  leaves require direct parent assignment, so the parent executes the directive. Registry-first reuse checks; chained
  discovery→execution flows; blocked outcomes passed through unchanged.
- **Leaf dependencies**: references/leaf-dependency-matrix.json (per-leaf programs, pins, roles, satisfaction routes,
  parent assets) + scripts/dependency_plan.py (--leaf plan / --verify host probe → READY/PARTIAL/MISSING matrix).
  PLAN_ONLY proposals; bindings happen through the leaf package install review; never installs anything itself.

## Children wiring (schema v1 constraint)

SCI package manifests cannot declare `children`; after installing this package, run the repository's parent-side
installer `rna-agent/install_rna_agent.py` (SCI runtime python, SCI_HOME at the profile) to wire the routed leaves
into the saved definition (revision-guarded edit) and verify every routed leaf is installed and enabled.

## Leaves routed

application-aware-sirna-designer · application-aware-grna-designer · rna-model-discovery · rna-model-execution

## Verification

    python3 -B tests/test_contract.py
    python3 -B scripts/validate_package.py --sci-source <sci-checkout> --sci-python <sci-python>

The shared registry CLI/schema are byte-identical copies with rna-model-discovery and rna-model-execution (the
package test asserts identity with the discovery copy); keep the three in sync.
