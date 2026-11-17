#!/usr/bin/env python3
# Modified for Agent Scientist: portable runtime integration and UTF-8/BOM handling.
# SPDX-License-Identifier: Apache-2.0
"""Octet backend: draw a resolved figure (format "resolved/1") with Octet Draw's own renderer.

  python octet_draw.py RESOLVED.json --out DIR [--dpi N] [--png-width N] [--small-dpi N] [--browser-cmd 'ssh HOST PYTHON']
                       [--browser auto|chrome|chromium|PATH] [--octet PATH --node-modules PATH --cache DIR]

From Python:  import octet_draw; report = octet_draw.draw(resolved_dict, out_dir, dpi=600, ...)

Outputs, steps and options: the repository's docs/backend.md.  ../check_rules.py checks the drawing; this file only reports
what it drew and what it could not do ("problems").  Exit status: 0 drawn, 2 bad input or the browser step failed.
"""
import argparse
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNNER = HERE / 'octet_run.py'
PINNED = '934719abf213e0a8c9725256338bcbc0f305cab6'
DIST_PAGE = HERE / 'dist' / 'octet-adapter.html'      # the prebuilt adapter page (build.mjs --record writes the .json)
DIST_RECORD = HERE / 'dist' / 'octet-adapter.json'
FORMAT = 'resolved/1'
CAP_HEIGHT = 0.716          # Arial cap height, em
BOND_PT = 14.4
ROOT_GAP = 0.15             # bond lengths between a residue's root vertex and its name
ARROW_KINDS = {'single': 'reaction', 'reaction': 'reaction', 'equilibrium': 'equilibrium', 'resonance': 'resonance', 'retro': 'retro',
               'both': 'reaction', 'stoich': 'line'}
VALENCE = {'C': 4, 'Si': 4, 'N': 3, 'P': 3, 'As': 3, 'B': 3, 'Al': 3, 'O': 2, 'S': 2, 'Se': 2, 'Te': 2, 'F': 1, 'Cl': 1, 'Br': 1, 'I': 1}
H_FIRST = {'O', 'F', 'S', 'Cl', 'Se', 'Br', 'Te', 'I'}
ELEMENT = re.compile(r'^[A-Z][a-z]?$')
# resolved style keys -> Octet DocStyle (pt; spacing in % of the bond length); the rest is Octet's "ACS Document 1996".
# font_size_pt sets the labels and the captions (texts, conditions); title_size_pt the titles; number_* the numbers.
STYLE_KEYS = {'bond_length_pt': ('bond', 1.0), 'line_width_pt': ('line', 1.0), 'bold_width_pt': ('bold', 1.0),
              'label_margin_pt': ('margin', 1.0), 'hash_spacing_pt': ('hash', 1.0), 'double_spacing': ('spacing', 100.0),
              'font_size_pt': ('labelSize', 1.0)}


class OctetError(RuntimeError):
    """Bad input, a missing tool or a failed browser step."""


# ------------------------------------------------------------------------------------------ small helpers
def markup_runs(text):
    """'H_{2}O', 'Mg^{2+}' -> Octet caption runs [(text, script)], script None, 'sub' or 'super'."""
    out, k = [], 0
    for m in re.finditer(r'([_^])\{([^{}]*)\}', text):
        if m.start() > k:
            out.append((text[k:m.start()], None))
        out.append((m.group(2), 'sub' if m.group(1) == '_' else 'super'))
        k = m.end()
    if k < len(text):
        out.append((text[k:], None))
    return [(t, s) for t, s in out if t]


def caption(text, x, y, align='center', size=None, color=None):
    """An Octet caption at (x, y) in Octet's frame (bond lengths, y up; y is the first baseline)."""
    runs = markup_runs(text)
    c = {'text': ''.join(t for t, _ in runs), 'x': round(x, 4), 'y': round(y, 4),
         'align': 'centre' if align in ('center', 'middle') else align, 'chemical': False}
    if size:
        c['size'] = round(float(size), 3)
    if color:
        c['colour'] = color.lower()
    if any(s for _, s in runs):
        c['runs'] = [dict(text=t, **({'script': s} if s else {})) for t, s in runs]
    return c


def octet_hydrogens(el, charge, used):
    """Octet's implicit hydrogen count (render.ts hydrogens)."""
    v = VALENCE.get(el)
    if v is None:
        return 0
    target = v - abs(charge) if v == 4 else (v - charge if el in ('B', 'Al') else v + charge)
    return max(0, int(round(target - used)))


def parse_h_label(label, el):
    """'H3N' -> ('first', 3), 'NH2' -> ('after', 2), 'OH' -> ('after', 1), 'N' -> (None, 0); None if not of that form."""
    m = re.fullmatch(r'(?:H(\d*))?%s(?:H(\d*))?' % re.escape(el), label)
    if not m or (m.group(1) is not None and m.group(2) is not None):
        return None
    if m.group(1) is not None:
        return 'first', int(m.group(1) or 1)
    if m.group(2) is not None:
        return 'after', int(m.group(2) or 1)
    return None, 0


def auto_reading(me, nbrs):
    """Octet's automatic reading direction of a label (render.ts): (reads right to left, steep).  y down, bond lengths."""
    vx = vy = 0.0
    for q in nbrs:
        dx, dy = q[0] - me[0], q[1] - me[1]
        n = math.hypot(dx, dy) or 1.0
        vx, vy = vx + dx / n, vy + dy / n
    steep = math.hypot(vx, vy) > 1e-6 and abs(vy) > abs(vx) * math.tan(math.radians(70))
    return (bool(nbrs) and not steep and vx > 1e-6), steep


