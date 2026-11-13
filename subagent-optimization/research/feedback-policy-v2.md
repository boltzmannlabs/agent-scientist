# Feedback-guided small-molecule investigation — v2 proposal

Tracking issue: agent-scientist#33. Status: capability direction approved;
offline decision component implemented; scientific setup and allocation remain
unapproved. This document does not authorize a profile update or live scientific
execution. The separately approved offline component and reproduction instructions
are in [prototype/feedback_policy](../prototype/feedback_policy/README.md).

## Goal and design choice

Build one reusable policy that uses molecular observations to choose a supported
next scientific action. Test candidate quality at a fixed observable evaluation
allowance as the primary claim. Test delegation value separately.

Instructions alone have not demonstrated an advantage. Larger pools can improve
scores through additional search opportunity. Fixed-pool selection is a useful
component, but cannot establish better molecular refinement. We therefore choose
an evidence-guided intervention policy, conditional on a feasible follow-up. This
is a development hypothesis, not a promise of improved results.

First scope: one generation, assessment and supported follow-up workflow. An
initial episode plus up to two follow-ups is a proposed ceiling, not three
mandatory jobs. A decision episode and a scientific job are different units.
Existing completed p38 campaigns remain closed development evidence.

The current first scientific case is
[PAMPA refinement](pampa-first-refinement.md), replacing the conditional
Solubility proposal at the user's request. The user-run Property_Prediction test
returned binary labels, so common eligibility is PAMPA class 1. The optimizer's
score boundary remains separately 0.5. Readiness delivery is demonstrated;
deployed provenance limitations and run parameters remain explicit. Earlier evidence is retained
in [the historical proposal](first-refinement-case.md); its -4 cutoff is inactive.
No completed campaign or active profile is changed.

## Inputs and responsibilities

The main agent supplies objectives, reference/target inputs, property methods and
constraints, available actions and allowance. It delegates the investigation
without prescribing each subsequent experiment.

The specialist receives a compact observation snapshot: candidate identities and
ancestry; actual measurements with methods, units and missing statuses; relevant
pose/preparation findings; attempted actions and returned identity overlap;
available controls; and remaining resources. Full evidence remains in referenced
artifacts. Summaries must retain decision-relevant exceptions and missing evidence.

Existing code owns parsing, calculations, identity joins and resource arithmetic.
Existing connectors own submission and collection. The specialist owns scientific
action selection. No new HTTP client, predictor or agent per tool is proposed.

## Proposed observation-to-action procedure

1. Reconcile pending or ambiguously accepted work before another submission.
   Closed experiments are not reopened by replaying their task files.
2. Identify the decision question: an unmet mandatory constraint, a quality
   improvement opportunity, missing trustworthy evidence, or exhausted useful
   actions. A control score is not an invented success cutoff.
3. Construct feasible options from the action menu. Remove options whose inputs,
   objective meanings or actual controls are unavailable. STOP is always an
   option. Unknown prerequisites are not invented values.
4. Relate options to measured property gaps, candidate families, available
   related-molecule comparisons and relevant pose evidence. Associations support
   hypotheses, not causal claims. More shapes or a different library is not
   automatically better. Distinguish exploitation, exploration and diagnostics.
5. Select an intervention using the candidate rules below, with a prospective
   rationale and an observation that could support or weaken it. If no grounded
   preference exists, identify the choice as exploration. These rules remain
   under review; this is not an implemented or validated scientific policy.
6. Execute the supported action through existing infrastructure. Assess actual
   products using the common evaluator. Retain failures and unintended changes,
   including any failure to retain a desired core.
7. Update evidence, best eligible candidates, attempted neighborhoods and remaining
   allowance. Repeated outputs require reassessment, not automatic top-ups. Then
   continue, choose another supported intervention, request evidence, or stop.

For each important decision record: goal; relevant observations; feasible options;
chosen action and supported controls; rationale; expected informative evidence;
and what would change the decision. A chemical causal story is not mandatory.

## Candidate decision rules for the first policy

This is a proposed, interpretable starting policy, not a claim of optimal search.
An established hosted model must act as a declared objective, hard constraint or
secondary objective. Its predictions cannot be attached merely as unused data.
The exact model, bounds, direction and ordering remain task inputs to approve.

### State and parent choice

Keep the original task reference separate from the current generation parent.
Where the task requires similarity to the original reference, changing the parent
does not change that comparison reference.

