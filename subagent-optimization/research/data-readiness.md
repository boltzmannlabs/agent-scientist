# Real-data prerequisites for the first specialist comparison

Date: 2026-11-03. Tracking: [agent-scientist#33](https://github.com/boltzmannlabs/agent-scientist/issues/33).

The first proposed action is choosing an approved, untried CReM input library
from contextual evidence. The new intake audit checks file/structure identities;
it supplies no scientific edit annotations and approves no actions.

The subsequent [structural alternatives study](library-alternatives/README.md)
has now prepared three traceable ChEMBL source cohorts and compared actual local
CReM fragment databases/reference lookups. It establishes candidate structural
alternatives, while scientific annotations, useful library cards and deployment
qualification remain pending. The earlier three-file intake record below is a
separate snapshot, not the inventory of these new source cohorts.

## What the supplied files can establish

[Candidate manifest](library-candidates.json) records a bounded local inspection
of three files, their exact byte hashes, installed RDKit version, canonical-input
counts and pairwise comparison. No raw structures are copied into this branch.

- CReM's bundled CSV and SMI are four-row examples of uncertain provenance. Keep
  both quarantined as examples. Parsing them does not make them a research library.
- The Graph GA file named `ZINC_first_1000.smi` is a potential intake source only.
  Its name is not evidence of release, selection criteria or data-use terms. It
  needs provenance review and an explicitly reviewed CSV conversion before use
  through the public CReM route.
- Larger REINVENT and MOSES training files were found during the source survey.
  They are not chemically audited or selected as campaign libraries here. Training
  corpora and their embedded split labels are not automatically evaluation tasks.

The generated manifest is an intake record, not a ready-to-run policy manifest.
All `available_for_policy` flags remain false; the approved asset count is zero.
Under the recorded protocol, both examples have the same four unique parsed
structures and order, despite different file bytes. The ZINC-named file has 1,000
unique parsed structures. None of the three has invalid or unsupported rows in
this audit. These counts establish parsing results, not suitability for the task.

## Information needed from the SMEs

For one small, feasible comparison, provide:

1. **Library provenance and intended use:** source/release, acquisition record,
   allowed use, selection criteria and any exclusions. Review the exact file and
   molecule set, including salt/stereo/charge handling. Identify at least two
   genuinely different plausible library choices; do not infer difference from
   filenames or byte hashes alone.
2. **Versioned chemical definitions:** what each edit family means in the selected
   parent/site/context, with a reviewed mapping from original parent to product.
   Mark multi-edit, ambiguous mapping, incompatible form and out-of-scope cases
   explicitly. A maximum common substructure alone does not prove an isolated edit.
3. **Evidence and library cards:** a few reviewed supporting pairs and
   counterexamples, and the basis for expecting each library to supply the intended
   transformations. A card is a hypothesis to test against actual products; it
   cannot guarantee an attachment site, retained scaffold or specific edit.

These inputs can be small. Establish a defensible first case before curating a
large ontology or library portfolio. Agent-written hypotheses are not SME reviews.

## What the AI implementation owns

Bind each reviewed subject to its asset-content hash, normalized-input hash and
policy version, context-definition hash, edit-family-definition hash and mapping
hash. `verify_review_binding` detects stale records. Actual reviewer identity,
authorization, provenance and file integrity must be verified by the host/review
process before any approval is imported; a JSON boolean is not that process.

Keep identity, pair annotation, score import and tool execution as reusable checked
code. The specialist should reason over a focused evidence packet and recommend
an investigation with rationale, counterexamples and reversal conditions. The
main agent retains orchestration, and the environment owns authoritative state
and actual assessment. This avoids two agents maintaining conflicting histories.

Freeze development/evaluation tasks and decision rules before comparison. Give
the plain main agent, equally guided main agent and delegated specialist the same
admitted evidence, assets, tools, stopping rules and resource accounting. This
tests scientific reasoning and any delegation benefit separately from better
information or extra tool access.

## Remaining execution qualifications

Before a real comparison, qualify the deployed input/model translation and output
units, actual CReM fragment preparation and overlap, tool availability, native
delegation permissions and cost accounting. Equal jobs do not imply equal internal
generation/prediction work. Temporary local fragment databases and lookup material
were qualified in the subsequent study; no platform service, candidate generation,
property-prediction campaign, model training or molecular improvement is established.