def h_side(me, nbrs):
    """Where a label writes its H so that they stand away from its drawn bonds: (best, Octet's own) among 'left', 'right'
    and, with two or more bonds, 'above' and 'below'; each scored by the angle to the nearest bond, the sides slightly
    preferred.  Octet's own choice follows its reading direction (auto_reading)."""
    dirs = [math.degrees(math.atan2(-(q[1] - me[1]), q[0] - me[0])) % 360 for q in nbrs]
    sides = {'right': 0.0, 'above': 90.0, 'left': 180.0, 'below': 270.0}
    allowed = ['left', 'right'] + (['above', 'below'] if len(nbrs) >= 2 else [])
    room = {k: min(min(abs(sides[k] - d) % 360, 360 - abs(sides[k] - d) % 360) for d in dirs) for k in allowed}
    best = max(allowed, key=lambda k: (room[k] + (15 if k in ('left', 'right') else 0), k == 'right'))
    rtl, steep = auto_reading(me, nbrs)
    own = ('above' if sum(q[1] - me[1] for q in nbrs) > 0 else 'below') if steep and len(nbrs) >= 2 else 'left' if rtl else 'right'
    return best, own, room


def text_side(me, nbrs):
    """Alignment of a written label (abbreviation) from its bonds: 'left' (reads away to the right), 'right', 'centre' (Octet's value)."""
    if not nbrs:
        return 'left'
    nx = sum(q[0] - me[0] for q in nbrs)
    ny = sum(q[1] - me[1] for q in nbrs)
    if abs(nx) < 0.3 * math.hypot(nx, ny):
        return 'centre'
    return 'left' if nx < 0 else 'right'


def kekule(bond_rows, atom_of):
    """Drawn orders for the bonds given as 1.5 (Octet draws its delocalized bond type as a plain single line, which
    would show a pyridine as a saturated ring): a Kekule structure, where every atom of those bonds that still has a
    free valence gets exactly one double bond among them (first with every such atom, then with N, O, S and P allowed
    to keep a lone pair, as in pyrrole).  -> ({bond index: 1 or 2}, True), or ({}, False) when there is none."""
    arom = [k for k, b in enumerate(bond_rows) if b.get('order', 1) == 1.5]
    if not arom:
        return {}, True
    other, n_arom, adj = {}, {}, {}
    for k, b in enumerate(bond_rows):
        for e, f in (('a', 'b'), ('b', 'a')):
            if b.get('order', 1) == 1.5:
                n_arom[b[e]] = n_arom.get(b[e], 0) + 1
                adj.setdefault(b[e], []).append((k, b[f]))
            else:
                other[b[e]] = other.get(b[e], 0) + b.get('order', 1)

    def free(ref):
        a = atom_of[ref]
        el, q = a.get('el') or 'C', int(a.get('charge') or 0)
        v = VALENCE.get(el)
        if v is None:
            return 0
        target = v - abs(q) if v == 4 else (v - q if el in ('B', 'Al') else v + q)
        form = parse_h_label(a['label'], el) if a.get('label') and ELEMENT.match(el) else None
        return target - other.get(ref, 0) - n_arom[ref] - (form[1] if form else 0)

    atoms_ = sorted(adj)
    can = {r for r in atoms_ if free(r) >= 1}
    for optional in (set(), {r for r in can if (atom_of[r].get('el') or 'C') in ('N', 'O', 'S', 'P')}):
        must = [r for r in atoms_ if r in can and r not in optional]
        matched, steps = {}, [0]

        def solve(i):
            while i < len(must) and must[i] in matched:
                i += 1
            if i == len(must):
                return True
            steps[0] += 1
            if steps[0] > 200000:
                return False
            r = must[i]
            for k, s in adj[r]:
                if s in can and s not in matched:
                    matched[r], matched[s] = k, k
                    if solve(i + 1):
                        return True
                    del matched[r], matched[s]
            return False
        if solve(0):
            doubles = set(matched.values())
            return {k: 2 if k in doubles else 1 for k in arom}, True
    return {}, False


def map_key(ref):
    """'R.gpp:7' -> ('R', '7'): the panel and the atom map, which names the same atom in every panel."""
    panel, _, rest = ref.partition('.')
    return panel, rest.rpartition(':')[2]


