# PE02: Predicting GFP fluorescence from mutation combinations

Evaluation issue: [#25](https://github.com/boltzmannlabs/agent-scientist/issues/25).

## Problem and target

Can measurements of individual amino-acid substitutions predict GFP fluorescence
when mutations are combined? Compare an additive model with a nonlinear model,
characterize reliability as mutation count increases, and use structural and
chemical context to propose conservative exploratory designs.

The target is the distributed assay fluorescence score, not absolute brightness,
measured solubility or a calibrated probability of fluorescence. Structural
plausibility and favorable descriptors support prioritization without proving
that an untested sequence functions. GFP is a fluorescent protein; this case
does not evaluate an enzyme catalytic endpoint.

The reported results follow the [collection's evidence provenance](README.md#evidence-provenance).

## Dataset, sources and permitted labels

- [Pinned assay CSV](https://huggingface.co/datasets/OATML-Markslab/ProteinGym_v0.1/resolve/4075aa679683f3071d527283819637f3446ca488/ProteinGym_substitutions/GFP_AEQVI_Sarkisyan_2016.csv).
- CSV SHA256: `dcfe5eb754186eb9eb3a2fe7889d83d791640963a4512b55e91e3c3d4ac65eb2`.
- [Pinned ProteinGym metadata](https://github.com/OATML-Markslab/ProteinGym/blob/144fe22b07dfaeec2b366f2346203a9838a55b4c/reference_files/DMS_substitutions.csv): select `GFP_AEQVI_Sarkisyan_2016` and use `target_seq`.
- [Sarkisyan et al., Nature (2016)](https://doi.org/10.1038/nature17995), experimental landscape.
- [RCSB 2WUR](https://www.rcsb.org/structure/2WUR), structural context.
- [NetSolP method](https://pubmed.ncbi.nlm.nih.gov/35088833/) and [ThermoMPNN method](https://pubmed.ncbi.nlm.nih.gov/38285937/).

Retain all 51,714 measured variants. `mutant` contains colon-separated
substitutions; `DMS_score` is the target. Obtain the assay reference from
metadata, rather than assuming identity to 2WUR.

| Split | Substitutions per variant | Variants | Label use |
| --- | --- | ---: | --- |
| Training | 1 | 1,084 | Fit models |
| Validation | 2 | 12,777 | Select settings; no refit |
| Test | 3 or more | 37,853 | Evaluate frozen predictions |

Fit only on singles. Doubles may guide selection but cannot enter the final
fit. Freeze models, test predictions and rankings before test-label access.
Mutation-count groups are not randomized; post-test redesign is exploratory.

## Workflow and reported predictive results

### 1. Audit the data

Verify reference residues, mutation positions, reconstructed sequences,
uniqueness and split counts. The reported study retained all 51,714 rows. The
source CSV lacks mutant-sequence strings for an independent reconstruction
comparison; record that limitation rather than claiming such a comparison.

### 2. Estimate additive effects

Use reference convention `b = 3.7891`, the singles' 95th percentile, not a
measured WT fluorescence value. For an observed substitution `m`, estimate
`effect(m) = score_single(m) − b`; a combination score is `b + sum(effect(m))`.
Unseen substitutions receive zero effect and explicit coverage flags. Preserve
this policy in training and evaluation rather than silently dropping variants.

### 3. Fit and select the nonlinear model

Fit RBF-kernel ridge on singles using substitution indicators and composition
changes scaled by 0.5. The reported predefined grid selected `gamma = 0.05`
and `alpha = 0.01` using doubles. No refit on doubles or pretrained
representation was used. Recover the complete grid and feature order from the
source artifacts. Kernel nonlinearity does not identify arbitrary pairwise
epistasis from single-mutant training data.

### 4. Freeze, predict and evaluate

Hash-freeze fitted models, all 37,853 test predictions and the top-20 ranking
before reading test scores. The primary metric equally weights Spearman across
bins 3, 4, 5 and 6+. Also report overall/per-bin Spearman and RMSE.

| Aggregate metric | Additive | Nonlinear |
| --- | ---: | ---: |
| Mean-bin Spearman, primary | 0.6052 | 0.6302 |
| Overall Spearman | 0.7607 | 0.5694 |
| Overall RMSE | 1.1285 | 1.5405 |

| Substitutions | Additive Spearman | Nonlinear Spearman | Additive RMSE | Nonlinear RMSE |
| --- | ---: | ---: | ---: | ---: |
| 3 | 0.7316 | 0.7758 | 0.6498 | 0.9318 |
| 4 | 0.7581 | 0.7982 | 0.9298 | 1.3599 |
| 5 | 0.6339 | 0.6664 | 1.1869 | 1.7291 |
| 6+ | 0.2972 | 0.2805 | 1.6479 | 2.1082 |

The nonlinear method leads on the declared primary metric; additivity leads on
overall ranking and RMSE. Preserve both conclusions. These comparisons are
descriptive, not significance-tested, and high-mutation-count extrapolation
remains uncertain. Recompute aggregates from full-precision predictions;
rounded table entries may not reproduce the final reported decimal.

Training covered 60.69% of unique test substitutions and 95.39% of their
occurrences; 81.15% of test variants were fully covered. With high fluorescence
defined as score ≥2.5, precision@20 was 0.95 for additivity and 0.85 for the
nonlinear model. Frozen top-20 scores are extrapolated model outputs, not
validated design measurements.

## Workflow and reported structural/chemical results

### 5. Map and assess the reference structure

Map assay positions using sequence and coordinate records. Assay and deposited
canonical sequences differ at positions 80, 167 and 238. Coordinates cover
230 of 238 assay positions; 1, 2 and 233–238 are unresolved. Fused chromophore
GYS is author residue 66 but represents assay residues 65–67. Sequential
structural labels therefore cannot substitute for the residue map.

The reference calculations used Shrake–Rupley accessibility, a 1.4 Å probe,
960 sphere points and Wilke normalization. Burial meant relative accessibility
<0.25. Contacts used minimum heavy-atom distance ≤5 Å; nonlocal pairs had
sequence separation >2. Count fused GYS once as a physical residue.

| Reference finding | Reported result |
| --- | ---: |
| Buried standard-residue positions | 134 |
| Positions within 5 Å of GYS, including its parents | 28 |
| Nonlocal physical-residue contact pairs | 786 |
| Unique PDBe validation-flagged author positions | 53 |

Nineteen of the 20 shortlisted test variants affect a flagged reference
position. These flags concern coordinate interpretation, not demonstrated
mutational harm. The deposited assembly's monomer assignment is PISA-derived,
rather than direct solution-state evidence.

### 6. Reassess chemistry and original hypotheses

The original exploratory hypotheses were:

- `R73L:K158G:S175T`.
- `P75H:K158G:L178V`.
- `N144G:K158G:G191V`.

Their shared K158G and extrapolated scores motivated a complementary set of
lower-mutation-burden hypotheses. Preserve both sets and label the redesign
as post-test exploration, rather than improving the frozen predictive result.

### 7. Select conservative exploratory alternatives

Favor measured component substitutions at exposed, coordinate-resolved sites
away from GYS, reference mismatches and validation flags. The reported screen
avoided charge-class changes, new cysteine, glycine/proline changes and negative
BLOSUM62 substitutions as heuristic cautions. Mutated site pairs had to be
>5 Å apart. These are transparent selection heuristics, not validated GFP rules.

The screen retained 91 qualifying candidates among 393 novel double-mutant
combinations. It selected near-reference pI, charge, hydropathy and instability
descriptors, required model disagreement ≤0.3 and both predicted scores inside
the singles' range.

| Revised hypothesis | Additive score | Nonlinear score | Local instability index |
| --- | ---: | ---: | ---: |
| T38S:S175T | 3.981 | 4.097 | 30.19 |
| S175T:T225S | 3.979 | 4.096 | 30.54 |
| T50S:S175T | 3.944 | 4.067 | 30.54 |

Each pair exchanges serine and threonine while preserving composition.
Calculated pI 5.670, illustrative pH-7 charge −7.614 and GRAVY −0.517 match
the reference; its instability index is 30.54. Use one consistent,
independently checked descriptor method. Alternative ToolUniverse instability
estimates disagreed in the reported study and were retained separately.
Composition preservation supports a chemical rationale but does not validate
packing or physical stability.

## Workflow and reported additional-property results

### 8. Predict solubility

Enzymes returned `enzyme_solubility = 1` for all seven sequences without a
probability/class mapping. NetSolP returned five component scores and their
verified mean. Service identifiers changed, so outputs were joined by exact
sequence. Neither output represents a measured soluble fraction; application
of an enzyme-labeled model to GFP is exploratory.

| Sequence | NetSolP score | Reported pLDDT | Reported pTM |
| --- | ---: | ---: | ---: |
| Reference | 0.6162 | 96.9 | 0.927 |
| T38S:S175T | 0.5852 | 96.8 | 0.926 |
| S175T:T225S | 0.5463 | 96.8 | 0.926 |
| T50S:S175T | 0.5713 | 96.8 | 0.926 |

Original-design NetSolP scores, in step-6 order, were 0.6031, 0.5963 and
0.6095. Keep the reference comparison visible; these values do not establish
solubility improvement for the redesigns.

### 9. Inspect predicted monomer structures

The original monomer job returned four complete, single-chain 238-residue
models matching its submitted sequences. The revised-model Cα RMSDs to the
predicted reference were 0.088, 0.084 and 0.111 Å, in step-7 order. This is
global fold agreement, not measured fluorescence or thermodynamic stability.
Standard-residue models do not simulate mature fused-GYS chemistry. Preserve
each job's submitted sequences and returned structures to disambiguate the
original and revised panels.

### 10. Check individual-mutation stability predictions

ThermoMPNN returned 4,540 rows across 227 structural positions. The reported
audit checked every WT identity, zero-valued control and numbering offset.
DynaMut2 returned four independently retrieved point predictions. Both methods
use the deposited 2WUR background, not the exact assay reference.

| Mutation | ThermoMPNN raw ddG_pred | DynaMut2 ΔΔG, kcal/mol |
| --- | ---: | ---: |
| T38S | 0.466 | −0.383 |
| S175T | 0.227 | −0.123 |
| T225S | 0.579 | −0.858 |
| T50S | 0.630 | +0.067 |

DynaMut2 declares positive values stabilizing and negative values destabilizing.
The deployed ThermoMPNN artifact does not explicitly supply sign/units; retain
raw values. Harmonize conventions before comparison and do not sum point
estimates into validated double-mutant energies.

### 11. Integrate and verify

The reference record reports complete test predictions, the primary-metric
comparison, conservative exploratory designs, solubility estimates and
high-confidence monomer models. Sequence identities, downloaded artifacts and
frozen hashes were checked. These support prioritization, not experimentally
improved fluorescence, solubility or stability. Dedicated aggregation prediction
and new experimental measurements were not obtained. Extensions include
calibrated uncertainty, aggregation assessment, mutant relaxation and matched
laboratory validation with a defined host, pH and temperature.

Published ProteinGym full-assay zero-shot Spearman values supplied for context
are Site-Independent 0.649, DeepSequence ensemble 0.673 and GEMME 0.678. They
are not matched to this supervised split or equal-weight mutation-bin metric;
no published benchmark prediction file was reused in the reported workflow.

## Fresh Agent Scientist evaluation deliverables

Produce all 37,853 frozen test predictions, fit/selection provenance, mutation
coverage flags, overall/per-bin metrics and the pre-scoring top-20 ranking.
Supply original and revised candidate sequences with separate provenance,
the fused-chromophore map, descriptor implementations, exact-sequence-matched
tool outputs and model-scale limitations. Record resource use, failures and
recovery separately from predictive performance. Report deviations from the
reference workflow without silently changing its training or selection rules.
