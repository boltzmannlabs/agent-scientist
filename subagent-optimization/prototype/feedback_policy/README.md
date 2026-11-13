# Offline feedback-policy component

Tracking: agent-scientist#33. **Implemented offline decision-policy prototype;
scientific usefulness unestablished.** Implements the proposed logical
contract in [feedback-policy-v2.md](../../research/feedback-policy-v2.md).
This is a component for the specialist, not an installed Agent Scientist role.
Subset/observation helpers have since supported bounded user-run cases; that
does not validate the prototype's route-choice heuristic. See the
[paired case review](../../results/sb202190-development-pair-review.md).

The current replacement property is **PAMPA**. The observed common-assessor output
is a binary label. Set property_metric="pampa", pampa_output_kind="class_label",
pampa_score_boundary=0.5 and label eligibility bounds 1..1 with an admitted label
method. Measurements must explicitly carry output_kind="class_label". An optimizer
score cannot populate that label field. Intermediate label values are unresolved.
The original class-score mode remains available for separately admitted score
methods. Separate route_objective_models allow CReM's proposed 0.5–1 window and GA's 0–0.5
classification-step configuration; they must not be blindly interchanged.
The original Solubility fixtures/default remain historical offline regression
coverage, not live authorization or an active physical-scale objective.
See [the PAMPA case](../../research/pampa-first-refinement.md).

## What it adds

The component takes a compact observation snapshot and a set of admitted actions.
It returns one recommendation with its goal, supporting evidence, alternatives,
actual proposed controls, and evidence that would weaken the hypothesis. Other
outcomes are WAIT, STOP and NEEDS_EVIDENCE. It uses existing observations; it does
not generate molecular predictions or create scientifically grounded library
hypotheses from an arbitrary file name.

| Observations | Implemented proposed preference |
| --- | --- |
| Feasible lead, no new candidates | Consider an admitted CReM docking-neighborhood hypothesis. Empty coverage alone is not a selected-property failure. |
| Otherwise-admissible candidates fail the selected property, eligible coverage is insufficient | Prefer qualified Graph GA cards targeting that deficit; PAMPA uses its classification step. |
| Parent evidence is insufficient | Prefer an admitted assessment that can resolve it. |
| No grounded preference among remaining actions | Seeded exploration, selecting the route before cards so extra libraries do not inflate route probability. |
| Pending/ambiguously accepted work | Wait on the existing receipt. |
| Final reserve cannot be retained, declared stopping condition, or no admissible action | Stop or report missing evidence. |

Passing property constraints alone does not stop quality optimization. A failed
batch does not automatically force a route switch. Parent choice follows feasible
Vina ranking or a nondominated constraint-violation frontier without adding
incompatible units. A justified replication is allowed; a fixed-seed repeat is
not automatically labelled stochastic exploration.
These route preferences are a hand-authored experimental heuristic. The source
code does not establish that either optimizer is scientifically superior.

## Boundaries and input contract

- **Host facts:** normalized stereochemistry-aware identities/SMILES, molecular
  validity, reference lead/control identities, method/units/precision-qualified
  measurements, scientific profile admission, model qualification and remaining
  observable allowances. The module checks supplied consistency, not authenticity.
- **Configuration:** `seed`, `panel_size`, `reference_roles`, three labelled
  `constraints`, a lower-is-better `quality` Vina method, optional constraint
  priorities and frozen public `objective_models` selections. No live model or
  numerical run allowance is approved by these files.
- **Snapshot:** task state, native job receipts/statuses, candidate observations,
  `attempted_action_keys`, and disjoint remaining generation/search/final-call
  allowances. Search/final counters count external docking/evaluation attempts,
  including failures; generation counters count submitted generation calls, not
  hidden worker proposals. The host derives disjoint search and final reserves
  from any common ceiling, persists the ledger and reserves work atomically
  before execution. It also checks time, financial and other service limits.
  This component only checks the supplied counters at recommendation time.
- **Action card:** admitted route/profile, parent, public-field payload, library
  material identity when applicable, targeted gap, hypothesis, counterevidence,
  evidence references and capped external search allocation. `qualified` and
  `objective_qualified` simulate host-established facts, never self-authorization.
  Admission covers the configured model semantics, steps and library scope.
- CReM/Graph GA proposals preserve documented fields. `assess` is an internal
  action description for a future shared evaluator adapter, not a Boltzmann API.
  Unsupported edit masks are rejected rather than turned into tool capabilities.
- Returned-count settings are not internal attempt/compute limits. Variable-sized
  batches use the shared seeded `assessment_subset` helper for the declared
  external allowance. The host must enforce it; the pure function cannot reserve
  capacity, prevent concurrent overspending or submit remote work.

