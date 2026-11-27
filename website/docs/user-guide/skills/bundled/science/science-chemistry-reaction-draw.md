---
title: "Reaction Draw — Draw mechanisms when explaining chemical reactions"
sidebar_label: "Reaction Draw"
description: "Draw mechanisms when explaining chemical reactions"
---

{/* This page is auto-generated from the skill's SKILL.md by website/scripts/generate-skill-docs.py. Edit the source SKILL.md, not this page. */}

# Reaction Draw

Draw mechanisms when explaining chemical reactions.

## Skill metadata

| | |
|---|---|
| Source | Bundled (installed by default) |
| Path | `skills/science/chemistry/reaction-draw` |
| Version | `1.0.0+sci.10` |
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
figures as part of useful chemistry explanations with the bundled Octet Draw renderer.
This draws the supplied or proposed
chemistry; a passing drawing check does not establish a mechanism or synthesis route.

## When to Use

Select this skill automatically for a chemical reaction discussed in the current
conversation when a diagram helps explain the reaction or its electron movement.
The user need not say "draw" or name this skill. Show the reaction's participating
reactants and product; for a mechanism request, expand its supported elementary
steps with curved electron-pushing arrows. Reuse an existing checked figure when
it covers the current question.

Requests to explain a reaction mechanism, show its elementary steps, or
illustrate a transformation call for checked figures alongside the explanation.
For example, "show enolate formation" and "illustrate the supported mechanism"
should select this skill without an explicit image request. Plain-text equations
or a no-LaTeX preference do not mean text-only output. Omit figures when the user
explicitly requests a text-only answer; if rendering is blocked, explain the
specific limitation instead of silently replacing the figure with prose.

Keep the scope to the reaction or reactions actually discussed. Retrosynthesis
route planning and route visualization belong to the existing retrosynthesis tool.
Do not trigger a whole-route diagram from a target SMILES, a route-planning request,
or a missing precursor. When several reactions are discussed, draw their individual
mechanisms with clear reaction labels. Add reactions or speculative alternatives
only when the user explicitly requests them.

Read references/reaction-coverage.md (source checkout: `skills/science/chemistry/reaction-draw/references/reaction-coverage.md`) before
planning a mechanism. A picture of reagent activation alone is partial coverage
when the question asks how all reactants form a product. Missing conditions or
incompatible structures require clarification, not an invented connecting route.
Accept named reactions, mapped structures, images and paper figures as sources.
Keep simple definitions, isolated property questions and explicitly text-only
answers concise without unrelated diagrams.

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
For layout findings or follow-up edits, read
references/layout-and-edits.md (source checkout: `skills/science/chemistry/reaction-draw/references/layout-and-edits.md`). It describes
supported text sizing and how to improve spacing while retaining a checked figure.

## Quick Reference

| Need | Resource |
|---|---|
| Atom maps, species, panels, reaction/curved arrows | Input format (source checkout: `skills/science/chemistry/reaction-draw/references/input-format.md`) |
| Colors, radicals, metal coordination, isotopes, transitions | Advanced input (source checkout: `skills/science/chemistry/reaction-draw/references/advanced-input.md`) |
| Acetic acid + ethanol, acid-catalyzed Fischer esterification | `templates/fischer_esterification_1.json`, then `templates/fischer_esterification_2.json` |
| Cyclohexanone + methyl vinyl ketone Robinson annulation | `templates/robinson_annulation_1.json` through `templates/robinson_annulation_4.json`, in order |
| Small-molecule acid–base proton transfer | `templates/proton_transfer_small_molecules.json` |
| Acyl substitution or enzyme/residue proton transfer | `templates/acyl_substitution.json`, `templates/proton_transfer.json` |
| Radicals, metals or requested transition states | `templates/radical_homolysis.json`, `templates/metal_substitution.json`, `templates/ts_diels_alder.json` |
| Cofactor/residue fragments | `templates/cofactor_fragments.json`, `templates/plp_aldimines.json` |
| Checks needing human interpretation | Audit checklist (source checkout: `skills/science/chemistry/reaction-draw/references/audit-checklist.md`), Drawing rules (source checkout: `skills/science/chemistry/reaction-draw/references/iupac-rules.md`) |

## Response time

Use one focused pass from chemistry to a checked image. For acetic acid and
ethanol under acid catalysis, use the two linked Fischer templates in Quick
Reference. Together they include the full mechanism and solvent-mediated proton
transfers. Copy both to the task workspace and render them in order. Change them
only if the requested chemistry differs; other substrates need reviewed adaptation.
Do not write the same mapped mechanism from scratch. Reuse a previously checked
figure only when its saved input, chemistry, conditions and requested coverage
match; changing a reactant or mechanism requires a new checked render. Read the
input reference and closest matching template together, then prepare the figure.
Run the normal renderer directly when the runtime is already installed; reserve
`--check-env` for setup diagnostics or an actual environment error. Avoid repeated
catalogue, directory, template and readiness calls for the same task.

