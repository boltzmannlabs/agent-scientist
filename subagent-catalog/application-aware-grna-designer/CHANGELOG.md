# Package changes

## 1.4.0 — execution environment, source-grounded parameters

Live-run testing (bench profile, 2026-11-17) found the specialist under-using its own staged assets: packaged audit
scripts were reported NOT_RUN when an exact path was not handed over, and inline code attempts hit the single-query
execution gate. This revision fixes both restrictions inside the leaf:

- instructions.md gains "Execution environment and tool-call discipline": the staged package root and scripts are the
  specialist's own execution environment; run scripts file-based with a stdlib Python; never inline `-c`/`-e`; check
  staged assets before declaring them missing; install-resolved interpreter bindings (RS3/CRISPRon/editing/BEHive/CBE
  profiles) are recorded in the definition's package_info.
- New skill `parameter-experimentation` plus `references/parameter-catalog.md`: source-grounded parameter discovery
  over the retained CRISPR-Design environment (R runner usage/env/thread pins, findSpacers enumeration settings,
  endpoint context lengths, request priorities weights/vetoes/min_standards, PRIDICT2/DeepPrime ensemble and batch
  axis, separate interpreter profiles), frozen-frame combination experiments and honest ranking with negative results.

No scientific claims, model stances or fixture contracts changed.

## 1.3.0 — benchmark-informed specialist

Added a complete publication-calibrated-crispr skill with standalone policy script and supporting model-policy/historical-evidence JSON. Retains native ensembles/defaults, keeps RS3refit opt-in research and CBE research-only, and prevents mismatched label/condition promotion. Adds APPLICATIONS.md, TOOLS_AND_SERVICES.md, review-only setup_plan.py,16CSVpolicy fixtures and policy/setup regression tests. Adds isolated CBE and RFcombined dependency profiles and optional executable bindings; generalized read-only R metadata probes. Current actual validation is tests/validation.json. Earlier package source was backed up before edits; earlier validation remains in tests/history/. No automatic specialist installation, credentials, remote service call or new scientific model/performance claim.

## 1.2.0 — reproducible scientific harness

### Scope and understanding

This is a portable, disabled-by-default SCI leaf specialist, not a bundled predictor. Its original thirteen CRISPR application routes, native scorer separation and parent-owned permission model remain. The chat harness supplied execution/evidence lessons; siRNA predictors, biological parameters and historical model approvals were not transferred to CRISPR.

### Delivered

- Updated application-aware-grna-workflow to 1.1.0 and added reproducible-scientific-harness 1.0.0. Both remain procedural skills; package-level schema/script resources are supplied by the parent/leaf instructions rather than dangling skill-local references.
- Added explicit config freezing, native feature/checkpoint applicability, pretrained-only training restrictions, unique-cohort accounting, label exposure, immutable row identity, coordinate conventions, native mode/dropout and retained failed-attempt rules.
- Split request-result output from scientific run-record schema version 2. Existing v1 records are not silently rewritten. Record v2 adds run/config identities, execution kinds, provenance, comparison applicability and completed-only benchmark publication metadata.
- Added the offline harness audit CLI. It checks consistency without executing listed scientific commands; optional schema validation uses explicit Draft 2020-12. No redundant dialect URL is embedded because the installed portable-package path scanner misclassifies URI schemes as drive paths.
- Artifact access is opt-in, root-confined and hash-bound; optional CSV/TSV data-row counts and decoded raster checks are available. Empty artifact verification is not accepted as an integrity pass. Decoding is not visual or biological validation.
- Hardened malformed request types and CLI JSON failures. siRNA/RNAi is out of scope, not Cas13; the existing pathogen review gate retains precedence. This metadata gate is not comprehensive biomedical safety clearance.
- Added the optional harness dependency profile, requirements/environment recipes and manifest executable binding. Native scientific profiles and external assets remain distinct.
- Fixed metadata distribution-name normalization and duplicate handling. Effective interpreter lookup is used instead of last-entry overwrite; conflicting visible versions remain in evidence.
- Added current-version package validation and a separate installed-SCI schema probe. SDK dependency selection is read-only and ABI-checked; no SCI bootstrap, synchronization, package installation, owning-profile edits or tool registration is performed.

### Executed verification

The installed SCI strict schema and leaf-tool restrictions passed. All 8 original request fixtures and 35 software/synthetic harness unit tests passed. Actual request/audit CLIs, core and optional harness metadata probes passed; both JSON Schemas and six environment YAML recipes validated. Check logs and current scope are in tests/validation.json and tests/*.log. tests/PROVENANCE.sha256 inventories relative-path file hashes and is verified by the packaged validation script.

The existing approved QA interpreter provided Python3.13.7, jsonschema4.19.2, PyYAML6.0.3, packaging26.3 and Pillow11.3.0 under effective metadata resolution. Multiple PyYAML/packaging metadata versions are visible and recorded; this is not a clean install, solver lock or guarantee of module/model readiness. No packages were installed for this update.

### Preserved and pending

Earlier validation is retained in tests/history/validation-v1.1.0.json but not reused as current-version live behavior. No scientific source dataset, checkpoint, native model or prior siRNA run was modified. No guide generation, native CRISPR inference, benchmark performance improvement, remote scientific job, live specialist test or newly reviewed installation was performed. Exact-dev-commit integration remains pending; automatic matching remains disabled. Native assets, scientific inputs, licenses, execution permissions and provider readiness must still be supplied/reviewed for a real assignment.

## 1.5.0 — mechanical read-scope guard

Model-comparison finding L1: read-scope policy was instruction-level only. New scripts/read_guard.py
(init/check/show/verify with append-only verdict log), mandatory instruction wiring (reads without ALLOW
verdicts invalidate the report) and unit tests. Also records the parent policy note for local-fixture registry
transitions in the shared registry CLI.

Retest amendment (same day): guard v1 FAILED its retest — all three models self-granted ALLOW by passing their
own --allow roots (the guarded entity controlled the allowlist), and one direct-execution hit a lost execute-bit.
v2 removes the flaw by construction: no --allow flag exists; authorized roots are extracted ONLY from explicit
authorization markers in the hashed verbatim assignment; verify detects assignment tampering; scripts are
invoked via python3 (execute-bit independent). Unit tests cover deny/allow/tamper.

## 1.6.0 — mechanical read-scope guard v2 + computational selection awareness

New scripts/selection_record.py (template/validate: criteria, ranked per-property rows, best computational
candidate with property attribution vs runner-up, sensitivity note) wired mandatorily into instructions after
any ranking. best_under_contract only; best_design stays null.
