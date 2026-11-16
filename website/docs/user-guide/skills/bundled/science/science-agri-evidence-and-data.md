---
title: "Agri Evidence And Data — Research sources and fit formulation observations"
sidebar_label: "Agri Evidence And Data"
description: "Research sources and fit formulation observations"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Agri Evidence And Data

Research sources and fit formulation observations.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/science/agri-evidence-and-data` |
| Version | `1.2.0` |
| Author | Gopi Krishna, Agent Scientist |
| License | MIT |
| Platforms | linux, macos, windows |
| Tags | `literature`, `patents`, `provenance`, `measurements` |
| Related skills | [`agri-formulation-workflow`](../../bundled/science/science-agri-formulation-workflow.md), [`agri-models-and-design`](../../bundled/science/science-agri-models-and-design.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Sci loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Agricultural Evidence and Data Skill

Use project-owned sources and explicitly declared observations to support a design
decision. Search hits, descriptive fits and simulator outputs each support different
claims; none automatically validates a product.

## When to Use

Use for literature/patent search, source review, measurement imports, calibration,
local response learning, grade/supplier specifications and prices, historical
benchmarks, citations and report exports.

## Prerequisites

Use the installed `sci-agriformulations` package through `terminal` and
`sci --run-module agri_tool --request-file PATH` for research/data/project actions.
Load the workflow skill for the exact request and workspace conventions. Use `skill_view` for
the workflow or model skill when designing recipes or applying fitted coefficients.
Actual full-text review may require Agent Scientist's available source-reading
tools; do not claim it happened merely because metadata was retrieved.

## How to Run

Discover `operation="catalogue", action="research"` (or `"data"`, `"project"`,
`"legacy"`) help first. The initial operation inventory is catalogue
`action="operations"`; do not invent a catalogue `discover` action.
Research actions save searches and source IDs. Data actions preview/import files,
review observations and fit by durable dataset ID. Project actions return saved
results and export artifacts. Keep all IDs tied to the owning project.

## Quick Reference

| Evidence | Meaning |
|---|---|
| LLM ingredient/property proposal | Explicit unvalidated design assumption |
| Retrieved metadata/abstract | Source discovery, with review scope stated |
| Reviewed source | Recorded source content, applicability and claim limits |
| Declared experimental data | User-supplied observations requiring provenance/QC |
| Declared synthetic data | Simulator/fixture observations; no empirical validation |
| Numerical scenario | Equation output under resolved inputs |
| Descriptive fitted model | Relationship fitted to declared observations |
| Validated local response learning | Restricted measured-domain prioritization, not approval |

## Grade, Supplier and Baseline Evidence

The workflow skill now automatically evaluates formulation problems and coordinates
cost/performance optimization. Load it with `skill_view`, including its
`references/cost-performance-optimization.md`, for the execution protocol. Support
all relevant grades, supplier alternatives and ingredient combinations with traceable
specifications and price evidence rather than silently assigning identical properties.

For each material option preserve chemical/grade identity, assay, supplier/lot,
TDS/COA source and scope, quote/listing date, currency, price unit, quantity tier,
delivery/freight terms, and availability/approval restrictions. Use supplied quotes
or actually retrieve public sources with available research/source-reading tools.
A web listing is not a firm quote; an old estimate is not a current supplier price.
Research does not authorize outreach, purchases or procurement commitments.

Store grade_source/supplier/lot in supported recipe fields and price provenance in
cost notes or price_estimate. Do not infer performance, impurity compatibility or
availability from a supplier name or assay alone. Link measurements/fits to the exact
recipe version and matching conditions; changed grades/ingredients can invalidate a
previous fit or require a new mapping. Preserve the untouched baseline, sources and
all iteration links. Report missing data and conditional scenarios explicitly.

## Procedure

1. Frame research around actual active, formulation class, application and the
   uncertainty that matters. Save searches through `research`; retain provider
   failures and partial retrieval instead of reporting a complete search.
2. Distinguish metadata-only, abstract-reviewed and full-text-reviewed evidence.
   Mark a source reviewed only after actual review with notes identifying the
   supporting observation, matching conditions and limitations. A reviewer label
   is not proof that a claim is supported.
3. For observations, preview the file and identify units, recipe, individual active,
   condition and independent batches. Ask for unresolved identity/unit mappings
   with native `clarify`, or in chat if it is unavailable. Never fabricate data.
4. Import with the true declared source kind: experimental, literature, synthetic
   or unknown. Preserve original bytes/hash, mapped columns, explicit unit
   conversion and excluded rows. Technical repeats do not replace independent
   batches; repeated times do not replace distinct recipes.
5. Review QC and exclusion reasons, then fit supported data by saved dataset ID.
   Fits are descriptive. Keep residuals, held-out error, measured range, batch
   counts and limitations visible; source origin alone does not prove validation.
6. Apply a fit only to its matching recipe/active/model and current source review.
   Retain engine and dataset identity checks. Extrapolation must be explicit, and
   edited fitted coefficients become assumed scenarios.
7. Local composition-response learning requires actual measured recipes, matching
   ingredient basis/format/process, a passing recipe-held-out utility gate and
   candidate compositions within the measured convex hull. Do not circumvent a
   refusal by invoking another fitter and calling its output validated.
8. Preserve quote/specification evidence and baseline comparisons through cost
   optimization. Ask only for essential unresolved evidence; do not force the
   automatic workflow into a manual mode-choice or Run menu.
9. Export the saved project/report when requested. Keep raw data, source notes,
   recipe versions, exact scenarios, result failures and manifests together.
   Historical workflows use only declared legacy identifiers; retain their
   original gate failures and scope. Run old lab-operation modules only when
   explicitly requested; they are not the current design roadmap.

## Chat Result Format

Respect the active chat surface: use Markdown tables where they render; in the
plain CLI use aligned columns or labeled sections, as Sci's platform guidance
requires. Keep the same values, units, criteria and warnings in either layout.

Summarize evidence, imports and fitted results in concise Markdown rather than
showing raw JSON. Use a table for source/title, review scope, relevance and
citation; use a separate table for fitted metrics with units, dataset identity,
measured range and validation status. Distinguish retrieved metadata from
reviewed evidence, synthetic from experimental data, and descriptive fit from
validated local learning. For material/cost alternatives include grade/supplier,
assay, price source/date/unit/quantity terms and the property evidence supporting
the baseline comparison. Keep provenance gaps and limitations visible, retain
the saved record IDs, and offer the PDF/ZIP when the user wants full detail.

## Pitfalls

- A patent hit does not establish novelty, freedom to operate, registrability or
  current legal status. A publication title does not establish claim support.
- Literature values transfer only under justified identity, units and assay
  conditions. Do not pool percent release with mg/g without an independent basis.
- Synthetic calibration verifies machinery; it cannot establish empirical accuracy.
- Descriptive curve fitting cannot identify unmeasured chemistry or resolve
  confounded parameters. Fitted release is not biological efficacy.
- Keep archived surrogate utility/coverage failures explicit. A historical report
  is not permission to advertise calibrated prediction intervals.
- Use only uploaded/project-owned data and the user's authorized sources. Never
  expose credentials or raw account diagnostics in the scientific report.

## Verification

Ensure citations refer to actually retrieved/reviewed sources, each fitted result
references its actual dataset, source kinds and units survived import, invalid or
excluded observations remain auditable, and output language matches the evidence.