Leave molecule placement automatic initially, including `offset`; use manual
placement only to fix a demonstrated layout issue. Read the structured checks and
stage timings after rendering. Once the complete figure passes, publish its PNG
with a short caption in an interim assistant message, then continue visual review
and explanation. Label visual inspection pending until it is performed, and retain
the final PNG directive so saved conversations also display the figure. Use one
visual review per figure. For a passing, readable figure, disclose minor spacing
caveats and deliver it. Do not send repeated zoomed or leading vision questions
seeking a more favorable opinion. An arrow approaching its receiving atom near
an existing bond is not by itself an incorrect electron movement. Rerender only
when the actual input or image confirms incorrect chemistry, missing steps or
unreadable labels. A speculative provider critique needs checking
against the actual input before any redraw. Preserve all validation and positive
controls and keep the complete mechanism requested by the user.

## Procedure

1. Choose the figure that best supports the current question and establish its
   source. For a paper, inspect the relevant
   figure/page and caption, and distinguish proposed from demonstrated chemistry.
   Identify the reactants and product of the reaction currently discussed.
   Check the coverage reference before choosing mechanistic panels.
2. Describe the complete supported transformation, including all participating
   reactants, intermediates and the product, before authoring JSON. List electron
   flow, bond changes, charges, protonation and atom mapping for each step. Preserve catalyst/cofactor regeneration where the
   source includes it. Ask only for ambiguities that materially change the drawing.
   A transferred hydrogen keeps the same atom-map number in the product even
   though it changes molecule. Do not introduce a new mapped hydrogen or mark a
   mechanistic step `summary: true` to conceal an electron/charge-balance failure.
3. Adapt the closest JSON template. Preserve atom maps across panels. Declare
   source-supported R/S and E/Z labels in `expected_stereo`; explicitly mark an
   unspecified stereocenter instead of guessing it. Draw moving hydrogens explicitly.
   Omit explicit arrow `bend` and species placement overrides on the first render;
   the renderer already computes curved electron arrows and automatic placement.
4. Run the renderer once before manual placement. Read its exit status, input
   errors, FIX/AUDIT lines and `RESULT`. Correct the input and rerun. Do not edit
   generated CDXML/SVG manually or disable the positive control to obtain a pass.
5. Inspect `figure_small.png` with an available image-viewing capability. Compare
   electron flow with the source and check labels, arrows, bonds and readability.
   Adjust only input coordinates, orientation, spacing or arrow bends for layout.
   Preserve chemistry when simplifying crowded panels or splitting a step.
   Verify a vision model's claimed endpoint/charge error against the input atom
   references and saved checks before changing it. For real crowding, improve
   species spacing first. Do not repeatedly increase arrow curvature or redraw
   solely for subjective styling preferences. Keep a checked version available
   while testing a layout change in a separate output directory.
6. Check that the figures cover the discussed reaction through its product. If
   a required step is unresolved, explain the gap and ask the needed question.
   Deliver individually passing figures even when a different part is blocked.
   Label the missing steps and any delivered partial figure explicitly; do not present it as the complete
   mechanism. Deliver every numbered mechanism figure in step order.
   Deliver a passing `figure.png`, `figure.svg` and editable `figure.cdxml`, with a
   short caption identifying the source, mechanism certainty and abbreviations.
   In classic CLI, dashboard chat, desktop chat, terminal TUI or a messaging surface that supports native media, display the
   PNG inline before the explanation using `MEDIA:/absolute/path/to/figure.png`
   on its own line, outside code fences or inline code. Substitute the actual
   output path. Provide SVG and CDXML through the same surface's file-delivery
   mechanism; a list of local paths alone does not display the figure. Follow the
   active platform's instructions: the terminal TUI shows a terminal-resolution
   preview and a link to the original PNG; desktop chat shows the image natively.
   Interactive classic CLI also paints the PNG preview. Keep the PNG directive on its own line.
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
Image delivery does not require a successful vision-provider call. If visual
inspection is unavailable, still deliver a passing render with its preview on
supported surfaces, and clearly mark visual inspection as pending. Do not describe
automated or SVG-only checks as a completed visual review.

When visual review flags a specific arrow, compare its source and destination
with the saved input and inspect that step before accepting the critique.
If a combined figure is too crowded to judge, split it into readable per-step
figures and retain the existing repair limit. Deliver independently valid steps
with their PNG directives and label any unresolved gap. A generic statement that
"a figure was generated" is not image delivery. Withhold a demonstrably incorrect
figure, but do not silently discard all valid figures because one step is unclear.
