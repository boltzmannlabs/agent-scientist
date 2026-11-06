# CReM: supported scientific controls

This guide describes inspected local source, not certification that every deployed
worker uses the same revision. Use the assignment's current canonical connector
contract for the actual request schema and file rules.

The inspected `Fragment_Based_Optimization` interface accepts a generation parent
through `ref_mol`, a supplied library through `library_path`, and selected
`global_models` and/or authorized `custom_models` with explicit threshold fields.
Optimization requires at least one property model. No model is inferred from the
task title; preserve the assignment's exact selection.

The local `crem_main.py` prepares library fragments, runs both GROW and MUTATE at
radii 1, 2 and 3, removes duplicates, computes descriptors, predicts selected
properties and writes the result. This path does not show a property-feedback
loop or requested-threshold filtering. Receiving rows outside a requested range
does not by itself prove service failure or objective infeasibility.

Do not propose `mode`, `radius`, `n_mols`, a random seed or internal evaluation
count as adjustable controls unless the current contract actually exposes them.
The action in this version is a supported parent–library combination with the
fixed objective, not an invented low-level CReM configuration.

## Before submission

- Select a registered exact parent form satisfying the task's parent rules.
- Use the admitted library's exact content identity and host-provided file path.
- Keep original-reference success checks independent of the generation parent.
- Use documented uploads and their actual returned storage references.
- Respect the host-approved experiment name and warning-specific authorization.
  A general run instruction is not approval to ignore new validation findings.
- Check unresolved previous actions before spending on another investigation.

## Interpret the returned batch

The returned row count is not necessarily an input control or internal oracle-call
count. Use the complete artifact and host-calculated identity/assessment results.
Output mode/radius labels describe generation provenance, not a causal edit map.

The selected Lipophilicity development task uses provider model-score range 0–3.
The reference score observed in qualification was -8.72. Its physical units and
exact checkpoint were unverified. Do not rename it LogP/LogD, substitute an RDKit
descriptor, infer experimental potency or change bounds after seeing outcomes.
