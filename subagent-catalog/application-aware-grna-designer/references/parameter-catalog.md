# Retained CRISPR/gRNA parameter surfaces (seed knowledge)

Seed catalog for source-grounded parameter work on the retained CRISPR-Design environment, as observed 2026-11-17.
ALWAYS re-verify against the approved source root before scientific use; stale entries are findings to record.
Procedure: skills/parameter-experimentation.

## Knockout runner (task 002)

Source: `environments/CRISPR-Design/src/run_002_knockout.R` (stage 1) and `run_002_specificity.R` (stage 2).

| Parameter | Retained value | Notes |
|---|---|---|
| invocation | `Rscript run_002_knockout.R <run_dir>` | single positional argument |
| `CRISPR_PRIOR_BASE` | env var; prior verified run root (defaults to the KIF11 GRCh38 base) | R library paths resolve under it |
| enumeration | `findSpacers(crisprNuclease=SpCas9, canonical=TRUE, both_strands=TRUE, remove_ambiguities=FALSE)` | NGG-only pool |
| region flank | gene start/end ± 100 bp | window extracted for spacer enumeration |
| threads | `OPENBLAS_NUM_THREADS=1`, `OMP_NUM_THREADS=1` | reproducibility pin |
| R timeout | `options(timeout=600)` | download bound |

Endpoint context requirements (never averaged, native units): RuleSet1 30 nt, RuleSet3-Sequence Hsu2013 30 nt
(python env), CRISPRater 20 nt, CRISPRscan 35 nt (T7/IVT context column), Lindel frameshift 65 nt.

## Request priorities (per-application ranking contract)

Source: `environments/CRISPR-Design/config/*.request.example.json`.

| Field | Example (002 knockout) | Notes |
|---|---|---|
| `priorities.weights` | on_target .35, specificity .25, outcome_quality .30, context .10 | single explicit endpoint per contract |
| `priorities.hard_vetoes` | off_target_exact_match, poly_t_termination_risk, gc_out_of_band | frozen; not tunable |
| `priorities.min_standards` | frameshift_probability 0.6 | acceptance floor |

## Model-policy retained configurations

Source: `skills/publication-calibrated-crispr/references/model-policy.json`.

- Prime-editing on-target: native five-checkpoint PRIDICT2/DeepPrime ensemble (`model_0`–`model_4`); single checkpoints
  and numeric-only replacements underperformed. Batch size is hardware-appropriate (Batch256 on the tested CPU), not a
  universal optimum — treat as a per-host experiment axis.
- Base editing: BEHive/RFcombined retained references; native CBE is a separate research endpoint, not a BEHive
  replacement. CBE feature generation pins RNAfold 2.5.1.
- RS3 full-pool refit is opt-in research, not an automatic upgrade.

## Interpreter profiles (separate environments; never merged)

python_rs3 3.8.20 · python_crispron 3.9.23 · python_editing 3.10.21 · python_behive 3.7.12 · python_crispria 2.7.15 ·
rscript 4.5.3 · python_cbe 3.10.14 + rnafold_cbe 2.5.1 · rscript_rfcombined 4.3.3. Install-time bindings for these
program ids are recorded in the specialist definition's package_info.

## Combination-experiment starting grids

Hold fixture, reference assembly, annotation and checkpoint hashes fixed:
1. Region flank: {50, 100, 200} bp around the target locus, enumeration settings fixed.
2. On-target endpoint selection among verified native scorers (single endpoint, never averaged).
3. Request weights: one-at-a-time ±0.05 perturbations, hard vetoes and min_standards fixed.
4. Prime-editing ensemble inference batch size on the approved host, with the five-checkpoint ensemble fixed.
