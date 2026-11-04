---
title: "Scientific Data Workflows — Use when chaining scientific retrievals and calculations"
sidebar_label: "Scientific Data Workflows"
description: "Use when chaining scientific retrievals and calculations"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Scientific Data Workflows

Use when chaining scientific retrievals and calculations.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/research/scientific-data-workflows` |
| Version | `1.0.0` |
| Author | Boltzmann Labs |
| License | Project-authored instructions: see repository LICENSE. |
| Platforms | linux, macos, windows |
| Tags | `science`, `workflow` |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Sci loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Scientific Data Workflows Skill

Use for scientific database lookups, sequence calculations, structural metadata, and integration tests requiring auditable data flow. Complements literature-search and citation skills.

## When to Use

Use for requests matching the workflow below; do not extend the scientific scope without clarification.

## Prerequisites

Inspect current tools with `tool_search` where available and installed skills with `skills_list`. Service connections, authorization, datasets, and scientific software are not included merely by installing these instructions. Verify the prerequisites in the procedure; obtain approval before downloads, installation, or execution.

## How to Run

Use `read_file` for supplied documents and `search_files` for local discovery. Use configured scientific tools when suitable; any local execution uses `terminal` in an approved environment, never an ad hoc modification of the Agent Scientist runtime. Keep credentials and private samples out of reusable instructions.

## Quick Reference

Confirm the requested input, output, available tools, and prerequisites before following the workflow. These instructions are not proof of scientific validity or an installed service.

## Procedure

1. Identify scientific operations, required inputs, output fields, and backend constraints. For ordinary database lookups, proceed from the named entity and requested fields; ask for a concrete test only when the user requests testing but omits the test target. For a single-tool test, count scientific executions separately from discovery/schema calls.
2. Discover operations with `mcp__tooluniverse__find_tools` and inspect returned parameter schemas before execution. Load the execution-wrapper schema with `tool_describe` when needed. Search a precise capability or exact tool name separately if a compound query omits a required operation; compound searches may return adjacent tools.
3. Execute through `mcp__tooluniverse__execute_tool` with explicit arguments. In ToolUniverse-only tests, never replace failed scientific calls with remembered facts or another backend. Do not install software or alter environment configuration for a read-only test. If higher-priority instructions require ancillary retrieval, disclose it separately from the tested scientific path.
4. Inspect the scientific payload, not just wrapper success. Responses may contain JSON serialized inside `result`. Check required fields before continuing; stop dependent operations when an accession, sequence, entity ID, or numeric input is missing.
5. Pass actual returned identifiers and full sequences into downstream operations. Preserve sequence strings exactly. Do not use accession-based refetch when the requested handoff is a sequence. Record producer tool and field → returned identifier or sequence → consumer tool and argument. Prefer direct programmatic transfer when available; otherwise check the submitted string against the source payload.
6. Parallelize independent calculations only after their shared retrieval succeeds. Submit each domain separately to each requested calculator; never concatenate chains. Compare returned lengths and overlapping composition fields, and report discrepancies rather than smoothing them over.
7. Return the requested result first, then a concise audit separating retrieved facts, calculated values, interpretation, tools used, handoffs, source links, and errors/missing data. Keep requested tables to the specified rows and columns. For a complete-result request, return every field of the scientific result.

### Standing reporting rules

- For Boltzmann jobs, never ask, confirm, or offer a choice about `experiment_name`. Preserve an exact name only when the user supplied one; otherwise omit the field so the connector generates a readable unique label, then report the returned name. Ask separately only for missing scientific inputs, substantive choices, validation gaps, or required execution authorization.
- Treat synthetic fixtures as deterministic tests, not antibodies or biological records. For live databases, validate field presence and identity rather than assuming permanent exact result lists.
- Preserve tool precision and units. Distinguish documented unit conventions from explicit returned unit fields; report absent units honestly.
- Never infer binding affinity from structure metadata or sequence calculations.
- Prefer links returned by tools. Label identifier-derived links as constructed. Never claim a page was visited, a search ran, or a citation was verified without a real corresponding call. Build the final tool audit from actual calls: a Python HTTP request is not a web.run visit, and a working REST response does not establish that the human-facing entry page loaded or failed.
- End tool-assisted answers with a concise `Tools used:` line naming the scientific operations actually executed and their retrieval routes. Loading a skill or discovering a schema is not database retrieval; do not describe results as verified until a returned payload supports them. Report failed attempts only when an actual call and error are present, not as a plausible explanation of provenance.
- Avoid extra scientific calls merely to embellish an integration-test answer; they obscure operation counts and add failure paths.

See `references/protein-sequence-structure.md` for sequence and structural-data recipes, `references/chemical-properties.md` for compound identity, SMILES, and 3D descriptor retrieval, and `references/histology-images.md` for database IHC image selection, metadata capture, and resolution verification.

## Pitfalls

Do not treat installed instructions or historical integration notes as proof that software, service authorization, or scientific validation is available. Confirm prerequisites and report missing access before execution.

## Verification

Inspect actual outputs, provenance, counts, units, and limitations. Report missing dependencies or partial results honestly. A successful command or security review does not establish scientific correctness.
