# Drawing scripts

A single command converts a JSON input file into a validated figure drawn with [Octet Draw](https://github.com/SamChemMan/Octet-Draw)'s rendering code, producing `.oct`, `.cdxml` (for ChemDraw), SVG, PNG, and a check summary. See [`../SKILL.md`](../SKILL.md) for the full workflow.

If any dependency is missing, run `python draw_figure.py --check-env` to see what to install.

## Input format

The input is a single JSON file (`"format": 2`) specifying the molecules, their reactions, and display options; the layout is computed automatically. Coordinates are in **bond lengths** (1.0 = 14.4 pt), with x pointing right and **y pointing down**. Angles are in degrees counterclockwise from the right (90 = up).

Example structure (full example: [`templates/beza.json`](../templates/beza.json)):

```json
{"format": 2, "name": "beza_mechanism", "source": "Tsutsumi et al., ... 2022, Figure 4", "numbers": {"11": "1"},
 "panels": [{"id": "R", "title": "Reactant",
             "species": [{"id": "sam", "smiles": "[*:21][S+:20]([CH3:11])...", "abbrev": {"21": "Ado"}, "show": [11]}],
             "arrows": [{"id": "A2", "from": "sam:20-11", "to": "sam:20"}]}],
 "reaction_arrows": [{"from": "R", "to": "I", "above": "methyl transfer"}]}
```

### Top level

| Key | Meaning |
|---|---|
| `format` | `2` |
| `name` | Figure name (default: input filename) |
| `source` | Free-text source citation (e.g., paper and figure number) |
| `panels` | Ordered list of panels (see [Panels](#panels)) |
| `rows` | Optional row layout by panel ID, e.g., `[["R", "I"], ["P"]]` (default: single row) |
| `reaction_arrows` | Straight arrows between panels (see [Reaction arrows](#reaction-arrows)) |
| `numbers` | Atom numbers to display (see [Atom numbers](#atom-numbers)) |
| `expected_stereo` | Optional R/S or E/Z labels from the source (see [below](#expected-stereo-and-the-stereo-report)) |
| `drawing` | Figure-wide defaults: `{"charge_circles": true, "partial_bonds": "dashed", "dpi": 600}`. Set `charge_circles` to `false` only if the source draws uncircled charges on structure atoms, and `partial_bonds` to `"dotted"` for dotted TS/1.5 partial bonds (hydrogen bonds are always dotted). Use a single consistent style throughout the figure |
| `colors` | Optional color settings ([more keys](../references/input-more.md#color)); default is black |

### Panels

| Key | Meaning |
|---|---|
| `id` | Short identifier (letters, digits, `_`, `-`); same-panel references need no panel prefix |
| `title` | Caption below the panel (auto-placed at a uniform height per row) |
| `species` | Molecules, ions, and residues (see [Species](#species)) |
| `arrows` | Curved arrows: `{"id", "from", "to", "electrons", "bend"}`. Uses atom/bond references, or a two-atom `to` array for a forming bond (see [below](#atom-and-bond-references)). `electrons`: `2` (full head, default) or `1` (fishhook). Optional `bend`: `0.1` to `1.6` (sign selects the curve direction) |
| `hbonds` | Hydrogen bonds drawn as dotted lines: `[["ser:4", "his:16"]]`. The line starts at the donor's H; if both ends carry an H, list the donor first |
| `lone_pairs` | Optional explicit reacting lone pairs, e.g., `["ser:3"]`. An omitted lone pair on an arrow-source atom is added automatically. Never draw all lone pairs |
| `texts` | Text placed at panel coordinates `{"text", "xy": [x, y]}` or relative to an atom `{"text", "near": "species:map", "dir": 300, "dist": 0.8}`. Optional `size` (pt) and `align` (`left`, `center`, `right`, defining whether `xy` is the start, middle, or end; ignored with `near`) |
| `plus` | Places a `"+"` between two species (`[["product", "bromine"]]` draws `product + bromine`); use only when shown in the source. A free-text `"+"` not between two species triggers a `plus_place` warning |

For less common panel keys (`eta`, `pseudobonds`, `polyhedron`, `boxes`, `angle_exceptions`), see [more keys](../references/input-more.md#panels).

### Species

Using the same `id` across panels represents **the same molecule**: non-reacting atoms inherit their coordinates from the nearest preceding panel (or nearest following panel if none precedes it).

| Key | Meaning |
|---|---|
| `id` | Molecule identifier, kept consistent across panels |
| `smiles` | SMILES **as drawn in this panel**. Every atom requires a map number (`[CH3:8]`, `[H:13]`, `[*:12]`) kept consistent across panels. Supports charges, isotopes (`[13CH3:8]`, `[2H:13]`), branches, rings, aromatic atoms, donor bonds `->`/`<-` (drawn plain), `/` `\`, and `@` |
| `abbrev` | `{"<map>": "OPP"}` draws a dummy atom `[*:n]` as an abbreviation; or `{"text", "element", "chemical", "charge"}` (`element` specifies the attachment atom, already known for `OPP`, `Ado`, `SCoA`, and other common abbreviations; `chemical: true` parses `text` as a formula). Expand charged groups (`C(=O)[O-]`) in full when touched by an arrow or hydrogen bond |
| `residue` | `{"<map>": "Glu170"}` draws a plain-text residue name at a dummy side-chain root ([style guide](../SKILL.md#amino-acid-residue-labels)); mixing styles within a figure fails |
| `show` | `[map, ...]` carbons whose `C` symbol is explicitly shown (e.g., methyl `CH3` or the C of CO₂) |
| `label` | `{"<map>": "text"}` overrides an atom's label |
| `near` | Places a species that has no curved arrows connecting it to others (e.g., an ion or water): `"species:map"` or `{"atom": "species:map", "dir": 60, "dist": 1.3}` (falls back to the nearest open spot if occupied, with a note). Omit `near` for a group that detached in the previous panel (e.g., Cl⁻ or a released product)—it automatically stays beside the atom it left |
| `xy`, `offset`, `rotate`, `flip` | Manual placement overrides; omit on the first run (see [Hand placement](#hand-placement)) |
| `keep_h` | List of mapped H atoms to draw explicitly, e.g., `[52]`; other non-reacting H atoms fold into their parent atom labels |
| `bond_style` | `{"a-b": "wedge" \| "hash" \| "bold" \| "plain" \| "partial" \| "1.5" \| "coord" \| "wavy"}`, where `a` is the narrow end of a wedge or hash. `coord`: plain single coordination bond preserving ligand H counts and formal charges. `partial`: dashed single bond (TS only), or dotted via `drawing.partial_bonds`. `1.5`: solid line plus a parallel partial line on the ring/inner side |
| `expected_stereo` | Optional stereo check, e.g., `{"2": "R", "6=7": "E"}` (see [below](#expected-stereo-and-the-stereo-report)) |
| `note` | Free-text comment (ignored) |

For radicals, oxidation states, metal geometry, and transition states (`radicals`, `radical_angles`, `oxidation`, `geometry`, `ts`), see [more keys](../references/input-more.md#species).

Titles, free texts, reaction-arrow labels, and residue names are rendered literally: use `^{...}` for superscripts and `_{...}` for subscripts (`S_{N}2`, `Mg^{2+}`); digits after letters stay on the baseline (`Glu170`). Ion species (`[Mg+2:14]`) take their superscript charge directly from the SMILES.

An H atom is drawn with an explicit bond whenever a curved arrow or hydrogen bond touches it (or its bond), or when required by stereochemistry; proton-donating water is drawn as H–OH, and isotopic H atoms remain visible.

### Atom and bond references

Reference an atom as `"species:map"` (`"gpp:6"`), a bond as `"species:map-map"` (`"sam:20-11"`; `=`, `#`, or `~` may replace `-`), and an atom in another panel as `"panel.species:map"`. An arrow from a bond starts at the midpoint of its visible line; an arrow to an atom ends with a small gap before the atom's symbol (e.g., the O of `OH`) or skeletal vertex.

For a forming bond, use `"to": ["nuc:1", "electrophile:2"]`. The head of a two-electron arrow reaches the receiving atom (the one not in `from`), whereas fishhooks meet in the gap between the atoms. A single-atom destination represents a new lone pair or unpaired electron; a single-electron arrow from an atom requires a radical dot on that atom.

### Atom numbers

`"numbers": {"7": "7", "6": "6", "11": "1"}` displays atom numbers for the specified maps across all species; keys may also be scoped as `"species:map"` or `"panel.species:map"`. Bare digits automatically receive prime marks based on the atom's origin species in the first panel: none for the first species (main substrate), `'` for the second, `''` for the third, and so on (e.g., in BezA, carbon 11 comes from SAM, so `"1"` renders as `1'`). Write `"1′"` to specify the exact string manually. Numbering an H atom drawn as a letter is rejected (number the heavy atom instead).

### Expected stereo and the stereo report

`expected_stereo` validates the **input SMILES** stereochemistry against the source paper before drawing:
- Top level: `{"lig:2": "R", "P.lig:6=7": "E"}` checks atom 2 of `lig` in every panel, and bond `6=7` in panel `P` only.
- Species level: `"expected_stereo": {"2": "R", "6=7": "E"}` checks only that panel's instance (species-prefixed keys also work).

Use `R`/`S` (or `r`/`s`) for stereocenters and `E`/`Z` for double bonds. Unknown map numbers, unspecified SMILES stereochemistry, or mismatches raise an input error naming both labels. Always fix the SMILES to match the source; do not change `expected_stereo` to match a bad SMILES.

Every stereocenter outside a transition state needs a configuration: write `@`/`@@` as the source figure draws it, or, if the source does not show it (a racemic center, or one the paper leaves open), declare it with `"unspecified"` (`{"lig:6": "unspecified"}`). A stereocenter left without either raises an input error.

In the output, `STEREO` lines list the CIP label of each stereocenter and double bond (`E.lig:2 R`, `R.gpp:2=3 E`). Any stereocenter or double bond specified in the SMILES without a corresponding `expected_stereo` entry is flagged with a `note:`.

### Reaction arrows

`{"from": "R", "to": "I", "kind": "single", "above": "methyl transfer", "below": "...", "length": 4}` connects two panels with a black arrow.

| Key | Meaning |
|---|---|
| `kind` | `single` (→), `resonance` (↔), `equilibrium` (⇌, two half-heads), `both` (⇄, two full heads), `stoich` (=), or `retro` (retrosynthetic arrow) |
| `length` | Arrow length in bond lengths (default: auto-sized to fit its labels and the panel titles) |
| `above`, `below` | Literal text labels; digits after letters stay on the baseline (`Enz1`); use `_{...}` for subscripts |
| `summary` | `true` when the source itself draws this step without curved arrows (several steps in one); otherwise every bond that forms, breaks or changes order between the two panels needs a curved arrow in the first panel (`arrows_steps`) |

For bold or uneven arrows (`weight`, `ratio`) and custom endpoints (`from_pt`, `to_pt`), see [more keys](../references/input-more.md#reaction-arrows).

### Hand placement

Omit these species keys on the first run so the layout engine places every species automatically. Use them when a `FIX` line asks, or after a pass to fix what still reads badly.

| Key | Meaning |
|---|---|
| `xy` | Manual coordinates `{"<map>": [x, y]}` (in panel coordinates, measured in bond lengths with y down and origin at the first atom of the panel's first species); overrides only the specified atoms |
| `offset`, `rotate`, `flip` | Translate (`[dx, dy]`), rotate (degrees counterclockwise), or mirror (`"x"` left-right, `"y"` up-down, `"xy"` both) the species |

Order of precedence: coordinates inherited from an earlier panel override `rotate` and `flip`; `offset` shifts the species next; and `xy` sets individual atoms last.

If a hydrogen-bond line crosses a label or bond, run `python fix_hbonds.py INPUT --out NEW_DIR` once; this saves an adjusted `input.hbonds.json` beside the input file. If the line still overlaps, move the smaller fragment (usually the residue) with `offset` or `rotate`, keeping the substrate in place and the contact short.

## draw_figure.py

```bash
python draw_figure.py INPUT.json --out DIR
```

- Exit `0`: All checks and the positive control pass.
- Exit `1`: One or more checks fail.
- Exit `2`: Invalid input file or a pipeline stage cannot run. Every input problem prints `input error: …`, followed by `NEXT: fix each input error in the input file and rerun the same command; do not stop.`

| Option | Meaning |
|---|---|
| `--dpi` | `figure.png` resolution at true size (default: `drawing.dpi` from the input, else `600`); `figure_small.png` is rendered at 150 dpi; the long edge is capped at 12,000 px |
| `--quiet` | Suppress `FIX` and `POSITIVE CONTROL` lines |

Each passing run saves the figure files, `summary.txt`, `resolved.json`, and a copy of the input (`input.json`) in `DIR/last_pass/`, replacing any previous passing snapshot.
