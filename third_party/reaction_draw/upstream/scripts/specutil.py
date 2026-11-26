#!/usr/bin/env python3
# Modified for Agent Scientist: portable runtime integration and UTF-8/BOM handling.
# SPDX-License-Identifier: Apache-2.0
"""Shared helpers of the drawing scripts: spec loading, resolve(spec) -> the resolved figure, a small SMILES reader and
colors.

  load_spec(path)    read and check a spec file
  resolve(spec)      spec (path or loaded dict) -> the resolved figure ("format": "resolved/1"): every atom, bond, curved
                     arrow, text, box and reaction arrow with coordinates, which a drawing backend draws as it is

The spec formats are documented in scripts/README.md, the resolved figure in resolve().  Coordinates are in bond lengths
(1.0 = one bond = 14.4 pt in ACS style); x grows to the right and y DOWN.  Standard library only, plus RDKit for the
automatic layout (layout.py).
"""
import collections
import json
import math
import re
from pathlib import Path
import iupac_features

RESOLVED_FORMAT = 'resolved/1'

# ACS style (ACS Document 1996): the values every backend and check uses unless a spec's "style" block changes them.
ACS_STYLE = {'font': 'Arial', 'font_size_pt': 10.0, 'bond_length_pt': 14.4, 'line_width_pt': 0.6, 'bold_width_pt': 2.0,
             'double_spacing': 0.18, 'label_margin_pt': 1.6, 'hash_spacing_pt': 2.5, 'number_size_pt': 8.0,
             'number_font': 'Arial', 'title_size_pt': 10.0}
CAP_HEIGHT = 0.716          # cap height of Arial per em: a text's (x, y) is the middle of its capital letters


# Color (the spec's optional "colors" block, see scripts/README.md).  Everything is black unless a spec asks for color.
# Element colors of the default palette: each has at least 4.5:1 contrast against white (checked by contrast_on_white).
DEFAULT_ELEMENT_COLORS = {'O': '#d00000', 'N': '#0040c0', 'S': '#9a6a00', 'P': '#c05000',
                          'F': '#007000', 'Cl': '#007000', 'Br': '#007000', 'I': '#007000',
                          '*': '#7030a0'}           # '*' = every other element except C, H and D (metals, B, Si, Se, ...)
NO_DEFAULT_ELEMENT_COLOR = ('C', 'H', 'D')          # these stay black unless "colors.element" names them
# Colors of the origin groups, in order, from the Okabe-Ito set (blue, vermillion, bluish green, reddish purple, orange, sky blue).
ORIGIN_COLORS = ('#0072b2', '#d55e00', '#009e73', '#cc79a7', '#e69f00', '#56b4e9')
LABEL_CONTRAST = 4.5        # WCAG 2 contrast on white wanted for text; a colored label below this is reported as a note
LINE_CONTRAST = 3.0         # and for lines (bonds)

PRIMES = ('', "'", "''", "'''")     # atom-number marks of the 1st, 2nd, 3rd, 4th molecule (ASCII apostrophes, as ChemDraw schemes)


class SpecError(ValueError):
    """The spec file is wrong; the message says where."""

    def __init__(self, problems):
        self.problems = [problems] if isinstance(problems, str) else list(problems)
        super().__init__('\n'.join(self.problems))


def drawing_options(raw=None):
    defaults = {'charge_circles': True, 'partial_bonds': 'dashed', 'dpi': 600}
    if raw is None:
        return defaults
    if not isinstance(raw, dict) or set(raw) - set(defaults):
        raise SpecError('drawing: use figure-wide charge_circles, partial_bonds and dpi only')
    out = dict(defaults, **raw)
    if not isinstance(out['charge_circles'], bool) or out['partial_bonds'] not in ('dotted', 'dashed'):
        raise SpecError('drawing: charge_circles must be true/false and partial_bonds dotted/dashed')
    if isinstance(out['dpi'], bool) or not isinstance(out['dpi'], (int, float)) or not 72 <= out['dpi'] <= 2400:
        raise SpecError('drawing: dpi must be a number from 72 to 2400')
    return out


def lone_pair_source_error(graph, atom_map, listed):
    """Require a drawn pair; a filled bonding shell cannot donate one (e.g. B in BH4-)."""
    atom = next(a for a in graph['atoms'] if a['map'] == atom_map)
    shell = {'H': 1, 'B': 3, 'Al': 3, 'C': 4, 'Si': 4, 'N': 5, 'P': 5, 'As': 5,
             'O': 6, 'S': 6, 'Se': 6, 'Te': 6, 'F': 7, 'Cl': 7, 'Br': 7, 'I': 7}
    used = sum(b['order'] for b in graph['bonds'] if atom['i'] in (b['a'], b['b']) and not b.get('coord'))
    if atom['symbol'] in shell and shell[atom['symbol']] - used - (atom['h'] or 0) - atom['charge'] - atom.get('radical', 0) < 2:
        return 'has no lone pair; start the arrow at a bond'
    return None


# ------------------------------------------------------------------------------------------ SMILES reader
_ORGANIC_VALENCE = {'B': (3,), 'C': (4,), 'N': (3, 5), 'O': (2,), 'P': (3, 5), 'S': (2, 4, 6),
                    'F': (1,), 'Cl': (1,), 'Br': (1,), 'I': (1,)}
_TOKEN = re.compile(r"(?P<bracket>\[[^\]]+\])|(?P<organic>Cl|Br|[BCNOPSFI]|[bcnops]|\*)|(?P<bond>->|<-|[-=#$:/\\.])"
                    r"|(?P<branch>[()])|(?P<ring>%\d\d|\d)")
_BRACKET = re.compile(r"^\[(?P<iso>\d+)?(?P<sym>\*|[A-Z][a-z]?|[a-z][a-z]?)(?P<chir>@@?)?(?P<h>H\d*)?"
                      r"(?P<chg>\+\+|--|[+-]\d*)?(?::(?P<map>\d+))?\]$")
_ORDER = {'-': 1, '=': 2, '#': 3, '$': 4, ':': 1.5, '/': 1, '\\': 1, '->': 'coord', '<-': 'coord'}


def _charge(text):
    if not text:
        return 0
    sign = 1 if text[0] == '+' else -1
    rest = text[1:]
    return sign * (int(rest) if rest.isdigit() else 1 + len(rest))


