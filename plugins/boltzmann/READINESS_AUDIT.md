# Boltzmann contract standardization — 2026-10-14

## Five enzyme integrations — 2026-10-22

The historical counts below describe the October 14 snapshot, not today's catalog.
Added callable canonical definitions, domain/module discovery, generated sheets,
complete advanced/template guides and file/limit rules for:

| Job | Domain/module | Latest recorded live reference outcome |
|---|---|---|
| `deepallo` | Protein Engineering / Enzyme Generation | Completed; three pocket predictions downloaded |
| `enzycontrol` | Protein Engineering / Enzyme Generation | Completed; ten backbone PDBs and summary downloaded |
| `Enzyme_RFD3` | Protein Engineering / Enzyme Generation | Accepted, then worker failed: `job_name` missing |
| `Catalytic_Geometry` | Protein Engineering / Protein Toolbox | Completed; 20 candidates / 40 geometry checks passed |
| `Mol_Probity` | Protein Engineering / Protein Toolbox | Accepted; last recorded status pending, no output |

No tool is blocked merely for missing contract details. Authentication, profile
access, invalid-input rejection and reviewed partial validation still apply.
RFD3's exact routing name was already correct; this integration does not claim
to repair its downstream worker failure. Existing pending/ambiguous jobs must
not be duplicated. No new scientific jobs were submitted during this integration.

The supplied three JSON files, sanitized bundle/notebook examples and API
snapshot were reconciled with observed submission outcomes. All five routes
use the existing helpers and no additional model tools or dependencies.
Node rejects Catalytic Geometry mapping CSV; the active contract uses JSON.
EnzyControl's required seed, Catalytic Geometry's required binding path,
MolProbity's conditional thresholds and all supplied RFD3 nested options are
represented. Notebook `"True"` is retained as historical evidence, not accepted
as a canonical lowercase `"true"`/`"false"` flag.

155 targeted tests passed across six files via `scripts/run_tests.sh`, including
localhost upload/submit/status, A→B→A authorization/receipt isolation, unchanged
wire payloads, no polling resubmission, inline threshold objects, JSON schemas,
invalid combinations, gzip handling, discovery and existing prompt stability.
These checks do not establish scientific validity or resolve worker deployment.
Structure-dependent chemistry, native contig parsing and diffusion schedule
validation remain disclosed specialized checks, not falsely claimed local checks.

See [complete usage and evidence guide](skills/boltzmann-tools/references/enzyme-tools-guide.md)
and [source provenance](contract_sources/enzyme-tools-2026-10-22/provenance.json).
Keys, live IDs, uploaded paths, signed URLs and bulk private artifacts are not
shipped. Generated backbones do not establish enzyme function; the geometry
reference checks user-defined preservation ranges, not catalytic activity.

## Enzyme CSV correction — 2026-10-19

The current public frontend bundle `main.5b329b08.js` declares exact `Seq_id`
and `Sequences` required columns for the `ENZ_PROP` credit checker. The canonical
`Enzymes.dataPath` rule now checks those headers and nonempty values before upload;
the previously documented `Sequence_ID` alias is not accepted. Differently named
columns require an explicitly reviewed copy, not a silent source-file rewrite.
The generated workflow sheet uses the same rule. Historical evidence is unchanged.

The frontend calculates credits separately with `tool="ENZ_PROP"`, the selected
property count, and input-mode information before creating the experiment. The
connector continues to use the published `/api/submit-job` contract; it does not
invent credit amounts or bypass that endpoint. The reported API response was
HTTP 500, `Failed to calculate credits`. The header incompatibility is established,
but its causal connection to that server exception is not independently verified.

After the owner explicitly approved one new production credit-path test, a reviewed
copy of the same three public enzyme sequences with the corrected header passed
upload validation and was accepted by `/api/submit-job` with a job ID. Exactly one
submission was made; the credit-calculation error did not recur. This establishes
acceptance for that corrected request, not completed predictions, an exact credit
charge, universal worker readiness, or the outcome of the older ambiguous attempt.
No automatic retry or follow-up scientific job was run. Credentials, private storage
references, and the user's experiment identifiers are not distributed in this repo.

