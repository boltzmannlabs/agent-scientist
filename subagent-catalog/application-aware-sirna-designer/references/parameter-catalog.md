# Retained siRNA parameter surfaces (seed knowledge)

Seed catalog for source-grounded parameter work. Entries reflect the retained siRNA harness as observed on 2026-11-17.
ALWAYS re-verify each entry against the approved source root before scientific use; a stale entry is a finding to
record, not a default to keep. Procedure: skills/parameter-experimentation.

## Generation — OligoFormer (retained runner)

Source: `sirna_env/models/generator.py` plus the integration runner (`run_local.py` in the oligoformer integration).

| Parameter | Type / range | Retained default | Notes |
|---|---|---|---|
| `transcript_fa` | path, single-record FASTA (DNA or RNA) | required | resolved versioned transcript |
| `top` | int 1–100 | 100 | top candidates also extracted |
| `output_dir` | path | `<fasta_dir>/generation_<stem>` | must NOT exist; created fresh per run |

Native outputs: `all_ranked_candidates.csv` (`oligoformer_native_score`, `target_start`, `target_end`) and `manifest.json`.

## Efficacy — RN.Ai-Predict (primary), RNAiSpline (restricted)

Source: `sirna_env/models/efficacy.py`.

| Parameter | Type | Retained default | Notes |
|---|---|---|---|
| `include_spline` | bool | False | adds restricted RNAiSpline scoring path |
| `guide` | 19–21 nt RNA string | required | antisense guide |
| `context` | mRNA context window | 57 nt recommended in the efficacy docstring; `score_batch` actually extracts 59 nt (`[start-20, start+39]`, Python half-open slicing) | verify the intended window at source before comparing runs; the docstring/code discrepancy is itself an experiment finding |

Outputs: `rnai_percent` (0–100), `rnai_applicability`. Experiment surfaces: context window length and offset;
RN.Ai vs RNAiSpline vs OligoFormer as the single explicit efficacy endpoint.

## Application profiles (ranking weights)

Source: `sirna_env/config.py` → `APPLICATION_PROFILES`.

| Parameter | Values |
|---|---|
| `weights` | dict over {efficacy, specificity, seed_tox, immune, stability}; e.g. oncology .35/.35/.15/.10/.05; allele-selective raises stability to .20 |
| `hard_vetoes` | list, e.g. `immune_ugugu`, `paralog_full_length_hits` |
| `review_window` | 100–150 candidates passed to review |

Weight sensitivity and positive-weight-on-unimplemented-component rules are frozen contract terms, not tunables.

## Frozen gate thresholds (v1.0)

Source: `configs/thresholds.json` (each entry carries provenance; user_operational vs literature_supported).

| Threshold | Value |
|---|---|
| `min_rnai_predict_score` | 50.0 |
| `min_rnaispline_score` | 0.5 |
| `max_full_length_offtarget_hits` | 10 |
| `max_seed_occurrence_fold` | 2.0 |
| `max_pots_percentile` | 90.0 |
| `min_seed_viability_avg_human` | 50.0 |
| `min_duplex_delta_g` / `max_duplex_delta_g` | -45.0 / -25.0 (units as defined in the source; verify) |
| `gc_min` / `gc_max` | 0.3 / 0.7 |

Frozen thresholds may be tightened in a run, never silently loosened.

## Specificity and seed endpoints

- bowtie2 against the GENCODE transcript index, locus-scoped by gene symbol; bowtie2 CLI flags (input format, reported
  alignments, no-unal behavior) are experiment-relevant — extract with the installed binary's help text at run time.
- Seed counting over the retained SEED7 table; POTS percentile from the sispotr human table; 6merDB seed-viability lookup.

## Structure — ViennaRNA 2.7.x

`RNAfold`, `RNAplfold`, `RNAduplex`: dangles, temperature, partition-function window and other CLI parameters must be
extracted from the installed binaries (`--help`) before a combination experiment; the duplex ΔG band above is the frozen
acceptance gate that structure runs feed.

## Combination-experiment starting grids

Hold the fixture, reference index and checkpoint hashes fixed. Suggested first sweeps:
1. Efficacy context window: {45, 53, 57, 61, 65} nt around the cleavage site, single efficacy endpoint fixed.
2. Generator `top`: {25, 50, 100} with identical downstream gates.
3. Application-profile weights: one-at-a-time ±0.05 perturbations around the frozen profile, hard vetoes fixed.
4. Gate thresholds: tightening-only sweeps (e.g. seed fold 2.0 → 1.5) reporting survivor counts, never loosening.
