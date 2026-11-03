# Small-Molecule Specialist Subagent

Tracking issue: [agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33)
Original research tracking: [science-environments#89](https://github.com/boltzmannlabs/science-environments/issues/89)
Related environment issue: https://github.com/boltzmannlabs/science-environments/issues/46
Status: Proposed

## Objective

Develop and evaluate one specialist subagent that improves scientific
decision-making within a molecular-optimisation workflow, using the
existing Agent Scientist tools and lead-optimisation environment.

## Planned Work

1. Review one existing molecular-optimisation workflow.
2. Identify a useful scientific decision that the specialist should own.
3. Check which decisions the existing agent and optimisation tools already handle.
4. Define the specialist's responsibilities, inputs, outputs and invocation conditions.
5. Design focused context handling and reusable supporting components.
6. Integrate through supported Agent Scientist delegation interfaces.
7. Compare the base agent, the main agent using the same guidance,
   and the specialist-assisted agent.

## Evaluation Approach

Use the same scientific task, tool access and agreed resource accounting
across comparisons.

Assess task success, scientific decision quality, redundant evaluations,
completion time and total parent-plus-child reasoning cost.

Scientific improvement remains untested.

## Daily Progress

### 2026-11-02

**Completed**
- Created the original tracking issue [science-environments#89](https://github.com/boltzmannlabs/science-environments/issues/89).
- Created a separate working folder for the BoltChem branch.
- Reviewed the DRD2 task, its saved execution review and the existing scientific
  progress view; recorded the [initial workflow review](workflow-review.md).
- Inspected Graph GA, Mars Plus and REINVENT request contracts for possible
  external controls. Live execution and internal optimiser behaviour remain
  unqualified.

**Next**
- Select one useful externally controllable scientific decision, checking that
  the chosen optimiser does not already handle it internally.
- Decide whether the existing task can measure that contribution and define the
  specialist comparison with common environment support.

**Open Questions**
- Which useful decisions can we control through the available tools?
- Which decisions do the optimisation tools already handle internally?
- What context does the specialist need for a justified recommendation?
- Which task can meaningfully measure the specialist's contribution?

### 2026-11-03

**Completed**
- Reviewed supplied v5 Graph GA internals and the CReM library-input path.
- Investigated three scientific directions: context-conditioned edit transfer,
  hypothesis-discriminating panels and allocation across chemical regions.
- Selected untried fragment-library choice as a candidate externally controllable
  workflow; scientific assets and actual service behaviour remain to be qualified.
- Implemented a deterministic contextual-family coverage baseline and a fixed-order
  reference with identical inputs. Artificial histories control timing/counts and
  change only observations; the contextual choice changes while fixed order does not.
- Added asset-content binding, equal-content alias protection, annotation conflict
  handling, deduplication, exact task rules, first-success/terminal safeguards and
  serial pending-attempt handling after independent AI-subagent review.
- Included the earlier reusable offline context/advisory-contract reference.
- Recorded actual software checks in [validation](../results/software-validation.json).
- Added a bounded local RDKit intake audit and immutable review-binding check.
  Normalized molecule-set aliases now cannot be selected as untried libraries.
- Inspected three real bundled files without exporting structures or running
  predictions. Recorded metadata in [candidate intake](library-candidates.json);
  no file has provenance/family approval or policy availability.
- Documented the exact [SME inputs and execution qualifications](data-readiness.md)
  needed before a real specialist comparison. Independent review found strict
  parsing/stereo-identity issues; regression checks cover the corrections.

**Current status**
- Offline helpers and the first local [saved-specialist development bundle](../specialist/README.md)
  exist. It supplies scientific instructions, gated evidence handoff, exact
  citation/action/freshness checks and a separate native fixture canary.
  Actual LLM instruction-following and improved scientific outcomes are untested.
- Policy/context fixtures are artificial; library intake uses local real files.
  Known archived cases are development material;
  no new scientific job, scoring campaign or training was run for this contribution.
- Work is maintained in the agent-scientist `subagent-optimization` branch after the authorized repository migration.
- The user explicitly authorized this repository migration and publication.
  Later publication still requires user authorization. No real profile has been installed by this work.
- Prepared three 20-source ChEMBL cohorts under a protocol saved before structure
  acquisition. Verified local v5 CReM material and reference lookups; all assets
  remain pending scientific review. [Study and limitations](library-alternatives/README.md).
- Implemented a standard greedy maximum-coverage planning baseline. A worked
  hypothetical case uses actual structural data; fixed ordering matches its
  choice, so no agent, molecular-quality or broad policy advantage is shown.

**Next**
- Qualify real library assets, actual fragment-material identities and
  reviewed parent/site/context/family annotations with SME input.
- Confirm actual model-bundle/units and service limits; distinguish native
  fixture checks from actual provider/scientific qualification.
- Test evidence-linked specialist reasoning against this baseline and equally
  guided main-agent reasoning under a prospectively agreed evaluation protocol.

**Open questions**
- Do approved libraries actually enrich the edit families described by their cards?
- Does contextual scientific reasoning improve over the simple transfer heuristic?
- Does separate delegation help enough to justify its reasoning/context overhead?
- How should internal generation/model work be measured fairly across library actions?