145 focused tests passed through `scripts/run_tests.sh`, including invalid-header
rejection before upload despite best-effort approval, unchanged source bytes,
valid-header upload, A-to-B-to-A receipt isolation, and stale-receipt rejection.
Backend logs or a sanitized successful request comparison remain necessary if
credit calculation fails for another correctly headed request.

## Follow-up corrections — 2026-10-19

Owner-supplied recordings of the current product UI and its generated Python
requests reconciled eight Small Molecule Design contracts. These recordings
establish current UI serialization, not production worker acceptance or
scientific correctness.

- Custom Property Model ML and DL now require their exact `model_category`
  selectors; DL uses scalar `modelName="DL"`, while ML preserves the lowercase
  `automl` identifier in its model-name array. The unobserved historical
  `transformation` field is no longer accepted by these strict contracts.
- Butina preserves the current case-sensitive `tSNE` and `Min_Max` values.
- K-Means uses the plural wire key `no_of_clusters` and a numeric string value.
- Binding Site Prediction accepts a documented PDB ID, AlphaFold UniProt ID, or
  uploaded PDB platform path through the same `pdb_path` field.
- Create Dataset maps the UI's Gene/Protein Name to `scrap_id` and records the
  displayed endpoint and assay enums.
- Reinvent no longer accepts the owner-confirmed removed `off_tar_seqs` field or
  other retired inputs. It no longer requires an internal duplicate experiment
  name, and model thresholds follow the UI's numeric-string/empty-string wire
  representation.
- Vina score-only now requires the complete current UI payload, including target,
  binding-pocket, historical `exhaustivness`, receptor, and ligand fields. Old
  `pdb_file` and `smiles` aliases are not accepted for this mode.

Generated module sheets and focused behavior tests are synchronized with these
definitions. The dated October 14 CSV/JSON and source hashes remain a historical
snapshot and intentionally predate these corrections.

## Follow-up correction — 2026-10-15

`Solublempnn.num_seq` now uses `type: string` with `x-numeric-string: true`.
The owner reported a successful run with a numeric string after a JSON integer
failed. The repository contract and installed module documentation now agree;
local regression checks accept numeric strings and reject JSON numbers and
non-numeric strings. No production experiment was repeated for this correction.
The dated CSV/JSON and hashes below describe the October 14 snapshot, not this
subsequently corrected definition. Historical source snapshots remain unchanged.

This report supersedes the earlier 19/10/68/25 classification. The earlier
classification is not a current executable-tool readiness score.

## Result and verification boundary

All 122 catalogued request entries passed local schema/type/requiredness checks,
file-mode registration checks, and generated-document synchronization checks.
38 entries received targeted source-backed corrections in addition to the shared
normalization. All 31 module sheets are generated from the same three definitions.

152 targeted tests passed across eight files using `scripts/run_tests.sh`.
They cover native/MCP discovery and forwarding, localhost upload → submission →
polling → downloads, refreshed status links, multiple/same-named artifacts,
sanitized failures, invalid inputs, authorization/revocation, A→B→A profile
isolation, fresh-session discovery and byte-stable existing prompts.

No production scientific jobs were submitted. Passing a local request-shape test
does not establish backend acceptance, current service availability, scientific
correctness, subscription entitlement, cost, or correct output for every tool.
Synthetic shape fixtures are not runnable scientific examples.

## What changed

- Request properties own inline/file/artifact semantics. The duplicated
  `file_fields` allowlist has been removed, eliminating the shared-omission gate.
- Twelve source-backed missing upload registrations were supplied. Multimer's
  recorded inline input was preserved rather than inventing a file mode.
