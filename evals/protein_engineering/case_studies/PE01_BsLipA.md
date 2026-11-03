# PE01: Ranking thermostable variants of Bacillus subtilis Lipase A

Evaluation issue: [#24](https://github.com/boltzmannlabs/agent-scientist/issues/24).

## Problem and target

Can sequence features and structural context prioritize single-amino-acid
substitutions in BsLipA at residue positions absent from training? Compare
interpretable baselines with sequence–structure models, evaluate ranking and
score error, and propose five additional substitutions outside the measured panel.

Use continuous, higher-is-better `DMS_score` from
`ESTA_BACSU_Nutschel_2020`. The source endpoint is T50, an assay-specific
thermal-inactivation measure. Do not reinterpret it as a universal melting
temperature or infer catalytic activity from a favorable prediction.

The reported results follow the [collection's evidence provenance](README.md#evidence-provenance).

## Dataset, sources and permitted labels

- [Pinned assay CSV](https://huggingface.co/datasets/OATML-Markslab/ProteinGym_v0.1/resolve/4075aa679683f3071d527283819637f3446ca488/ProteinGym_substitutions/ESTA_BACSU_Nutschel_2020.csv).
- CSV SHA256: `15c895d371676e981538246b1313f999a840fb6942d728705a5f2f85763359fd`.
- [Pinned ProteinGym metadata](https://github.com/OATML-Markslab/ProteinGym/blob/144fe22b07dfaeec2b366f2346203a9838a55b4c/reference_files/DMS_substitutions.csv): select this assay and use `target_seq`.
- [Nutschel et al. (2020), assay study](https://pubmed.ncbi.nlm.nih.gov/31905288/).
- [RCSB 1I6W, experimental structure and catalytic context](https://www.rcsb.org/structure/1I6W).
- [UniProt P37957](https://www.uniprot.org/uniprotkb/P37957/entry), supporting annotations.
- [ThermoMPNN method](https://pubmed.ncbi.nlm.nih.gov/38285937/).

Retain all 2,172 single-substitution records and the 212-residue assay reference.
Exclude the binary median label. Original challenge split files were unavailable;
the reference study used the following independent position-disjoint split.

| Split | Positions | Variants | Label use |
| --- | ---: | ---: | --- |
| Training | 101 | 1,380 | Fit models |
| Validation | 27 | 329 | Select settings; no refit |
| Test | 40 | 463 | Evaluate frozen predictions |

All substitutions at a position remain together. Select by validation Spearman,
with RMSE as tie-breaker, and lock the method before test evaluation. Later
external-tool comparisons retain that selection. Recover the complete original
position manifest to reproduce this split; the counts do not specify membership.

## Workflow and reported predictive results

### 1. Audit the data

Verify mutation notation, WT identities, reconstructed sequences and uniqueness.
The reference record reports that all 2,172 rows match the assay sequence.
Record sources and checksums and export the complete position-level manifest.

### 2. Establish interpretable baselines

Fit a constant training-mean predictor and residue-property ridge models using
training labels only. Include hydropathy, molecular mass, charge-class proxies,
aromaticity and proline/glycine indicators. Preserve fitted preprocessing.

### 3. Fit and select sequence–structure models

The study compared 11 configurations spanning ridge regression, Extra Trees
and histogram gradient boosting. Additional features were substitution identity,
local composition, normalized position, solvent accessibility, 8 Å Cα contacts,
B-factors, centroid distance and accessibility–property interactions. Validation
selected `structure_ridge_100`, with Spearman 0.505. Recover the full grid,
preprocessing and model configuration from the original artifacts for exact replay.

### 4. Freeze, predict and evaluate

Save the selection lock before test scoring and export every held-out prediction.
Primary evaluation is Spearman; secondary metrics are RMSE and precision@20,
defined here as the fraction of the top 20 predictions in the test-set top decile.

| Method, same 463 test variants | Spearman | RMSE | Precision@20 |
| --- | ---: | ---: | --- |
| Training mean | Undefined | 2.457 | Ties |
| Residue-property ridge | 0.079 | 2.476 | 15% |
| Sequence-only Extra Trees | 0.209 | 2.444 | 20% |
| Selected sequence–structure ridge | 0.333 | 2.424 | 5% |
| Structure Extra Trees | 0.384 | 2.205 | 45% |
| ThermoMPNN, train-calibrated | 0.346 | 2.336 | 25% |
| Enzyme thermal predictor, raw | 0.122 | — | 0% |

The selected ridge's reported 95% position-bootstrap Spearman interval is
0.101–0.518; ThermoMPNN's is 0.161–0.501. Structure Extra Trees remains a
comparison, rather than a winner substituted after inspecting test results.
Uncalibrated thermal-property scores use another scale, so their RMSE is omitted.
Any calibration must use training labels only.

Metric intervals resample positions. Thirty training-position bootstrap refits
provide per-variant model SD. A matched ridge comparison reports a
structural-minus-sequence Spearman interval of 0.068–0.434. DynaMut2 scored a
predeclared 20-position diagnostic subset: Spearman 0.394, interval
−0.100–0.717. Keep that subset separate from the full-test comparison and record
the exact resampling implementation and random seeds.

## Workflow and reported structural/chemical results

### 5. Map and assess the reference structure

Align the complete assay reference to deposited 1I6W sequence and coordinate
records before extracting features. Retain every assay position, including
positions without coordinates.

| Reference finding | Reported result |
| --- | --- |
| Assay sequence | 212 residues |
| Mature modeled enzyme | 181 residues; assay residues 32–212 |
| Resolved residues in 1I6W chain B | 180 |
| Numbering relationship | Assay position = mature position + 31 |
| Catalytic triad, mature / assay | S77–D133–H156 / S108–D164–H187 |
| Oxyanion-hole residues, mature / assay | I12 and M78 / I43 and M109 |

The reference workflow used Biopython for accessibility, contacts and distances;
ToolUniverse EBI Proteins annotations for P37957 supported the catalytic mapping.
Boltzmann RC_Plot supplied the reference Ramachandran view. Preserve the exact
structure, chain, atom selection and coordinate coverage used by each tool.

### 6. Reassess chemistry and structural context

Review substitutions with solvent exposure and catalytic proximity. The reported
candidates preserve triad and oxyanion-hole identities. M165N maps to mature
M134N, immediately after catalytic Asp133; the other changes affect charge,
aromatic packing or polar contacts. Evaluate local confidence and measured atom
geometry alongside global fold similarity when interpreting the active site.

### 7. Select five additional hypotheses

Rank substitutions absent from the entire measured panel using predicted score
minus bootstrap model SD, retaining five distinct positions. Absence from this
panel does not establish literature novelty.

| Assay / mature mutation | Locked-model score ± SD | Chemical rationale |
| --- | ---: | --- |
| W73K / W42K | 50.43 ± 0.82 | Aromatic → basic; exposed-site electrostatics |
| M165N / M134N | 50.55 ± 1.40 | Thioether → amide; catalytic-acid neighbor |
| Y170N / Y139N | 49.64 ± 0.63 | Phenol → amide; local polar/packing change |
| E33K / E2K | 49.97 ± 1.44 | Acidic → basic; mature N-terminal context |
| R64S / R33S | 49.10 ± 1.09 | Guanidinium → hydroxyl; charge/contact change |

Keep WT as a matched comparator throughout. Save full sequences, the residue
map, scoring model identity and candidate-selection evidence.

## Workflow and reported additional-property results

### 8. Predict solubility and related properties

Boltzmann Enzymes returned `enzyme_solubility`, `pHPred` and
`function_prediction` for WT and the five mature variants. Verify each returned
sequence and requested output column. The following table combines those raw
properties with the structural comparisons in step 9.

| Sequence, assay mutation label | Solubility raw | pH raw | Mean pLDDT | TM-score |
| --- | ---: | ---: | ---: | ---: |
| WT | 1 | 7.04 | 0.87 | 0.956 |
| W73K | 1 | 7.04 | 0.85 | 0.941 |
| M165N | 1 | 7.04 | 0.88 | 0.957 |
| Y170N | 1 | 7.04 | 0.87 | 0.956 |
| E33K | 1 | 7.04 | 0.85 | 0.943 |
| R64S | 1 | 7.04 | 0.87 | 0.956 |

Identical solubility and pH outputs provide no within-panel ranking and are not
measured soluble fractions or experimentally established optimal pH values.
The function model returned EC 3.1.1.3 for WT and four variants, and 3.1.1.5 for
Y170N. Keep audited pI/GRAVY descriptors distinct from function predictions.

### 9. Inspect predicted monomer structures

ToolUniverse ESMFold returned six complete 181-residue structures. Boltzmann
TM-align compared them with 1I6W B; TM-scores 0.941–0.957 are normalized to
reference length. MolProbity assessed all six. Ramachandran outliers were 0%
for WT/M165N/R64S, 0.56% for Y170N, 3.35% for W73K and 3.91% for E33K.
Asp133 local pLDDT was 0.54–0.59. These confidence values use the reported
tool's 0–1 scale. Preserve local uncertainty even when the global fold agrees.

### 10. Check individual-mutation stability predictions

ThermoMPNN returned 3,600 rows; excluding 180 identity controls left 3,420
substitutions. Check zero-based ordinals against every WT residue. Retrieve
DynaMut2 point outputs independently and preserve the numbering conversion.

| Assay mutation | ThermoMPNN raw ddG_pred | DynaMut2 ΔΔG, kcal/mol |
| --- | ---: | ---: |
| W73K | 0.324 | +0.542 |
| M165N | 0.120 | +1.280 |
| Y170N | 0.924 | +0.817 |
| E33K | 0.049 | −0.185 |
| R64S | 0.202 | −0.402 |

DynaMut2 declares positive values stabilizing. The deployed ThermoMPNN values
remain on their raw supplied scale. Preserve model-specific estimates rather
than summing them or treating them as equivalent energies or T50 measurements.

### 11. Integrate and verify

The supplied study reports complete held-out predictions, position-level
uncertainty, a verified numbering map, five traceable hypotheses, matched monomer
structures and complementary property assessments. Prioritize with ranking,
chemistry, local confidence and structural quality together. A next-stage
functional assessment needs a defined substrate, assay pH and matched WT.

The original reproducibility bundle is named `PE01_BsLipA_multimodel/` and is
described as containing scripts, `requirements.lock.txt`, source checksums,
screen logs, tool receipts and row-level outputs. Its contents are not bundled
here; recover it before claiming exact historical reproduction.

## Fresh Agent Scientist evaluation deliverables

Produce all 463 test predictions, the recovered/versioned split manifest,
selection lock, fitted artifacts, uncertainty outputs and exact-sequence-matched
tool evidence. Compare every reported metric on the same subset and score scale;
explain deviations and unavailable operations. Record resources, stage failures
and recovery attempts independently of candidate quality. A fresh run is judged
on verified execution and scientific interpretation, not copied reference tables.