# ------------------------------------------------------------------------------------------ resolved -> document
def build_job(resolved, options=None):
    """Resolved figure -> (page job for adapter.ts, notes).  Raises OctetError on bad input."""
    if not isinstance(resolved, dict) or resolved.get('format') != FORMAT:
        raise OctetError('not a resolved figure (format %r expected)' % FORMAT)
    style = resolved.get('style') or {}
    number_pt = float(style.get('number_size_pt', 8))
    number_font = style.get('number_font')
    doc_style = {}
    for k, (v, scale) in STYLE_KEYS.items():
        if style.get(k) is not None:
            doc_style[v] = round(float(style[k]) * scale, 4)
    if 'labelSize' in doc_style:
        doc_style['captionSize'] = doc_style['labelSize']
    if style.get('font'):
        doc_style['labelFont'] = doc_style['captionFont'] = style['font']
    label_pt = doc_style.get('labelSize', 10.0)
    bond_pt = doc_style.get('bond', BOND_PT)
    title_pt = float(style.get('title_size_pt') or label_pt)
    cap_h = CAP_HEIGHT * label_pt / bond_pt

    def baseline(y, size_pt):
        """A text's (x, y) in the resolved figure is the middle of its capital letters (y down); Octet's is the
        baseline of its first line (y up)."""
        return -(float(y) + CAP_HEIGHT * float(size_pt) / bond_pt / 2.0)

    atoms, captions, arrows, shapes = [], [], [], []
    refs, roles, attached, numbers, titles, curved, fixed_angles, notes = [], [], [], [], [], [], [], []
    index = {}
    panels = resolved.get('panels') or []
    if not panels:
        raise OctetError('the figure has no panels')

    def cap(c, role):
        captions.append(c)
        roles.append(role)
        return len(captions) - 1

    # atoms (all panels first: bonds and arrows name atoms by ref)
    for p in panels:
        for a in p.get('atoms', []):
            ref = a.get('ref')
            if not ref or ref in index:
                raise OctetError('atom ref %r missing or used twice' % ref)
            index[ref] = len(refs)
            refs.append(ref)
            atoms.append(a)
    pos = {ref: (atoms[k]['x'], atoms[k]['y']) for ref, k in index.items()}
    nbrs = {ref: [] for ref in index}
    shown = {ref: [] for ref in index}         # neighbors drawn as bonds (not a folded H): they decide a label's side
    used = {ref: 0.0 for ref in index}
    bond_rows = []
    for p in panels:
        for b in p.get('bonds', []):
            for e in ('a', 'b'):
                if b.get(e) not in index:
                    raise OctetError('panel %s: bond to unknown atom %r' % (p.get('id'), b.get(e)))
            order = b.get('order', 1)
            if order not in (1, 2, 3, 1.5):
                raise OctetError('panel %s: bond order %r' % (p.get('id'), order))
            nbrs[b['a']].append(pos[b['b']])
            nbrs[b['b']].append(pos[b['a']])
            for me, other in ((b['a'], b['b']), (b['b'], b['a'])):
                if not atoms[index[other]].get('hidden_h'):
                    shown[me].append(pos[other])
            bond_rows.append(b)
    # order 1.5: a Kekule structure where there is one, else a double bond with its second line dashed
    kek, kek_ok = kekule(bond_rows, {ref: atoms[k] for ref, k in index.items()})
    drawn_order = []
    for k, b in enumerate(bond_rows):
        order = b.get('order', 1)
        if order == 1.5:
            order = kek[k] if kek_ok else 2
        if b.get('style') == '1.5':
            order = 2
        drawn_order.append(order)
        used[b['a']] += order          # as Octet counts it for hydrogens
        used[b['b']] += order
    n15 = sum(1 for b in bond_rows if b.get('order') == 1.5 and not b.get('haptic'))
    if n15:
        notes.append('%d bonds of order 1.5 drawn %s (give Kekule orders in the resolved figure)' % (
            n15, 'as a Kekule structure' if kek_ok else 'as double bonds with a dashed second line: no Kekule structure was found'))
    pairs = {}
    for p in panels:
        for ref in p.get('lone_pairs', []):
            if ref not in index:
                raise OctetError('panel %s: lone pair on unknown atom %r' % (p.get('id'), ref))
            pairs[ref] = pairs.get(ref, 0) + 1

    doc_atoms = []
    for k, a in enumerate(atoms):
        ref, el, label = refs[k], a.get('el') or 'C', a.get('label')
        charge = int(a.get('charge') or 0)
        x, y = float(a['x']), float(a['y'])
        e = {'label': el if ELEMENT.match(el) else 'C', 'x': round(x, 4), 'y': round(-y, 4), 'hiddenNumber': str(k)}
        if a.get('isotope'):
            e['isotope'] = int(a['isotope'])
        if a.get('radical'):
            e['radical'] = int(a['radical'])
            e['angles'] = {'radical0': 30, **({'radical1': 330} if a['radical'] == 2 else {})}
        if a.get('hidden_h'):
            e['hidden'] = True
        if a.get('center'):
            e['centre'] = {'atoms': [index[r] for r in a['center']]}
        if a.get('preserve_h') or a.get('ts'):
            e['implicitHCount'] = int(a.get('h') or 0)
        color = (a.get('color') or '').lower() or None
        residue = label if label and (a.get('kind') == 'residue' or el in ('*', 'R')) else None
        if residue:
            # A residue's name (Glu170) beside a bare root vertex: Octet draws the digits of an atom label as subscripts.
            e['label'] = 'C'
            me = (x, y)
            side = text_side(me, shown[ref])
            if side == 'left':
                c = caption(residue, x + ROOT_GAP, -(y + cap_h / 2), 'left', color=color)
            elif side == 'right':
                c = caption(residue, x - ROOT_GAP, -(y + cap_h / 2), 'right', color=color)
            else:
                up = sum(q[1] - y for q in shown[ref]) > 0          # bond goes down: the name goes above
                c = caption(residue, x, -(y - ROOT_GAP) if up else -(y + ROOT_GAP + cap_h), 'center', color=color)
            attached.append({'caption': cap(c, 'residue'), 'atom': k})
        elif label and (label != el or a.get('kind') == 'abbrev'):   # an abbreviation spelled like its element (P) is text, not the atom (PH2)
            form = parse_h_label(label, el) if ELEMENT.match(el) else None
            want_h = int(a.get('display_h', a.get('h')) or 0) if a.get('preserve_h') or a.get('ts') else max(0, octet_hydrogens(el, charge, used[ref]) - int(a.get('radical') or 0))
            if a.get('display_h') is not None:
                want_h = a['display_h']
            if form is not None and form[1] == want_h and (form[0] is not None or want_h == 0):
                rtl, steep = auto_reading((x, y), shown[ref])
                if el == 'C':
                    e['shown'] = True
                if form[0] == 'first':
                    if rtl or steep or not shown[ref]:
                        e['align'] = 'right'
                    else:
                        notes.append('%s: label %s would put the H on the bond side; Octet reads it the other way' % (ref, label))
                elif form[0] == 'after':
                    if not shown[ref]:
                        e['align'] = 'left'
                    elif rtl:
                        notes.append('%s: label %s would put the H on the bond side; Octet reads it the other way' % (ref, label))
                # the written H stand away from the drawn bonds: where Octet's own reading puts them near a bond and
                # another side is clearly freer, that side is set
                if shown[ref] and want_h and 'align' not in e:
                    best, own, room = h_side((x, y), shown[ref])
                    if room[own] < 60 and room[best] > room[own] + 20:
                        e['align'] = {'left': 'right', 'right': 'left', 'above': 'above', 'below': 'below'}[best]
            elif form is not None:
                # Octet would count another number of hydrogens: the label is written out as text
                e['text'] = label
                e['chemical'] = False
                if el == 'C':
                    e['shown'] = True
                e['align'] = text_side((x, y), shown[ref])
                notes.append('%s: label %s written as text (Octet counts %d H for %s here)' % (ref, label, want_h, el))
            else:
                e['text'] = label
                if not a.get('chemical'):
                    e['chemical'] = False
                e['align'] = text_side((x, y), shown[ref])
        elif label == 'C' and el == 'C':
            e['shown'] = True       # a bare carbon the spec asks to show (the C of CO2): Octet hides carbon symbols unless 'shown'
        elif label is None and el != 'C' and ELEMENT.match(el):
            notes.append('%s: %s has no label; Octet draws heteroatoms with their symbol' % (ref, el))
        if charge:
            e['charge'] = charge
            if a.get('circled'):
                e['circled'] = True
        if a.get('charge_angle') is not None:
            e['angles'] = {'charge': round(float(a['charge_angle']) % 360.0, 3)}
            fixed_angles.append(k)
        if 'native_align' in a:
            e['align'] = a['native_align']
        if pairs.get(ref):
            e['pairs'] = min(4, pairs[ref])
        if a.get('oxidation') is not None:
            from iupac_features import roman
            e['ox'] = int(a['oxidation'])
            kcap = cap(caption('^{%s}' % roman(a['oxidation']), x + 0.45, -(y + 0.25), 'left'), 'oxidation')
            attached.append({'caption': kcap, 'atom': k})
        if color:
            e['colour'] = color          # (a residue's root vertex shows nothing; its name carries the color too)
        if a.get('number'):
            if el == 'H':
                notes.append('%s: number %r refused: numbers never go on an H drawn as a letter' % (ref, a['number']))
            else:
                n = caption(str(a['number']), x, -(y + 0.6), 'center', size=number_pt)
                if number_font:
                    n['font'] = number_font
                numbers.append({'atom': k, 'caption': cap(n, 'number')})
        doc_atoms.append(e)

    doc_bonds, move_ends = [], []
    for k, b in enumerate(bond_rows):
        e = {'atoms': [index[b['a']], index[b['b']]], 'type': int(drawn_order[k])}
        if b.get('haptic'):
            e['type'] = 4
        if b.get('move') in (b['a'], b['b']):
            move_ends.append({'bond': k, 'atom': index[b['move']]})      # this end moves when the bond is lengthened
        if b.get('order') == 1.5 and not kek_ok and not b.get('haptic'):
            e['display'] = 'dashed'
        st = b.get('style') or 'plain'
        if st == 'wedge':
            e['stereo'] = 1
        elif st == 'hash':
            e['stereo'] = 6
        elif st in ('bold', 'dashed', 'wavy', 'hashed', 'hollow', 'partial', '1.5'):
            e['display'] = 'dashed' if st in ('partial', '1.5') else st
        elif st not in ('plain', 'coord'):
            raise OctetError('bond %s-%s: style %r' % (b['a'], b['b'], st))
        if st == '1.5':
            # Force a main line on the axis and its dashed companion inside the
            # shortest ring; without a ring, face the other substituents.
            adj = {r: [] for r in index}
            for edge in bond_rows:
                if edge is not b:
                    adj[edge['a']].append(edge['b'])
                    adj[edge['b']].append(edge['a'])
            styles = {frozenset((edge['a'], edge['b'])): edge.get('style') for edge in bond_rows}
            ring = delocalized_ring(adj, b['a'], b['b'], styles)
            p0, p1 = pos[b['a']], pos[b['b']]
            def cross(r, p0=p0, p1=p1):
                return (p1[0] - p0[0]) * (pos[r][1] - p0[1]) - (p1[1] - p0[1]) * (pos[r][0] - p0[0])
            value = ring_side(ring, styles, cross) if ring else sum(cross(r) for r in adj[b['a']] + adj[b['b']])
            e['position'] = 'left' if value < 0 else 'right'
        if b.get('color'):
            e['colour'] = b['color'].lower()
        doc_bonds.append(e)
    ts_frames = []
    for p in panels:
        for pair in p.get('pseudobonds', []):
            doc_bonds.append({'atoms': [index[r] for r in pair], 'type': 10})
        for pair in p.get('hbonds', []):
            if len(pair) != 2 or any(r not in index for r in pair):
                raise OctetError('panel %s: hydrogen bond %r' % (p.get('id'), pair))
            doc_bonds.append({'atoms': [index[pair[0]], index[pair[1]]], 'type': 10})
        for bx in p.get('boxes', []):
            s = {'kind': bx.get('kind', 'box'), 'x1': round(float(bx['x1']), 4), 'y1': round(-float(bx['y1']), 4),
                 'x2': round(float(bx['x2']), 4), 'y2': round(-float(bx['y2']), 4)}
            if s['kind'] not in ('box', 'rounded', 'oval', 'brackets'):
                raise OctetError('panel %s: box kind %r' % (p.get('id'), s['kind']))
            if bx.get('color'):
                s['colour'] = bx['color'].lower()
            if bx.get('dashed'):
                s['dashed'] = True
            shapes.append(s)
            if bx.get('ts'):
                k = cap(caption('‡', float(bx['x2']) + .25, baseline(float(bx['y1']) - .2, label_pt),
                                'left', size=label_pt), 'ts')
                ts_frames.append({'shape': len(shapes) - 1, 'caption': k,
                                  'atoms': [index[a['ref']] for a in p['atoms'] if a.get('species') == bx['ts']]})
        for t in p.get('texts', []):
            size = float(t.get('size') or label_pt)
            c = caption(t['text'], float(t['x']), baseline(t['y'], size), t.get('align', 'center'), size=t.get('size'), color=t.get('color'))
            cap(c, 'text')
        title = p.get('title')
        if title and title.get('text'):
            tx, ty = title.get('x'), title.get('y')
            tsize = float(title.get('size') or title_pt)
            k = cap(caption(title['text'], float(tx or 0.0), baseline(ty, tsize) if ty is not None else 0.0, 'center',
                            size=tsize if abs(tsize - label_pt) > 1e-6 else None), 'title')
            titles.append({'caption': k, 'atoms': [index[a['ref']] for a in p.get('atoms', [])], 'autoX': tx is None, 'autoY': ty is None, 'generated': title.get('auto', False)})
        for c in p.get('curved', []):
            def end(e, what):
                kind, rs = e.get('kind'), e.get('refs') or []
                if kind not in ('atom', 'bond', 'gap') or len(rs) != (1 if kind == 'atom' else 2) or any(r not in index for r in rs):
                    raise OctetError('curved arrow %s: bad %s %r' % (c.get('id'), what, e))
                return {'kind': kind, 'atoms': [index[r] for r in rs]}
            curved.append({'id': str(c.get('id') or 'C%d' % (len(curved) + 1)), 'src': end(c['from'], 'start'), 'snk': end(c['to'], 'end'),
                           'electrons': int(c.get('electrons', 2)), **({'bend': float(c['bend'])} if c.get('bend') is not None else {})})
    straight_names, arrow_groups = [], []
    for k, ra in enumerate(resolved.get('reaction_arrows') or []):
        kind = ARROW_KINDS.get(ra.get('kind', 'single'))
        if not kind:
            raise OctetError('reaction arrow %d: kind %r' % (k, ra.get('kind')))
        arrows.append({'kind': kind, 'x1': round(float(ra['x1']), 4), 'y1': round(-float(ra['y1']), 4), 'x2': round(float(ra['x2']), 4),
                       'y2': round(-float(ra['y2']), 4), 'colour': '#000000', **({'style': 'bold'} if ra.get('weight') == 'bold' else {}),
                       **({'start': 'none', 'end': 'none'} if ra.get('kind') == 'stoich' else {}),
                       **({'ratio': float(ra['ratio'])} if ra.get('ratio') else {})})
        arrow_index = len(arrows) - 1
        if ra.get('kind') in ('both', 'stoich'):
            first = arrows[-1]
            second = dict(first)
            dx, dy = first['x2'] - first['x1'], first['y2'] - first['y1']
            length = math.hypot(dx, dy) or 1
            nx, ny = -dy / length * 0.11, dx / length * 0.11
            for end in ('1', '2'):
                first['x' + end] += nx
                first['y' + end] += ny
                second['x' + end] -= nx
                second['y' + end] -= ny
            if ra['kind'] == 'both':
                second['x1'], second['x2'] = second['x2'], second['x1']
                second['y1'], second['y2'] = second['y2'], second['y1']
            arrows.append(second)
            arrow_groups.append({'kind': ra['kind'], 'indices': [arrow_index, arrow_index + 1]})
            straight_names.append(str(ra.get('id') or 'R%d' % (k + 1)) + '-back')
        straight_names.append(str(ra.get('id') or 'R%d' % (k + 1)))
        for side in ('above', 'below'):
            if ra.get(side):
                c = caption(ra[side], 0.0, 0.0, 'center')
                if re.search(r'\d', c['text']):
                    c.setdefault('runs', [{'text': c['text']}])  # Octet sets a condition on an arrow as a formula (digits after letters become subscripts) unless it has runs
                c['on'] = {'arrow': arrow_index, 'side': side}
                cap(c, 'condition')
    # Open delocalized ligands use a native editable headless curve; closed ones use Octet's haptic ellipse.
    for panel in panels:
        for eta in panel.get('eta', []):
            if not eta.get('path'):
                continue
            curve_index = len(arrows)
            points = [pos[ref] for ref in eta['path']]
            x, y = pos[eta['center']]
            points = [(x + .65 * (px - x), -(y + .65 * (py - y))) for px, py in points]
            curve = []
            for i, point in enumerate(points):
                before, after = points[max(0, i - 1)], points[min(len(points) - 1, i + 1)]
                tangent = ((after[0] - before[0]) / 6, (after[1] - before[1]) / 6)
                curve.append({'at': point, 'c1': [point[k] - tangent[k] for k in (0, 1)], 'c2': [point[k] + tangent[k] for k in (0, 1)]})
            arrows.append({'kind': 'curve', 'x1': points[0][0], 'y1': points[0][1], 'x2': points[-1][0], 'y2': points[-1][1],
                           'curve': {'points': curve}, 'start': 'none', 'end': 'none', 'colour': '#000000'})
            arrow_groups.append({'kind': 'delocalization', 'indices': [curve_index], 'center': eta['center']})
            straight_names.append('eta-curve-' + eta['center'])
    # the same atom in several panels (same atom map and element, one per panel): its circled charge goes the same way
    groups = {}
    for k, ref in enumerate(refs):
        panel, mp = map_key(ref)
        groups.setdefault((mp, doc_atoms[k]['label']), []).append((panel, k))
    same = []
    for members in groups.values():
        panels_seen = [pn for pn, _ in members]
        if len(members) > 1 and len(set(panels_seen)) == len(panels_seen):
            same.append([k for _, k in members])
    # the atom identities, kept in the file: hiddenNumber -> ref (Octet keeps 1 to 8 characters there)
    lines = ['%d=%s' % (k, r) for k, r in enumerate(refs)]
    annotations, chunk = [], []
    for ln in lines:
        if sum(len(x) + 1 for x in chunk) + len(ln) > 9000:
            annotations.append(chunk)
            chunk = []
        chunk.append(ln)
    if chunk:
        annotations.append(chunk)
    doc = {'format': 'octet', 'version': 1, 'structure': {'atoms': doc_atoms, 'bonds': doc_bonds},
           'annotations': [{'keyword': 'figure-refs' if i == 0 else 'figure-refs-%d' % (i + 1), 'content': '\n'.join(c)} for i, c in enumerate(annotations)]}
    ts_h = {str(k): int(a.get('h') or 0) for k, a in enumerate(atoms) if (a.get('ts') or a.get('preserve_h')) and a.get('kind') == 'atom'}
    if ts_h:
        doc['annotations'].append({'keyword': 'figure-ts-h', 'content': json.dumps(ts_h, sort_keys=True)})
    doc['annotations'].append({'keyword': 'figure-drawing', 'content': json.dumps(resolved.get('drawing', {'charge_circles': True, 'partial_bonds': 'dashed'}))})
    if arrow_groups:
        doc['annotations'].append({'keyword': 'figure-arrow-groups', 'content': json.dumps(arrow_groups)})
    chemistry = {str(k): {key: a[key] for key in ('h', 'display_h', 'radical', 'isotope', 'hidden_h', 'oxidation') if key in a}
                 for k, a in enumerate(atoms) if any(a.get(key) for key in ('hidden_h', 'preserve_h', 'radical', 'isotope')) or a.get('oxidation') is not None}
    if chemistry:
        doc['annotations'].append({'keyword': 'figure-chemistry', 'content': json.dumps(chemistry, sort_keys=True)})
    if arrows:
        doc['arrows'] = arrows
    if shapes:
        doc['shapes'] = shapes
    if captions:
        doc['captions'] = captions
    page = {'doc': json.dumps(doc, ensure_ascii=False), 'refs': refs, 'curved': curved, 'numbers': numbers, 'titles': titles, 'attached': attached,
            'captionRoles': roles, 'fixedChargeAngles': fixed_angles, 'sameAtom': same, 'straightNames': straight_names, 'style': doc_style, 'moveEnds': move_ends,
            'options': dict(options or {}), 'tsFrames': ts_frames,
            'metalCenters': [index[g['center']] for p in resolved['panels'] for g in p.get('metal_geometry', [])],
            'fixedLabelAligns': [index[a['ref']] for p in resolved['panels'] for a in p['atoms'] if 'native_align' in a],
            'radicalAngles': {k: a['radical_angle'] for k, a in enumerate(atoms) if a.get('radical_angle') is not None}}
    return page, notes


