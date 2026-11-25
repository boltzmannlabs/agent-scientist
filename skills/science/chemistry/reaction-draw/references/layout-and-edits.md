# Layout and follow-up edits

Use the saved JSON and the existing input-format reference; there is no separate
`reaction-draw-inputs` skill. Rendered files are outputs, not editable source.

## First render and visual review

- Let the renderer choose curved-arrow routing and species placement first. An
  electron-pushing diagram already gets curved arrows without a `bend` value.
- Read automated findings together with the preview. Vision descriptions can
  misidentify a crowded arrowhead or charge. Compare the exact `from`/`to` atom
  or bond references, source chemistry and resolved output before altering them.
- For visible crowding, separate the relevant species with `offset: [dx, dy]`
  or a rigid `rotate` in degrees, using the input-format coordinate conventions.
  Keep connectivity, atom maps, protonation and stereochemistry unchanged. Adjust
  one layout cause at a time. Explicit arrow curvature is a later option, not a
  substitute for adequate space around the reacting atoms.
- A subjective preference for a different layout does not invalidate a checked,
  readable diagram. Deliver it without claiming it is experimental proof.

## Keep the checked image during refinements

Preserve the current input and checked outputs. Render each proposed layout into
a different task-owned output directory. If it fails, retain the previous checked
figure; never publish the failed candidate or describe an uncompleted edit as done.
Do not repeat the same unsuccessful curvature adjustment. If a layout change is
still unresolved after the skill's redraw limit, deliver the checked version and
briefly state what remains to improve.

## Repair loops from duplicated solvent species

If a panel contains two identical small solvent molecules (for example a byproduct
water plus a catalyst water), the automatic placer can cycle indefinitely on
`overlap_text_text`, repeating `repairArrows`/`repairCharges` lines until the
command times out with no `summary.txt`. When this happens, stop rerunning: give
the detached byproduct an explicit `offset` (about 1.5–2.5 bond lengths away from
the reacting complex) and remove any `plus` pair that spans the crowded species,
then rerender into a fresh output directory. Also prefer a single-row `rows`
layout for multi-panel mechanisms: 2-row layouts can leave a cross-row reaction
arrow visually disconnected from its left panel, which reads as a missing
preceding structure. A known source/chemistry error must be fixed
before delivery, even if the automated drawing checks pass.

## Supported sizes and labels

The top-level `style` object controls figure-wide sizes in points. For example:

```json
{"style": {"font_size_pt": 12, "title_size_pt": 14, "bond_length_pt": 17.28}}
```

Use only the requested changes. Increasing bond length in proportion to atom text
can preserve readability; rerun the normal checks rather than assuming the change
is valid. Increasing `--dpi` changes raster resolution, not the type size in SVG.

Panel `title` is the normal panel caption. For an additional heading, use a panel
`texts` entry with `text`, `xy`, optional `size` in points, and `align`. Avoid keeping
both an old title and a replacement text at the same location. Exact supported
style keys are `font`, `font_size_pt`, `bond_length_pt`, `line_width_pt`,
`bold_width_pt`, `double_spacing`, `label_margin_pt`, `hash_spacing_pt`,
`number_size_pt`, `number_font` and `title_size_pt`.

After a title/size edit, check the requested text in the SVG and compare its font
sizes with the previous figure. A different PNG hash alone does not establish
that the requested label change happened. Deliver the edited PNG inline plus
the SVG and editable CDXML, keeping the previous version for comparison.

## Intramolecular and bond-to-proton arrows

The bundled adapter now bounds long-arrow searches by the requested atoms.
When a long arrow is present but crosses another bond, retain the requested
electron flow and improve the chain conformation or split resonance contributors
into clearly labelled panels. Explicit coordinates should respect normal bond
angles, as the layout engine normalizes nonstandard chain geometry. Validate the
new render through the same checks and inspect it visually before delivery.