def parse_smiles(smiles):
    """Read a SMILES string into a graph, atoms in written order.

    Returns {'atoms': [{'i', 'symbol', 'charge', 'h', 'map', 'aromatic', 'dummy', 'bracket', 'chiral'}], 'bonds': [{'a', 'b', 'order'}]}.
    'h' is the hydrogen count written in a bracket atom, or the count the default valence gives an organic-subset atom.
    Stereo marks (@, /, \\) are read; '@'/'@@' is kept as 'chiral' (the layout turns it into wedges with RDKit), '/' and '\\'
    are left to RDKit.  Aromatic atoms get bond order 1.5.
    """
    atoms, bonds = [], []
    stack, prev, pending, rings = [], None, None, {}
    pos = 0
    text = smiles.strip()
    while pos < len(text):
        m = _TOKEN.match(text, pos)
        if not m:
            raise SpecError('cannot read SMILES %r at %r' % (smiles, text[pos:pos + 12]))
        pos = m.end()
        kind = m.lastgroup
        tok = m.group(kind)
        if kind in ('bracket', 'organic'):
            if kind == 'bracket':
                b = _BRACKET.match(tok)
                if not b:
                    raise SpecError('cannot read bracket atom %s in %r' % (tok, smiles))
                sym = b.group('sym')
                hs = b.group('h')
                h = 0 if not hs else (int(hs[1:]) if hs[1:] else 1)
                atom = {'symbol': sym.capitalize() if sym != '*' else '*', 'charge': _charge(b.group('chg')), 'h': h,
                        'map': int(b.group('map')) if b.group('map') else None, 'aromatic': sym[0].islower(),
                        'dummy': sym == '*', 'bracket': True, 'chiral': b.group('chir'), 'isotope': int(b.group('iso') or 0)}
            else:
                atom = {'symbol': tok.capitalize() if tok != '*' else '*', 'charge': 0, 'h': None, 'map': None,
                        'aromatic': tok[0].islower() and tok != '*', 'dummy': tok == '*', 'bracket': False, 'chiral': None}
            atom['i'] = len(atoms)
            atoms.append(atom)
            if prev is not None:
                order = pending if pending is not None else (1.5 if atom['aromatic'] and atoms[prev]['aromatic'] else 1)
                bonds.append({'a': prev, 'b': atom['i'], 'order': 1 if order == 'coord' else order,
                              **({'coord': True} if order == 'coord' else {})})
            pending = None
            prev = atom['i']
        elif kind == 'bond':
            if tok == '.':
                prev = None
            else:
                pending = _ORDER[tok]
        elif kind == 'branch':
            if tok == '(':
                stack.append(prev)
            else:
                if not stack:
                    raise SpecError('unbalanced ) in SMILES %r' % smiles)
                prev = stack.pop()
        else:  # ring closure digit
            key = int(tok[1:]) if tok.startswith('%') else int(tok)
            if key in rings:
                other, order = rings.pop(key)
                o = pending if pending is not None else order
                if o is None:
                    o = 1.5 if atoms[other]['aromatic'] and atoms[prev]['aromatic'] else 1
                bonds.append({'a': other, 'b': prev, 'order': 1 if o == 'coord' else o,
                              **({'coord': True} if o == 'coord' else {})})
            else:
                rings[key] = (prev, pending)
            pending = None
    if stack or rings:
        raise SpecError('unclosed branch or ring in SMILES %r' % smiles)
    used = [0.0] * len(atoms)
    for b in bonds:
        used[b['a']] += b['order']
        used[b['b']] += b['order']
    for a in atoms:
        if a['h'] is None:
            sym = a['symbol']
            if a['dummy'] or sym not in _ORGANIC_VALENCE:
                a['h'] = 0
            else:
                total = used[a['i']] + (0.5 if a['aromatic'] and used[a['i']] % 1 else 0)
                options = [v for v in _ORGANIC_VALENCE[sym] if v >= total - 1e-9]
                a['h'] = int(round(options[0] - total)) if options else 0
    return {'atoms': atoms, 'bonds': bonds}


def kekulize_smiles(smiles):
    """Aromatic SMILES -> Kekule SMILES with the atom maps kept (needs RDKit; raises SpecError otherwise)."""
    try:
        from rdkit import Chem
    except ImportError:
        raise SpecError('aromatic atoms in %r need RDKit to be kekulized; write the Kekule form instead' % smiles)
    params = Chem.SmilesParserParams()
    params.removeHs = False
    m = Chem.MolFromSmiles(smiles, params)
    if m is None:
        raise SpecError('RDKit cannot read %r' % smiles)
    Chem.Kekulize(m, clearAromaticFlags=True)
    return Chem.MolToSmiles(m, kekuleSmiles=True, canonical=False)


# ------------------------------------------------------------------------------------------ small markup
def markup_runs(text):
    """'Mg^{2+}' -> [('Mg', None), ('2+', 'super')]; '_{2}' is a subscript."""
    runs, pos = [], 0
    for m in re.finditer(r'([\^_])\{([^}]*)\}', text):
        if m.start() > pos:
            runs.append((text[pos:m.start()], None))
        runs.append((m.group(2), 'super' if m.group(1) == '^' else 'sub'))
        pos = m.end()
    if pos < len(text):
        runs.append((text[pos:], None))
    return runs


def plain_text(text):
    return ''.join(t for t, _ in markup_runs(text))


# ------------------------------------------------------------------------------------------ spec loading helpers


def _xy(value, where):
    if (not isinstance(value, (list, tuple)) or len(value) != 2
            or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value)):
        raise SpecError('%s must be [x, y] in bond lengths' % where)
    return (float(value[0]), float(value[1]))


# Abbreviations a spec may write as plain text; the element is the atom they attach through (Octet draws the label on it).
KNOWN_ABBREV_ELEMENT = {'OPP': 'O', 'OP': 'O', 'OPPP': 'O', 'OAc': 'O', 'OMe': 'O', 'OEt': 'O', 'OTs': 'O', 'OBn': 'O',
                        'OTf': 'O', 'OMs': 'O', 'OTBS': 'O', 'SCoA': 'S', 'SACP': 'S', 'SAM': 'C', 'Ado': 'C', 'ACP': 'C',
                        'CoA': 'C', 'P': 'P', 'NHAc': 'N', 'NHBoc': 'N', 'Ph': 'C', 'Me': 'C', 'Et': 'C', 'Ac': 'C', 'Bn': 'C', 'Ts': 'S'}


def _abbrev(value, where):
    if isinstance(value, str):
        value = {'text': value}
    if not isinstance(value, dict) or not isinstance(value.get('text'), str):
        raise SpecError('%s must be a string or {"text": ...}' % where)
    element = value.get('element') or KNOWN_ABBREV_ELEMENT.get(plain_text(value['text']))
    return {'text': value['text'], 'element': element, 'charge': int(value.get('charge', 0)),
            'chemical': bool(value.get('chemical', False))}


def _residue_text(value, where):
    if not isinstance(value, str) or not value:
        raise SpecError('%s must be the residue label text, e.g. "Glu170"' % where)
    return value


# ------------------------------------------------------------------------------------------ color
def contrast_on_white(color):
    """WCAG 2 contrast ratio of '#rrggbb' against white (1 to 21)."""
    def lin(v):
        v /= 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(color[i:i + 2], 16) for i in (1, 3, 5))
    return 1.05 / (0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b) + 0.05)


def _hex(value, where):
    if not isinstance(value, str) or not re.match(r'^#[0-9a-fA-F]{6}$', value):
        raise SpecError('%s must be a color written as "#rrggbb", not %r' % (where, value))
    return value.lower()


def _origin_items(item, where, by_species, maps_in, by_key=None):
    """One entry of an origin group's "atoms" -> [('species', id)] or [('atom', id, map), ...].
    An entry is a species id (all its atoms; also the panel-free name such as "gpp", meaning that species in
    every panel), "species-id:map" (one atom), or an atom map (that atom in every species that has it)."""
    by_key = by_key or {}
    if isinstance(item, bool) or not isinstance(item, (int, str)):
        raise SpecError('%s: %r is not an atom map, "species-id:map" or species id' % (where, item))
    if isinstance(item, str):
        text = item.strip()
        if text in by_species:
            return [('species', text)]
        if text in by_key:
            return [('species', sid) for sid in by_key[text]]
        if ':' in text:
            sid, _, number = text.rpartition(':')
            sids = [sid] if sid in by_species else by_key.get(sid, [])
            if not sids or not number.isdigit() or not any(int(number) in by_species[s]['map_to_index'] for s in sids):
                raise SpecError('%s: %r is neither a species id nor an atom of this input ("species-id:map")' % (where, item))
            return [('atom', s, int(number)) for s in sids if int(number) in by_species[s]['map_to_index']]
        if not text.isdigit():
            raise SpecError('%s: %r is neither a species id nor an atom map' % (where, item))
        item = int(text)
    if item not in maps_in:
        raise SpecError('%s: atom map %d is in no species' % (where, item))
    return [('atom', sid, item) for sid in maps_in[item]]