Preserve every record, but select parents only from validated identities with the
measurements required by the declared selection rule. Missing evidence is unknown,
not a zero or an automatic poor score. A permitted assessment can resolve it.

If qualifying parents exist, use the task's declared objective ordering; break
exact ties by canonical molecular identity. If none qualify, construct per-
constraint violation vectors: zero for a satisfied interval, otherwise distance
to the violated bound in that metric's own units. Keep their nondominated frontier
without summing incompatible units. Choose within that frontier using declared
constraint priorities; if no priorities distinguish the options, use seeded
uniform exploration after sorting canonical identities. Seed and tie rules must
be recorded before outcomes. This exploratory choice is not evidence of a
scientifically superior parent.

### Eligible actions and route selection

| Situation | Proposed rule |
| --- | --- |
| Existing scientific work is pending or acceptance is unclear | WAIT or reconcile its receipt. No replacement submission. |
| A mandatory input/measurement is unusable | Resolve the specific issue within permitted operations, or return its prerequisite. Do not silently change objectives. |
| No allowance remains for the proposed work plus required final assessment | STOP; do not spend the final-assessment reserve. |
| A parent/library intervention is proposed | CReM is eligible only with an admitted parent/library, established objective configuration and an evidence-linked neighborhood hypothesis or explicit exploration question. The library's contents and prior products must support what is actually claimed. |
| Iterative hosted-property search is proposed | Graph GA is eligible only with a valid seed, approved count/step profile, established scoring terms and evidence that intended predictors are available. Nonempty model fields alone are insufficient. |
| Only one eligible route addresses the current decision question | Select that route as the available test, not as a proven best optimizer. |
| Both routes address the question | Apply any task-approved evidence preference. Otherwise choose uniformly between eligible routes using the declared seed, then uniformly among that route's deduplicated eligible cards in canonical order. Extra libraries/configuration aliases must not increase a route's selection weight. Do not invent expected improvement values or always prefer CReM. |
| No useful admissible test remains, or the task's stopping condition is reached | STOP with the unresolved scientific conclusion. Passing property bounds alone does not complete a quality-maximization task. |

Each action card binds the current question, evidence, parent identity, exact
public controls, objective version, library/configuration identity and a result
that would support or weaken the hypothesis. A rationale is written before the
result, not reconstructed afterward. Input aliases and row order must not create
new scientific actions. Exact repeated requests require a stated replication or
justified stochastic-resampling question within the authorized allowance; they
are not automatically novel exploration. A specialist may choose such a permitted
action without asking the user to prescribe each next experiment.

No evidence preference is currently approved. Seeded exploration is a transparent
default for unresolved choices, not the scientific contribution by itself. A
learned action-ranking model is not proposed without supporting data. Later
evidence-based ranking revisions require their own prospective comparison.

### Proposed bottleneck-to-action preference

The following evidence preference replaces unguided route selection when its
conditions hold. It is an unvalidated heuristic to test, not an established
advantage over the base agent:

| Observed bottleneck | Preferred supported intervention and reasoning | Evidence weakening the choice |
| --- | --- | --- |
| Measured selected-property failures prevent otherwise admissible candidates from qualifying | Prefer qualified Graph GA when its intended PAMPA classification reward, seed and request profile are established. It addresses this deficit through its classification step; CReM remains an alternative with a supported parent/library hypothesis. | No eligibility gain, other constraints worsen, or unavailable/unsupported predictions drive the apparent gain. |
| An eligible lead or eligible candidates support a docking-improvement investigation, with allowance remaining | Prefer a CReM parent/library intervention only when observed parent results and library contents support a specific neighborhood hypothesis. The outer Vina assessment tests docking progress; an already-satisfied PAMPA classification bonus does not directly optimize docking. | The intended changes are absent, products repeat prior identities, eligibility is lost, or docking does not improve. |
| QED or Crippen LogP is limiting | Select only a card whose actual controls or supported neighborhood hypothesis address that specific gap; otherwise label the action exploration or resolve a prerequisite. | Products do not address the gap or lose other mandatory conditions. |
| Decision-critical candidate evidence is missing | Prefer a bounded supported assessment when its result can distinguish the available actions. Separate this from one-time host/service qualification. | The assessment cannot resolve the choice or its cost exceeds the remaining allowance. |