# ------------------------------------------------------------------------------------------ bundle (cached)
def _sha(*parts):
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else str(p).encode())
        h.update(b'\0')
    return h.hexdigest()


def bundle(octet_dir, node_modules=None, cache_dir=None, node='node'):
    """The adapter page for this checkout, built once and kept in cache_dir.  Returns (path, built_now)."""
    octet = Path(octet_dir).resolve()
    src = octet / 'src'
    if not (src / 'render.ts').is_file():
        raise OctetError('%s is not an Octet Draw checkout (no src/render.ts)' % octet)
    parts = [(HERE / 'adapter.ts').read_bytes(), (HERE / 'build.mjs').read_bytes()]
    for p in sorted(src.rglob('*')):
        if p.is_file():
            parts += [str(p.relative_to(src)), p.read_bytes()]
    if (octet / 'package.json').is_file():
        parts.append((octet / 'package.json').read_bytes())
    nm = Path(node_modules).resolve() if node_modules else None
    if nm and (nm / 'esbuild' / 'package.json').is_file():
        parts.append((nm / 'esbuild' / 'package.json').read_bytes())
    key = _sha(*parts)[:16]
    user_cache = Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'reaction-draw'
    cache = Path(cache_dir or os.environ.get('OCTET_DRAW_CACHE') or user_cache).resolve()   # never the (read-only) skill folder
    html = cache / ('adapter-%s.html' % key)
    if html.is_file():
        return html, False
    cache.mkdir(parents=True, exist_ok=True)
    tmp = cache / ('.adapter-%s-%d.html' % (key, os.getpid()))
    cmd = [node, str(HERE / 'build.mjs'), '--octet', str(octet), '--out', str(tmp)]
    if nm:
        cmd += ['--node-modules', str(nm)]
    env = dict(os.environ)
    if nm:
        env['NODE_PATH'] = str(nm) + (os.pathsep + env['NODE_PATH'] if env.get('NODE_PATH') else '')
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding='utf-8')
    if r.returncode != 0 or not tmp.is_file():
        raise OctetError('build.mjs failed (exit %d): %s' % (r.returncode, (r.stderr or r.stdout).strip()[-2000:]))
    for line in r.stderr.splitlines():
        if 'warning' in line:
            print('octet_draw: ' + line, file=sys.stderr)
    os.replace(tmp, html)
    return html, True