def resolve_colors(raw, species):
    """The "colors" block of a spec -> the color of every atom (its label, charge and text) and every bond, or None.

    raw: {"element": true | {"O": "#hex", "S": null, "*": "#hex"}, "origin": [{"name", "color", "atoms": [...]}],
          "heteroatoms": "element" | "origin"}.  Rules, all documented in scripts/README.md:
      * element: the label of every atom that is not C, H or D takes its element's color (default palette
        DEFAULT_ELEMENT_COLORS; an abbreviation such as OPP counts as the atom it attaches through, residue labels have none);
        bonds stay black.  null in the object leaves that element black; "*" is the color of every unlisted element.
      * origin: each group colors its atoms (label, charge) and the bonds between two of its own atoms; a bond between two
        groups, or between a group and an atom outside every group, stays black.  An atom named by "species-id:map" or
        by a map wins over a whole-species entry; naming one atom (or one species) in two groups is an error.
      * both: the origin color wins for bonds and for C and H labels; a heteroatom label keeps its element color
        ("heteroatoms": "element", the default) or takes the origin color ("origin").
    Returns {'atom': {(species id, map): '#hex'}, 'bond': {(species id, (map, map) sorted): '#hex'}, 'element': palette or None,
    'groups': [{'name', 'color', 'atoms'}], 'heteroatoms', 'notes': [str]}; black ('#000000') entries are dropped.
    """
    if raw in (None, False) or raw == {}:
        return None
    if not isinstance(raw, dict):
        raise SpecError('"colors" must be an object such as {"element": true}')
    extra = sorted(set(raw) - {'element', 'origin', 'heteroatoms'})
    if extra:
        raise SpecError('"colors": unknown key(s) %s (known: element, origin, heteroatoms)' % extra)
    # ---- element palette ----
    element = raw.get('element', False)
    palette = None
    if element:
        palette = dict(DEFAULT_ELEMENT_COLORS)
        if element is not True:
            if not isinstance(element, dict):
                raise SpecError('"colors.element" must be true or an object such as {"O": "#d00000"}')
            for sym, c in element.items():
                if sym != '*' and not re.match(r'^[A-Z][a-z]?$', sym):
                    raise SpecError('"colors.element": %r is not an element symbol (or "*")' % sym)
                palette[sym] = None if c in (None, False) else _hex(c, '"colors.element"[%r]' % sym)
    heteroatoms = raw.get('heteroatoms', 'element')
    if heteroatoms not in ('element', 'origin'):
        raise SpecError('"colors.heteroatoms" must be "element" or "origin"')
    # ---- origin groups ----
    origin = raw.get('origin') or []
    if not isinstance(origin, list):
        raise SpecError('"colors.origin" must be a list of {"name", "color", "atoms"}')
    by_species = {s['id']: s for s in species}
    by_key = collections.defaultdict(list)
    for s in species:
        if s.get('key') and s['key'] != s['id']:
            by_key[s['key']].append(s['id'])
    maps_in = collections.defaultdict(list)
    for s in species:
        for mp in s['map_to_index']:
            maps_in[mp].append(s['id'])
    groups, whole, explicit = [], {}, {}
    for gi, g in enumerate(origin):
        where = '"colors.origin"[%d]' % gi
        if not isinstance(g, dict) or not g.get('atoms') or not isinstance(g['atoms'], list):
            raise SpecError('%s needs a non-empty "atoms" list' % where)
        if g.get('color') is None:
            if gi >= len(ORIGIN_COLORS):
                raise SpecError('%s: give "color" for every group after the %d-th' % (where, len(ORIGIN_COLORS)))
            color = ORIGIN_COLORS[gi]
        else:
            color = _hex(g['color'], where + ' "color"')
        name = str(g.get('name', 'group %d' % (gi + 1)))
        groups.append({'name': name, 'color': color, 'atoms': 0})
        for item in g['atoms']:
            for found in _origin_items(item, where, by_species, maps_in, by_key):
                if found[0] == 'species':
                    if whole.get(found[1], gi) != gi:
                        raise SpecError('%s: species %s is also in group %r' % (where, found[1], groups[whole[found[1]]]['name']))
                    whole[found[1]] = gi
                else:
                    key = (found[1], found[2])
                    if explicit.get(key, gi) != gi:
                        raise SpecError('%s: atom %s:%d is also in group %r' % (where, key[0], key[1], groups[explicit[key]]['name']))
                    explicit[key] = gi

    if palette is None and not groups:
        return None                                              # {"element": false} asks for nothing

    def group_of(sid, mp):
        return explicit.get((sid, mp), whole.get(sid))

    def element_of(sp, mp):
        a = sp['graph']['atoms'][sp['map_to_index'][mp]]
        if not a['dummy']:
            return a['symbol']
        ab = sp['abbrev'].get(mp)
        return (ab['element'] or 'C') if ab else None          # an abbreviation counts as the atom it attaches through

    atom_color, bond_color, label_colors, line_colors = {}, {}, collections.defaultdict(set), collections.defaultdict(set)
    for sp in species:
        sid = sp['id']
        shown = set(sp['show']) | set(sp['label'])
        for a in sp['graph']['atoms']:
            mp = a['map']
            gi = group_of(sid, mp)
            sym = element_of(sp, mp)
            ec = None
            if palette is not None and sym is not None:
                if sym in palette:
                    ec = palette[sym]
                elif sym not in NO_DEFAULT_ELEMENT_COLOR:
                    ec = palette.get('*')
            if gi is not None and ec is not None:
                c = ec if heteroatoms == 'element' else groups[gi]['color']
            elif gi is not None:
                c = groups[gi]['color']
            else:
                c = ec
            if gi is not None:
                groups[gi]['atoms'] += 1
            if c and c != '#000000':
                atom_color[(sid, mp)] = c
                labeled = a['dummy'] or sym not in (None, 'C') or mp in shown
                (label_colors if labeled else line_colors)[c].add('%s:%d' % (sid, mp))
        for b in sp['graph']['bonds']:
            ma, mb = sp['graph']['atoms'][b['a']]['map'], sp['graph']['atoms'][b['b']]['map']
            ga, gb = group_of(sid, ma), group_of(sid, mb)
            if ga is not None and ga == gb and groups[ga]['color'] != '#000000':
                bond_color[(sid, tuple(sorted((ma, mb))))] = groups[ga]['color']
                line_colors[groups[ga]['color']].add('%s:%d-%d' % (sid, ma, mb))
    notes = []
    for c in sorted(label_colors):
        ratio = contrast_on_white(c)
        if ratio < LABEL_CONTRAST:
            notes.append('color %s used on %d atom label(s) has contrast %.2f:1 on white (below %.1f:1): small text in it may be '
                         'hard to read' % (c, len(label_colors[c]), ratio, LABEL_CONTRAST))
    for c in sorted(line_colors):
        ratio = contrast_on_white(c)
        if ratio < LINE_CONTRAST and c not in label_colors:
            notes.append('color %s used only on lines has contrast %.2f:1 on white (below %.1f:1)' % (c, ratio, LINE_CONTRAST))
    return {'atom': atom_color, 'bond': bond_color, 'element': palette, 'groups': groups, 'heteroatoms': heteroatoms, 'notes': notes}


# ------------------------------------------------------------------------------------------ spec loading
def _read_json(path):
    path = Path(path)
    try:
        return json.loads(path.read_text(encoding='utf-8-sig')), path
    except (OSError, json.JSONDecodeError) as e:
        raise SpecError('cannot read input %s: %s' % (path, e))


