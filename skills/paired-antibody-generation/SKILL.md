---
name: paired-antibody-generation
description: Use when generating paired antibody VH/VL sequences.
version: 1.0.0
author: Boltzmann Labs
license: 'Project-authored instructions: see repository LICENSE.'
platforms:
  - linux
  - macos
  - windows
metadata:
  sci:
    tags:
      - science
      - workflow
    category: science
---

# Paired antibody generation Skill

Use an actual paired generative model for de novo requests; database retrieval and uniform amino-acid randomization are not substitutes. Specify VH/VL versus full-length chains and distinguish computational checks from functional validation.

## When to Use

Use for requests matching the workflow below; do not extend the scientific scope without clarification.

## Prerequisites

Inspect current tools with `tool_search` where available and installed skills with `skills_list`. Service connections, authorization, datasets, and scientific software are not included merely by installing these instructions. Verify the prerequisites in the procedure; obtain approval before downloads, installation, or execution.

## How to Run

Use `read_file` for supplied documents and `search_files` for local discovery. Use configured scientific tools when suitable; any local execution uses `terminal` in an approved environment, never an ad hoc modification of the Agent Scientist runtime. Keep credentials and private samples out of reusable instructions.

## Quick Reference

Confirm the requested input, output, available tools, and prerequisites before following the workflow. These instructions are not proof of scientific validity or an installed service.

## Procedure

### Workflow specification and provider selection

- Inspect available scientific tools before choosing execution. When Boltzmann is authorized, first load `skill_view(name='boltzmann:tools')` and its matching complete contract; this plugin skill is not in the ordinary available-skills index. Discover deferred operations with `tool_search` and inspect their schemas with `tool_describe`. For random-antibody requests, start with that skill's `references/modules/protein-antibody-generation.md`, not the local procedure below.
- Execute a matching verified workflow with Boltzmann. Supporting skill instructions do not authorize changing providers. Missing session tools mean setup/restart is needed, not that no suitable tool exists. Missing inputs or authentication failure stop execution; never silently switch providers. For a nonmatching contract, explain the limitation and obtain explicit approval before an alternative. Use the local procedure only after an explicit local-execution request or an informed, approved fallback; do not inspect GPUs or download local generators before this decision.
- For a workflow-only request, create a concrete SOP and request templates without submitting jobs. Mark missing required scientific values unresolved, distinguish proposed settings from confirmed inputs, and validate request field names and dependency order. Never ask for an experiment name; if a Boltzmann job is later submitted, omit the name unless the user supplied it and report the connector-generated name.
- Build target-aware handoffs as antigen/framework structures -> structural design -> paired sequence design when needed -> paired QC -> developability/CDR predictions -> antigen/VH/VL complex prediction -> optional interface scoring -> shortlist. Require explicit source pairing and actual output inspection at every boundary; separate submission acceptance from terminal and scientific validation.
- Use complete prediction bundles with matching confidence/PAE companions for interface scoring. Keep antigen-to-antibody scores separate from VH-to-VL scores because the internal antibody interface does not establish target binding.
- Record partial output counts without inventing pairings or launching automatic top-up jobs. Preserve framework numbering when mapping CDR selections to structure-conditioned sequence-design inputs.

### Local unconditional-generation workflow

1. Inspect primary source https://github.com/OliverT1/p-IgGen and model card ollieturnbull/p-IgGen. Read model.py and utils.py rather than guessing APIs. Check hardware and free GPU memory without disturbing other workloads.
2. Use an isolated Python 3.11 environment outside the user's project. A tested combination is torch==2.8.0, transformers==4.56.2, antpack==0.3.8.6.2 and p-IgGen source package. Increase UV_HTTP_TIMEOUT for wheel download timeouts; do not change global environments.
3. Resolve and record model and source commit hashes. Download a pinned Hugging Face snapshot, then construct piggen.model.pIgGen(model_name=local_snapshot, device='cuda'). Seed transformers.set_seed. Generate small batches with model.generate(num_return_sequences=5, temp=1.0, top_p=0.95, discard_bottom_n_percent=None) under torch.inference_mode(). No antigen prompt is needed for unconditional generation.
4. Store formatted raw samples incrementally. The model emits concatenated VH+VL; do not split by assumed length. Use antpack.PairedChainAnnotator(scheme='imgt').analyze_seq(sequence), requiring H and K/L calls with empty errors. trim_alignment(sequence, result) returns sequence, numbering, start, exclusive end. Require complete nonoverlapping domains covering the whole generated sequence, retaining original pairings. Endpoint checks used in the tested workflow were H 1/128 and L 1/127. Document acceptance criteria.
5. Keep the first requested number of unique accepted pairs, with a bounded retry budget and rejection log. Export paired CSV and separate VH/VL FASTA records. Save seed, sampling settings, versions, hashes, generation code, and validation report. Re-read exports to verify counts, unique pairs, amino-acid alphabet, cross-format equivalence, and annotation calls.
6. Report actual outputs, tools, and absolute paths. Never call outputs experimentally validated binders. Domain annotation is not structure prediction, functional validation, or a guarantee of novelty relative to training data.

### Target-aware pipelines and reporting

- When alternatives are authorized, discover tools by the required scientific capability, then validate the selected tool's exact schema. A retrieval tool or documentation-information tool is not a generator or simulator.
- Keep unconditional paired generation distinct from antigen-conditioned design; antibody architecture checks and generic binding scores do not establish binding to a named antigen.
- Apply solubility and absolute melting-temperature thresholds only when the returned model's scale, units, and applicability are verified. Mutation ddG and sequence instability indices are not melting temperatures in degrees Celsius.
- For multi-stage requests, report each stage as actual input -> operation and actual tool -> returned artifact -> exact transformation for the next stage. Preserve IDs and VH/VL pairing; stop dependent stages on an error or unmet required gate instead of inventing scores or forcing a top-N shortlist.
- Consolidate necessary target-state, epitope, framework, run-size, and compute-budget questions into one clarification round before submissions. Distinguish a pilot trajectory from converged or experimental validation.

## Pitfalls

- The upstream separated-output CLI has suspicious iteration over a tuple of chain lists; use Python generation API and explicitly paired annotation/export instead.
- The upstream batch_size argument does not implement chunked generation; manually loop over small num_return_sequences batches to bound memory.
- Upstream README direction wording is inconsistent. Verify implementation: forward prompt is '1', forward output is VH+VL, terminating at '2'.
- Annotation scores are not folding or binding probabilities.

## Verification

Inspect actual outputs, provenance, counts, units, and limitations. Report missing dependencies or partial results honestly. A successful command or security review does not establish scientific correctness.
