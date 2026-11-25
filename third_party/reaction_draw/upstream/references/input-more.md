# More input keys

Keys for metals, radicals, transition states, free arrow endpoints, and colors. For the basic input format, see [scripts/README.md](../scripts/README.md#input-format).

## Panels

| Key | Meaning |
|---|---|
| `eta` | Haptic attachments: `[{"metal":"metal:1", "atoms":["ring:2","ring:3", "ring:4", "ring:5", "ring:6", "ring:7"], "delocalized":true}]`; draws one plain bond to the ligand center. Requires contiguous atoms from a single ligand. Cyclic ligands default to a delocalized curve; use `false` for a system with one localized bond pattern. |
| `pseudobonds` | Distinct dotted connections between named atoms (using the same pair syntax as `hbonds`); they do not consume valence. |
| `polyhedron` | If `true`, validates the panel as a coordination-polyhedron view: at least seven donor vertices connected by pseudobonds, with no central metal atom. |
| `boxes` | Shapes enclosing species: `[{"species": ["asp"], "pad": 0.35}]` (expands to fit labels). `kind` can be `box` (rectangle, default), `rounded`, `oval`, or `brackets`. |
| `angle_exceptions` | `{"species:map": "reason"}`: allows a chain angle to deviate by more than 10°, with a required reason. |

## Species

| Key | Meaning |
|---|---|
| `radicals` | `{"<map>":1}`: number of unpaired electrons (0, 1, or 2), normally inferred from bracket H counts, charges, and bonds. Overrides must agree with the underlying chemistry. Carbon radical labels are shown; a fishhook starting at an atom leaves its movable dot. Two unpaired electrons use separated dots; radical ions retain both dot and charge. More than two localized unpaired electrons on a single atom are not supported. |
| `oxidation` | `{"<map>":2}`: adds a superscript Roman-numeral oxidation state (`0` for zero); does not affect the formal charge. |
| `geometry` | `{"<center map>":"linear"}` or `{"1":{"kind":"square_planar","ligands":[2,3,4,5]}}`. Ligand order follows the template, defaulting to SMILES neighbor order. Specify the geometry explicitly from the source; it is not inferred from the coordination number. |
| `radical_angles` | Optional atom-map-to-angle override, e.g., `{"1":180}`. Reacting dots face their fishhook target by default; deviations produce a warning. |
| `ts` | Optional boolean (default `false`). If `true`, draws the species in square brackets with an upper-right ‡. Do not add manual brackets or a dagger. |

Coordination bonds to metals are recognized automatically; `coord` also represents an additional branch of a multicenter bond. Keep these bonds straight. A haptic attachment creates a single native multi-attachment center rather than covalent bonds to every ligand atom. Delocalized rings get an ellipse, while open unbranched systems get an editable headless curve. Open systems with one localized bond pattern must set `delocalized: false`.

Geometry names: `linear`, `angular`, `trigonal_planar`, `t_shaped`, `square_planar`, `square_pyramidal4`, `see_saw`, `trigonal_bipyramidal`, `square_pyramidal`, `octahedral`, `trigonal_prismatic`. Linear centers are drawn at 180°. Wedges and hashes follow the chosen template. While `xy` still overrides final coordinates (producing warnings on angle deviations), linear centers deviating from 180° and forbidden mixed-type adjacent bonds fail. Chelating ligands require explicit coordinates rather than independent branch rotation.

Transition states (TSs) are optional; include one only when requested ([Diels–Alder template](../templates/ts_diels_alder.json), [preview](../templates/ts_diels_alder.png)). In a TS SMILES, represent every forming or breaking bond as a **single bond** with `bond_style: "partial"`, and encode each `"1.5"` bond as a **single or double bond** (the template uses single bonds). Specify intended H counts explicitly inside atom brackets (e.g., `[CH2:1]`); dashed display bonds must not determine them.

## Reaction arrows

| Key | Meaning |
|---|---|
| `weight` | `normal` (default) or `bold` (Octet's bold arrow: 2.0 pt line with a larger head, e.g., for the favored path). |
| `ratio` | `equilibrium` only: forward-to-backward length ratio (default 1; 1.25 makes the back arrow 20% shorter). |
| `from_pt`, `to_pt` | Free endpoints (specify both or neither; see below). |

For arrows that cannot be positioned by the panel layout (e.g., slanted arrows, arrows starting inside a panel, or arrows between two species in the same panel), specify both endpoints:

```json
{"from": "R", "to": "I", "from_pt": {"atom": "R.gpp:6", "dxy": [4, 0]}, "to_pt": {"atom": "I.gpp:6", "dxy": [-3, -1.5]}}
```

Each endpoint specifies an atom (`"panel.species:map"`) and an offset `dxy` in bond lengths (x right, y down; default `[0, 0]`). `from` and `to` are still required to identify and place the panels (specifying the same panel twice is allowed). The arrow's `length` does not affect the drawn arrow itself, but, like `above` and `below`, still counts toward the row's arrow length and panel gap. Arrow labels assume a horizontal arrow and may touch a steep one (causing `overlap_arrow_text` to fail). An arrow between single-column panels in adjacent rows is always vertical, even when endpoints are specified.

## Color

Everything is black unless the input includes a top-level `"colors"` block. Arrows are always `#000000`; no key colors arrows, reaction-condition text, panel titles, or atom numbers.

```json
"colors": {"element": true, "heteroatoms": "element",
  "origin": [{"name": "GPP", "color": "#0072B2", "atoms": ["gpp"]},
             {"name": "methyl from SAM", "color": "#D55E00", "atoms": ["sam:11", "gpp:11"]},
             {"name": "rest of SAM/SAH", "atoms": ["sam"]},
             {"name": "E170", "color": "#CC79A7", "atoms": ["e170"]}]}
```

Specify `element`, `origin`, or both; `"colors": {}` or `{"element": false}` disables coloring.

| Key | Meaning |
|---|---|
| `element` | If `true`, labels (letters, H, charge signs) of atoms other than C, H, and D take the element color, while bonds, C, H, and D stay black. Default palette (≥ 4.5:1 on white): O `#D00000`, N `#0040C0`, S `#9A6A00`, P `#C05000`, F/Cl/Br/I `#007000`, all others (metals, B, Si, Se, etc.) `#7030A0`. Passing an object overrides specific entries: `{"O": "#B00020"}` recolors O, `{"S": null}` keeps S black, `"*"` sets (`null` clears) all other elements, and `"C"` colors C as well. An abbreviation (`OPP`) takes the element of its attachment atom; residue names have no element. |
| `origin` | List of groups `{"name", "color", "atoms"}`. Each `atoms` entry is a species `id` (all panels), `"panel.species"` (single panel), `"species:map"` (single atom across all panels), or an atom map (all species containing it). Atom-level entries take precedence over whole-species entries; assigning the same atom or species to multiple groups is an error. Each group colors its atoms (labels, H, charges, abbreviations, residue text) and bonds **between two of its own atoms**; other bonds **stay black** (one color per bond; black marks the join). `color` defaults to the Okabe–Ito palette in order (`#0072B2`, `#D55E00`, `#009E73`, `#CC79A7`, `#E69F00`, `#56B4E9`); groups beyond the sixth must specify a `color`. |
| `heteroatoms` | When both `element` and `origin` are active: `"element"` (default) keeps heteroatom labels in element color and colors the rest by origin; `"origin"` colors all atoms by origin. |

Colors use `#rrggbb` format; a `note:` flags low-contrast colors. The scripts write explicit colors onto atoms, bonds, and residue names (rather than using Octet's "Colour by Element"), preserving them across `.oct`, `.cdxml`, and SVG outputs. Examples: `templates/beza_color_element.json`, `beza_color_origin.json`.