def load_spec(path):
    """Read and check a spec file; the result is described in load_spec_v2."""
    data, path = _read_json(path)
    from spec_validation import inspect_spec
    problems, _ = inspect_spec(data)
    if problems:
        raise SpecError(problems)
    spec = load_spec_v2(data, path)
    spec['drawing'] = drawing_options(data.get('drawing'))
    return spec


# ------------------------------------------------------------------------------------------ spec
_REF = re.compile(r'^(?:(?P<panel>[^.:\s]+)\.)?(?P<species>[^.:\s]+):(?P<a>\d+)(?:(?P<bond>[-=#~])(?P<b>\d+))?$')
V2_TOP_KEYS = {'format', 'name', 'source', 'style', 'rows', 'numbers', 'colors', 'panels', 'reaction_arrows', 'arrows',
               'expected_stereo', 'drawing'}
V2_PANEL_KEYS = {'id', 'title', 'species', 'arrows', 'hbonds', 'lone_pairs', 'boxes', 'texts', 'plus', 'angle_exceptions',
                 'eta', 'pseudobonds', 'polyhedron'}
V2_SPECIES_KEYS = {'id', 'smiles', 'abbrev', 'residue', 'show', 'label', 'xy', 'near', 'flip', 'rotate', 'offset',
                   'bond_style', 'note', 'expected_stereo', 'ts', 'radicals', 'oxidation', 'geometry', 'keep_h', 'radical_angles'}


def parse_ref(text, panel=None, where='reference'):
    """'gpp:6' -> ('R', 'gpp', 6, None); 'gpp:6=7' or 'gpp:6-7' -> ('R', 'gpp', 6, 7); 'I.gpp:6' names the panel."""
    m = _REF.match(str(text).strip()) if isinstance(text, (str, int)) else None
    if not m:
        raise SpecError('%s: %r is not an atom ("species:map") or a bond ("species:map-map")' % (where, text))
    p = m.group('panel') or panel
    if p is None:
        raise SpecError('%s: %r needs a panel ("panel.species:map")' % (where, text))
    return p, m.group('species'), int(m.group('a')), (int(m.group('b')) if m.group('b') else None)


def ref_text(panel, key, mp):
    """The atom reference used in the resolved figure: "<panel>.<species>:<map>"."""
    return '%s.%s:%d' % (panel, key, mp)


def hbond_hydrogens(data):
    """A heteroatom that a hydrogen bond leaves shows its H as bonds (O-H, N-H), not folded into its label (OH, NH2), so
    the dotted line is not read as a bond to the label and each H takes a place of its own in the layout.  Rewrites
    [NH2:6] in that panel's SMILES to [N:6]([H:n])([H:n+1]) and lists the new maps in the species' keep_h; a map is the
    same in every panel for the same H.  A hydrogen bond between two heavy atoms then starts at the donor's H: the end
    that carries H, or the first-listed end when both do (one H per bond, in order).  An atom the spec places by hand
    ("xy") is left as written.  Returns a copy of data (or data itself)."""
    import copy
    panels = data.get('panels') if isinstance(data.get('panels'), list) else []
    ends = {}
    for p in panels:
        if not isinstance(p, dict):
            continue
        for pair in p.get('hbonds') or []:
            for text in (pair if isinstance(pair, list) else []):
                try:
                    pid, key, m, m2 = parse_ref(text, p.get('id'))
                except SpecError:
                    continue
                if m2 is None and pid == p.get('id'):
                    ends.setdefault((pid, key), set()).add(m)
    if not ends:
        return data

    def heavy(smiles, want):
        """[(start, end, bracket match)] of the hydrogen-bearing heteroatoms of want in smiles."""
        out = []
        for t in re.finditer(r'\[[^\]]+\]', smiles):
            b = _BRACKET.match(t.group(0))
            if (b and b.group('map') and int(b.group('map')) in want and b.group('h') and not b.group('chir')
                    and b.group('sym').capitalize() not in ('*', 'C', 'H')):
                out.append((t.start(), t.end(), b))
        return out
    species = [(p.get('id'), s) for p in panels if isinstance(p, dict) for s in p.get('species') or []
               if isinstance(s, dict) and isinstance(s.get('smiles'), str)]
    def wanted(pid, sp):
        hand = {int(k) for k in (sp.get('xy') or {}) if str(k).isdigit()} if isinstance(sp.get('xy'), dict) else set()
        return ends.get((pid, sp.get('id')), set()) - hand
    pairs = set()
    for pid, sp in species:
        for _, _, b in heavy(sp['smiles'], wanted(pid, sp)):
            n = int(b.group('h')[1:] or 1)
            pairs.update((int(b.group('map')), k) for k in range(n))
    if not pairs:
        return data
    top = max(int(x) for _, sp in species for x in re.findall(r':(\d+)\]', sp['smiles']))
    new = {pair: top + 1 + i for i, pair in enumerate(sorted(pairs))}
    out = copy.deepcopy(data)
    drawn = {}                                   # (panel, species, heavy map) -> the maps of its H drawn as bonds
    for p in out['panels']:
        for sp in p.get('species') or []:
            if not isinstance(sp, dict) or not isinstance(sp.get('smiles'), str):
                continue
            smiles, keep, pos, text = sp['smiles'], [], 0, ''
            for start, end, b in heavy(smiles, wanted(p.get('id'), sp)):
                mp, n = int(b.group('map')), int(b.group('h')[1:] or 1)
                drawn[(p.get('id'), sp.get('id'), mp)] = [new[(mp, k)] for k in range(n)]
                ring = re.match(r'(?:[-=#$:/\\]?(?:%\d\d|\d))*', smiles[end:]).group(0)   # ring closures stay on the atom
                hs = [new[(mp, k)] for k in range(n)]
                text += smiles[pos:start] + '[%s%s%s:%d]' % (b.group('iso') or '', b.group('sym'), b.group('chg') or '', mp)
                text += ring + ''.join('([H:%d])' % h for h in hs)
                pos = end + len(ring)
                keep += hs
            if keep:
                sp['smiles'] = text + smiles[pos:]
                sp['keep_h'] = list(sp.get('keep_h') or []) + keep
    def is_h(p, end):
        sp = next((x for x in p.get('species') or [] if isinstance(x, dict) and x.get('id') == end[1]), None)
        t = re.search(r'\[(\d*)([A-Za-z*][a-z]?)[^\]]*:%d\]' % end[2], sp.get('smiles') or '') if sp else None
        return bool(t) and t.group(2) == 'H'
    for p in out['panels']:
        used = {}
        bonds = p.get('hbonds') if isinstance(p, dict) and isinstance(p.get('hbonds'), list) else []
        for pair in bonds:
            if not isinstance(pair, list) or len(pair) != 2:
                continue
            ends = []
            for text in pair:
                try:
                    pid, key, m, m2 = parse_ref(text, p.get('id'))
                except SpecError:
                    break
                ends.append((pid, key, m) if m2 is None and pid == p.get('id') else None)
            if len(ends) != 2 or None in ends or not any(e in drawn for e in ends) or any(is_h(p, e) for e in ends):
                continue                         # a bond that already starts at a drawn H stays
            # the donor: the end whose H are drawn, the first-listed one when both are
            k = 0 if ends[0] in drawn else 1
            free = [h for h in drawn[ends[k]] if h not in used.get(ends[k], ())]
            if not free:
                continue
            used.setdefault(ends[k], set()).add(free[0])
            text = str(pair[k])
            pair[k] = text[:text.rindex(':') + 1] + str(free[0])
    return out