Ten distinct eligible candidates are an output-completeness requirement, not
evidence of a selected-property deficit. Zero new candidates at initialization,
insufficient emissions, missing predictions or failed docking do not establish
that deficit. If the supplied lead is already feasible, the investigation may
start with a supported docking-improvement hypothesis while seeking new eligible
identities. If failures have several causes, retain their separate counts and
choose a card addressing the observed cause rather than assuming a PAMPA failure.

These are conditions, not a compulsory optimizer sequence. A CReM quality-mode
preference requires a real admissible library hypothesis; it is not a universal
claim that CReM beats GA. If the preferred route is unavailable, consider the
other admissible cards or STOP. One unsuccessful batch does not force a switch.
Use seeded exploration only when no grounded preference distinguishes the
remaining options. Record the options, chosen controls, rationale and
counterevidence before execution. A cheap seeded/fixed-routing control can help
test this heuristic without requiring another simultaneous live arm.

### Update from returned results

Record these outcome dimensions separately; they are not mutually exclusive.
A batch may improve one objective, weaken a structural hypothesis and still
contain missing measurements. Missing data remain explicit in every summary:

- **Progress:** objective improvement under the task's predeclared rule, with
  completeness and constraint compliance retained. Search progress is distinct
  from the final committed-panel endpoint.
- **Counterevidence:** assessable new molecules were produced, but the intended
  change was absent, constraints worsened, or the tested hypothesis did not
  produce the expected outcome. This can inform the next action; it does not
  prove the whole optimizer is unsuitable.
- **No new information:** duplicate-only products under the same measurement
  conditions, or outputs that cannot answer the declared question. Reconsider
  the exact action before spending again. Authorized state/seed replication is
  different from new-molecule discovery.
- **Unresolved evidence:** failed preparation, missing predictions, unknown
  objective terms or unverified ancestry. Retain missing values and investigate
  only where the task permits; never convert them into success or poor affinity.

Keep intended interventions, actual public controls and measured product changes
in separate fields. A library change does not establish a particular edit,
reduced flexibility or core preservation. Multiple changed features remain
confounded; source library membership does not uniquely identify fragment ancestry.

After each result, rebuild parent and eligible-action choices using the same
rules. Preserve the best eligible observations and unsuccessful hypotheses.
Do not switch CReM to Graph GA merely because one batch had no score gain. The
next action must address the updated question and remaining useful options.

### Required decision-mechanics cases

1. Equivalent evidence with renamed presentation IDs or reordered rows gives an
   equivalent scientific choice under the same declared seed.
2. Relevant property evidence changes parent eligibility or the action rationale
   appropriately; irrelevant presentation changes do not.
3. A valid GA payload with missing predictor evidence does not become a claim of
   objective-qualified optimization. No model term is silently removed.
4. CReM products lacking the intended structural change leave that hypothesis
   unsupported, despite a successful job.
5. Novel non-improving products and duplicate-only products receive different
   evidence classifications.
6. All property bounds pass while the quality objective remains: no automatic
   declaration of goal achievement.
7. Pending acceptance or insufficient final-assessment reserve prevents another
   submission without erasing existing receipts or resetting allowances.

These are future functional checks, not tests executed in this planning review,
and cannot establish molecular improvement. Source/configuration qualification,
exact selection priorities and the live evaluation protocol remain unresolved.

## Action feasibility

| Action | Exposed controls | Evidence-dependent use | Readiness and limits |
| --- | --- | --- | --- |
| Assess supplied candidates | Task's declared preparation, scorer and measurements | Resolve unknown candidate quality or a specific uncertainty | Prior p38 execution demonstrated the route. New diagnostics still require a prospective question and allowance. |
| Structure-Based Generator | `protein_Path`, `no_of_shapes`, `no_of_decodings`; optional documented property models | Change sampling allocation for a stated exploration question | Previously executed live. No exposed parent SMILES, generation seed, protected atoms or direct docking reward. Repeated-output mechanism remains unknown. |
| Fragment-Based Optimization / CReM | `ref_mol`, uploaded `library_path`, documented property-model selections | Choose a parent and fragment-source library to test a chemical-neighborhood hypothesis | Conditional. Previously executed with hosted properties. Source enumerates growth/mutation before optional property prediction; no native docking-feedback loop is shown. The future request mode, objective and assets need establishing. |
| Graph GA | `smiles`, `n_mols`, `n_steps`, documented property-model selections | Select a seed and search allocation for an established hosted-property objective | Contract/source reviewed; not live-qualified here. Source requires nonempty properties and uses hosted MPO. No verified native docking reward or arbitrary protected-atom control. |
| STOP / return a specific prerequisite | No scientific submission | No feasible useful intervention, completed task, exhausted allowance or unresolved acceptance | Valid action; not proof the chemical problem is impossible. |

