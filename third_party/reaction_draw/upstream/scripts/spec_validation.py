#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Browser-free, accumulating spec diagnostics; the normal loader still checks the result."""
import difflib
import math
import re

import specutil as su
import stereochemistry as stereo
import iupac_features as ip


def inspect_spec(data):
    """Return (all independent problems, stereo sources); never repair or discard spec data."""
    errors, sources, species, graphs, labels, pair_graphs = [], {}, {}, {}, {}, {}

    def bad(where, message):
        errors.append('%s: %s' % (where, message))

    def obj(value, where):
        if not isinstance(value, dict):
            bad(where, 'must be an object')
            return {}
        return value

    def seq(value, where):
        if not isinstance(value, list):
            bad(where, 'must be a list')
            return []
        return value

    def unknown(value, keys, where):
        for key in sorted(set(value) - keys):
            close = difflib.get_close_matches(str(key), sorted(keys), n=1)
            bad(where, 'unknown key %r; %s' % (key, 'did you mean %r?' % close[0] if close else 'remove it or use a documented key'))

    def number(value, where, positive=False):
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (positive and value <= 0):
            bad(where, 'must be a finite %snumber' % ('positive ' if positive else ''))

    def xy(value, where):
        if not isinstance(value, (list, tuple)) or len(value) != 2:
            bad(where, 'must be [x, y] in bond lengths')
        else:
            for v in value:
                number(v, where)

    def attempt(fn, where):
        try:
            return fn()
        except (su.SpecError, ValueError, TypeError, KeyError, RuntimeError, IndexError) as exc:
            bad(where, str(exc))

    if not isinstance(data, dict):
        return ['input: must be a JSON object'], sources
    attempt(lambda: su.drawing_options(data.get('drawing')), 'drawing')
    if data.get('format', 2) != 2:
        return ['input.format: must be 2 (or left out)'], sources
    unknown(data, su.V2_TOP_KEYS, 'input')
    for k, v in obj(data.get('style') or {}, 'style').items():
        if k not in su.ACS_STYLE:
            bad('style', 'unknown key %r' % k)
        elif k in ('font', 'number_font'):
            if not isinstance(v, str) or not v.strip():
                bad('style.' + k, 'must be a font name')
        else:
            number(v, 'style.' + k, positive=True)
    panels = seq(data.get('panels'), 'panels')
    if not panels:
        bad('panels', 'must contain at least one panel')
    panel_ids, panel_rows, raw_species = [], [], []
    for pi, p0 in enumerate(panels):
        pw = 'panels[%d]' % pi
        p = obj(p0, pw)
        pid = str(p.get('id', 'P%d' % (pi + 1)))
        if pid in panel_ids or not re.fullmatch(r'[A-Za-z0-9_-]+', pid):
            bad(pw + '.id', '%r is duplicated or invalid; use a unique name of letters, digits, _ and -' % pid)
        panel_ids.append(pid)
        pw = 'panel %s (%s)' % (pid, pw)
        panel_rows.append((pid, p, pw))
        unknown(p, su.V2_PANEL_KEYS, pw)
        title = p.get('title')
        title = title.get('text') if isinstance(title, dict) else title
        if title is not None and not isinstance(title, str):
            bad(pw + '.title', 'must be text')
        keys = set()
        for si, s0 in enumerate(seq(p.get('species') or [], pw + '.species')):
            sw = '%s.species[%d]' % (pw, si)
            s = obj(s0, sw)
            key = s.get('id')
            valid = isinstance(key, str) and bool(re.fullmatch(r'[A-Za-z0-9_-]+', key))
            sid = '%s.%s' % (pid, key)
            if not valid or key in keys or sid in species:
                bad(sw + '.id', '%r is missing, invalid or duplicated in this panel; use a unique species id' % key)
            if not valid:
                continue
            keys.add(key)
            sw = '%s, species %s' % (pw, key)
            unknown(s, su.V2_SPECIES_KEYS, sw)
            species[sid] = s
            raw_species.append((sid, pid, key, s, sw))
    for sid, pid, key, s, sw in raw_species:
        smiles = s.get('smiles')
        if not isinstance(smiles, str) or not smiles.strip():
            bad(sw + '.smiles', 'is missing; write a mapped SMILES for this panel')
            continue
        graph = attempt(lambda: su.parse_smiles(smiles), sw + '.smiles')
        if graph is None:
            continue
        pair_graphs[sid] = graph
        atoms = graph['atoms']
        maps = {}
        for atom in atoms:
            mp = atom['map']
            if mp is None or mp <= 0:
                bad(sw + '.smiles', 'atom %d (%s) needs a positive map, e.g. [CH3:8] or explicit [H:13]' % (atom['i'] + 1, atom['symbol']))
            elif mp in maps:
                bad(sw + '.smiles', 'atom map %d is used twice; assign a unique map to each atom' % mp)
            else:
                maps[mp] = atom
        edges = {frozenset((atoms[b['a']]['map'], atoms[b['b']]['map'])) for b in graph['bonds']}
        graphs[sid] = (maps, edges)
        is_ts = s.get('ts', False)
        if not isinstance(is_ts, bool):
            bad(sw + '.ts', 'must be true or false')
        styles = s.get('bond_style') if isinstance(s.get('bond_style'), dict) else {}
        try:
            from rdkit import Chem, rdBase
            pars = Chem.SmilesParserParams()
            pars.removeHs, pars.sanitize = False, False
            with rdBase.BlockLogs():
                mol = Chem.MolFromSmiles(smiles, pars)
                if mol is None:
                    bad(sw + '.smiles', 'RDKit cannot parse this SMILES; correct its branches, rings and explicit H')
                else:
                    # A TS graph includes forming/breaking single bonds. They are not
                    # full-valence bonds; validate the remaining chemistry normally.
                    valence_mol = Chem.RWMol(mol)
                    if is_ts or ip.coordination_edges(graph, styles):
                        for bk, style in styles.items():
                            match = re.fullmatch(r'(\d+)[-=#~](\d+)', str(bk))
                            if style in ('partial', 'coord') and match:
                                inds = {a.GetAtomMapNum(): a.GetIdx() for a in mol.GetAtoms()}
                                a, b = map(int, match.groups())
                                if a in inds and b in inds and valence_mol.GetBondBetweenAtoms(inds[a], inds[b]):
                                    valence_mol.RemoveBond(inds[a], inds[b])
                        for edge in ip.coordination_edges(graph, styles):
                            if valence_mol.GetBondBetweenAtoms(edge['a'], edge['b']):
                                valence_mol.RemoveBond(edge['a'], edge['b'])
                    problems = Chem.DetectChemistryProblems(valence_mol)
                    for problem in problems:
                        ix = problem.GetAtomIdx() if hasattr(problem, 'GetAtomIdx') else None
                        place = 'atom %s' % mol.GetAtomWithIdx(ix).GetAtomMapNum() if ix is not None else 'graph'
                        bad(sw + '.smiles', '%s: %s; correct the bond orders, charge or H count' % (place, problem.Message()))
                    if not problems and len(maps) == len(atoms):
                        labels[sid] = stereo.chemical(sid, smiles, stereo.stub_names(sid, data),
                                                      relaxed=is_ts or bool(ip.coordination_edges(graph, styles)))
                        sources[sid] = smiles
        except ImportError:
            bad(sw, 'install RDKit in this Python: python -m pip install rdkit')
        except (ValueError, RuntimeError) as exc:
            bad(sw + '.smiles', 'stereo/valence could not be checked: %s' % exc)
        keyed = ('abbrev', 'residue', 'label', 'xy')
        fields = {}
        for field in keyed:
            fields[field] = obj(s.get(field) or {}, sw + '.' + field)
            for mk, value in fields[field].items():
                if not str(mk).isdigit() or int(mk) not in maps:
                    bad(sw + '.' + field, 'unknown atom map %r; add that mapped atom to SMILES or correct the reference' % mk)
                    continue
                atom = maps[int(mk)]
                if field in ('abbrev', 'residue'):
                    if not atom['dummy']:
                        bad(sw + '.' + field, 'atom %s must be a dummy [*:%s]' % (mk, mk))
                    if field == 'abbrev':
                        attempt(lambda: su._abbrev(value, sw), sw + '.abbrev[' + str(mk) + ']')
                    else:
                        attempt(lambda: su._residue_text(value, sw), sw + '.residue[' + str(mk) + ']')
                if field == 'xy':
                    xy(value, sw + '.xy[' + str(mk) + ']')
        for mp, atom in maps.items():
            if atom['dummy'] and str(mp) not in fields['abbrev'] and str(mp) not in fields['residue']:
                bad(sw, 'dummy atom %d needs an abbrev or residue label' % mp)
        for mp in seq(s.get('show') or [], sw + '.show'):
            if not isinstance(mp, int) or isinstance(mp, bool) or mp not in maps:
                bad(sw + '.show', 'unknown atom map %r; correct the map' % mp)
        for bk, val in obj(s.get('bond_style') or {}, sw + '.bond_style').items():
            m = re.fullmatch(r'(\d+)[-=#~](\d+)', str(bk))
            if not m or frozenset(map(int, m.groups())) not in edges:
                bad(sw + '.bond_style', '%r is not a bond of this species' % bk)
            if val not in ('plain', 'wedge', 'hash', 'bold', 'partial', '1.5', 'wavy', 'coord'):
                bad(sw + '.bond_style', '%r must be plain, wedge, hash, bold, partial, 1.5 wavy or coord' % val)
            if val == 'partial' and not is_ts:
                bad(sw + '.bond_style', 'partial requires "ts": true')
            if m and val in ('partial', '1.5'):
                pair = frozenset(map(int, m.groups()))
                orders = [b['order'] for b in graph['bonds'] if frozenset((atoms[b['a']]['map'], atoms[b['b']]['map'])) == pair]
                if orders and orders[0] not in ((1,) if val == 'partial' else (1, 2)):
                    bad(sw + '.bond_style', '%s needs a %s bond in SMILES' % (bk, 'single' if val == 'partial' else 'single or double'))
        number(s.get('rotate', 0), sw + '.rotate')
        if s.get('flip') not in (None, 'x', 'y', 'xy'):
            bad(sw + '.flip', 'must be x, y or xy')
        if s.get('offset') is not None:
            xy(s['offset'], sw + '.offset')

    def ref(value, pid, where, atom_only=False):
        if isinstance(value, list):
            if atom_only or len(value) != 2:
                bad(where, 'a forming bond is a pair of atom references, allowed only as an arrow destination')
                return
            for v in value:
                ref(v, pid, where, atom_only=True)
            if value[0] == value[1]:
                bad(where, 'a forming bond needs two different atoms')
            return
        parsed = attempt(lambda: su.parse_ref(value, pid, where), where)
        if parsed is None:
            return
        p, k, a, b = parsed
        sid, members = '%s.%s' % (p, k), [a] + ([b] if b is not None else [])
        if atom_only and len(members) != 1:
            bad(where, 'must name one atom, not a bond')
        if sid not in species:
            bad(where, 'unknown species %r; correct the panel/species id' % sid)
        elif sid in graphs:
            maps, edges = graphs[sid]
            for mp in members:
                if not isinstance(mp, int) or mp not in maps:
                    bad(where, 'atom map %r is not in %s; correct the map, or add a moving H as [H:map] (bracket H counts have no map)' % (mp, sid))
            if len(members) == 2 and all(isinstance(m, int) and m in maps for m in members) and frozenset(members) not in edges:
                bad(where, 'atoms %s are not bonded in %s; reference an existing bond' % (members, sid))
        return sid, members

    arrow_ids = {}
    def arrows(rows, pid, where, pair_atoms=()):
        for ai, a0 in enumerate(seq(rows or [], where)):
            a = obj(a0, '%s[%d]' % (where, ai))
            aid = a.get('id', 'A%d' % (len(arrow_ids) + 1))
            if isinstance(aid, str) and arrow_ids.get(aid, pid) != pid:
                aid = '%s-%s' % (pid, aid)          # an id repeated from another panel takes this panel's name
            aw = '%s[%d] (arrow %s)' % (where, ai, aid)
            if not isinstance(aid, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', aid) or aid in arrow_ids:
                bad(aw, 'arrow id is invalid or duplicated; use a unique id across the figure')
            if isinstance(aid, str):
                arrow_ids[aid] = pid
            if a.get('electrons', 2) not in (1, 2) or isinstance(a.get('electrons'), bool):
                bad(aw, 'electrons must be 1 or 2')
            bend = a.get('bend')
            if bend is not None and (isinstance(bend, bool) or not isinstance(bend, (int, float)) or not 0.1 <= abs(bend) <= 1.6):
                bad(aw, 'bend must be a number with 0.1 <= |bend| <= 1.6; its sign picks the side the arrow bulges to')
            for end in ('from', 'to'):
                if end == 'from' and isinstance(a.get(end), list):
                    bad(aw, 'a forming bond cannot supply electrons')
                rr = ref(a.get(end), pid, aw + '.' + end)
                if end == 'from' and rr and len(rr[1]) == 1 and a.get('electrons', 2) == 2:
                    atom = '%s:%s' % (rr[0], rr[1][0])
                    if rr[0] in pair_graphs and any(a['map'] == rr[1][0] for a in pair_graphs[rr[0]]['atoms']):
                        problem = su.lone_pair_source_error(pair_graphs[rr[0]], rr[1][0], atom in pair_atoms)
                        if problem:
                            bad(aw + '.from', 'atom %s: %s' % (atom, problem.format(ref=atom)))
    for pid, p, pw in panel_rows:
        pair_atoms = []
        for r in seq(p.get('lone_pairs') or [], pw + '.lone_pairs'):
            rr = ref(r, pid, pw + '.lone_pairs', atom_only=True)
            if rr and len(rr[1]) == 1:
                pair_atoms.append('%s:%s' % (rr[0], rr[1][0]))
        arrows(p.get('arrows', []), pid, pw + '.arrows', pair_atoms)
        for sid, spid, key, s, sw in raw_species:
            if spid != pid or s.get('near') is None:
                continue
            near = {'atom': s['near']} if isinstance(s['near'], str) else obj(s['near'], sw + '.near')
            rr = ref(near.get('atom'), pid, sw + '.near', atom_only=True)
            if rr and not rr[0].startswith(pid + '.'):
                bad(sw + '.near', 'must refer to an atom of this panel')
            for k in ('dist', 'dir'):
                if near.get(k) is not None:
                    number(near[k], sw + '.near.' + k, positive=k == 'dist')
        for hi, pair in enumerate(seq(p.get('hbonds') or [], pw + '.hbonds')):
            hw = '%s.hbonds[%d]' % (pw, hi)
            if not isinstance(pair, list) or len(pair) != 2:
                bad(hw, 'must be a pair of atom references')
            else:
                for r in pair:
                    ref(r, pid, hw, atom_only=True)
        for bi, b0 in enumerate(seq(p.get('boxes') or [], pw + '.boxes')):
            bw = '%s.boxes[%d]' % (pw, bi)
            b = obj(b0, bw)
            keys = seq(b.get('species'), bw + '.species')
            if not keys:
                bad(bw, 'must enclose at least one species')
            for k in keys:
                if '%s.%s' % (pid, k) not in species:
                    bad(bw, 'unknown species %r in this panel' % k)
            if b.get('kind', 'box') not in ('box', 'rounded', 'oval', 'brackets'):
                bad(bw, 'kind must be box, rounded, oval or brackets')
            number(b.get('pad', 0.35), bw + '.pad')
        for ti, t0 in enumerate(seq(p.get('texts') or [], pw + '.texts')):
            tw = '%s.texts[%d]' % (pw, ti)
            t = obj(t0, tw)
            if not isinstance(t.get('text'), str):
                bad(tw, 'text must be a string')
            if t.get('xy') is not None:
                xy(t['xy'], tw + '.xy')
            elif t.get('near') is not None:
                ref(t['near'], pid, tw + '.near', atom_only=True)
            else:
                bad(tw, 'give xy or near')
            if t.get('align', 'center') not in ('left', 'center', 'right'):
                bad(tw, 'align must be left, center or right')
            if 'size' in t:
                number(t['size'], tw + '.size', positive=True)
            for key in ('dist', 'dir'):
                if t.get(key) is not None:
                    number(t[key], tw + '.' + key, positive=key == 'dist')
        for r in obj(p.get('angle_exceptions') or {}, pw + '.angle_exceptions'):
            ref(r, pid, pw + '.angle_exceptions', atom_only=True)
    if data.get('arrows'):
        bad('arrows', 'move curved arrows into their panel')
    rows = data.get('rows') or [panel_ids]
    rows = seq(rows, 'rows')
    flat = [x for i, row in enumerate(rows) for x in seq(row, 'rows[%d]' % i)]
    if sorted(map(str, flat)) != sorted(panel_ids):
        bad('rows', 'must name each panel exactly once')
    for k, value in obj(data.get('numbers') or {}, 'numbers').items():
        nw = 'numbers[%r]' % k
        m = re.fullmatch(r'(?:(?P<panel>[^.:]+)\.)?(?:(?P<species>[^.:]+):)?(?P<map>\d+)', str(k))
        if not m:
            bad(nw, 'use a map, species:map or panel.species:map')
            continue
        targets = [(sid, maps[int(m['map'])]) for sid, (maps, _) in graphs.items() if int(m['map']) in maps
                   and (m['panel'] is None or sid.split('.')[0] == m['panel'])
                   and (m['species'] is None or sid.split('.', 1)[1] == m['species'])]
        if not targets:
            bad(nw, 'names no atom; correct the panel, species or map')
        for sid, atom in targets:
            if atom['symbol'] == 'H':
                bad(nw, '%s is an explicit H; keep numbers on its heavy atom' % sid)
        text = value.get('text') if isinstance(value, dict) else value
        if not isinstance(text, (str, int)) or isinstance(text, bool) or str(text) == '':
            bad(nw, 'must be nonempty number text')
    for ri, r0 in enumerate(seq(data.get('reaction_arrows') or [], 'reaction_arrows')):
        rw = 'reaction_arrows[%d]' % ri
        r = obj(r0, rw)
        for end in ('from', 'to'):
            if r.get(end) not in panel_ids:
                bad(rw + '.' + end, 'unknown panel %r' % r.get(end))
        kind = r.get('kind', 'single')
        if kind not in ip.REACTION_KINDS:
            bad(rw + '.kind', 'must be ' + ', '.join(ip.REACTION_KINDS))
        if r.get('weight', 'normal') not in ('normal', 'bold'):
            bad(rw + '.weight', 'must be normal or bold')
        if not isinstance(r.get('summary', False), bool):
            bad(rw + '.summary', 'must be true or false')
        if r.get('ratio') is not None:
            number(r['ratio'], rw + '.ratio', positive=True)
            if kind != 'equilibrium' or (isinstance(r['ratio'], (int, float)) and r['ratio'] > 100):
                bad(rw + '.ratio', 'must be at most 100 and used only on an equilibrium arrow')
        if r.get('length') is not None:
            number(r['length'], rw + '.length', positive=True)
        if (r.get('from_pt') is None) != (r.get('to_pt') is None):
            bad(rw, 'give from_pt and to_pt together')
        for end in ('from_pt', 'to_pt'):
            if r.get(end) is not None:
                v = obj(r[end], rw + '.' + end)
                ref(v.get('atom'), r.get(end[:-3]), rw + '.' + end, atom_only=True)
                xy(v.get('dxy', [0, 0]), rw + '.' + end + '.dxy')

    colors = data.get('colors')
    if colors not in (None, False) and colors != {}:
        colors = obj(colors, 'colors')
        unknown(colors, {'element', 'origin', 'heteroatoms'}, 'colors')
        palette = colors.get('element')
        if palette and palette is not True:
            for sym, color in obj(palette, 'colors.element').items():
                if sym != '*' and not re.fullmatch(r'[A-Z][a-z]?', sym):
                    bad('colors.element', '%r is not an element symbol' % sym)
                if color not in (None, False):
                    attempt(lambda: su._hex(color, 'colors.element[%s]' % sym), 'colors.element')
        if colors.get('heteroatoms', 'element') not in ('element', 'origin'):
            bad('colors.heteroatoms', 'must be element or origin')
        proxies = {sid: {'map_to_index': maps} for sid, (maps, _) in graphs.items()}
        by_key, maps_in, assigned = {}, {}, {}
        for sid, (maps, _) in graphs.items():
            by_key.setdefault(sid.split('.', 1)[1], []).append(sid)
            for mp in maps:
                maps_in.setdefault(mp, []).append(sid)
        for gi, g0 in enumerate(seq(colors.get('origin') or [], 'colors.origin')):
            gw = 'colors.origin[%d]' % gi
            g = obj(g0, gw)
            members = seq(g.get('atoms'), gw + '.atoms')
            if not members:
                bad(gw, 'must have a nonempty atoms list')
            if g.get('color') is not None:
                attempt(lambda: su._hex(g['color'], gw), gw)
            elif gi >= len(su.ORIGIN_COLORS):
                bad(gw, 'give color for every group after group %d' % len(su.ORIGIN_COLORS))
            for item in members:
                found = attempt(lambda: su._origin_items(item, gw, proxies, maps_in, by_key), gw)
                for target in found or []:
                    if target in assigned and assigned[target] != gi:
                        bad(gw, '%s also belongs to colors.origin[%d]; keep one origin per atom/species' % (target, assigned[target]))
                    assigned[target] = gi

    # Expectations can be global (all matching panels) or local to a species.
    # "unspecified" declares a stereocenter whose configuration the source does not show (harness_rsi D541).
    declared = {}
    def expectations(block, where, own_sid=None):
        for key, want in obj(block, where).items():
            ew = '%s[%r]' % (where, key)
            if want not in ('R', 'S', 'r', 's', 'E', 'Z', 'unspecified'):
                bad(ew, 'must be R, S, r, s, E, Z or unspecified')
                continue
            target = str(key)
            if own_sid and ':' not in target:
                target = own_sid + ':' + target
            if ':' not in target:
                bad(ew, 'use species:map or species:a=b (panel prefix optional)')
                continue
            sk, mk = target.rsplit(':', 1)
            matches = [sid for sid in species if sid == sk or sid.split('.', 1)[1] == sk]
            if own_sid:
                matches = [sid for sid in matches if sid == own_sid]
            if not matches:
                bad(ew, 'unknown species %r' % sk)
                continue
            m = re.fullmatch(r'(\d+)(?:=(\d+))?', mk)
            if not m:
                bad(ew, 'use an atom map or two double-bond maps a=b')
                continue
            a, b = int(m[1]), int(m[2]) if m[2] else None
            if (b is None and want not in ('R', 'S', 'r', 's', 'unspecified')) or (b is not None and want not in ('E', 'Z')):
                bad(ew, 'use R/S (or unspecified) for an atom and E/Z for a double bond')
                continue
            if want == 'unspecified':
                for sid in matches:
                    declared.setdefault(sid, set()).add(a)
            if want == 'unspecified':     # a declaration applies to the panels that draw the atom
                if all(a not in graphs[sid][0] for sid in matches if sid in graphs):
                    bad(ew, 'unknown atom map %d' % a)
                matches = [sid for sid in matches if sid in graphs and a in graphs[sid][0]]
            for sid in matches:
                if sid not in graphs:
                    continue
                maps, edges = graphs[sid]
                for mp in [a] + ([b] if b is not None else []):
                    if mp not in maps:
                        bad(ew, '%s: unknown atom map %d' % (sid, mp))
                if sid not in labels:
                    continue
                (atom_labels, bond_labels), depends = labels[sid]
                ar = sid + ':' + str(a)
                br = sid + ':' + str(b)
                got = atom_labels.get(ar) if b is None else bond_labels.get(tuple(sorted((ar, br))))
                if want == 'unspecified':
                    if got is not None:
                        bad(ew, '%s: SMILES has %s; write the configuration in expected_stereo, or remove @/@@ if the source does not show it' % (ar, got))
                    continue
                if (ar if b is None else tuple(sorted((ar, br)))) in depends:
                    bad(ew, '%s%s: the label depends on an abbreviation or residue stub; write that group in full in the SMILES' % (
                        ar, '' if b is None else '=' + str(b)))
                elif got != want:
                    bad(ew, '%s%s: SMILES has %s, expected %s; correct @/@@ or / and \\ against the source figure' % (
                        ar, '' if b is None else '=' + str(b), got or 'unspecified', want))
    expectations(data.get('expected_stereo', {}), 'expected_stereo')
    for sid, _, _, s, sw in raw_species:
        expectations(s.get('expected_stereo', {}), sw + '.expected_stereo', sid)
    # Every stereocenter outside a transition state has a configuration from the source, or is declared unspecified.
    for sid, _, key, s, sw in raw_species:
        if sid not in labels or sid not in sources or s.get('ts'):
            continue
        styles = s.get('bond_style') if isinstance(s.get('bond_style'), dict) else {}
        try:
            centers = stereo.potential_centers(sid, sources[sid], relaxed='coord' in styles.values() or '->' in sources[sid] or '<-' in sources[sid],
                                               names=stereo.stub_names(sid, data))
        except (ValueError, RuntimeError):
            continue
        maps = graphs[sid][0] if sid in graphs else {}
        for ref in sorted(centers - set(labels[sid][0][0]), key=lambda r: int(r.rsplit(':', 1)[1])):
            mp = int(ref.rsplit(':', 1)[1])
            if mp in declared.get(sid, ()) or (maps.get(mp) or {}).get('symbol') in ip.METALS:
                continue
            bad(sw + '.smiles', 'atom %d is a stereocenter without a configuration; write @/@@ as the source figure draws it '
                '(and its R/S in expected_stereo), or, if the source does not show this configuration, add '
                '"%s:%d": "unspecified" to expected_stereo' % (mp, key, mp))
    return list(dict.fromkeys(errors)), sources