def load_spec_v2(data, path=None):
    """Check and normalize a spec.  Returns {'format': 2, 'name', 'style', 'rows', 'panels', 'species', 'species_by_id',
    'reaction_arrows', 'numbers', 'colors', 'colors_raw', 'source', 'raw'}; every species gets 'id' = "<panel>.<species>",
    'key' (the panel-free name, the same molecule in every panel), its graph and per-atom fields keyed by atom map."""
    if not isinstance(data, dict):
        raise SpecError('the input is a JSON object')
    data = hbond_hydrogens(data)
    extra = sorted(set(data) - V2_TOP_KEYS)
    if extra:
        raise SpecError('unknown top-level key(s) %s (known: %s)' % (extra, ', '.join(sorted(V2_TOP_KEYS))))
    style = dict(ACS_STYLE)
    for k, v in (data.get('style') or {}).items():
        if k not in ACS_STYLE:
            raise SpecError('"style": unknown key %r (known: %s)' % (k, ', '.join(sorted(ACS_STYLE))))
        style[k] = v
    panels_raw = data.get('panels')
    if not isinstance(panels_raw, list) or not panels_raw:
        raise SpecError('"panels" must be a non-empty list')
    panels, species, by_id = [], [], {}
    seen_panels = set()
    for pi, p in enumerate(panels_raw):
        where = 'panels[%d]' % pi
        if not isinstance(p, dict):
            raise SpecError('%s must be an object' % where)
        extra = sorted(set(p) - V2_PANEL_KEYS)
        if extra:
            raise SpecError('%s: unknown key(s) %s (known: %s)' % (where, extra, ', '.join(sorted(V2_PANEL_KEYS))))
        pid = str(p.get('id', 'P%d' % (pi + 1)))
        if pid in seen_panels or not re.match(r'^[A-Za-z0-9_-]+$', pid):
            raise SpecError('%s: panel id %r is duplicated or not made of letters, digits, _ and -' % (where, pid))
        seen_panels.add(pid)
        title = p.get('title')
        if isinstance(title, dict):
            title = title.get('text')
        if title is not None and not isinstance(title, str):
            raise SpecError('%s: "title" must be a text' % where)
        keys = []
        for si, s in enumerate(p.get('species') or []):
            sw = '%s.species[%d]' % (where, si)
            if not isinstance(s, dict):
                raise SpecError('%s must be an object' % sw)
            extra = sorted(set(s) - V2_SPECIES_KEYS)
            if extra:
                raise SpecError('%s: unknown key(s) %s (known: %s)' % (sw, extra, ', '.join(sorted(V2_SPECIES_KEYS))))
            key = s.get('id')
            if not isinstance(key, str) or not re.match(r'^[A-Za-z0-9_-]+$', key) or key in keys:
                raise SpecError('%s: "id" must be a unique name of letters, digits, _ and - (the same name in another panel is '
                                'the same molecule), not %r' % (sw, key))
            keys.append(key)
            sid = '%s.%s' % (pid, key)
            if not isinstance(s.get('smiles'), str):
                raise SpecError('%s (%s): "smiles" is missing' % (sw, sid))
            smiles = s['smiles']
            graph = parse_smiles(smiles)
            if any(a['aromatic'] for a in graph['atoms']):
                smiles = kekulize_smiles(smiles)
                graph = parse_smiles(smiles)
            maps = {}
            for a in graph['atoms']:
                if a['map'] is None:
                    raise SpecError('%s (%s): every atom of the SMILES needs an atom map, e.g. [CH3:8] or [*:12]' % (sw, sid))
                if a['map'] in maps:
                    raise SpecError('%s (%s): atom map %d is used twice' % (sw, sid, a['map']))
                maps[a['map']] = a['i']

            def keyed(name, conv=lambda v, w: v):
                out = {}
                val = s.get(name) or {}
                if not isinstance(val, dict):
                    raise SpecError('%s (%s): "%s" must be an object keyed by atom map' % (sw, sid, name))
                for k, v in val.items():
                    if not str(k).isdigit() or int(k) not in maps:
                        raise SpecError('%s (%s): "%s" names atom map %r, which is not in the SMILES' % (sw, sid, name, k))
                    out[int(k)] = conv(v, '%s (%s) %s[%s]' % (sw, sid, name, k))
                return out

            abbrev = keyed('abbrev', _abbrev)
            residue = keyed('residue', _residue_text)
            for mp in list(abbrev) + list(residue):
                if not graph['atoms'][maps[mp]]['dummy']:
                    raise SpecError('%s (%s): abbrev/residue map %d must be a dummy atom [*:%d]' % (sw, sid, mp, mp))
            for a in graph['atoms']:
                if a['dummy'] and a['map'] not in abbrev and a['map'] not in residue:
                    raise SpecError('%s (%s): dummy atom [*:%d] needs an "abbrev" or "residue" entry' % (sw, sid, a['map']))
            show = []
            for mp in s.get('show') or []:
                if not isinstance(mp, int) or mp not in maps:
                    raise SpecError('%s (%s): "show" names atom map %r, which is not in the SMILES' % (sw, sid, mp))
                show.append(mp)
            bond_style = {}
            for k, v in (s.get('bond_style') or {}).items():
                m = re.match(r'^(\d+)[-=#~](\d+)$', str(k))
                if not m or int(m.group(1)) not in maps or int(m.group(2)) not in maps:
                    raise SpecError('%s (%s): bond_style key %r must be "a-b" with two atom maps of the SMILES' % (sw, sid, k))
                if v not in ('plain', 'wedge', 'hash', 'bold', 'partial', '1.5', 'wavy', 'coord'):
                    raise SpecError('%s (%s): unknown bond_style %r' % (sw, sid, v))
                a, b = int(m.group(1)), int(m.group(2))
                if not any({x['a'], x['b']} == {maps[a], maps[b]} for x in graph['bonds']):
                    raise SpecError('%s (%s): bond_style %r: atoms %d and %d are not bonded' % (sw, sid, k, a, b))
                bond_style[(a, b)] = v                     # (narrow end, wide end) for wedges and hashes
            rot = s.get('rotate', 0)
            if not isinstance(rot, (int, float)) or isinstance(rot, bool):
                raise SpecError('%s (%s): "rotate" must be degrees' % (sw, sid))
            flip = s.get('flip')
            if flip not in (None, 'x', 'y', 'xy'):
                raise SpecError('%s (%s): "flip" must be "x" (mirror left-right), "y" (mirror up-down) or "xy"' % (sw, sid))
            near = s.get('near')
            if near is not None:
                if isinstance(near, str):
                    near = {'atom': near}
                if not isinstance(near, dict) or 'atom' not in near:
                    raise SpecError('%s (%s): "near" must be "species:map" or {"atom": "species:map", "dir": deg, "dist": d}' % (sw, sid))
                np_, nk, nm, nb = parse_ref(near['atom'], pid, '%s (%s) near' % (sw, sid))
                if np_ != pid or nb is not None:
                    raise SpecError('%s (%s): "near" must name one atom of the same panel' % (sw, sid))
                near = {'species': nk, 'atom': nm, 'dir': near.get('dir'), 'dist': near.get('dist')}
            sp = {'id': sid, 'key': key, 'panel': pid, 'panel_index': pi, 'smiles': smiles, 'smiles_written': s['smiles'],
                  'graph': graph, 'map_to_index': maps, 'abbrev': abbrev, 'residue': residue, 'show': show,
                  'label': keyed('label', lambda v, w: str(v)), 'xy': keyed('xy', _xy), 'near': near, 'flip': flip,
                  'rotate': float(rot), 'offset': _xy(s['offset'], '%s offset' % sw) if s.get('offset') is not None else None,
                  'bond_style': bond_style, 'ts': s.get('ts', False)}
            iupac_features.prepare_species(sp, s)
            species.append(sp)
            by_id[sid] = sp
        panels.append({'id': pid, 'index': pi, 'title': title, 'species': keys, 'raw': p})
    # ---- references inside panels
    def atom_ref(text, pid, where):
        if isinstance(text, list):
            if len(text) != 2:
                raise SpecError('%s: a forming bond needs two atom references' % where)
            members = [atom_ref(t, pid, where) for t in text]
            if any(r['atom2'] is not None or r['panel'] != pid for r in members) or members[0] == members[1]:
                raise SpecError('%s: a forming bond needs two distinct atoms in this panel' % where)
            return dict(members[0], members=members)
        p, k, a, b = parse_ref(text, pid, where)
        sid = '%s.%s' % (p, k)
        if sid not in by_id:
            raise SpecError('%s: species %r is not in panel %s' % (where, k, p))
        sp = by_id[sid]
        for mp in (a,) + ((b,) if b is not None else ()):
            if mp not in sp['map_to_index']:
                raise SpecError('%s: atom map %d is not in %s' % (where, mp, sid))
        if b is not None and not any({x['a'], x['b']} == {sp['map_to_index'][a], sp['map_to_index'][b]} for x in sp['graph']['bonds']):
            raise SpecError('%s: atoms %d and %d are not bonded in %s' % (where, a, b, sid))
        return {'panel': p, 'species': k, 'sid': sid, 'atom': a, 'atom2': b}

    all_arrows = []
    for panel in panels:
        p, pid = panel['raw'], panel['id']
        arrows = []
        for ai, a in enumerate(p.get('arrows') or []):
            where = 'panel %s arrows[%d]' % (pid, ai)
            if not isinstance(a, dict) or 'from' not in a or 'to' not in a:
                raise SpecError('%s needs "from" and "to"' % where)
            el = a.get('electrons', 2)
            if el not in (1, 2):
                raise SpecError('%s: "electrons" must be 1 or 2' % where)
            aid = str(a.get('id', 'A%d' % (len(all_arrows) + len(arrows) + 1)))
            if any(x['id'] == aid for x in all_arrows):     # an id repeated from another panel takes this panel's name
                aid = '%s-%s' % (pid, aid)
            arrows.append({'id': aid, 'panel': pid,
                           'from': atom_ref(a['from'], pid, where + ' from'), 'to': atom_ref(a['to'], pid, where + ' to'),
                           'electrons': int(el), 'bend': a.get('bend')})
        panel['arrows'] = arrows
        all_arrows += arrows
        panel['hbonds'] = []
        for hi, h in enumerate(p.get('hbonds') or []):
            where = 'panel %s hbonds[%d]' % (pid, hi)
            if not isinstance(h, (list, tuple)) or len(h) != 2:
                raise SpecError('%s must be ["species:map", "species:map"]' % where)
            r = [atom_ref(x, pid, where) for x in h]
            if any(x['atom2'] is not None for x in r):
                raise SpecError('%s: a hydrogen bond joins two atoms, not bonds' % where)
            panel['hbonds'].append(r)
        panel['lone_pairs'] = []
        for li, l in enumerate(p.get('lone_pairs') or []):
            r = atom_ref(l, pid, 'panel %s lone_pairs[%d]' % (pid, li))
            if r['atom2'] is not None:
                raise SpecError('panel %s lone_pairs[%d]: name an atom' % (pid, li))
            panel['lone_pairs'].append(r)
        pair_atoms = {(r['sid'], r['atom']) for r in panel['lone_pairs']}
        for arrow in arrows:
            r = arrow['from']
            if arrow['electrons'] == 2 and r['atom2'] is None:
                ref = '%s:%s' % (r['species'], r['atom'])
                problem = lone_pair_source_error(by_id[r['sid']]['graph'], r['atom'], (r['sid'], r['atom']) in pair_atoms)
                if problem:
                    raise SpecError('panel %s arrow %s, atom %s: %s' % (pid, arrow['id'], ref, problem.format(ref=ref)))
                if (r['sid'], r['atom']) not in pair_atoms:
                    panel['lone_pairs'].append(dict(r))
                    pair_atoms.add((r['sid'], r['atom']))
                    panel.setdefault('auto_pairs', []).append(ref)
        iupac_features.prepare_panel(panel, by_id, atom_ref)
        panel['boxes'] = []
        for bi, b in enumerate(p.get('boxes') or []):
            if not isinstance(b, dict) or not isinstance(b.get('species'), list) or not b['species']:
                raise SpecError('panel %s boxes[%d] must be {"species": [names], "pad": bond lengths}' % (pid, bi))
            for k in b['species']:
                if k not in panel['species']:
                    raise SpecError('panel %s boxes[%d]: species %r is not in this panel' % (pid, bi, k))
            kind = b.get('kind', 'box')
            if kind not in ('box', 'rounded', 'oval', 'brackets'):
                raise SpecError('panel %s boxes[%d]: "kind" must be box, rounded, oval or brackets' % (pid, bi))
            panel['boxes'].append({'species': list(b['species']), 'pad': float(b.get('pad', 0.35)), 'kind': kind})
        for key in panel['species']:
            if by_id['%s.%s' % (pid, key)].get('ts'):
                panel['boxes'].append({'species': [key], 'pad': 0.4, 'kind': 'brackets', 'ts': '%s.%s' % (pid, key)})
        panel['texts'] = []
        for ti, t in enumerate(p.get('texts') or []):
            where = 'panel %s texts[%d]' % (pid, ti)
            if not isinstance(t, dict) or not isinstance(t.get('text'), str):
                raise SpecError('%s must be {"text": ..., "xy": [x, y]} or {"text": ..., "near": "species:map"}' % where)
            tt = {'text': t['text'], 'size': float(t.get('size', style['font_size_pt'])),
                  'align': t.get('align', 'center')}
            if tt['align'] not in ('left', 'center', 'right'):
                raise SpecError('%s: "align" must be left, center or right' % where)
            if t.get('xy') is not None:
                tt['xy'] = _xy(t['xy'], where + ' xy')
            elif t.get('near') is not None:
                tt['near'] = atom_ref(t['near'], pid, where + ' near')
                tt['dir'], tt['dist'] = t.get('dir'), t.get('dist')
            else:
                raise SpecError('%s: give "xy" (panel frame, bond lengths, y down) or "near"' % where)
            panel['texts'].append(tt)
        panel['plus'] = []
        for pi, pair in enumerate(p.get('plus') or []):
            if not (isinstance(pair, list) and len(pair) == 2 and all(k in panel['species'] for k in pair) and pair[0] != pair[1]):
                raise SpecError('panel %s plus[%d] must be [species, species]: two different species of this panel' % (pid, pi))
            panel['plus'].append(list(pair))
        panel['angle_exceptions'] = {}
        for k, why in (p.get('angle_exceptions') or {}).items():
            r = atom_ref(k, pid, 'panel %s angle_exceptions' % pid)
            panel['angle_exceptions'][ref_text(r['panel'], r['species'], r['atom'])] = str(why)
    if data.get('arrows'):
        raise SpecError('curved arrows stay inside their panel: move "arrows" into the panel they belong to')
    # ---- rows and reaction arrows
    ids = [p['id'] for p in panels]
    rows = data.get('rows') or [ids]
    if not isinstance(rows, list) or not all(isinstance(r, list) and r for r in rows):
        raise SpecError('"rows" must be a list of lists of panel ids, e.g. [["R", "I"], ["P"]]')
    flat = [x for r in rows for x in r]
    if sorted(flat) != sorted(ids):
        raise SpecError('"rows" must name every panel exactly once (panels %s, rows %s)' % (ids, rows))
    reaction_arrows = []
    for ri, r in enumerate(data.get('reaction_arrows') or []):
        where = 'reaction_arrows[%d]' % ri
        if not isinstance(r, dict) or r.get('from') not in ids or r.get('to') not in ids:
            raise SpecError('%s must be {"from": panel id, "to": panel id, ...}' % where)
        kind = r.get('kind', 'single')
        if kind not in iupac_features.REACTION_KINDS:
            raise SpecError('%s: "kind" must be one of %s' % (where, ', '.join(iupac_features.REACTION_KINDS)))
        weight = r.get('weight', 'normal')
        if weight not in ('normal', 'bold'):
            raise SpecError('%s: "weight" must be "normal" or "bold"' % where)
        ratio = r.get('ratio')
        if ratio is not None and (kind != 'equilibrium' or isinstance(ratio, bool) or not isinstance(ratio, (int, float)) or not 0 < ratio <= 100):
            raise SpecError('%s: "ratio" is a number above 0 for an "equilibrium" arrow (forward arrow / back arrow length)' % where)
        if not isinstance(r.get('summary', False), bool):
            raise SpecError('%s: "summary" must be true or false' % where)
        item = {'from': r['from'], 'to': r['to'], 'kind': kind,
                'above': r.get('above'), 'below': r.get('below'), 'length': r.get('length'), 'weight': weight, 'ratio': ratio,
                'summary': r.get('summary', False)}
        if (r.get('from_pt') is None) != (r.get('to_pt') is None):
            raise SpecError('%s: give "from_pt" and "to_pt" together' % where)
        for end in ('from_pt', 'to_pt'):            # an end point given as an atom ("panel.species:map") plus an offset in bond lengths
            v = r.get(end)
            if v is not None:
                if not isinstance(v, dict) or 'atom' not in v:
                    raise SpecError('%s: "%s" must be {"atom": "panel.species:map", "dxy": [dx, dy]}' % (where, end))
                ref = atom_ref(v['atom'], r[end[:-3]], '%s %s' % (where, end))
                if ref['atom2'] is not None:
                    raise SpecError('%s: "%s" names an atom, not a bond' % (where, end))
                item[end] = {'sid': ref['sid'], 'atom': ref['atom'], 'dxy': _xy(v.get('dxy', [0, 0]), '%s %s dxy' % (where, end))}
        reaction_arrows.append(item)
    # ---- atom numbers: by atom map (all panels), "species:map" (that species in every panel) or "panel.species:map"
    numbers = {}
    for k, v in (data.get('numbers') or {}).items():
        text = v.get('text') if isinstance(v, dict) else v
        if not isinstance(text, (str, int)) or isinstance(text, bool) or str(text) == '':
            raise SpecError('"numbers"[%r] must be the number text, e.g. "6" or "1\'"' % k)
        numbers[str(k)] = str(text)
    colors_raw = data.get('colors')
    out = {'format': 2, 'name': data.get('name') or (Path(path).stem if path else 'figure'), 'source': data.get('source'), 'drawing': drawing_options(data.get('drawing')),
           'style': style, 'rows': rows, 'panels': panels, 'species': species, 'species_by_id': by_id,
           'arrows': all_arrows, 'reaction_arrows': reaction_arrows, 'numbers': numbers,
           'colors': resolve_colors(colors_raw, species), 'colors_raw': colors_raw, 'raw': data}
    _assign_numbers(out)
    return out


