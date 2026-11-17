---
title: "Reaction Draw — Draw chemical structures and reaction mechanisms"
sidebar_label: "Reaction Draw"
description: "Draw chemical structures and reaction mechanisms"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Reaction Draw

Draw chemical structures and reaction mechanisms.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/science/chemistry/reaction-draw` |
| Version | `1.0.0+sci.1` |
| Author | Takuto Ohmura (@t-0hmura); Gopi Krishna; Sci Agent |
| License | Apache-2.0 |
| Platforms | linux, macos, windows |
| Tags | `chemistry`, `synthesis`, `mechanisms`, `drawing` |
| Related skills | [`rdkit`](../../bundled/science/science-chemistry-rdkit.md) |

## Reference: full SKILL.md

:::info
The following is the complete skill definition that Sci loads when this skill is triggered. This is what the agent sees as instructions when the skill is active.
:::

# Reaction Draw Skill

Create or edit chemical structures, reaction schemes and curved-arrow mechanism
figures with the bundled Octet Draw renderer. This draws the supplied or proposed
chemistry; a passing drawing check does not establish a mechanism or synthesis route.

## When to Use

Use for chemical drawings, electron-pushing diagrams, reaction schemes, and
illustrating selected steps from a supplied synthesis/retrosynthesis route. Accept
reaction descriptions, named reactions, mapped structures, images or relevant paper
figures. Planning a route alone does not request a mechanism drawing.

## Prerequisites

Use the existing `terminal` tool and `sci reaction-draw` command. The command
prepares its locked RDKit/Playwright environment through Sci's package manager and
uses managed Chromium; no separate model, API key or plugin is required.
Arial or Liberation Sans and the browser's native host libraries must be available.
`sci reaction-draw --check-env` checks readiness without installing. When setup is
needed, use `sci reaction-draw --setup`; explain an installation refusal or missing
host/browser prerequisites rather than replacing the renderer or disabling checks.

For papers/images use available `read_file`, `web_extract` or `vision_analyze`
capabilities. If the structure cannot be read reliably, ask for the relevant figure,
SMILES or missing identity. Check available skills before loading `rdkit`.

## How to Run

Use `read_file` to read references/input-format.md (source checkout: `skills/science/chemistry/reaction-draw/references/input-format.md`)
and a matching template, then write a task-owned format-2 JSON input with the
normal file tools. Keep source and output paths in the user's task workspace;
never write into installed skill or renderer directories.

```text
sci reaction-draw INPUT.json --out OUTPUT_DIR
sci reaction-draw INPUT.json --out OUTPUT_DIR --dpi 600
sci reaction-draw --check-env
```

Paths are actual task paths, passed as separate quoted arguments where needed.
Use this command instead of bare Python, raw package installation or rebuilding
the bundled JavaScript adapter. Preserve inputs and outputs for follow-up edits.

## Quick Reference

| Need | Resource |
|---|---|
| Atom maps, species, panels, reaction/curved arrows | Input format (source checkout: `skills/science/chemistry/reaction-draw/references/input-format.md`) |
| Colors, radicals, metal coordination, isotopes, transitions | Advanced input (source checkout: `skills/science/chemistry/reaction-draw/references/advanced-input.md`) |
| Acyl substitution or proton transfer | `templates/acyl_substitution.json`, `templates/proton_transfer.json` |
| Radicals, metals or requested transition states | `templates/radical_homolysis.json`, `templates/metal_substitution.json`, `templates/ts_diels_alder.json` |
| Cofactor/residue fragments | `templates/cofactor_fragments.json`, `templates/plp_aldimines.json` |
| Checks needing human interpretation | Audit checklist (source checkout: `skills/science/chemistry/reaction-draw/references/audit-checklist.md`), Drawing rules (source checkout: `skills/science/chemistry/reaction-draw/references/iupac-rules.md`) |

## Procedure

1. Establish the requested figure and source. For a paper, inspect the relevant
   figure/page and caption, and distinguish proposed from demonstrated chemistry.
   For an existing route, use its actual reactant/product identities; do not infer
   an experimentally established mechanism from route connectivity alone.
2. Describe the steps, species, charges, protonation, atom mapping and electron
   flow before authoring JSON. Preserve catalyst/cofactor regeneration where the
   source includes it. Ask only for ambiguities that materially change the drawing.
3. Adapt the closest JSON template. Preserve atom maps across panels. Declare
   source-supported R/S and E/Z labels in `expected_stereo`; explicitly mark an
   unspecified stereocenter instead of guessing it. Draw moving hydrogens explicitly.
4. Run the renderer once before manual placement. Read its exit status, input
   errors, FIX/AUDIT lines and `RESULT`. Correct the input and rerun. Do not edit
   generated CDXML/SVG manually or disable the positive control to obtain a pass.
5. Inspect `figure_small.png` with an available image-viewing capability. Compare
   electron flow with the source and check labels, arrows, bonds and readability.
   Adjust only input coordinates, orientation, spacing or arrow bends for layout.
   Preserve chemistry when simplifying crowded panels or splitting a step.
6. Deliver a passing `figure.png`, `figure.svg` and editable `figure.cdxml`, with a
   short caption identifying the source, mechanism certainty and abbreviations.
   Keep JSON input, check records and `.oct` in the output directory for editing.
   PDF/TIFF/ZIP are additional outputs only when requested.
7. For edits, revise the saved JSON and render again. Never deliver unchecked
   files from a failed run. A `last_pass/` snapshot can be used only if it still
   represents the requested chemistry; disclose any unresolved requested change.

## Pitfalls

- Preserve formal charges, explicit moving hydrogens, stereochemistry and source
  atom identity. Never change protonation or chemistry solely to improve layout.
- Bond-origin electron arrows, fishhooks, coordination and transition-state
  features use their dedicated input fields; do not fake them with free text.
- Automatic checks cover declared chemistry/drawing consistency and round trips;
  they do not prove that a proposed mechanism occurs experimentally.
- Missing browser libraries/fonts or an unreadable source are actionable blockers.
  Keep partial work and explain the specific issue without claiming success.
- Repair actionable input/layout findings. If two redraws do not improve the
  figure, simplify crowded panels; if still unresolved, report the limitation
  rather than retrying indefinitely or changing the chemical question.

## Verification

Require a zero renderer exit status and `RESULT: all checks pass`. Inspect the
image and stereo/audit output as well as the existence of genuine PNG, SVG and
CDXML files. Include the source and certainty in the caption, then provide the
files through the active chat's artifact mechanism. Describe the resulting figure
without exposing backend code paths or dumping raw logs.
