
# References

Tracking issue: [agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33)
Original research tracking: [science-environments#89](https://github.com/boltzmannlabs/science-environments/issues/89)

## Framework and Delegation

- [Hermes advanced delegation](https://hermes-agent.nousresearch.com/docs/plugins/advanced-delegation)
  - Reference for model routing, profile routing and task delegation.

## Existing Environment

- [Small-molecule lead-optimisation environment — issue #46](https://github.com/boltzmannlabs/science-environments/issues/46)
  - Related environment development and tracking.

## Scientific Papers and Software

Additional reviewed references will be recorded here with their
relevance, useful ideas and limitations.

## Local Sources for the Initial Workflow Review — 2026-11-02

These are inspected working files, including local unpublished environment
changes. Their content is not established by a repository commit alone. They
were not copied into this tracking branch; reproduce the review against the
matching working files before relying on their interface details.

Science-environments root: `/home/boltzmann13/science-environments`.
Environment prefix: `environments/small-molecule-lead-optimization/`.

| Source under the environment prefix | Used for | SHA-256 |
| --- | --- | --- |
| `tasks/drd2/RUN_PROTOCOL.md` | Exact objective, stopping, ownership and original comparison | `5598688f4d755089a0da29ddfd95eafdff22746f46d0ec37f63ff57b9c759b8e` |
| `tasks/drd2/README.md` | Assessor meaning, fingerprint distinction and task scope | `dab8de47db5b11623cd89a29743104414d2b275f4a92d119651b6a961f2405bf` |
| `results/batch-evidence-task-review.json` | Saved single-task outcome and execution limitations | `ba1b1012abbe8b8c4bdb1241f995b654909a2cee982c3903e138380a1725f43a` |
| `src/leadopt_env/progress.py` | Existing evidence projection and absence of action selection | `c27c28af4547789db548236bccdade9ab30ad64908e7cc44d89304f33aeb1813` |

Agent Scientist root: `/home/boltzmann13/agent-scientist`.

- Source: `plugins/boltzmann/skills/boltzmann-tools/references/tool-contracts.v1.json`.
- SHA-256: `379043475affb384751b8b594ca755108c20bdfd80aa535ee19d7b6cd3ec7afd`.
- Used for documented Graph GA, Mars Plus and REINVENT inputs and limitations.
  Contract inspection does not establish live service readiness or deployed
  optimiser internals.

## Current Source Review — 2026-11-03

The supplied v5 CReM implementation consumes `ref_mol` and `library_path`, builds
the fragment database from the library, and retains its own GROW/MUTATE/radius
logic. Graph GA's worker controls and reward behaviour were also inspected.
Exact working-file hashes are in [source-inspection.json](source-inspection.json).
These hashes establish inspected source identity, not deployed build identity.

The intake extension also inspects CReM's duplicate-removal/header preparation and
fragment-database build scripts, recorded in the same source manifest. Canonical
input identity is not fragment-material identity: fragment preparation has its
own stereochemistry, radius, core and frequency conventions.

- [CReM primary documentation](https://crem.readthedocs.io/en/latest/): broad
  fragment databases can be built from molecular collections or obtained from
  ChEMBL-derived sources. A fragment source supplies chemical possibilities;
  target activity requires a separate appropriate evaluator. Upstream controls
  are not automatically exposed by the supplied hosted wrapper. No library for
  every target is assumed by the conditional first specialist study.

The [new structural study](library-alternatives/README.md) records ChEMBL 37
acquisition and source-level v5 material checks. Data terms are retained in its
[data notice](library-alternatives/DATA_NOTICE.md). Its current-release API snapshot
is hash-bound; it is not a guarantee the same query will return those bytes later.
The known greedy coverage algorithm is used as a planning baseline, not claimed
as a new scientific model or a validated molecular-discovery strategy.

- [RDKit chemistry API](https://www.rdkit.org/docs/source/rdkit.Chem.html)
  and [RDKit Book](https://www.rdkit.org/docs/RDKit_Book.html): primary references
  for parsing and molecular representations. The audit records its actual local
  version and parser/stereo settings; online documentation may describe a later
  release. No property-prediction model is invoked by canonicalization.

## Earlier External Reference Assessment — 2026-11-01

The [reuse register](reference-reuse.csv) and [source manifest](external-source-manifest.json)
retain four commit-pinned repository assessments from the earlier preparation.
They are dated reviews, not installed dependencies or a fresh audit of upstream.

- [MolClaw](https://github.com/InternScience/MolClaw/tree/c16be3a70deef4228f19930b4495ec2748fafa38): evidence-linked iterative investigation and recorded decisions. Do not import fixed rounds, task-threshold defaults or Pareto escape from hard constraints.
- [BioSymphony small molecules](https://github.com/BioSymphony/small-molecules/tree/fc1e639677572d6f95c41d4d8ca358716ce100c3): focused scientific references and module routing. It supplies guidance, not execution authority.
- [K-Dense medicinal chemist profile](https://github.com/K-Dense-AI/scientific-agents/tree/98c7fae46648724e1a43a1f2b207b0c82fcc462e/scientific-agents/medicinal-chemist): hypothesis-led analogue interpretation; profession wording does not establish scientific expertise or measured SAR.
- [K-Dense generative design](https://github.com/K-Dense-AI/drug-discovery-agent-skills/tree/d5d44a381ceb348b62149bbdec2d3043b2b41092/skills/generative-design): distinguish sampling, optimisation objectives and component results. Local REINVENT configuration is not a hosted service contract.

The earlier review recorded MIT root licences. Code/instruction licences do not
establish external model, data, dependency or service terms. No upstream package,
skill or executor was installed; the baseline code is an original implementation.
One earlier licence-text hash was not retained, as explicitly recorded in the
manifest. Recheck authoritative terms before actual copying or distribution of
upstream content.