def _assign_numbers(spec):
    """Number texts per atom: spec['number_of'] = {(species id, map): text}.  A bare digit string gets the prime of the
    molecule the atom comes from: none for the first species of the first panel (the main substrate), ' for the second
    species, '' for the third, in the order the species first appear; a text that already has a mark is used as it is."""
    order = []
    origin_key = {}
    for panel in spec['panels']:
        for key in panel['species']:
            if key not in order:
                order.append(key)
            sp = spec['species_by_id']['%s.%s' % (panel['id'], key)]
            for mp in sp['map_to_index']:
                origin_key.setdefault(mp, key)
    number_of = {}
    for k, text in spec['numbers'].items():
        m = re.match(r'^(?:(?P<panel>[^.:]+)\.)?(?:(?P<species>[^.:]+):)?(?P<map>\d+)$', k)
        if not m:
            raise SpecError('"numbers": key %r must be an atom map, "species:map" or "panel.species:map"' % k)
        mp = int(m.group('map'))
        targets = [sp for sp in spec['species'] if mp in sp['map_to_index']
                   and (m.group('species') is None or sp['key'] == m.group('species'))
                   and (m.group('panel') is None or sp['panel'] == m.group('panel'))]
        if not targets:
            raise SpecError('"numbers": %r names no atom of the input' % k)
        if re.match(r'^\d+$', text):
            rank = order.index(origin_key[mp]) if m.group('species') is None else order.index(m.group('species'))
            text = text + (PRIMES[rank] if rank < len(PRIMES) else "'" * rank)
        for sp in targets:
            a = sp['graph']['atoms'][sp['map_to_index'][mp]]
            if a['symbol'] == 'H':
                raise SpecError('"numbers": %r is an H drawn as a letter; numbers go on the heavy atom only' % k)
            number_of[(sp['id'], mp)] = text
    spec['number_of'] = number_of


