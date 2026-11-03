# Protein-engineering case studies for Agent Scientist evaluation

These case studies specify three end-to-end evaluations of Agent Scientist:

| Case | Question | Generalization setting | Detailed case study |
| --- | --- | --- | --- |
| PE01 | Rank BsLipA substitutions by the distributed thermostability score | Single substitutions at positions absent from training | [BsLipA](PE01_BsLipA.md) |
| PE02 | Predict GFP fluorescence when individual substitutions are combined | Fit singles; select on doubles; test on three or more substitutions | [GFP](PE02_GFP.md) |
| PE03 | Predict and prioritize UBE4B domain double mutants | Exploratory train/validation/test partitions of measured doubles | [UBE4B](PE03_UBE4B.md) |

Tracking issues: [PE01 #24](https://github.com/boltzmannlabs/agent-scientist/issues/24), [PE02 #25](https://github.com/boltzmannlabs/agent-scientist/issues/25), [PE03 #26](https://github.com/boltzmannlabs/agent-scientist/issues/26).

The collection covers protein engineering: BsLipA is an enzyme, GFP is a
fluorescent protein, and PE03 concerns a UBE4B domain stability assay. Their
targets and biological interpretations differ.

## Evidence provenance

The numerical results, candidate lists and tool observations below are the
reported reference studies supplied by the project owner. Their original
model artifacts, split manifests, prediction files and provider receipts are
not included in this documentation contribution. Preserve these results as
reference baselines; a fresh Agent Scientist evaluation must produce its own
execution evidence before claiming reproduction. Public papers establish assay
and method context, not the local supervised-model results quoted here.

The linked BsLipA and GFP CSVs were checked against their immutable
Hugging Face revision while preparing these documents. Their row counts match
the supplied brief. ProteinGym metadata was inspected at revision
`144fe22b07dfaeec2b366f2346203a9838a55b4c`; this is a documented metadata lookup,
not a claim about the revision used by the original studies. PE03 still needs
the original extracted CSV and its checksum for an exact replay.

## Running an evaluation

Use each case's problem, data contract, split and workflow as the execution
brief. Keep the reported result tables as reviewer reference material when
conducting a blind evaluation. Separate model fitting and selection from a
held-out evaluator's access to test labels. The case-study documents themselves
contain historical test summaries and are not blind test fixtures.

1. Freeze the Sci revision, provider/model identity, prompt, available tool
   schemas, dependency versions, seeds and authorized resource allowance.
2. Audit the downloaded data and assay sequence; save URLs, immutable revisions
   and hashes. Reconstruct variants and retain numbering/coordinate coverage.
3. Recover the exact split manifests. PE01 counts and PE03 seed 303 alone do not
   reconstruct the historical partitions. If those artifacts cannot be
   recovered, version the new partition and report it as a different evaluation.
4. Fit and select only with the permitted labels. Save a selection lock and
   hashes of predictions before test scoring. Freeze candidate rankings where
   required. External comparisons must preserve the original selected method.
5. Execute suitable real tools, retaining provider/job identities, raw artifacts,
   exact submitted/returned sequence checks and mapping evidence. Record
   unavailable operations and failed calls; a catalog entry is not an output.
6. Evaluate predictive performance, coverage, uncertainty, structural context
   and candidate trade-offs. Recompute metrics from row-level predictions using
   each case's declared subsets and aggregation rules.
7. Report agent execution reliability and scientific quality separately:
   completed stages, failures, recovery attempts, elapsed time, CPU/GPU use,
   remote-service cost where known, and the strength of each biological claim.

Run scripts and any long-lived harness in a persistent session when appropriate.
Store datasets, caches, models, logs, trajectories and raw tool outputs in the
run's external artifact directory; keep repository changes reviewable. Freeze
resource ceilings before dispatch rather than silently renewing them after a
failed run. Respect genuine approval, licensing and access gates.

## Required result bundle

- Dataset/source hashes, reference sequence, residue maps and split manifests.
- Reproducible scripts, dependency lock, prompt/configuration and resource record.
- Fit/selection provenance, frozen model artifacts, prediction hashes and all
  required row-level held-out predictions, including coverage flags.
- Metrics with subset definitions, undefined-value/tie handling, units and
  uncertainty methodology; comparison to the reported baseline with deviations.
- Candidate sequences, mutation identities, selection rationale and distinction
  between measured leads and prospective hypotheses.
- Exact-sequence-matched property, structure, geometry and fold-comparison
  outputs with raw scales, numbering conventions, job receipts and failures.
- A final report distinguishing assay observations, statistical predictions,
  structure/property predictions and untested biological conclusions.

## Interpretation rules

Validation chooses the method; test results characterize its generalization.
Imputed component effects remain distinguishable from measured effects. A
high-confidence fold is supporting evidence, not an assay measurement. Preserve
tool-specific scales and sign conventions, normalize structural comparisons
explicitly, and avoid summing single-mutant predictions into validated
combination energies. The execution issues track fresh runs; adding these
case-study documents does not itself complete those evaluations.
