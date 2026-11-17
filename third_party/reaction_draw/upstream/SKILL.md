---
name: reaction-draw
description: Draw chemical structures and electron-pushing mechanisms from papers, hand-drawn images, reaction names, or descriptions using Octet Draw. Templates and a single command produce checked ChemDraw (.cdxml), SVG, and PNG files.
---

# Chemical structures and reaction-mechanism figures

Use the bundled scripts for layout, numbering, arrows, and checks; do not write your own PDF parser, checker, or renderer.

## Steps

Run the scripts using this folder's path, and keep both the input JSON file ([format and commands](scripts/README.md)) and the output folder (`DIR`) in your working directory.

1. For a paper, search for `mechanism`, `proposed`, `Scheme`, or `Figure` using `pdftotext` or PyMuPDF (if installed), and read only the relevant page and legend. For an image, read the species and arrows directly from it. For a reaction name or description, use the standard textbook mechanism.
2. Before writing the JSON, list every step (including catalyst/cofactor regeneration), each residue with its number, each curved arrow (source → target), charges/protonation states, and *(R)*/*(S)* descriptors. Copy the closest reaction template from [templates/](templates/README.md) and edit only the chemistry. Take cofactor SMILES from `templates/cofactor_fragments.json`. Preserve atom maps and cite the figure or page in `source`. Set `"expected_stereo": {"species:map": "R"}` for every stereocenter using the paper's *(R)*/*(S)* descriptors; otherwise, derive it from the compound's standard name or a database entry ([input format](scripts/README.md#input-format)).
3. Run `python scripts/draw_figure.py input.json --out DIR` once before adding manual coordinates. Require `RESULT: all checks pass` (`WARNING` lines need no action). On failure, resolve every `input error` or `FIX` line by updating the input file and rerun; do not stop, and never edit the generated drawing manually. Run `python scripts/draw_figure.py --check-env` and install what its `MISSING` lines name only if `layout error` or `drawing failed` occurs.
   Never deliver figures with `CHECKS FAILED`. After two failed runs, simplify crowded panels (abbreviate non-reacting groups, remove manual coordinates, or split the step into two panels) and rerun.
4. Check `DIR/figure_small.png` to verify the electron flow against the source, and review the `AUDIT` lines printed by the passing run. Then fix what still reads badly (overlapping labels, hidden bonds, unclear arrowheads, or crowded/awkward placements; look first at each arrow named in a `WARNING: arrows_clear` line) using `xy`, `offset`, `rotate`, or arrow `bend`, then rerun and re-inspect. Keep changes only if all checks still pass; otherwise, revert to `DIR/last_pass/`.
5. Hand over only `figure.cdxml`, `figure.svg`, `figure.png`, and a 2–4 line caption (citing the source, level of certainty, and abbreviation definitions). Leave `figure.oct` (for checks) and `figure_small.png` (for review) in `DIR`. Do not include PDF, TIFF, or ZIP files unless requested.

## Input file rules

- Copy elements, bond orders, charges, and stereochemistry directly from the source structure, SMILES, paper figure, or editable file.
- Never alter protonation states or the mechanism for drawing convenience. Follow the paper's species and electron flow, asking only if they are unspecified. State the mechanism's certainty (e.g., proposed, likely) in the caption.
- Start a curved arrow from a bond when its source atom has no lone pair.
- Write moving hydrogens explicitly (`[H:n]`).
- List in `show` every carbon whose symbol must be displayed (e.g., terminal methyls, carbons named in the text, or the C of CO₂); do not label every skeletal carbon.
- Number only essential atoms (those referenced in the text or product names, or moving between molecules) using `numbers`, never free text.
- Use the dedicated [input keys](references/input-more.md) for radicals, coordination bonds, η/π ligands, oxidation states, and isotopes; never simulate them with charges, extra bonds, or free text.
- Omit `+` signs between species within a panel, as the panel title already identifies them. Use `plus` (never free text) only when the source explicitly shows a `+` or when a scheme lists separate reactants or products.
- Draw transition states only on request: use `"ts": true` with `partial` or `1.5` bonds ([template](templates/ts_diels_alder.json)).
- Arrange the figure to flow left to right (wrapping into rows), with reactants oriented so electron pushing also proceeds left to right. Use another arrangement only when it reads better or is requested.
- The scripts automatically enforce ACS dimensions and checkable IUPAC rules; consult [unautomated IUPAC rules](references/iupac-rules.md) when a drawing choice is not covered here or a `FIX` line is unclear.

## Color

- Default to black unless color is requested. When using color, color heteroatom labels by element and ask whether to distinguish source molecules (substrate, cofactor, transferred group) ([color keys](references/input-more.md#color)).

## Amino-acid residue labels

- Use three-letter codes with residue numbers (`Glu170`), or one-letter codes (`K123`) when requested or used consistently in the source. Maintain one style per figure.
- Explicitly draw the reacting group's atoms, bonds, and charges, and attach arrows directly to them; the residue name serves only as a display label. Verify residue numbers and chain IDs against the source.
