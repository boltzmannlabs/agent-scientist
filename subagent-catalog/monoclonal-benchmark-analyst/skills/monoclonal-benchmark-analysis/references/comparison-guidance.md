# Comparable measurements

Before execution, specify which quantities answer the actual task and which conditions must match. Preserve assay/construct, sequence pairing, native context, software/model revision, preparation, sampling budget, metric units/direction, aggregation and selection rules.

Label each comparison as matched, conditionally comparable, non-comparable, unavailable or not-applicable with its reason. Retain source-reported values separately from MAIN's new outputs. Dataset aggregates remain aggregates; they are not candidate measurements or universal thresholds.

Use a suitable experimental/native reference for native-based structural accuracy. The [official DockQ implementation](github.com/wallnerlab/DockQ) takes model and reference complexes; valid chain/residue correspondence matters. Agreement to a predicted reference is model agreement, not experimental docking accuracy. Missing reference data makes the metric unavailable, not zero.

Prediction confidence, interface scores, sequence likelihood and contact counts describe different evidence from experimental affinity/function. Developability descriptors, such as those in [TAP](opig.stats.ox.ac.uk/webapps/sabdab-sabpred/sabpred/tap), have applicability and reference-population limits. Do not force a composite or predicted KD when no calibrated, task-valid method exists.

Investigate training/test overlap, related-sequence or structural leakage, label availability and evaluator access before claiming benchmark reproduction. The [FLAb2 preprint](pmc.ncbi.nlm.nih.gov/articles/PMC12767642/) is a primary example of why property-specific validation and confounders matter; it does not prescribe a threshold for this task.

A reference-only or single-case comparison does not reproduce a population benchmark. Missing experimental endpoints remain missing. Report disagreement and uncertainty, including failed controls, rather than choosing only favorable scores.