# ------------------------------------------------------------------------------------------ the resolved figure
def _is_monatomic_ion(sp, a):
    return len(sp['graph']['atoms']) == 1 and not a['dummy'] and a['charge'] != 0 and not a['h']


def atom_kind(sp, a):
    """'abbrev', 'residue' or 'atom'."""
    if a['dummy']:
        return 'abbrev' if a['map'] in sp['abbrev'] else 'residue'
    return 'atom'


def label_text(sp, a, xy):
    """The text an atom shows, or None for a skeletal carbon.  xy: {map: (x, y)} of the species (y down) to decide on
    which side the hydrogens go (left when the bonds come from the right, and H3N for an ammonium whose bond is not on
    its left, so that the circled + sits next to the N)."""
    mp = a['map']
    if a.get('hidden_h'):
        return None
    if a['dummy']:
        return sp['abbrev'][mp]['text'] if mp in sp['abbrev'] else sp['residue'][mp]
    if mp in sp['label']:
        return sp['label'][mp]
    sym, h = a['symbol'], a.get('display_h', a['h']) or 0
    nbrs = [b['b'] if b['a'] == a['i'] else b['a'] for b in sp['graph']['bonds'] if a['i'] in (b['a'], b['b'])]
    alone = not nbrs
    one_bond_carbon = (len(nbrs) == 1 and sym == 'C' and sp['graph']['atoms'][nbrs[0]]['symbol'] == 'C'
                       and sum(nbrs[0] in (b['a'], b['b']) for b in sp['graph']['bonds']) == 1)
    linear_carbon = False
    if len(nbrs) == 2 and all(b['order'] == 2 for b in sp['graph']['bonds'] if a['i'] in (b['a'], b['b'])):
        p = xy[mp]
        v = [(xy[sp['graph']['atoms'][j]['map']][0] - p[0], xy[sp['graph']['atoms'][j]['map']][1] - p[1]) for j in nbrs]
        linear_carbon = v[0][0] * v[1][0] + v[0][1] * v[1][1] < -math.cos(math.radians(2)) * math.hypot(*v[0]) * math.hypot(*v[1])
    if sym == 'C' and mp not in sp['show'] and not a.get('isotope') and not alone and not one_bond_carbon and not linear_carbon:
        return None
    hs = '' if h == 0 else 'H' if h == 1 else 'H%d' % h
    if not hs:
        return sym
    if alone:
        return (hs + sym) if sym in ('O', 'S') else (sym + hs)          # H2O, H2S, NH3, CH4
    nbrs = [b['b'] if b['a'] == a['i'] else b['a'] for b in sp['graph']['bonds'] if a['i'] in (b['a'], b['b'])]
    nbrs = [j for j in nbrs if not sp['graph']['atoms'][j].get('hidden_h')]
    if not nbrs:
        return (hs + sym) if sym in ('O', 'S') else (sym + hs)
    x0 = xy[mp][0]
    dx = sum(xy[sp['graph']['atoms'][j]['map']][0] - x0 for j in nbrs) / max(1, len(nbrs))
    if dx > 0.25 or (sym == 'N' and a['charge'] > 0 and dx > -0.25):
        return hs + sym
    return sym + hs