- Nested model/threshold schemas, numeric-string fields, requiredness and
  conditional inputs were reconciled from the retained evidence.
- File rules and limits are sparse supplements, not mandatory duplicate entries.
  Missing specialized rules do not alone prohibit an otherwise documented call.
- Basic FASTA/PDB syntax inspection supplements existing CSV/ZIP/XYZ/SDF checks.
  Scientific suitability is not falsely marked verified.
- Native and MCP helper arguments agree. Polling retains all returned links and
  refreshes terminal responses; artifact filename collisions no longer overwrite.
- Development classifications/history live outside active skill knowledge.

The storage reference returned by upload is used unchanged in the declared
payload field. The existing helper response key is `s3_path`; that name does not
require changing a platform-returned GCP/object reference or inventing a URL.

## Remaining boundaries — not hidden

Two file modes remain restricted for serialized-code safety:

- `Thermal_MPNN.model_path`: custom serialized model upload. The documented
  platform-default mode is separate.
- `epitope_abgen.input_path`: prepared serialized features/archive. The recorded
  PDB-input mode is separate.

Authentication, profile permission checks, unsafe archives and known-invalid
inputs remain enforced. User approval does not make those inputs safe.

The retained sources do not fully specify these optional nested shapes:
`boltzgen.atom1_list`, `boltzgen.atom2_list`, and `boltzgen.total_len`. Existing
descriptions/examples are preserved, but full item/object constraints were not
fabricated. These do not create a blanket tool-level block. A platform-owner
request example/specification is needed before claiming every optional mode is
precisely modeled. `Lead_Generation_Reinvent.off_tar_seqs` is not part of this
boundary: the platform owner confirmed that field was removed, and the active
contract rejects it.

Seven historical entries below lack a complete reconciled executable request
and remain outside the 122-job catalog. Twenty-six additional historical names
remain in the prior developer audit; they have not been silently enabled or
mapped to similarly named services. The old audit is retained at
`contract_sources/availability-audit-before-standardization.md`.

## Additional unavailable entries

| Name | Historical job name | Missing information |
|---|---|---|
| Create Library | `create_library` | Historical job name documented; no reconciled executable request contract in this catalog. Do not infer a payload or claim current service availability. |
| Deepcodon | `Deepcodon` | Historical job name documented; no reconciled executable request contract in this catalog. Do not infer a payload or claim current service availability. |
| Formulation Search | `Formulation_Search` | Historical job name documented; no reconciled executable request contract in this catalog. Do not infer a payload or claim current service availability. |
| Fragments | `fragments` | Historical job name documented; no reconciled executable request contract in this catalog. Do not infer a payload or claim current service availability. |
| Interactive Builder | `not established` | No explicit job name or executable request contract established in the reviewed sources. |
| QM-MM Single-Point Energy | `QM_MM_SPE` | Historical job name documented; no reconciled executable request contract in this catalog. Do not infer a payload or claim current service availability. |
| Toxicophore Screening | `toxic_screening` | Historical job name documented; no reconciled executable request contract in this catalog. Do not infer a payload or claim current service availability. |

## Full 122-job list

Every row below passed local contract checks, not a production experiment.
File-mode restrictions and incomplete optional shape definitions are explicitly
listed in the CSV/JSON inventory; a passing row does not erase those boundaries.

