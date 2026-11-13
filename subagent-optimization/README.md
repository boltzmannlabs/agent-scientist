# Subagent Optimization

Research and proposed evaluation of a specialist subagent for small-molecule optimization in Agent Scientist.

The goal is to improve evidence-driven molecular decisions using existing scientific tools, with explicit constraints, uncertainty, context management and resource accounting. The current saved specialist uses native Boltzmann tools; reusable local helpers support assessment and reporting. Execution has been exercised in bounded user-run cases, but a scientific advantage over a capable base agent has not been demonstrated. No new prediction model is claimed.

## Current work — 12 November 2026, reviewed 13 November

The [feedback specialist](specialist/feedback-v2/SETUP.md) owns a bounded
CReM → common PAMPA/RDKit assessment → Vina → justified continuation or STOP
investigation. It records evidence, competing options, parameter reasons,
uncertainty and actual native receipts without adding another submission client.

The [12 November work summary](research/progress-2026-11-12.md) links the source,
validation and case records. Main deliverables are:

- [Common refinement decision guide](specialist/feedback-v2/evaluation/matched-v1/COMMON_GUIDE.md)
  and [scientific-reasoning contract](research/scientific-reasoning-contract-v1.md):
  joint-constraint diagnosis, typed evidence, uncertainty consequences and visible
  trade-offs; computational feedback remains distinct from experimental feedback.
- [Feedback-policy prototype and observation adapters](prototype/feedback_policy/README.md):
  70 offline checks pass. This code does not qualify models or enforce backend
  budgets; Graph GA logic remains an offline development option, not a live route
  authorized in these cases.
- [SB202190 shared preparation and paired assignments](specialist/feedback-v2/evaluation/matched-v1/case-sb202190-v1/arms-v1/README.md):
  the same starting evidence, scientific choices and observable allowances for
  the base agent and specialist; the common evaluation adapter has seven passing
  checks. Source snapshots contain no service credentials or raw job archives.
- [Completed feedback-pilot review](results/p38-refinement-feedback-completion-review.md)
  and [development-pair comparison](results/sb202190-development-pair-review.md):
  execution is demonstrated; specialist selection benefit is not. Both paired
  arms chose the same action and eight-molecule panel. BASE's final service job
  failed; the specialist assessed eight slots. Neither completed ten slots.
- [Framework approval issue](research/agent-scientist-subagent-approval-issue.md):
  the default noninteractive denial was misleadingly reported as user denial;
  the local temporary workaround is not a framework fix.

Private inputs, raw poses/downloads, profiles, credentials and compiled caches
remain outside this source publication. Historical run manifests preserve their
original hashes, including excluded local cache members where applicable; see
the [publication inventory](results/publication-20261112.json). The archived
case tasks require their original local inputs and a new explicit assignment;
cloning this source alone does not install a role or authorize/reproduce a run.

## Historical work — 4 November 2026

The [development workflow](workflow/README.md) implements one CReM investigation:
the specialist chooses a parent and fragment-source library, the owning host
validates the request and uses the original connector, and the environment retains
results for the next decision. The optimization skill and CReM reference are
actually injected into the named specialist. Private state supports bounded
execution and resume. The profile-local entry plugin is installed for testing;
Agent Scientist source and Git history were not changed.

The [main-agent entry instructions](integration/README.md) explain the prompt or
Markdown-task flow and provide the exact task file for a first test. The native
plugin is installed in the local CLI profile; open a new conversation to load its
saved-specialist snapshot.

The [current validation report](results/optimization-v1-validation.md) separates
software checks, actual model reasoning, live scientific jobs and decision controls.
The development campaign stopped after three generation jobs including one shared
prior batch: **790 distinct structures including the reference, zero qualifying
candidates**. A paired first-decision control chose the same action with and
without the specialist. This is working execution evidence, not evidence that the
specialist improves optimization.

## Historical work — 3 November 2026

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
