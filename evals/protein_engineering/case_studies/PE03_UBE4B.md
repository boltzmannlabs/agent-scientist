# PE03: Prioritizing UBE4B double-mutant candidates

Evaluation issue: [#26](https://github.com/boltzmannlabs/agent-scientist/issues/26).

## Problem and target

Can individual amino-acid substitution measurements predict mutation-pair
behavior, and which UBE4B variants are promising follow-up candidates?
Establish a single-mutant additive reference, model combination scores and
integrate complementary property assessments to prioritize measured leads
and propose new combinations.

Use distributed `DMS_score` for `UBE4B_HUMAN_Tsuboyama_2023_3L1X`.
ProteinGym orients this score so higher values represent more favorable assay
performance. Retain that distributed scale; assign no unsupported thermodynamic
units and do not treat a positive score as a measured gain over WT. This is
a domain stability-related assay, not a measurement of full-length UBE4B activity.

The reported results follow the [collection's evidence provenance](README.md#evidence-provenance).

## Dataset, sources and permitted labels

- [ProteinGym dataset and score documentation](https://github.com/OATML-Markslab/ProteinGym).
- [Pinned assay metadata](https://github.com/OATML-Markslab/ProteinGym/blob/144fe22b07dfaeec2b366f2346203a9838a55b4c/reference_files/DMS_substitutions.csv): select `UBE4B_HUMAN_Tsuboyama_2023_3L1X` and use `target_seq`.
- [Tsuboyama et al., Nature (2023)](https://www.nature.com/articles/s41586-023-06328-6), proteolysis-based stability study.
- [RCSB 3L1X](https://www.rcsb.org/structure/3L1X), deposited construct.
- [NetSolP method](https://pubmed.ncbi.nlm.nih.gov/35088833/) and [ThermoMPNN method](https://pubmed.ncbi.nlm.nih.gov/38285937/).

The extracted assay has 1,118 singles and 2,504 doubles spanning nine
residue-position pairs. Multiple substitutions are colon-separated. Its
69-residue reference maps exactly to residues 25–93 of the 100-residue
deposited construct, and all assay residues have coordinates. Recover the
original extracted CSV and hash it before an exact replay; no original CSV
revision/checksum is supplied with this reference narrative.

| Analysis group | Records | Label use |
| --- | ---: | --- |
| Training singles | 1,118 | Estimate individual effects |
| Training doubles | 1,502 | Fit combination-score models |
| Validation doubles | 501 | Select settings; exclude from fitting |
| Test doubles | 501 | Evaluate frozen predictions |

These are exploratory locally generated splits, seed 303, not certified
official PE03 challenge splits. Original starter metadata was unavailable.
Public ProteinGym documentation supports score orientation. Recover the split
manifest, ordering and construction rules: a seed and counts alone do not
identify the partition, nor establish held-out residue-position-pair testing.
Reference score zero below is a modeling convention, not a WT measurement.

## Workflow and reported predictive results

### 1. Audit the construct and score

Verify mutation identities, WT residues, reconstructed sequences and uniqueness.
Save the construct alignment and residue map rather than assuming that assay
and full-construct numbering agree. Metadata identifies cDNA-display
proteolysis and raw field `ddG_ML_float`; retain distributed `DMS_score` for
analysis and document the source orientation.

### 2. Estimate additive effects

For component substitutions A and B, use
`additive(A:B) = score(A) + score(B) − reference_score`, with
`reference_score = 0` by convention. Both measured component scores exist
for 2,370 of 2,504 doubles. Flag the other 134 explicitly. A ridge imputation
branch fitted only to training singles supplies missing effects without
relabeling those doubles as measured-component-covered.

### 3. Fit and select the combination-score model

Compare sequence, structural-distance and combined features on validation
doubles. Sequence features encode substitution identity and physicochemical
change; structural features include reference distances, accessibility and
B-factors. Validation Spearman selected sequence ridge. Exclude validation
labels from final fitting and learned preprocessing. Recover the full model
grid and transformations for exact reproduction.

### 4. Freeze, predict and evaluate

Freeze predictions and artifacts before scripted test evaluation. Every test
double receives a prediction. Compare measured-component baselines on the
same covered subset, retaining a separately labeled imputation branch elsewhere.

| Test subset | N / fraction | Selected Spearman | Selected RMSE | Additive/imputed Spearman | Additive/imputed RMSE |
| --- | --- | ---: | ---: | ---: | ---: |
| All doubles | 501 / 100% | 0.9090 | 0.3643 | 0.6594 | 1.4899 |
| Covered | 476 / 95.01% | 0.9166 | 0.3539 | 0.6974 | 1.5195 |
| Uncovered | 25 / 4.99% | 0.4546 | 0.5240 | 0.3623 | 0.7240 |

RMSE is in distributed score units. The baseline uses measured components
on covered rows and labeled imputations elsewhere.

Across 1,000 reported exact mutation-pair bootstrap resamples, the covered
subset's 95% Spearman interval was 0.8967–0.9325 and RMSE interval was
0.2893–0.4271. The Spearman improvement interval was 0.1780–0.2693 and
RMSE-reduction interval was 1.0838–1.2552. Recover the original resampling
unit, membership and random-seed implementation rather than inferring them
from these intervals.

The study reports improved prediction over raw additivity within these sampled
panels. Residual maps describe departures from the baseline; proximity and a
large residual alone do not establish physical epistasis. Intervals describe
fixed-model sampling variability, not full model-selection or assay uncertainty.

## Workflow and reported structural/chemical results

### 5. Map and assess the reference structure

Map the complete assay domain to 3L1X and retain distances for interpretation.
Use the interaction map to connect double-mutant residuals with residue-pair
context. Preserve assay numbering in recommendations and full-construct
numbering in the coordinate map, including the +24 sequence-position offset.
Verify author residue identifiers separately rather than treating the sequence
offset as a universal PDB author-numbering rule.

### 6. Review candidate chemistry

Calculate molecular mass, theoretical pI, GRAVY and residue composition for WT,
measured candidates and hypotheses using consistent methods. Reported WT
values are 8,021.13 Da, pI 4.5416 and GRAVY −0.5188.
S39N:T41W and S39Y:T41W retain that calculated pI and introduce no cysteine.
S39C:T41C is a complementary redox-sensitive hypothesis requiring defined
conditions, rather than an assumed beneficial disulfide.

### 7. Select measured-panel recommendations and separate new hypotheses

The ten measured recommendations are the highest-scoring training doubles,
not a shortlist chosen from test labels. Preserve the complete panel and
property trade-offs.

| Measured candidate | DMS_score | NetSolP score |
| --- | ---: | ---: |
| D8M:D28M | 2.2894 | 0.2970 |
| D17C:R29Y | 1.4638 | 0.3021 |
| D8W:D28H | 1.0849 | 0.3102 |
| S39C:T41C | 0.9620 | 0.3678 |
| S39Y:T41W | 0.7378 | 0.3580 |
| R29I:K61I | 0.5525 | 0.3137 |
| S39N:T41W | 0.5405 | 0.3694 |
| S39H:T41Y | 0.4624 | 0.3599 |
| S39F:T41Y | 0.4275 | 0.3392 |
| S39Y:T41F | 0.4036 | 0.3537 |

Balanced follow-up priorities in the reference study were S39N:T41W and
S39Y:T41W, combining favorable assay scores, above-WT mean NetSolP outputs
and close modeled fold agreement. S39C:T41C adds a chemistry-focused question.
D8M:D28M is the highest measured assay-score comparator, not a claim of
superiority on every property.

Five optional combinations were carried forward from the frozen-model
prospective screen. Their position pairs lie outside measured training panels;
their scores are exploratory predictions.

| Hypothesis | Predicted DMS_score | Reported pLDDT |
| --- | ---: | ---: |
| D4C:D12F | 2.159 | 95.9 |
| D12W:T48F | 1.896 | 97.4 |
| T41W:T48Y | 1.592 | 96.8 |
| D1K:D12C | 1.546 | 94.5 |
| D12C:Q65L | 1.538 | 96.2 |

## Workflow and reported additional-property results

### 8. Predict solubility

NetSolP returned all 63 requested sequence assessments, including WT,
component singles, doubles and controls. Join results by exact sequence and
verify five-member ensemble means. WT scored 0.3479; S39N:T41W scored
0.3694, with all five members above corresponding WT member scores.
S39Y:T41W scored 0.3580 and S39C:T41C 0.3678. These are generic
expression-context estimates, not soluble concentrations or yields.

### 9. Inspect monomer structures and fold similarity

All 16 requested structures matched their submitted 69-residue sequences:
WT, ten measured candidates and five hypotheses. Verify TM Align and
MolProbity outputs for all 16 without dropping a candidate. TM-scores below
are normalized to the experimental assay-domain reference; RMSD is in Å.

| Sequence | pLDDT | pTM | TM-score | RMSD, Å |
| --- | ---: | ---: | ---: | ---: |
| WT | 96.6 | 0.808 | 0.9820 | 0.398 |
| S39N:T41W | 96.9 | 0.818 | 0.9801 | 0.420 |
| S39Y:T41W | 97.2 | 0.830 | 0.9825 | 0.395 |
| S39C:T41C | 95.6 | 0.788 | 0.9823 | 0.396 |

The highlighted variants' MolProbity clashscores were 0.88, 0.88 and 0.90,
respectively, with zero Ramachandran outliers. Geometry was assessed in
measurement-only mode; hydrogen-containing and heavy-atom bond flags were
separated. Fold confidence and geometry support structural interpretation
without constituting stability measurements.

### 10. Check individual-mutation stability outputs

ThermoMPNN returned 1,500 rows over 75 observed structural positions.
Residue mapping and WT checks yielded 1,311 nonself substitutions in the
69-residue assay domain. Preserve those mapped raw outputs as supplementary
point-mutant context. They did not enter the original frozen-model selection
and must not be summed into validated combined-mutant energies.

### 11. Integrate and verify

The reference record links a construct/score audit, full test coverage,
interaction map, ten measured recommendations and five hypotheses to
sequence-property and structural assessments. Keep WT and component singles
with every double for follow-up. Preserve all 63 solubility outputs and all
16 structure, geometry and fold-comparison records, including trade-offs.
Specify host, pH, temperature and redox conditions for follow-up selection.
Aggregation and full-length UBE4B activity remain outside the assessed endpoints.

## Fresh Agent Scientist evaluation deliverables

Produce the recovered/versioned split manifest, original CSV hash, construct
map, additive coverage/imputation flags, selection lock and all 501 frozen
test predictions. Recompute subset metrics and bootstrap comparisons, retain
the complete ten-lead/five-hypothesis panels and identity-check every external
tool record. Report execution reliability, resource consumption and missing
results separately from score quality and biological interpretation.
