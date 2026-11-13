# PAMPA readiness assignment — user-run Agent Scientist test

**Completed historical assignment.** Job 6af455a44bcdd4891fc0f85f returned Success
and two source-interpreted positive labels. Do not submit another job solely to
repeat this readiness check. See [result](../results/pampa-label-readiness-20261111.md).

## Original assignment (preserved)

Perform a small live PAMPA property-prediction readiness test yourself.
Do not delegate or run generation, optimization or docking.

Read the selected case:
/home/boltzmann13/agent-scientist-subagent-optimization/subagent-optimization/research/pampa-first-refinement.md

Use native Boltzmann tools authorized in this profile. Check the current
Property_Prediction contract. Prepare one CSV containing exactly these two inputs,
retaining names and identities in a separate join manifest:

e072:
```text
CCC(C)(C)NC(=O)C(F)(F)c1cccc(NC(=O)Cc2cncnc2)c1
```

SB2 reference:
```text
C[S@](=O)c1ccc(-c2nc(-c3ccc(F)cc3)c(-c3ccncc3)[nH]2)cc1
```

Select global_models=["PAMPA"], uncertainty=0 and explainability=0 using the
documented payload. This is separate from the earlier Vina submissions.

I authorize one Property_Prediction job for these two inputs and its required
upload, monitoring, download and available exact-ID diagnostics. Review input
warnings yourself; use scoped partial-validation approval only after checking
the exact files and unchecked aspects. Do not override validation errors.

Submit once and retain the actual ID. Collect that same job and preserve every
artifact and failure. If acceptance is ambiguous and no ID returns, retain the
receipt and stop; do not resubmit or guess an ID.

Verify identity association and establish whether PAMPA returns a class-1 score,
a binary label or both. The inspected source uses high-permeability class 1 and
a 0.5 classifier boundary. Confirm actual output semantics: a number between
0 and 1 alone is insufficient. Preserve available head and loading/inference
evidence. Zero alone neither establishes failure nor proves successful inference.

If score meaning is supported, report each raw score/class and its decision under
the existing boundary. Keep rounded-boundary ambiguity explicit. Do not interpret
0.5 as 50% absorption or claim calibrated confidence or measured permeability.
If evidence is insufficient, preserve the output with unresolved interpretation.

Save new inputs, receipts, raw results, identity mappings, resource use and a
concise report in a separate output directory. Preserve older campaigns/records.
Do not edit profile configuration or install/update the saved specialist.
Report technical readiness and remaining limits; do not claim optimization gain.
