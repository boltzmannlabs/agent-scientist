# Independent AI-subagent review — library intake extension

Date: 2026-11-03. Reviewer: separate `real_data_independent_review` AI subagent,
with read-only access. Scope: offline software and metadata intake; no human
scientific approval, deployed qualification or molecular-performance evaluation.

## Verdict

Accepted within that scope. No remaining blocker was reported.

The first review found that permissive RDKit parsing could discard trailing tokens
as a molecule name, and that unrecorded global stereo settings could alter identity.
The coordinator added explicit strict parser parameters, versioned stereo settings,
rejection of extended stereo and discarded tetrahedral annotations, and four
regression checks. The reviewer independently reran those four checks successfully.

The final review independently verified:

- All 14 software source hashes and 13 inspected-source hashes match the files.
- Regenerated intake metadata matches the saved report except for its timestamp.
- Both CReM examples have four unique parsed structures, different byte hashes,
  and identical normalized sets and first-occurrence sequences.
- The ZINC-named file has 1,000 unique parsed structures.
- Every intake asset remains unavailable; the approved count is zero.
- The recorded final suite reports 95 passing tests and zero skips: 32 policy,
  43 context and 20 audit. The reviewer did not rerun all 95 in the final pass.

Only the two CReM examples have a recorded pairwise overlap comparison. The alias
guard consumes host-trusted input identities; it does not authenticate metadata
or establish fragment-material equivalence, output novelty or service parity.

Provenance, data-use terms, authenticated SME annotations/cards, form conventions,
actual fragment overlap, deployed execution, leakage-controlled evaluation and
cost accounting remain open. No native specialist or scientific gain is established.

The reviewer changed no files and used no Git/network access, installations,
predictions, scientific jobs or raw-structure exports.
