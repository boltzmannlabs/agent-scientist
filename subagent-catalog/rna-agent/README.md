# RNA-Agent (orchestrator package)

Portable SCI package for the RNA design orchestrator: deterministic table-backed routing of RNA requirements to the
approved leaf specialists, delegation-directive control, and leaf dependency planning + host verification. Same
structure and discipline as the leaf packages (manifest/instructions/skills/references/scripts/tests).

## What it controls

- **Routing**: scripts/route_request.py + references/routing-table.json are the single source of truth (mechanism
  first; ambiguity → one structured ASK; not-covered classes reported; gap verbs dominate design mentions). The
  orchestrator's LLM routing is backed by this deterministic classifier and records any disagreement.
- **Delegation**: uses SCI's reviewed hierarchy bindings and `delegate_task` to assign the approved children.
  Registry-first reuse checks, discovery→execution chains within the original approvals, and unchanged blocked
  outcomes remain part of the contract. A written directive alone is not reported as an executed run.
- **Leaf dependencies**: references/leaf-dependency-matrix.json (per-leaf programs, pins, roles, satisfaction routes,
  parent assets) + scripts/dependency_plan.py (--leaf plan / --verify host probe → READY/PARTIAL/MISSING matrix).
  PLAN_ONLY proposals; bindings happen through the leaf package install review; never installs anything itself.

## Install the reviewed hierarchy

This parent uses SCI package schema v2 and declares all four children with compatible version ranges. Keep their
package folders beside `rna-agent`, then run the normal command in SCI:

```text
/subagent package install "/full/path/to/subagent-catalog/rna-agent"
```

Choose the owning profile and review each package's tools, references and optional dependencies. SCI installs
children first, binds their actual local names, and publishes the reviewed hierarchy. No separate installer or
manual definition edits are required. Renaming the parent is supported. Use `/new` after saving.

For an installation smoke check, ask the coordinator to describe its child roster and missing requirements,
without scientific jobs or downloads. Deferred optional dependencies do not establish readiness for model
inference; the affected mode must report its missing inputs/software and existing authorization requirements.
Validate the merged dev version separately before promotion to main.

## Leaves routed

application-aware-sirna-designer · application-aware-grna-designer · rna-model-discovery · rna-model-execution

## Verification

    python3 -B tests/test_contract.py
    python3 -B scripts/validate_package.py --sci-source <sci-checkout> --sci-python <sci-python>

The shared registry CLI/schema are byte-identical copies with rna-model-discovery and rna-model-execution (the
package test asserts identity with the discovery copy); keep the three in sync.
