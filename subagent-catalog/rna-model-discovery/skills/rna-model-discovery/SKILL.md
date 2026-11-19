---
name: rna-model-discovery
description: Use when an RNA workflow lacks a computational capability and a suitable open-source model or tool must be found, verified and specified for integration.
version: 1.0.0
author: Agent Scientist
license: MIT
---

# RNA model discovery procedure

## 1. Classify before searching

State the biological task, the RNA domain (mrna, sirna, aso, grna, circrna, structure, protein/ligand interactions)
and the exact missing capability as a one-line gap statement ("predict translation efficiency from CDS+UTR
sequence"). A vague gap produces a vague search; sharpen it with the parent if needed.

## 2. Check the registry first

Read the parent-supplied registry ({{resource.scripts/registry.py}} show). An entry already at EVIDENCE_REVIEWED or
WEIGHTS_AVAILABLE for this capability is reused, not rediscovered — report it and stop unless the parent explicitly
orders a refresh.

## 3. Search under authorization

Search only with the parent's explicit search authorization naming sources and scope. Source families: GitHub,
Hugging Face, PubMed, Europe PMC, bioRxiv, Zenodo, official documentation, established bioinformatics repositories.
Parent-owned connectors (pubmed, tooluniverse) are used through their contracts; when unavailable, return a provider
handoff. Record URL, access date and retrieved evidence for every candidate.

## 4. Verify weights availability per candidate

Classify each candidate: WEIGHTS_PUBLIC (artifact URLs resolve, checksums when published), WEIGHTS_RESTRICTED
(license/registration gated — state the gate), NO_WEIGHTS (training-only release). Cite the exact location that
establishes the verdict. A NO_WEIGHTS model is never inference-ready.

## 5. Evaluate on evidence, not accuracy alone

Score with [evaluation criteria](references/evaluation-criteria.md): task compatibility, benchmark credibility,
dataset relevance, weights availability, repository quality, license/commercial terms, installation complexity,
hardware fit, reproducibility, maintenance. Unverifiable dimensions are UNVERIFIED, never assumed. Rank with the
evidence attached; publication accuracy is one row, never the decision.

## 6. Emit the spec

Build the ModelIntegrationSpec for the selected candidate, validate it
({{resource.scripts/validate_spec.py}}, exit 0 required), and record alternatives with their verdicts. The spec is a
plan: it claims no installation, execution or validity. If nothing qualifies, report the searched scope and the
failure reasons — an empty result with scope is a valid deliverable.

## 7. Registry directives

Create/advance registry entries only within DISCOVERED → EVIDENCE_REVIEWED → WEIGHTS_AVAILABLE using
{{resource.scripts/registry.py}}; INSTALLED and beyond belong to rna-model-execution. Adjacent transitions with
evidence notes only. Hand the spec path and registry directives to the parent.

Read [discovery sources](references/discovery-sources.md) and the package
[evidence rules](../../../references/evidence-rules.md).