Public fields differ from internal worker fields such as `attribute`; internal
fields must not be copied into unsupported public requests. CReM radii and modes
are worker behavior, not exposed request controls. Source recognizes `*` for GROW
attachment handling, but MUTATE runs separately; this does not qualify a public
edit mask or guaranteed protected-core preservation. Measure retention explicitly.

Hosted Lipophilicity is not assumed to equal Crippen LogP. A selected platform
Vina evaluator can assess returned products without becoming an optimizer's
internal reward. Do not choose
an unrelated property model merely to make a request acceptable.

Further source inspection narrows the prerequisite: CReM's property_prediction
function explicitly returns the generated table unchanged for an empty attribute
list. Its public schema requires only ref_mol and library_path. This supports a
source-level proposal-only mode, not proof that the deployed connector/consumer
accepts it. Graph GA explicitly rejects empty properties and is different.

The user previously required a property model to provide an optimization
objective. Retain that interpretation unless explicitly changed. For CReM, the
outer policy can use an established model's predictions when choosing subsequent
parents/libraries; the enumeration worker need not contain the feedback loop.
Model meaning, supported bounds, authorization and deployed request behavior must
be established before those values guide decisions.

An informational-only property model with documented empty bounds is a different,
UNAPPROVED proposed configuration. In that proposal the outer objective would be
the selected docking score with QED/Crippen checks. Merely attaching a model does not satisfy the prior
optimization-objective requirement. Do not use this configuration without explicit
agreement on the changed interpretation. Do not invent a model, use unknown-scale
values as constraints, or assume empty bounds are valid for Graph GA.

A model-free CReM configuration is a separate possibility, not the default here.
It would require explicit acceptance of a change to the earlier model requirement,
alongside deployed qualification. Neither configuration has been newly executed.

A complete p38 refinement branch under the proposed platform-docking/property
objective is not yet qualified. Establish an appropriate supported objective/request setup
through a configuration consistent with the user's model requirement, or propose
a separately scoped tool capability.
Native docking reward support is not a prerequisite. If a useful follow-up cannot
be established, revise the live scope. Offline mechanics can still be developed
with explicit unavailable-capability states. A sample-count change
alone will not be labelled chemical refinement.

## Acceptance and evaluation

Functional acceptance requires supported requests; bounded autonomous completion;
appropriate response to relevant counterevidence; stability to irrelevant label or
presentation changes; preserved evidence; and correct continuation/accounting.
Changing actions after an artificial perturbation alone does not prove usefulness.

Stage the comparison: base versus base with policy first, then main-agent policy
versus delegated policy. Share scientific inputs, actions, helpers, model settings
and declared allowances. This separates policy value from delegation value.

For the new p38 development case, choose one qualified Boltzmann Vina variant
and use the complete ten-slot mean native docking score as the proposed primary
quality metric. Record its sign, units, preparation, settings and aggregation;
both approaches must use the same evaluator. Smina was local historical
evaluation, not a Boltzmann platform capability. Changing this scorer requires
a fresh matched comparison, not reusing old Smina scores as the new baseline.
Keep DiffDock pose-confidence outputs separate from Vina energy scores.
Use the same proposed feasibility-first panel rule in both approaches:

1. Eligibility requires a source-supported PAMPA class-1 result from the common
   Property_Prediction assessor, QED >= 0.5 and Crippen
   LogP 0–5 inclusive, with valid identities and the required measurements.
   Missing required evidence is unresolved, not a pass. Exclude the supplied
   starting lead and SB2 control from the designed panel; retain their recoveries.
2. Deduplicate using the same declared stereochemistry-aware identity procedure.
   Rank eligible, search-assessed new identities by native Vina score, lower
   preferred; break exact ties by canonical identity. This shared calculation is
   available to the base agent too and is not specialist intelligence.
3. Commit ten identities before fresh final assessment. If fewer qualify,
   preserve unfilled slots. Final failures or lost eligibility remain recorded;
   no replacement or automatic top-up is allowed.
4. Report qualifying endpoints out of ten, all three constraint outcomes and
   failures. Report the primary complete-panel mean only when all ten have valid
   final measurements. Never average only successful slots.

