# Data sources and attribution

ChEMBL-derived structural data in `run-v1/*.csv`, `run-v1/*.smi`, source-ID lists
and fragment examples come from **ChEMBL release 37**, acquired on 3 November 2026.
Exact query, response hash, release-status metadata and retrieval time are in
`run-v1/curation.json`. ChEMBL data are available under
[CC Attribution-ShareAlike 3.0 Unported](https://creativecommons.org/licenses/by-sa/3.0/);
retain this attribution and applicable terms with redistributed derived data.
See the [official licensing statement](https://chembl.gitbook.io/chembl-interface-documentation/about#data-licensing).

Changes: bounded structure-only acquisition, RDKit canonicalization/deduplication,
structural filters, matched cohorts and supplied CReM fragmentation. No activity
labels were requested. These data establish neither experimental sample identity,
pharmacology nor independence from classifier training data.

The public starting structure is separately attributed to
[MolecularAI/transformer_rl, pinned source](https://github.com/MolecularAI/transformer_rl/blob/a0622fc2fe16812c7530bca20dcca9a9fd874513/support/example.json)
and [He et al., 2024](https://doi.org/10.1186/s13321-024-00887-0).
Its source and unspecified stereochemistry are retained in `run-v1/material.json`.
It is separate from the ChEMBL source cohorts.

The supplied tool implementation was executed locally, not copied here. Its file
hashes are in the material report. Data terms do not replace software licenses.
