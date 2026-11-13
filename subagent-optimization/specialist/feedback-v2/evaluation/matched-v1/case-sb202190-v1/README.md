# SB202190 refinement case — proposed shared preparation

Tracking: agent-scientist#33. Prepared 12 November 2026.
Status: **offline case checks complete; no hosted outcome or execution authorization**.
The matched arm protocol is still proposed. This case does not reopen the
completed e072 investigation.

## Goal and choice

The goal is to compare how a capable base agent and the specialist choose one
refinement action from the same actual initial observations, tool choices and
observable allowances. First prepare that common evidence once; do not launch
both arms before it exists.

Options considered were reusing e072, choosing another target, and choosing a
different documented p38 lead. e072 is useful for regression but its outcomes
already informed development. Another target would also change receptor and
scoring preparation. Choose **SB202190** for a deliberately selected within-family
pilot: its target association is documented and the fixed p38 setup is reusable.
This is a feasibility choice, not evidence that it will improve or a representative
sample of leads. Do not replace the case after unfavorable hosted outcomes.

[ChEBI CHEBI:79090](https://www.ebi.ac.uk/chebi/CHEBI:79090) and
[PubChem CID 5169](https://pubchem.ncbi.nlm.nih.gov/compound/sb-202190) support the
identity and p38 association. [1A9U](https://www.rcsb.org/structure/1A9U) contains
SB203580/SB2, **not SB202190**. Retain native SB2 coordinates as the structural
reference. Any SB202190 coordinates will be prepared/predicted.

The lead and SB2 share a pyridinyl-imidazole family. This is not a scaffold
holdout, proof of novelty or generalization test. Existing p38 work also informed
the target setup and policy. Published biological association is case provenance,
not a new predicted or experimental outcome for our generated molecules.

## Explicit input representation

Use only this declared lead form in the proposed preparation:

```text
Oc1ccc(-c2nc(-c3ccncc3)c(-c3ccc(F)cc3)[nH]2)cc1
```

It was reconstructed from the ChEBI InChI using RDKit 2025.09.6, then written as
canonical isomeric SMILES. The complete source InChI, method and resulting hash
are recorded in [local_case_review.json](local_case_review.json).
Different imidazole tautomers can share its standard InChIKey; InChIKey equality
alone does not establish exact-form equality. This conversion selects a
reproducible input graph, not a proven preferred binding or protonation state.
Do not silently exchange forms, enumerate states or merge their outcomes.

Local descriptors: QED **0.574239**, Crippen LogP **4.6504**, 25 heavy atoms,
three rotatable bonds and no identified stereocentres. This passes only the
local QED/LogP conditions. Common PAMPA class, Vina Score and generated-product
eligibility remain unmeasured. Crippen LogP is not hosted Lipophilicity or
PubChem XLogP.

## Checks performed

- All nine located original candidate registries were checked through identity
  fields only. No exact-form or standard-InChIKey match was found, and no
  nonempty identity failed parsing. Registry hashes stayed unchanged. The report
  names the inspected files; this is only a local prior-exposure check.
- Existing receptor, native SB2 coordinates and all three source-library hashes
  matched their recorded values. No target-specific fragment applicability or
  product benefit is inferred from valid library files.
- Two proposed reference inputs are in
  [proposed_references.csv](proposed_references.csv): **SB202190 and SB2**.
  e072 is not an additional control or generation input in this new case.
- A separate evaluation critic supported packet-only preparation, emphasizing
  exact-form provenance, unknown PAMPA, the within-family limitation and
  retention of negative/partial outcomes. No scientific execution was reviewed
  or performed for this case.
- A separate execution critic reviewed the actual preparation task and prompt
  and found no critical blocker: the 3/40/42/42 ceilings, fixed inputs, subset
  commitment, scorer settings and stopping/collection rules agree. No extra
  readiness job or profile modification is required for this preparation.
- Local read-back checks passed for reference CSV shape/content, case JSON,
  script hash, all nine registry hashes, five asset hashes and relative document
  links. These are input/document checks, not scientific outcome validation.

Primary source fields were inspected through the web tool. Raw database files
were not archived; a direct shell PubChem request failed DNS resolution. Do not
describe the local JSON as an untouched database download.

Reproduce the local checks from the project root with:

```bash
/home/boltzmann13/drug_discovery_ml/ml_env/bin/python -B specialist/feedback-v2/evaluation/matched-v1/case-sb202190-v1/prepare_case.py
```

The script writes only the local case-review JSON and proposed reference CSV.
It performs no upload, prediction, generation, docking, profile edit or Git action.

## Next boundary

[PREPARATION_TASK.md](PREPARATION_TASK.md) specifies only the shared initial
packet: one mixed-library CReM attempt, an outcome-blind subset of up to 40
identities, common PAMPA and eligible-candidate Vina with the two references.
At most **three** user-authorized native submission attempts, no follow-up and
no final-panel request. [PREPARE_PROMPT.md](PREPARE_PROMPT.md) is a proposed
user-run instruction; merely saving it grants no service permission.

After preparation, freeze actual observations and failures before issuing arm
assignments. The [matched evaluation draft](../../../../../research/refinement-matched-evaluation-v1.md)
and [common guide](../COMMON_GUIDE.md) remain the comparison design. Approval
parity, access separation, model settings, arm order and collection rules still
need to be fixed for the arm runs. Same-profile new chats are procedural
separation, not an enforced isolation boundary. Do not silently change profiles
or describe an operationally asymmetric development test as an isolated benchmark.