Completion and joint eligibility take priority over docking quality. A more
favorable mean cannot establish benefit with worse completion or compliance.
Compare docking quality when both panels are complete and fully eligible;
eligibility gains are a separate outcome, not an invented docking improvement.
These are proposed rules for the NEW case, not retroactive changes to the older
unfiltered-panel experiments. The final shortlist uses the same frozen ordering.

Before live use, declare a common candidate-assessment allocation rule. If a
batch exceeds its remaining search allowance, use a prospectively seeded uniform
subset of sorted, deduplicated admitted identities without looking at their
unmeasured docking outcomes. Preserve the full returned batch, excluded records
and subset seed. Count failed assessments and reserve final-assessment capacity.
Equal docking allowances do not equal total compute: also fix route profiles
covering GA steps/output requests and CReM library scope, and disclose hidden work.

Efficiency includes actual generation/evaluation attempts, failures, elapsed time
and combined parent/child model use. Equal jobs are not equal hidden compute.
Context/reuse measures include avoidable rereads/recalculations, missing essential
evidence and recovery correctness. Parent context length alone is not an efficiency
result. Separate functional completion, descriptive improvement and generalization.

Existing p38 artifacts and fixed-pool replay are development/component evidence,
not prospective validation of new chemistry or independent run replicates. Ties
and losses remain results. No broad claim follows from this single target.

## Separate development and live-evaluation requirements

1. **Offline component:** approve or revise the proposed objective priorities,
   panel rule, bottleneck preferences, exploration and accounting rules. Build
   the observation-to-action component and seven functional cases above with
   explicit unavailable-method states. No model or service execution is needed.
2. **One-time host qualification before scientific use:** establish the selected
   PAMPA output kind and method mapping; use common assessor labels for both
   arms and keep optimizer-native scores separate. Retain the available
   source-supported semantics and unknown deployed revision as stated limitations.
   Use the completed two-ligand Vina readiness evidence and freeze
   the common comparison configuration. Use available
   documentation and execution evidence rather than repeatedly requiring private
   metadata inside children. An accepted GA request alone does not prove an active
   property objective: require available loading evidence and finite intended
   property outputs, otherwise mark the objective unresolved.
3. **Before live comparison:** freeze parent/library assets, route profiles,
   numerical observable allowances, subset seed, failure/cache treatment, final
   reserves, stopping rules, repeats and minimum useful gain/uncertainty rule.
   Panel SD is not uncertainty across independent policy runs; identical returned
   batches do not add independent generation evidence.
4. **Later studies:** test delegation/context efficiency separately and then
   generalization to unseen cases. Neither should delay the offline component.

No universal improvement percentage or invented provider threshold is supplied.
Record scientific methods and policy versions. Document interface-only changes;
review material scientific changes. Inaccessible host metadata must not repeatedly
become a child-level scientific prerequisite.

## Source evidence reviewed

- Local Agent Scientist `plugins/boltzmann/skills/boltzmann-tools/references/modules/small-molecule-structure-generation.md`: SBG public inputs, line 22 onward.
- Same module directory, `small-molecule-optimization.md`: CReM controls at line 22 and Graph GA controls at line 234.
- Same module directory, `small-molecule-toolbox.md`: platform Vina variants and DiffDock, including pose-confidence interpretation.
- `BOLTCHEM-FEATURES/v5/Molecule_Generation/Generation/ligann_new/ligann.py:81`: sampling loops.
- `BOLTCHEM-FEATURES/v5/Molecule Optimzation/crem/crem_main.py:98`: enumeration and subsequent prediction; `crem/utils/data_processing.py:137`: attachment handling.
- `BOLTCHEM-FEATURES/v5/Molecule Optimzation/crem/prop_inference_new/bpp_main.py:142`: optional prediction and empty-attribute passthrough at the end of the function.
- `BOLTCHEM-FEATURES/v5/Molecule Optimzation/Graph_GA/main.py:211`: mandatory properties; line 292 onward: hosted MPO search.
- Existing `specialist/optimization-v1`, `prototype/library_policy`, and `results/optimization-v1-validation.md`: starting material and prior limited/negative evidence.

Source inspection does not certify deployed revision or current access. No source
scripts were executed and no scientific jobs were submitted during this review.
Source and adversarial reviews support the planning distinctions above. The
offline component now tests their logical behavior separately; neither source
review nor those functional tests establish a fully fixed live evaluation
contract or improved molecular outcomes.