Before live use, a host adapter must supply real qualified facts, validate the
current full connector schema and assets, persist decisions/receipts, enforce
all approved limits and use native upload/submit/status/download calls. Actual
prediction outputs must support the intended active objective; job success alone
does not establish it. No live profile, wrapper, backend or frozen study is changed.

## Recorded-observation and Vina adapters

`observations.py` now implements the next host boundary:

- `import_long_records` joins host registry and long measurement CSV records by
  candidate key **and canonical isomeric SMILES**. This adapter's
  `canonical_identity` column must contain that representation, not an opaque
  hash, because it is also used as the policy's SMILES. It does not canonicalize
  or independently validate the host's chemistry claims.
- It retains every original registry/measurement row, source hashes, phases,
  producer methods/units, failed values and unmapped metrics. Precise calculated
  QED/Crippen values remain separate from rounded generator annotations.
- Search/final observations do not overwrite one another. Contradictory records
  within a phase become unresolved; identical repeats retain provenance without
  independent-count inflation. Unknown methods/units remain unqualified.
- `prepare_basic_vina_csv` produces exactly `SMILES,NAMES` plus a bound ordered
  input manifest. `import_basic_vina_csv` uses the input ordinal with names/SMILES
  cross-checks, preserves every native pose and applies an explicit pose selection.
  CSV pose 0 maps to SDF pose 1 in the inspected source. Failed `Pose=-1,Score=100`
  records become failed/null, even though their raw score is finite.
- The Vina mapping defaults to unqualified. Actual method and selected-pose
  identity/score checks must be supplied by the host before values become usable.
  Source code alone does not prove the deployed output or scientific readiness.

`replay_archive.py` imports the reviewed p38 historical format after checking
the three selected source members against its recorded manifest. Manifest/member
reads are bounded inside the supplied bundle; referenced pose/model paths are
not followed. It writes only to a separate new directory. The archive remains
frozen, receives no action cards or restored allowances, and returns STOP.
It does not reconstruct or rejudge the old endpoint panel under new criteria.

The actual baseline import preserved 99 registry rows and 660 measurements.
There are no Solubility or platform-Vina observations in that archive. Historical
Smina values remain Smina; neither its native-Vina scoring setting nor shared
scoring lineage authorizes relabelling them.

## Shared evaluation and feedback

`select_panel` applies the same feasibility-first rule for either comparison arm:
three passing constraints, unique generated identities, excluded lead/control
recoveries, then ascending Vina score and canonical-identity ties. It returns ten
slots (or the supplied panel size), preserving nulls. Its digest detects a changed
selection against a retained digest; it is not immutable storage or proof that
final assessment occurred later. The host must persist the commitment first.

`summarize_final` reads only committed identities and keeps missing/failed slots.
Its completeness flag and mean describe measurement coverage; joint eligibility
is reported separately by `all_eligible` and `qualifying_slots`. It can therefore
return a measurement-only mean for ten scored but not all-eligible slots. That
is not an eligible-panel primary endpoint. The paired task uses a common
`evaluation_support.confirmed_panel_summary` adapter that suppresses the primary
mean unless all ten slots are confirmed eligible with valid final poses/scores.
Extra candidates cannot replace a failure.

`classify_batch` keeps progress, counterevidence, no-new-information and unresolved
evidence separate. Search progress means increased capped eligible coverage or a
more favorable retained full-panel mean. Improving slots below the single best
molecule counts. Historical lead/control roles remain excluded. Retained-pool
search evidence is distinct from fresh final assessment and from policy benefit.
An unverified intended change remains unresolved even if scores improve.
Differing observations for an existing identity are flagged as unresolved
conflicts and do not overwrite retained evidence. Repeated-state/seed measurements
need a separately declared host aggregation rule; a stronger rescore alone is not
new chemistry. Conflicting duplicate rows within one snapshot are rejected.

## Reproduce

From this directory, with Python 3 (standard library only):

```bash
python3 -B -m unittest -v test_feedback_policy test_observations test_pampa
python3 -B demo.py
```

All `fixtures.py` values are **artificial**, including identity/SMILES strings,
scores, allowances and qualification flags. They are deliberately unsuitable for
scientific execution. The demo exercises changed evidence, waiting, panel failures
and overlapping outcome dimensions. It does not inspect existing private runs,
load models, calculate descriptors, dock molecules, access credentials or network,
write campaign files, or call a scientific service.

Tests establish logical behavior only. The policy has not demonstrated better
molecules than a base agent. Model/Vina qualification, a bounded live comparison
and later delegation/context-efficiency evaluation remain separate work.
The combined suite currently passes 70 tests, including typed PAMPA label cases.
The synthetic native-Vina tests
qualify adapter mechanics, not a deployed service. See
[observation integration results](../../results/feedback-policy-v2-observation-integration.md)
and [platform readiness evidence](../../research/feedback-platform-readiness.md).
