# 1.1.0 — execution environment, source-grounded parameters

Live-run testing (bench profile, 2026-11-17) found the specialist under-using its own staged assets: it reported
"no approved controller interpreter" though its scripts are standard-library only, and declared packaged scripts
NOT_RUN when an exact path was not handed over. This revision fixes both restrictions inside the leaf:

- instructions.md gains "Execution environment and tool-call discipline": the staged package root and scripts are the
  specialist's own execution environment; run scripts file-based with a stdlib Python; never inline `-c`/`-e` (blocked
  in single-query sessions); check staged assets before declaring them missing; install-resolved program bindings live
  in the definition's package_info.
- New skill `parameter-experimentation` plus `references/parameter-catalog.md`: source-grounded parameter discovery
  (go to the approved source, extract the real surface, verify catalog entries), frozen-frame combination experiments
  (fixture + budget + acceptance metric declared before running), file-based one-job-per-configuration execution, and
  honest ranking with negative results. Seeded from the retained harness: OligoFormer runner flags, RN.Ai/RNAiSpline
  context window, application-profile weights/vetoes, frozen thresholds, ViennaRNA/bowtie2 surfaces.

No scientific claims, gates or model stances changed; fixture contracts are untouched.

# Initial portable siRNA package — 1.0.0

## Delivered

A new application-aware-sirna-designer directory was created rather than overwriting the older sirna-design-specialist, its code or its historical results. The current SCI manifest declares a disabled-by-default leaf, three complete custom skills, exact built-in grants, optional selected executable bindings and reviewed optional Boltzmann RNA integration. No external MCP or credential is bundled.

The package transfers the retained human siRNA harness's eleven task frames, scoped application requirements, frozen-gate discipline, single-endpoint requirement ranking, model/input identity and native-mode audits, preserved config trajectories, pretrained-only restriction and publication-calibrated conclusions. It does not transfer siRNA parameters into CRISPR or ASO and does not promote the exploratory core19 configuration as a demonstrated upgrade.

Setup is first-class: profile-specific direct requirements, a separate bio-tools conda recipe, an executable plan/approved-fresh-venv installer, private binding template, isolated dependency metadata probes, opt-in root-confined asset hashing and separate scientific fixture requirements. No implicit network, existing-prefix mutation, model acquisition, license acceptance or third-party source-code redistribution is performed. Requirements are checksum-bound to the reviewed plan. Installer caches stay in the fresh approved prefix. Inherited pip configuration/target/index variables are cleared; wheel-only resolution avoids unreviewed source builds. The host must still enforce actual filesystem/network policy.

The generic MIT-authored harness record auditor and installed-SCI schema probe are reused with siRNA task IDs; no third-party model code is copied. Separate preflight and scientific-record contracts avoid pretending a missing-input response is a scored run. Synthetic metadata fixtures are barred from measured benchmark publication.

## Actual evidence and limitations

Local software/metadata CLI tests, malformed-input and scope tests, config/record identity, cache-versus-fresh evidence, incomparable protocol deltas, cardinality, artifact hashes/rows/raster checks, source-root and symlink escape, approval and no-overwrite checks are exercised. A real disposable core venv is created and verified without pip or network, then cleaned as test scratch. A separate synthetic launch-failure test verifies incomplete-state receipts and inherited PIP_TARGET removal; it is not a real scientific/tool failure. Current counts, check logs, strict SDK status and hashes are recorded in tests/validation.json and tests/PROVENANCE.sha256.

The optional QA and existing OligoFormer interpreters pass isolated direct-package metadata checks. The existing RN.Ai/RNAiSpline interpreter does not: isolated mode excludes inherited packages used by the historical layered environment. RN.Ai is missing scikit-learn, biopython, tensorflow and keras metadata there; RNAiSpline is missing scikit-learn, biopython and torch. These actual checks are retained in tests/dependency-probe-evidence.json. This finding neither repeats nor invalidates prior efficacy runs; it prevents a false claim of self-contained native readiness. All metadata checks keep model_readiness_verified=false.

No third-party dependency clean reconstruction, native CRISPR/siRNA inference, candidate generation, new benchmark, model training, target/reference acquisition, GPU probe, platform job, live LLM specialist run or owning-profile installation was performed for this package. Exact native assets, permissions, licenses, valid model features and trusted fixtures remain prerequisites. New source-package functionality is distinct from an installed/enabled agent and from biological validation. Old performance claims are not reasserted as new results or global predictor ceilings.

## 1.1.2 — boltzmann integration configuration pass

No content changes. Version bump to re-enter the managed-update review and configure the optional Boltzmann
integration (private authorization + workflow tools) that was deferred at the original install, closing the
tool gap surfaced by the CS4 model-comparison case.

## 1.2.0 — mechanical read-scope guard

Model-comparison finding L1: read-scope policy was instruction-level only — compliant models blocked unauthorized
reads, others read out-of-scope and executed (CS2, 2026-11-18). This revision makes the gate mechanical and
auditable: new scripts/read_guard.py (init/check/show/verify; workspace/output/package roots auto-allowed;
everything else DENIES with an append-only verdict log), mandatory wiring in instructions (a read without an
ALLOW verdict, or any overridden DENY, invalidates the report; verify exit 0 required) and unit tests. Also
records the parent policy note for local-fixture registry transitions in the shared registry CLI.

Retest amendment (same day): guard v1 FAILED its retest — all three models self-granted ALLOW by passing their
own --allow roots (the guarded entity controlled the allowlist), and one direct-execution hit a lost execute-bit.
v2 removes the flaw by construction: no --allow flag exists; authorized roots are extracted ONLY from explicit
authorization markers in the hashed verbatim assignment; verify detects assignment tampering; scripts are
invoked via python3 (execute-bit independent). Unit tests cover deny/allow/tamper.

## 1.3.0 — mechanical read-scope guard v2 + computational selection awareness

Request finding: ranked panels existed but no structured "which design was best and which properties made it
best" record. New scripts/selection_record.py (template/validate; criteria, ranked rows with per-property values,
best_computational_candidate with explicit property attribution vs runner-up, sensitivity note; validates
rank-1 consistency and the mandatory not-experimental limitation) wired mandatorily into instructions after any
ranking. best_under_contract only; best_design stays null.