| # | Scientific tool | Exact job name | Module |
|---:|---|---|---|
| 1 | Geometry Optimization | `Geometry_Optimization` | quantum-chemistry |
| 2 | HOMO-LUMO & Reactivity Descriptors | `Reactivity_Descriptors_Combined` | quantum-chemistry |
| 3 | Single Point Energy | `Single_Point_Energy` | quantum-chemistry |
| 4 | MDS Gromacs | `MDS_Gromacs` | molecular-dynamics |
| 5 | MDS OpenMM | `MDS_openMM` | molecular-dynamics |
| 6 | Antibody Backbone to Sequence Generation | `Antibody_Backbone_to_Sequence_Generation` | protein-antibody-generation |
| 7 | Backbone Generation | `Backbone_Generation` | protein-antibody-generation |
| 8 | CDR Generator | `CDR_Generator` | protein-antibody-generation |
| 9 | Random Antibody Generation | `Random_Antibody_Generation` | protein-antibody-generation |
| 10 | MegaDock | `MegaDock` | protein-docking |
| 11 | Placer | `Placer` | protein-docking |
| 12 | Function-Based Enzyme Generation | `Function_Based_Enzyme_Generation` | protein-enzyme-generation |
| 13 | Genzyme Generation | `Genzyme_Generation` | protein-enzyme-generation |
| 14 | BoltzGen | `boltzgen` | protein-generative-design |
| 15 | PPI Flow Antibody | `ppiflowantibody` | protein-generative-design |
| 16 | PPI Flow Monomer | `ppiflowmonomer` | protein-generative-design |
| 17 | PPI Flow Nanobody | `ppiflownanobody` | protein-generative-design |
| 18 | PPI Flow Protein | `ppiflowprotein` | protein-generative-design |
| 19 | PX Design Infer | `pxdesigninfer` | protein-generative-design |
| 20 | PX Design Pipeline | `pxdesignpipeline` | protein-generative-design |
| 21 | Directed Evolution (MLDE) | `Insilico_Directed_Evolution` | protein-optimization |
| 22 | Random Controlled Mutagenesis | `Random_Controlled_Mutagenesis` | protein-optimization |
| 23 | ActSeek | `act_seek` | protein-optimization |
| 24 | Stability-Binding DDG | `stability-binding-ddg` | protein-optimization |
| 25 | Evobind | `Evobind` | protein-peptide-generation |
| 26 | Sequence based peptide generation | `Sequence_based_peptide_generation` | protein-peptide-generation |
| 27 | Structure-Based Peptide Generation | `Structure_based_peptide_generation` | protein-peptide-generation |
| 28 | Cyclic Binder | `cyclic_binder` | protein-peptide-generation |
| 29 | Antibody Property Prediction | `Antibody_Prediction` | protein-property-prediction |
| 30 | Enzymes | `Enzymes` | protein-property-prediction |
| 31 | Peptide Property Prediction | `Peptide_Property_Prediction` | protein-property-prediction |
| 32 | Vaccines | `Vaccines` | protein-property-prediction |
| 33 | Kinetic Kcat | `kcat_km` | protein-property-prediction |
| 34 | Kcatnet | `kcatnet` | protein-property-prediction |
| 35 | Peptiverse | `peptiverse` | protein-property-prediction |
| 36 | Boltz-2 | `Boltz2` | protein-structure-prediction |
| 37 | Multimer Structure Prediction | `Multimer_Structure_Prediction` | protein-structure-prediction |
| 38 | Monomer Structure Prediction | `Protein_Structure_Prediction` | protein-structure-prediction |
| 39 | ipSAE Generation | `ipsae-protein` | protein-structure-prediction |
| 40 | AntiBMPNN | `AntiBMPNN` | protein-target-aware-antibody |
| 41 | Antibody RFD3 | `agcdr_diff` | protein-target-aware-antibody |
| 42 | Target-Aware CDR Designer / Epitope Conditioned Antibody Generation | `epitope_abgen` | protein-target-aware-antibody |
| 43 | RF-Antibody | `rfdiffusion_proteinmpnn` | protein-target-aware-antibody |
| 44 | Antibody Numbering | `Antibody_Numbering` | protein-toolbox |
| 45 | Cat_Pred (Catalyst Prediction) | `Cat_Pred` | protein-toolbox |
| 46 | Clean (Enzyme Classification) | `Clean` | protein-toolbox |
| 47 | Ligand MPNN | `Ligand_MPNN` | protein-toolbox |
| 48 | Motif Scaffolding | `Motiff_Scaffolding` | protein-toolbox |
| 49 | NetsolP (Solubility) | `Netsolp` | protein-toolbox |
| 50 | Pep_Patch | `Pep_Patch` | protein-toolbox |
| 51 | Prodigy (Binding Affinity) | `Prodigy` | protein-toolbox |
| 52 | RC Plot | `RC_Plot` | protein-toolbox |
| 53 | Solublempnn | `Solublempnn` | protein-toolbox |
| 54 | Thermal MPNN | `Thermal_MPNN` | protein-toolbox |
| 55 | Unconditional Sampling | `Uncondtional_Sampling` | protein-toolbox |
| 56 | IG Design | `igdesign` | protein-toolbox |
| 57 | TM Align | `tm_align` | protein-toolbox |
| 58 | Protein-RNA Interaction Prediction | `Rna_Inter_Pred` | rna-binding |
| 59 | RNA_Binding_Specificity_Prediction | `rna_bind_specificity_pred` | rna-binding |
| 60 | RNA Pocket Prediction | `rna_pocket_pred` | rna-binding |
| 61 | Circular RNA Design | `CircRNA` | rna-circrna |
| 62 | Circular RNA Evaluation | `CircRNAEvaluate` | rna-circrna |
| 63 | BiomambaRna | `BiomambaRna` | rna-generation |
| 64 | siRNA Generation | `rna_siRNA_gen` | rna-generation |
| 65 | RNA 3'UTR Generation | `rnagen_3utr` | rna-generation |
| 66 | RNA 5'UTR Generation | `rnagen_5utr` | rna-generation |
| 67 | RNA CDS Generation | `rnagen_cds` | rna-generation |
| 68 | RNA mRNA Generation | `rnagen_cds_mrna-gen` | rna-generation |
| 69 | CRISPR Bystander Effect Prediction | `BE_bystander_prediction` | rna-grna-design |
| 70 | CRISPR Base-Editing Efficacy Prediction | `BE_efficacy_pred` | rna-grna-design |
| 71 | CRISPR Base Editing | `crispr_base_editing` | rna-grna-design |
| 72 | CRISPR IndelShift Prediction | `crispr_fs_score` | rna-grna-design |
| 73 | CRISPR Off-Target Prediction | `crispr_score` | rna-grna-design |
| 74 | CRISPR gRNA Design | `gRNA_design` | rna-grna-design |
| 75 | RNA Tertiary Folding | `TertiaryFolding` | rna-inverse-fold |
| 76 | RNA 2D Inverse Folding | `rna_inverse_fold` | rna-inverse-fold |
| 77 | CDS Property Prediction | `CodonRLBERTPropPred` | rna-property-prediction |
| 78 | mRNA Property Calculation | `rna_property_calculation` | rna-property-prediction |
| 79 | RNA Property Prediction — In-Cell Stability | `rna_property_prediction_incell_stabilty` | rna-property-prediction |
| 80 | RNA Property Prediction — Mean Ribosomal Load | `rna_property_prediction_mean_ribosomal_load` | rna-property-prediction |
| 81 | siRNA Efficacy Prediction | `rna_siRNA_efficacy_pred` | rna-property-prediction |
| 82 | siRNA Property Prediction | `siRNA_obj_pred` | rna-property-prediction |
| 83 | RNA Tertiary Structure Prediction | `rna_structure_prediction` | rna-structure-prediction |
| 84 | Secondary Structure Prediction | `sec_struct_pred` | rna-structure-prediction |
| 85 | CodonRLBERT | `CodonRLBERT` | rna-translation-codon |
| 86 | RNA Translation Prediction | `RNA_Translation` | rna-translation-codon |
| 87 | RNA Translational Efficiency Prediction | `transla_score` | rna-translation-codon |
| 88 | R-Group Enumeration | `Molecule_Enumeration` | small-molecule-enumeration |
| 89 | Create Dataset | `dataset_creation` | small-molecule-enumeration |
| 90 | Fragment-Based Optimization | `Fragment_Based_Optimization` | small-molecule-optimization |
| 91 | Lead Generation — Augmented | `Lead_Generation_Augmented` | small-molecule-optimization |
| 92 | Graph GA | `Lead_Generation_Graph_GA` | small-molecule-optimization |
| 93 | Mars Plus | `Lead_Generation_Mars_Plus` | small-molecule-optimization |
| 94 | Lead Generation — Reinvent | `Lead_Generation_Reinvent` | small-molecule-optimization |
| 95 | Lead Optimization MCTS | `Lead_Optimization_Mcts` | small-molecule-optimization |
| 96 | Pharmacophore-Based Generator (pgmg_molgen) | `Pharmacophore_Based_Generator` | small-molecule-pharmacophore-generation |
| 97 | Pharmacophore Hypothesis (phcore_gen) | `Pharmacophore_Hypothesis` | small-molecule-pharmacophore-generation |
| 98 | Custom Property Model ML | `Custom_Property_Model_Automl` | small-molecule-qspr |
| 99 | Custom Property Model DL | `Custom_Property_Model_DL` | small-molecule-qspr |
| 100 | Property Prediction (propinf) | `Property_Prediction` | small-molecule-qspr |
| 101 | global_ic50 | `global_ic50` | small-molecule-qspr |
| 102 | Random Generation — Inference | `Random_based_generation_Inference_transvaegen` | small-molecule-random-generation |
| 103 | Random Generation — Inference | `Random_based_generation_nontrans` | small-molecule-random-generation |
| 104 | Random based generation training | `Random_based_generation_training` | small-molecule-random-generation |
| 105 | Butina Clustering | `Butina_Clustering` | small-molecule-screening |
| 106 | K-Means Clustering | `K_Means_Clustering` | small-molecule-screening |
| 107 | Novelty Check | `Novelty` | small-molecule-screening |
| 108 | Pharmacophore Screening | `Pharmacophore_Screening` | small-molecule-screening |
| 109 | QSPR Screening | `QSPR_Screening` | small-molecule-screening |
| 110 | Similarity Screening | `Similarity_Screening` | small-molecule-screening |
| 111 | Substructure Screening | `Substructure_Screening` | small-molecule-screening |
| 112 | Structure-Based Generator | `Structure_Based_Generator` | small-molecule-structure-generation |
| 113 | Binding Site Prediction (fpocket) | `Binding_Site_Prediction` | small-molecule-toolbox |
| 114 | Molecular Docking — DiffDock Mode | `Diffdock` | small-molecule-toolbox |
| 115 | Flexible Docking | `Vina_Flexible_Docking` | small-molecule-toolbox |
| 116 | Molecular Docking — Vina Score Only Mode | `Vina_Score_only_docking` | small-molecule-toolbox |
| 117 | Molecular Docking | `Vina_basic_docking` | small-molecule-toolbox |
| 118 | Atom Mapping | `atom_mapping` | synthetic-forward-reaction |
| 119 | Condition Recommendation | `condition_recommendation` | synthetic-forward-reaction |
| 120 | Forward Reaction Prediction | `forward_reaction` | synthetic-forward-reaction |
| 121 | Impurity Prediction | `impurity_prediction` | synthetic-forward-reaction |
| 122 | Retrosynthesis | `retrosynthesis` | synthetic-retrosynthesis |

## Reproducible records

- [Filterable per-tool CSV](contract_sources/verification-2026-10-14.csv)
- [Per-tool JSON and source hashes](contract_sources/verification-2026-10-14.json)
- [Original definitions and change notes](contract_sources/standardization-record.v1.json)
- [Definition ownership and maintenance](CONTRACTS.md)

Use a fresh process/conversation after updating installed code; do not reload
instructions into an existing cached conversation. Profile state and credentials
are not distributed with these definitions.
