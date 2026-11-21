# Candidate evaluation criteria (evidence-attached scoring)

Score every candidate on each dimension with a value and an evidence citation (URL + access date, or registry/file
reference). Never let a single dimension decide.

| Dimension | What counts as evidence | Red flags |
|---|---|---|
| Task compatibility | README/paper task statement matches the gap, input modality and organism scope | task name matches, input modality differs |
| Benchmark performance | published numbers **with cohort, endpoint and protocol context** | accuracy quoted without cohort/baseline |
| Dataset quality/relevance | dataset citation, size, label provenance, leakage discussion | labels from the same source as training |
| Pretrained weights | artifact URL resolving + published checksum | "weights available soon", registration walls undisclosed |
| Repository quality | tests/CI present, runnable example, issue activity | no example, dead issues, force-push history |
| License/commercial use | LICENSE file read at the pinned commit | "research only" in README but MIT in LICENSE root |
| Installation complexity | dependency file at commit, framework versions | unpinned deps, conda+pip mixes without lock |
| Hardware requirements | stated VRAM/RAM or inferred from architecture, cited | unstated and architecture suggests large GPU |
| Reproducibility | seeds, deterministic paths, fixed commits | floating `main`, missing seeds |
| Maintenance status | commit dates, release cadence at access date | abandoned with open breakage |

Scoring: VERIFIED_GOOD / VERIFIED_WEAK / UNVERIFIED per dimension. A candidate may be selected with VERIFIED_WEAK
dimensions only when the rationale says why they are acceptable. UNVERIFIED dimensions cap the registry entry at
EVIDENCE_REVIEWED — never advance to WEIGHTS_AVAILABLE with an unverified weights verdict.
