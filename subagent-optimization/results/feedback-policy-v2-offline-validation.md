# Feedback-policy v2 — offline component validation

Date: 11 November 2026. Tracking issue: agent-scientist#33.
Status: **offline mechanics implemented and tested; scientific benefit untested**.

## Delivered

[Component and reproduction instructions](../prototype/feedback_policy/README.md):
pure observation-to-action selection, shared feasibility-first panel selection,
final-panel completeness reporting, seeded assessment allocation and descriptive
batch feedback. Returns a rationale and alternatives without executing an action.

All validation records are artificial. Fixture identities, SMILES strings, method
labels, measurements, allowances and qualification flags represent no actual
molecules, predictions or qualified services. No historical campaign was reopened.

## Executed checks

From `subagent-optimization/prototype/feedback_policy/`:

```bash
python3 -B -m unittest -v test_feedback_policy
python3 -B demo.py
```

The final unit suite passed **36 tests, zero failures or errors**. The demo
executed successfully using artificial observations only.

Coverage includes:

- A feasible lead with an empty output pool does not invent a solubility deficit;
  measured otherwise-admissible solubility failures can change the chosen route.
- Missing/wrong-scale observations remain unresolved; missing objective
  qualification cannot be repaired by a syntactically valid model selection.
- Pending/ambiguous jobs prevent another proposal; supplied search/final/generation
  allowance checks preserve the final reserve without changing the ledger.
- Parent choice uses feasible docking order or a nondominated violation frontier.
  Input order, display labels and library aliases do not bias the scientific key
  or route selection. Unsupported public controls are rejected.
- Lead/control recoveries, duplicates and ineligible strong docking scores do not
  enter the designed panel. Missing final slots suppress its full-panel mean;
  extra candidates cannot replace a failure.
- Improving a non-best panel slot counts toward retained-pool quality progress.
  Novel nonimproving products differ from duplicate-only results. Progress,
  counterevidence and unresolved evidence can coexist.
- Partial/conflicting duplicate observations do not overwrite retained evidence
  or turn rescoring into new-chemistry improvement.

## Critic review and corrections

An evaluation critic identified and reviewed corrections for the single-best-score
progress bug, historical reference recoveries and caller-overwritten action keys.
A feasibility critic independently ran the initial 34-test suite and identified
same-identity observation replacement and the need to clarify accounting and
experimental route preferences. Both observation regressions were added to the
final 36-test suite. Both critics confirmed their findings were addressed within
the documented offline scope. The README defines the trusted-host boundary and
labels the route preferences as an experimental heuristic.

## Limits and next integration boundary

These checks establish behavior under supplied facts, not better molecular
optimization. The component does not verify chemistry, model meaning, source
authenticity, service readiness, authorization, immutable commitment or execution
ordering. It checks independently supplied observable counters but cannot enforce
a shared ceiling or reserve capacity atomically; the host must do so.

Before live use, connect real host observations/admitted action profiles, qualify
the Solubility endpoint and one common platform Vina setup, and approve the live
allowances and comparison contract. Profile integration, scientific qualification,
matched live comparison and delegation/context-efficiency claims remain untested.
No scientific jobs, profile changes or Git operations were performed for this
offline implementation.