def resolve(spec):
    """Spec (a path or the result of load_spec) -> the resolved figure ("resolved/1"), a JSON-ready dict described
    under "The resolved figure" in the repository's docs/backend.md.  Coordinates are in bond lengths, x right, y down, one frame."""
    if not isinstance(spec, dict):
        spec = load_spec(spec)
    import layout                                     # automatic layout (RDKit); local module next to this file
    import iupac_features
    iupac_features.resolve_new_bond_heads(spec)
    for panel in spec['panels']:
        problems = iupac_features.electron_flow_errors(panel['arrows'], spec['species_by_id'],
                    pair_counts=collections.Counter('%s:%s' % (a['sid'], a['atom']) for a in panel['lone_pairs']))
        if problems:
            raise SpecError(problems)
    iupac_features.prepare_hydrogens(spec)
    lay = layout.compute(spec)
    return _assemble(spec, lay)


def auto_pair_notes(spec):
    added = ['%s.%s' % (p['id'], ref) for p in spec['panels'] for ref in p.get('auto_pairs', [])]
    return ['added reacting lone pair automatically: ' + ', '.join(added)] if added else []


def stereo_sources(spec):
    """Original mapped SMILES, independent of resolved coordinates and chosen wedges."""
    species = spec['species_by_id'].values()
    return {sp['id']: sp.get('smiles_written', sp['smiles']) for sp in species}


def _assemble(spec, lay):
    style = spec['style']
    colors = spec['colors'] or {'atom': {}, 'bond': {}}
    out_panels = []
    for panel in spec['panels']:
        pid = panel['id']
        atoms, bonds, curved = [], [], []
        for key in panel['species']:
            sp = spec['species_by_id']['%s.%s' % (pid, key)]
            xy = lay['xy'][sp['id']]
            for a in sp['graph']['atoms']:
                mp = a['map']
                kind = atom_kind(sp, a)
                el = a['symbol'] if kind == 'atom' else (sp['abbrev'][mp]['element'] or 'C') if kind == 'abbrev' else 'C'
                q = a['charge'] if kind == 'atom' else (sp['abbrev'][mp]['charge'] if kind == 'abbrev' else 0)
                ion = kind == 'atom' and (abs(q) >= 2 or _is_monatomic_ion(sp, a) or bool(a.get('radical')))
                atoms.append({'ref': ref_text(pid, key, mp), 'el': el, 'label': label_text(sp, a, xy),
                              'x': round(xy[mp][0], 4), 'y': round(xy[mp][1], 4), 'charge': q,
                              'circled': bool(q) and abs(q) == 1 and not ion and kind == 'atom' and spec.get('drawing', {}).get('charge_circles', True), 'ion_text': bool(q) and ion,
                              'number': spec['number_of'].get((sp['id'], mp)), 'color': colors['atom'].get((sp['id'], mp)),
                              'kind': kind, 'h': a['h'] or 0, 'species': sp['id'], **({'ts': True} if sp.get('ts') else {}),
                              **iupac_features.atom_fields(sp, a)})
            styles = lay['bond_style'].get(sp['id'], {})
            for b in sp['graph']['bonds']:
                ma, mb = sp['graph']['atoms'][b['a']]['map'], sp['graph']['atoms'][b['b']]['map']
                st, ends = styles.get(frozenset((ma, mb)), ('plain', (ma, mb)))
                a_, b_ = ends
                move = lay['move'].get((sp['id'], frozenset((ma, mb))))
                bonds.append({'a': ref_text(pid, key, a_), 'b': ref_text(pid, key, b_), 'order': b['order'], 'style': st,
                              **({'coord': True} if b.get('coord') else {}),
                              'color': colors['bond'].get((sp['id'], tuple(sorted((ma, mb))))),
                              'move': ref_text(pid, key, move) if move is not None else None})
        for ar in panel['arrows']:
            curved.append({'id': ar['id'], 'from': _end(ar['from']), 'to': _end(ar['to']), 'electrons': ar['electrons'],
                           **({'bend': ar['bend']} if ar.get('bend') is not None else {})})
        pl = lay['panels'][pid]
        iupac_features.assemble_panel(panel, atoms, bonds, lay)
        panel['resolved_geometry'] = [dict(cfg, center=ref_text(pid, key, mp),
                                         ligands=[ref_text(pid, key, m) for m in cfg['ligands']])
                                      for key in panel['species']
                                      for mp, cfg in spec['species_by_id'][pid + '.' + key].get('geometry', {}).items()]
        out_panels.append({
            'id': pid,
            'title': ({'text': panel['title'], 'x': round(pl['title'][0], 4), 'y': round(pl['title'][1], 4), 'auto': True}
                      if panel['title'] else None),
            'atoms': atoms, 'bonds': bonds, 'curved': curved,
            'hbonds': [[ref_text(h['panel'], h['species'], h['atom']) for h in pair] for pair in panel['hbonds']],
            'lone_pairs': [ref_text(l['panel'], l['species'], l['atom']) for l in panel['lone_pairs']],
            'boxes': [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in b.items()} for b in pl['boxes']],
            'texts': [dict(t, x=round(t['x'], 4), y=round(t['y'], 4)) for t in pl['texts']],
            'eta': panel.get('resolved_eta', []), 'pseudobonds': panel.get('resolved_pseudobonds', []),
            'metal_geometry': panel.get('resolved_geometry', []),
            'angle_exceptions': dict(panel['angle_exceptions'])})
    return {'format': RESOLVED_FORMAT, 'name': spec['name'], 'source': spec.get('source'), 'spec_format': 2,
            'stereo_sources': stereo_sources(spec),
            'drawing': spec.get('drawing', drawing_options()), 'style': dict(style), 'panels': out_panels,
            'reaction_arrows': [{k: (round(v, 4) if isinstance(v, float) else v) for k, v in r.items()} for r in lay['reaction_arrows']],
            'colors': spec.get('colors_raw'), 'notes': list(lay.get('notes', [])) + list((spec['colors'] or {}).get('notes', [])) + auto_pair_notes(spec)}


def _end(r):
    if r.get('members'):
        return {'kind': 'gap', 'refs': [ref_text(a['panel'], a['species'], a['atom']) for a in r['members']]}
    if r['atom2'] is None:
        return {'kind': 'atom', 'refs': [ref_text(r['panel'], r['species'], r['atom'])]}
    return {'kind': 'bond', 'refs': [ref_text(r['panel'], r['species'], r['atom']), ref_text(r['panel'], r['species'], r['atom2'])]}


# ------------------------------------------------------------------------------------------ PNG helper


def png_size(data):
    """(width, height) of PNG bytes without Pillow."""
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError('not a PNG')
    return int.from_bytes(data[16:20], 'big'), int.from_bytes(data[20:24], 'big')
