# Subagent Optimization

Research and proposed evaluation of a specialist subagent for small-molecule optimization in Agent Scientist.

The goal is to identify a useful scientific decision that a specialist can improve, while retaining the native agent's tools and the lead-optimization environment's evidence/assessment responsibilities. The offline baseline, context reference, local saved-specialist bundle and conditional pilot runner are implemented. Actual LLM reasoning, scientific advantage and real-profile deployment remain unvalidated; no new prediction model is claimed.

## Current work — 3 November 2026

End-of-day progress is recorded in the [3 November work summary](research/progress-2026-11-03.md).
The final implementation has 27 passing portable checks, an explicit property-model
requirement and a Lipophilicity-specific evaluator. The reference prediction was
verified and the new CReM job was accepted; generated results and actual agent
reasoning had not been evaluated at that day's cutoff. The [publication check](results/pilot-property-validation-20261104.json)
records a repeat of the portable checks on 4 November and current source hashes.

- [Decision brief](research/decision-brief.md): source-backed scientific choice and review-driven corrections.
- [Specialist design](research/specialist-design.md): one role, context, input/output meaning, invocation conditions and comparison proposal.
- [Local specialist implementation](specialist/README.md): native definition, complete evidence packet, invocation gates and freshness/citation checks. Library choice is a conditional first study, not library curation for every target.
- [Library-policy prototype](prototype/library_policy/README.md): choose among untried library assets using reviewed contextual edit evidence; fixed-order reference included.
- [Context reference](prototype/context_contract/README.md): artificial tests for focused evidence, rules, freshness and advisory returns.
- [Library intake audit](prototype/library_audit/README.md): local RDKit identity checks, normalized-input alias protection and stale-review binding.
- [Real-data readiness](research/data-readiness.md): inspected candidate files, internal computational checks and remaining execution qualifications.
- [Actual library alternatives and algorithm](research/library-alternatives/README.md): three matched ChEMBL source cohorts, source-level CReM material checks and a standard coverage-planning baseline. This is structural development evidence, not molecular improvement.
- [Conditional pilot](pilot/README.md): private persistent runs, existing NodeAPI connector handoff, fixed assessment and recorded named-child routing. See its [evaluation protocol](pilot/PROTOCOL.md).
- [Initial pilot validation](results/pilot-validation.md): historical early-day checks and the limits of that evidence; its hashes and counts predate the property-objective implementation.
- [Initial live preflight](results/pilot-live-preflight-20261103.json): the connector requested approval of its generic-CSV SMILES warning; independent checks passed for all three source libraries.
- [Earlier approved live attempt](results/pilot-live-attempt-20261103.json): the user approved that warning, the upload succeeded, and the model-free submission returned `attribute is required` without a job ID. That original attempt remains preserved. The later, separately selected [Lipophilicity task](pilot/PROPERTY_PROTOCOL.md) requires an explicit property model and does not retry the old task.
- [Software validation](results/software-validation.json): actual test results, code hashes and controlled artificial demonstration; scientific benefit remains untested.
- [Native integration canary](results/specialist-native-validation.json): two checks pass with disposable profiles and canned loopback responses; no actual LLM reasoning is evaluated.
- [Specialist development review](results/specialist-development-review.md): independent review of the current local implementation and its limits.
- [Independent AI-subagent review](results/independent-review.md): accepted within offline scope; scientific and native prerequisites remain open.
- [Intake extension review](results/data-readiness-review.md): current metadata and identity checks independently reviewed; all assets remain unapproved.
- [Delegation boundary](research/runtime-integration-review.md): model/profile routing and host integration prerequisites.

## Reproduce the offline checks

```bash
cd subagent-optimization/prototype/library_policy
python3 -B run_checks.py
python3 -B demo.py
```

Policy, context and specialist-adapter checks use Python's standard library. Optional structure
identity checks use existing RDKit; missing RDKit is reported as skipped, not
installed automatically. The runner records small results under
`subagent-optimization/results/`. It submits no jobs or model requests and runs
no property predictors. The separate intake script inspects explicit local files
and exports metadata only; its report approves no library.

See the [repository migration record](research/repository-migration.md) for source provenance and previous tracking.

## Research

- [Research notes](research/research-notes.md): objective, progress and open questions.
- [Workflow review](research/workflow-review.md): existing responsibilities, possible external controls and proposed evaluation.
- [References](research/references.md): sources and the inspected source hashes.

Tracking: [agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33). Previous repository tracking: [BOLTCHEM-FEATURES#147](https://github.com/boltzmannlabs/BOLTCHEM-FEATURES/issues/147). Original research tracking: [science-environments#89](https://github.com/boltzmannlabs/science-environments/issues/89). Related environment: [science-environments#46](https://github.com/boltzmannlabs/science-environments/issues/46).

## Structure

```text
subagent-optimization/
├── README.md
├── research/                 # Sources, design, findings and uncertainties
├── specialist/               # Local saved-specialist definition and host adapter
├── pilot/                    # Conditional run state, assessment and native handoffs
├── prototype/
│   ├── library_policy/       # Implemented baseline and artificial examples
│   ├── context_contract/    # Reusable advisory-handoff engineering reference
│   └── library_audit/       # Optional RDKit intake and review-binding checks
└── results/                  # Small reproducible software-check evidence
```

Maintained in `boltzmannlabs/agent-scientist` on the `subagent-optimization` branch. The lead-optimization environment remains in `boltzmannlabs/science-environments` on `BoltChem`. The primary issue belongs to this repository; cross-repository links retain the original research and environment history. This focused branch contains no tool implementation changes, installed profiles, private job artifacts, model weights or large datasets.