def bundled_page():
    """The prebuilt adapter page shipped in dist/ -> (path, notes).  A note says when adapter.ts has changed since the
    page was built (the page then does not have the change: rebuild it with build.mjs, or pass an Octet checkout)."""
    if not DIST_PAGE.is_file():
        raise OctetError('the prebuilt page %s is missing: pass --octet (an Octet Draw checkout; needs Node.js and esbuild) '
                         'to build one' % DIST_PAGE.name)
    notes = []
    try:
        rec = json.loads(DIST_RECORD.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        rec = {}
    want = rec.get('adapter_sha256')
    if want and want != hashlib.sha256((HERE / 'adapter.ts').read_bytes()).hexdigest():
        notes.append('adapter.ts has changed since dist/%s was built: the drawing uses the bundled page, without the '
                     'change (rebuild it with build.mjs, or pass --octet with an Octet Draw checkout)' % DIST_PAGE.name)
    return DIST_PAGE, notes


# ------------------------------------------------------------------------------------------ draw
def check_environment(browser_cmd=None, octet_dir=None, node_modules=None):
    """Probe the actual browser command and the drawing font without writing a figure."""
    checkout = octet_dir or os.environ.get('OCTET_DRAW_CHECKOUT')
    if checkout:
        html, _ = bundle(checkout, node_modules or os.environ.get('OCTET_DRAW_NODE_MODULES'))
        notes = []
    else:
        html, notes = bundled_page()
    if notes:
        return {'ok': False, 'problems': notes}
    command = browser_cmd if browser_cmd is not None else os.environ.get('OCTET_DRAW_BROWSER_CMD')
    if not command:
        import octet_run
        return octet_run.check_environment(html)
    try:
        r = subprocess.run('%s %s --check-env %s' % (command, shlex.quote(str(RUNNER)), shlex.quote(str(html))),
                           shell=True, capture_output=True, text=True, timeout=25, encoding='utf-8')
    except subprocess.TimeoutExpired:
        return {'ok': False, 'problems': ['browser command: timed out; check the command or configure --browser-cmd '
                                        'with a reachable Python that has Playwright and Chromium installed']}
    if r.returncode:
        detail = (r.stderr or r.stdout).strip().splitlines()
        return {'ok': False, 'problems': ['browser command: %s; configure --browser-cmd with a working Python '
                                        'and install Playwright and Chromium there' % (detail[-1] if detail else 'failed')]}
    try:
        return json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {'ok': False, 'problems': ['browser command: did not return the probe JSON; use a command that forwards '
                                        'the runner and its arguments to Python']}


def delocalized_ring(adj, a, z, styles):
    """The ring through bond a-z: the shortest other path from a to z; among equally short ones, the one with the most
    1.5 or partial bonds (the delocalized system), else the first in neighbor order. None without a ring."""
    dist, queue = {z: 0}, [z]
    for x in queue:
        for y in adj[x]:
            if y not in dist:
                dist[y] = dist[x] + 1
                queue.append(y)
    if a not in dist:
        return None
    paths = [[a]]
    while paths[0][-1] != z:
        paths = [p + [y] for p in paths for y in adj[p[-1]] if dist.get(y) == dist[p[-1]] - 1]
    return max(paths, key=lambda p: sum(styles.get(frozenset(e)) in ('1.5', 'partial') for e in zip(p, p[1:])))


def ring_side(ring, styles, cross):
    """Which side of bond ring[0]-ring[-1] its ring lies on, as a signed value of cross (the caller's cross product of
    the bond with an atom). The two ring neighbors decide; when a twisted (perspective) ring puts them on opposite
    sides, the neighbor joined by a 1.5 bond decides, else the whole ring."""
    a, z = ring[0], ring[-1]
    sa, sz = cross(ring[1]), cross(ring[-2])
    if sa * sz > 0:
        return sa
    la, lz = (styles.get(frozenset(e)) == '1.5' for e in ((a, ring[1]), (z, ring[-2])))
    if la != lz:
        return sa if la else sz
    return sum(cross(r) for r in ring)


def draw(resolved, out_dir, png_width=None, octet_dir=None, node_modules=None, browser_cmd=None, small_dpi=150,
         browser='auto', cache_dir=None, node='node', options=None, dpi=None):
    """Draw a resolved figure with Octet into out_dir and return the report (dict); options: the repository's docs/backend.md."""
    t0 = time.perf_counter()
    timings = {}
    out = Path(out_dir).resolve()
    if isinstance(resolved, (str, Path)):
        resolved = json.loads(Path(resolved).read_text(encoding='utf-8-sig'))
    page, notes = build_job(resolved, options)
    out.mkdir(parents=True, exist_ok=True)
    timings['document'] = time.perf_counter() - t0
    t = time.perf_counter()
    octet_dir = octet_dir or os.environ.get('OCTET_DRAW_CHECKOUT')
    if octet_dir:
        node_modules = node_modules or os.environ.get('OCTET_DRAW_NODE_MODULES')
        html, built = bundle(octet_dir, node_modules, cache_dir, node)
        source = 'built from a checkout'
    else:
        html, extra = bundled_page()
        built, source = False, 'bundled'
        notes = notes + extra
    timings['bundle'] = time.perf_counter() - t
    browser_cmd = browser_cmd if browser_cmd is not None else os.environ.get('OCTET_DRAW_BROWSER_CMD')
    dpi = dpi or resolved.get('drawing', {}).get('dpi', 600)
    job = {'html': str(html), 'out_dir': str(out), 'dpi': dpi, 'png_width': png_width, 'small_dpi': small_dpi or 0, 'browser': browser, 'page': page}
    fd, job_path = tempfile.mkstemp(prefix='.octet-job-', suffix='.json', dir=str(out))
    with os.fdopen(fd, 'w', encoding='utf-8') as fh:
        json.dump(job, fh, ensure_ascii=False)
    t = time.perf_counter()
    try:
        if browser_cmd:
            r = subprocess.run('%s %s %s' % (browser_cmd, shlex.quote(str(RUNNER)), shlex.quote(job_path)), shell=True, capture_output=True, text=True, encoding='utf-8')
            if r.returncode != 0:
                raise OctetError('browser step failed (exit %d): %s' % (r.returncode, (r.stderr or r.stdout).strip()[-3000:]))
            status = json.loads(r.stdout.strip().splitlines()[-1])
        else:
            sys.path.insert(0, str(HERE))
            import octet_run
            status = octet_run.run_job(job_path)
    finally:
        os.unlink(job_path)
    timings['browser_call'] = time.perf_counter() - t
    # the report of this run (a network file system can show another machine's new file a few seconds late)
    deadline = time.time() + 15
    while True:
        try:
            report = json.loads((out / 'report.json').read_text(encoding='utf-8-sig'))
            if report.get('timings_s', {}).get('runner_s') == status.get('runner_s'):
                break
        except (OSError, ValueError):
            pass
        if time.time() > deadline:
            raise OctetError('the report of the browser step did not appear in %s' % out)
        time.sleep(0.2)
    tm = report.setdefault('timings_s', {})
    tm.update({k: round(v, 3) for k, v in timings.items()})
    tm['bundle_built'] = built
    tm['ssh_and_start'] = round(timings['browser_call'] - status.get('runner_s', 0.0), 3) if browser_cmd else 0.0
    tm['total'] = round(time.perf_counter() - t0, 3)
    report['notes'] = notes + report.get('notes', [])
    report['adapter_page'] = {'file': html.name, 'source': source}       # (no local path: the report may be shared)
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description='Draw a resolved figure (resolved/1 JSON) with Octet Draw.')
    ap.add_argument('resolved', help='resolved figure (JSON)')
    ap.add_argument('--out', required=True, help='output directory')
    ap.add_argument('--dpi', type=float, help='figure.png resolution at the true size (default: drawing.dpi, else 600)')
    ap.add_argument('--png-width', type=int, help='figure.png width in px instead of --dpi')
    ap.add_argument('--small-dpi', type=float, default=150, help='figure_small.png resolution (0: none)')
    ap.add_argument('--octet', help='build the adapter page from this Octet Draw checkout (needs Node.js and esbuild; '
                                    'default: $OCTET_DRAW_CHECKOUT, else the prebuilt dist/octet-adapter.html)')
    ap.add_argument('--node-modules', help='node_modules with esbuild, with --octet (default: $OCTET_DRAW_NODE_MODULES or NODE_PATH)')
    ap.add_argument('--browser-cmd', help="command that runs Python with Playwright where the browser is, e.g. 'ssh host /path/python'")
    ap.add_argument('--browser', default='auto', help='auto | chrome | chromium | path of a Chrome/Chromium executable')
    ap.add_argument('--cache', help='where a page built with --octet is kept (default: $OCTET_DRAW_CACHE, else ~/.cache/reaction-draw)')
    ap.add_argument('--node', default='node', help='node executable for build.mjs')
    args = ap.parse_args(argv)
    try:
        rep = draw(Path(args.resolved), args.out, args.png_width, args.octet, args.node_modules, args.browser_cmd, args.small_dpi,
                   args.browser, args.cache, args.node, dpi=args.dpi)
    except (OctetError, OSError, ValueError, KeyError) as e:
        print('octet_draw.py: %s' % e, file=sys.stderr)
        return 2
    for n in rep.get('notes', []):
        print('note: ' + n, file=sys.stderr)
    for p in rep.get('problems', []):
        print('problem: ' + p, file=sys.stderr)
    print(json.dumps({'out': str(Path(args.out).resolve()), 'atoms': len(rep.get('atoms', {})), 'curved': len(rep.get('curved', [])),
                      'numbers': len(rep.get('numbers', [])), 'problems': len(rep.get('problems', [])), 'timings_s': rep.get('timings_s')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())
