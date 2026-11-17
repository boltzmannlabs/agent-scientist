#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Chemical annotations and display choices independent of the organic layout rules."""
import collections
import math

REACTION_KINDS = ('single', 'equilibrium', 'resonance', 'both', 'stoich', 'retro')
METALS = set(('Li Be Na Mg Al K Ca Sc Ti V Cr Mn Fe Co Ni Cu Zn Ga Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn '
              'Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt Au Hg Tl Pb Bi '
              'Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr').split())
# Page angles, counterclockwise. These are drawing templates, not inferred stereochemistry.
GEOMETRIES = {
    'linear': [(180, 'plain'), (0, 'plain')],
    'angular': [(150, 'plain'), (30, 'plain')],
    'trigonal_planar': [(90, 'plain'), (210, 'plain'), (330, 'plain')],
    't_shaped': [(90, 'plain'), (180, 'plain'), (270, 'plain')],
    'square_planar': [(45, 'plain'), (135, 'plain'), (225, 'plain'), (315, 'plain')],
    'square_pyramidal4': [(200, 'hash'), (240, 'wedge'), (300, 'wedge'), (340, 'hash')],
    'see_saw': [(90, 'plain'), (270, 'plain'), (30, 'hash'), (330, 'wedge')],
    'trigonal_bipyramidal': [(90, 'plain'), (270, 'plain'), (180, 'plain'), (30, 'hash'), (330, 'wedge')],
    'square_pyramidal': [(90, 'plain'), (30, 'hash'), (150, 'hash'), (210, 'wedge'), (330, 'wedge')],
    'octahedral': [(90, 'plain'), (270, 'plain'), (30, 'hash'), (150, 'hash'), (210, 'wedge'), (330, 'wedge')],
    'trigonal_prismatic': [(150, 'plain'), (210, 'plain'), (30, 'hash'), (330, 'hash'), (90, 'wedge'), (270, 'wedge')],
}


def fail(message):
    from specutil import SpecError
    raise SpecError(message)


def coordination_edges(graph, styles=None):
    """Plain metal bonds and explicit donor arrows are coordination, with unchanged charges/H."""
    atoms = graph['atoms']
    styles = styles or {}
    result = []
    for b in graph['bonds']:
        a, c = atoms[b['a']], atoms[b['b']]
        mp = (a['map'], c['map'])
        style = styles.get(mp, styles.get(mp[::-1], styles.get('%s-%s' % mp, styles.get('%s-%s' % mp[::-1]))))
        if b.get('coord') or style == 'coord' or (b['order'] == 1 and (a['symbol'] in METALS or c['symbol'] in METALS)):
            result.append(b)
    return result


def prepare_species(sp, raw):
    g, sid = sp['graph'], sp['id']
    atoms, maps = g['atoms'], sp['map_to_index']
    coords = coordination_edges(g, sp['bond_style'])
    for b in coords:
        b['coord'] = True
        a, c = atoms[b['a']], atoms[b['b']]
        sp['bond_style'].setdefault((a['map'], c['map']), 'coord')
        a['preserve_h'] = c['preserve_h'] = True
        for atom in (a, c):
            if atom['h'] and atom['map'] not in sp['show']:
                sp['show'].append(atom['map'])
    # RDKit's radical assignment handles charge, aromaticity and expanded main-group valence.
    from rdkit import Chem, rdBase
    pars = Chem.SmilesParserParams()
    pars.removeHs, pars.sanitize = False, False
    with rdBase.BlockLogs():
        mol = Chem.RWMol(Chem.MolFromSmiles(sp['smiles'], pars))
        for b in coords:
            mol.RemoveBond(b['a'], b['b'])
        mol.UpdatePropertyCache(strict=False)
        Chem.AssignRadicals(mol)
    explicit = raw.get('radicals') or {}
    if not isinstance(explicit, dict):
        fail('%s.radicals must be an object keyed by atom map' % sid)
    for key, n in explicit.items():
        if not str(key).isdigit() or int(key) not in maps or isinstance(n, bool) or not isinstance(n, int) or n not in (0, 1, 2):
            fail('%s.radicals: use existing atom maps and 0, 1 or 2 unpaired electrons' % sid)
    for i, a in enumerate(atoms):
        n = 0 if a['dummy'] or a['symbol'] in METALS or a.get('preserve_h') or sp.get('ts') else mol.GetAtomWithIdx(i).GetNumRadicalElectrons()
        a['radical'] = explicit.get(str(a['map']), n)
        if str(a['map']) in explicit and a['symbol'] not in METALS and not a.get('preserve_h') and not sp.get('ts') and a['radical'] != n:
            fail('%s:%s: radicals=%d disagrees with the bracket H count, charge and bonds (expected %d)' % (sid, a['map'], a['radical'], n))
        if a['radical'] > 2:
            fail('%s:%s: more than two localized unpaired electrons needs an explicit electronic-state depiction' % (sid, a['map']))
        if a['radical'] and a['map'] not in sp['show']:
            sp['show'].append(a['map'])
        if a.get('isotope') and a['dummy']:
            fail('%s:%s: isotopes need an explicit element, not an abbreviation' % (sid, a['map']))
    keep = raw.get('keep_h') or []
    if not isinstance(keep, list) or any(isinstance(mp, bool) or not isinstance(mp, int) or mp not in maps or atoms[maps[mp]]['symbol'] != 'H' for mp in keep):
        fail('%s.keep_h must list existing hydrogen atom maps' % sid)
    for mp in keep:
        atoms[maps[mp]]['keep_h'] = True
    angles = raw.get('radical_angles') or {}
    if not isinstance(angles, dict) or any(not str(mp).isdigit() or int(mp) not in maps or isinstance(deg, bool) or not isinstance(deg, (int, float)) or not math.isfinite(deg) or not atoms[maps[int(mp)]].get('radical') for mp, deg in angles.items()):
        fail('%s.radical_angles must map radical atoms to finite angles in degrees' % sid)
    for mp, deg in angles.items():
        atoms[maps[int(mp)]]['radical_angle'] = deg % 360
    oxidation = raw.get('oxidation') or {}
    if not isinstance(oxidation, dict):
        fail('%s.oxidation must be an object keyed by atom map' % sid)
    sp['oxidation'] = {}
    for key, n in oxidation.items():
        if not str(key).isdigit() or int(key) not in maps or isinstance(n, bool) or not isinstance(n, int) or not -99 <= n <= 99:
            fail('%s.oxidation: use existing atom maps and integer oxidation states from -99 to 99' % sid)
        sp['oxidation'][int(key)] = n
    geometry = raw.get('geometry') or {}
    if not isinstance(geometry, dict):
        fail('%s.geometry must be an object keyed by center atom map' % sid)
    sp['geometry'] = {}
    for key, value in geometry.items():
        if not str(key).isdigit() or int(key) not in maps:
            fail('%s.geometry: unknown center %r' % (sid, key))
        value = {'kind': value} if isinstance(value, str) else value
        if not isinstance(value, dict) or value.get('kind') not in GEOMETRIES:
            fail('%s.geometry: choose %s' % (sid, ', '.join(GEOMETRIES)))
        mp = int(key)
        symbol = atoms[maps[mp]]['symbol']
        if value['kind'] == 't_shaped' and symbol in ('C', 'N'):
            fail('%s.geometry: a carbon or nitrogen center cannot use the T-shaped drawing' % sid)
        if value['kind'] in ('square_pyramidal4', 'see_saw') and (symbol in ('C', 'Si', 'Ge', 'Sn', 'Pb') or
                (symbol == 'N' and atoms[maps[mp]]['charge'] == 1) or (symbol == 'B' and atoms[maps[mp]]['charge'] == -1)):
            fail('%s.geometry: this carbon-group or isoelectronic center cannot use %s' % (sid, value['kind']))
        neighbors = [atoms[b['b'] if b['a'] == maps[mp] else b['a']]['map'] for b in g['bonds'] if maps[mp] in (b['a'], b['b'])]
        ligands = value.get('ligands', neighbors)
        if not isinstance(ligands, list) or sorted(ligands) != sorted(neighbors) or len(ligands) != len(GEOMETRIES[value['kind']]):
            fail('%s.geometry[%s]: ligands must list all %d neighbors in template order' % (sid, key, len(GEOMETRIES[value['kind']])))
        sp['geometry'][mp] = dict(value, ligands=ligands)


def prepare_panel(panel, by_id, atom_ref):
    pid, raw = panel['id'], panel['raw']
    if not isinstance(raw.get('polyhedron', False), bool):
        fail('polyhedron must be true or false')
    panel['eta'] = []
    for e in raw.get('eta') or []:
        if not isinstance(e, dict) or not isinstance(e.get('atoms'), list) or len(e['atoms']) < 2:
            fail('panel %s.eta: use {metal: atom, atoms: [at least two contiguous atoms]}' % pid)
        metal = atom_ref(e.get('metal'), pid, 'eta.metal')
        members = [atom_ref(a, pid, 'eta.atoms') for a in e['atoms']]
        if metal.get('atom2') or any(a.get('atom2') for a in members) or len({(a['sid'], a['atom']) for a in members}) != len(members):
            fail('eta must name distinct atoms, not bonds')
        if by_id[metal['sid']]['graph']['atoms'][by_id[metal['sid']]['map_to_index'][metal['atom']]]['symbol'] not in METALS:
            fail('eta.metal must name a metal atom')
        if len({a['sid'] for a in members}) != 1 or any(a['panel'] != pid for a in members + [metal]):
            fail('eta atoms must form one contiguous ligand in this panel')
        ligand = by_id[members[0]['sid']]
        selected = {a['atom'] for a in members}
        edges = [(ligand['graph']['atoms'][b['a']]['map'], ligand['graph']['atoms'][b['b']]['map']) for b in ligand['graph']['bonds']]
        reached = {next(iter(selected))}
        for _ in selected:
            reached |= {v for u, v in edges + [(v, u) for u, v in edges] if u in reached and v in selected}
        if reached != selected:
            fail('eta atoms must be contiguous')
        cyclic = len(selected) >= 3 and all(sum(a in (u, v) and u in selected and v in selected for u, v in edges) == 2 for a in selected)
        delocalized = e.get('delocalized', cyclic)
        if not isinstance(delocalized, bool):
            fail('eta.delocalized must be true or false')
        path = []
        if delocalized and not cyclic:
            adjacency = {a: [v if u == a else u for u, v in edges if a in (u, v) and u in selected and v in selected] for a in selected}
            ends = [a for a in selected if len(adjacency[a]) == 1]
            if len(ends) != 2 or any(len(v) > 2 for v in adjacency.values()):
                fail('an open delocalized haptic ligand must form an unbranched path')
            path = [min(ends)]
            while len(path) < len(selected):
                path.append(next(a for a in adjacency[path[-1]] if a not in path))
            path = [next(a for a in members if a['atom'] == mp) for mp in path]
        for a in members:
            ligand['graph']['atoms'][ligand['map_to_index'][a['atom']]]['preserve_h'] = True
        panel['eta'].append({'metal': metal, 'atoms': members, 'delocalized': delocalized, 'path': path})
    panel['pseudobonds'] = []
    for pair in raw.get('pseudobonds') or []:
        if not isinstance(pair, list) or len(pair) != 2:
            fail('pseudobonds must be pairs of atom references')
        ends = [atom_ref(a, pid, 'pseudobonds') for a in pair]
        if ends[0] == ends[1] or any(a.get('atom2') or a['panel'] != pid for a in ends):
            fail('pseudobonds must connect two distinct atoms of this panel')
        panel['pseudobonds'].append(ends)
        for a in ends:
            sp = by_id[a['sid']]
            sp['graph']['atoms'][sp['map_to_index'][a['atom']]]['preserve_h'] = True
    if raw.get('polyhedron'):
        vertices = {(a['sid'], a['atom']) for pair in panel['pseudobonds'] for a in pair}
        if len(vertices) < 7 or any(a['symbol'] in METALS for key in panel['species'] for a in by_id[pid + '.' + key]['graph']['atoms']):
            fail('a coordination polyhedron needs at least seven donor vertices, pseudobonds, and no central metal atom')
    for ar in panel['arrows']:
        if ar['from'].get('members'):
            fail('arrow %s: a forming bond cannot supply electrons' % ar['id'])
        r = ar['from']
        a = by_id[r['sid']]['graph']['atoms'][by_id[r['sid']]['map_to_index'][r['atom']]]
        if ar['electrons'] == 1 and r['atom2'] is None and not a.get('radical'):
            fail('arrow %s: a fishhook from an atom needs a drawn unpaired electron' % ar['id'])
    touched = {(r['sid'], mp) for ar in panel['arrows'] for end in (ar['from'], ar['to'])
               for r in end.get('members', [end]) for mp in (r['atom'], r.get('atom2')) if mp is not None}
    touched |= {(r['sid'], r['atom']) for pair in panel['hbonds'] for r in pair}
    for sid, mp in touched:
        if by_id[sid].get('abbrev', {}).get(mp, {}).get('charge'):
            fail('%s:%s: expand a charged abbreviation touched by an arrow or hydrogen bond' % (sid, mp))
    counts = collections.Counter('%s:%s' % (a['sid'], a['atom']) for a in panel['lone_pairs'])
    if any(n > 4 for n in counts.values()):
        fail('lone_pairs supports at most four drawn pairs on one atom')
    errors = electron_flow_errors(panel['arrows'], by_id, pair_counts=counts)
    if errors:
        fail(errors)


def electron_flow_errors(arrows, by_id=None, atoms=None, bonds=None, pair_counts=None, advisory=False):
    """Count electrons leaving each source. Homolysis requires both bond electrons."""
    out, sources, gaps = [], collections.defaultdict(list), collections.defaultdict(list)
    for ar in arrows:
        end = ar['from']
        if 'refs' in end:
            key = tuple(sorted(end['refs']))
        else:
            key = tuple(sorted(['%s:%s' % (end['sid'], end['atom'])] + ([] if end['atom2'] is None else ['%s:%s' % (end['sid'], end['atom2'])])))
        sources[key].append(ar)
        dest = ar['to']
        if dest.get('kind') == 'gap' or dest.get('members'):
            target = tuple(sorted(dest['refs'])) if 'refs' in dest else tuple(sorted('%s:%s' % (r['sid'], r['atom']) for r in dest['members']))
            gaps[target].append(ar)
    for key, rows in sources.items():
        count = sum(r['electrons'] for r in rows)
        if len(key) == 1:
            singles = sum(r['electrons'] == 1 for r in rows)
            if atoms is not None:
                available = atoms[key[0]].get('radical', 0)
            else:
                sid, mp = key[0].rsplit(':', 1)
                available = by_id[sid]['graph']['atoms'][by_id[sid]['map_to_index'][int(mp)]].get('radical', 0)
            if singles > available:
                out.append('%s: %d fishhooks exceed %d drawn unpaired electrons' % (key[0], singles, available))
            if pair_counts is not None and sum(r['electrons'] == 2 for r in rows) > pair_counts.get(key[0], 0):
                out.append('%s: full-headed arrows exceed the drawn lone-pair sources' % key[0])
        else:
            def refs(end):
                if 'refs' in end:
                    return end['refs']
                return ['%s:%s' % (a['sid'], mp) for a in end.get('members', [end]) for mp in [a['atom']] + ([] if a['atom2'] is None else [a['atom2']])]
            cleavage = any(set(refs(r['to'])) & set(key) for r in rows)
            if advisory and cleavage and any(r['electrons'] == 1 for r in rows) and (count != 2 or len(rows) != 2 or any(r['electrons'] != 1 for r in rows)):
                out.append('%s: bond homolysis needs two one-electron fishhooks, one for each electron' % '-'.join(key))
            if advisory and count > 2:
                out.append('%s: more than two electrons leave one bond in a step' % '-'.join(key))
    for key, rows in gaps.items():
        if advisory and sum(r['electrons'] for r in rows) != 2:
            out.append('%s: a new bond needs two electrons, supplied by two fishhooks or one full-headed arrow' % '-'.join(key))
    return out


def prepare_hydrogens(spec):
    """Keep every mapped H and bond; select Octet's native hidden-H display per panel."""
    for p in spec['panels']:
        touched = set()
        for ar in p['arrows']:
            for end in (ar['from'], ar['to']):
                for r in end.get('members', [end]):
                    touched.add((r['sid'], r['atom']))
                    if r['atom2'] is not None:
                        touched.add((r['sid'], r['atom2']))
        touched |= {(r['sid'], r['atom']) for pair in p['hbonds'] for r in pair}
        for key in p['species']:
            sp = spec['species_by_id'][p['id'] + '.' + key]
            for a in sp['graph']['atoms']:
                a.pop('hidden_h', None)
                a['display_h'] = a['h'] or 0
            for a in sp['graph']['atoms']:
                if a['symbol'] != 'H' or a.get('keep_h') or a.get('isotope') or a.get('charge') or a.get('radical') or (sp['id'], a['map']) in touched:
                    continue
                edges = [b for b in sp['graph']['bonds'] if a['i'] in (b['a'], b['b'])]
                if len(edges) != 1 or edges[0]['order'] != 1 or edges[0].get('coord'):
                    continue
                edge = edges[0]
                other = sp['graph']['atoms'][edge['b'] if edge['a'] == a['i'] else edge['a']]
                if other['symbol'] == 'H' or other.get('chiral') or any(sp['bond_style'].get(k) in ('wedge', 'hash') for k in ((a['map'], other['map']), (other['map'], a['map']))):
                    continue
                a['hidden_h'] = True
                other['display_h'] += 1


def resolve_new_bond_heads(spec):
    """When the mapped next panel forms a bond, place its arrow head in that bond's gap."""
    for p in spec['panels']:
        next_ids = [r['to'] for r in spec['reaction_arrows'] if r['from'] == p['id']]
        if len(set(next_ids)) != 1:
            continue
        following = next(x for x in spec['panels'] if x['id'] == next_ids[0])
        new_edges = {}
        for key in following['species']:
            sp = spec['species_by_id'][following['id'] + '.' + key]
            new_edges.update({frozenset((sp['graph']['atoms'][b['a']]['map'], sp['graph']['atoms'][b['b']]['map'])): b['order'] for b in sp['graph']['bonds']})
        for ar in p['arrows']:
            src, dst = ar['from'], ar['to']
            if src.get('members') or dst.get('members') or dst['atom2'] is not None:
                continue
            sp = spec['species_by_id'][src['sid']]
            old_edges = {frozenset((sp['graph']['atoms'][b['a']]['map'], sp['graph']['atoms'][b['b']]['map'])): b['order'] for b in sp['graph']['bonds']}
            candidates = []
            for mp in [src['atom']] + ([] if src['atom2'] is None else [src['atom2']]):
                pair = frozenset((mp, dst['atom']))
                old = old_edges.get(pair, 0) if src['sid'] == dst['sid'] else 0
                if len(pair) == 2 and pair in new_edges and new_edges[pair] > old:
                    candidates.append((mp, old))
            if len(candidates) == 1:
                mp, old = candidates[0]
                if old:
                    ar['to'] = dict(src, atom=mp, atom2=dst['atom'])
                else:
                    ar['to'] = dict(dst, members=[dict(src, atom=mp, atom2=None), dict(dst)])


def atom_fields(sp, a):
    out = {k: a[k] for k in ('isotope', 'radical', 'hidden_h', 'preserve_h', 'keep_h', 'radical_angle') if a.get(k) is not None}
    if a.get('display_h', a['h']) != a['h']:
        out['display_h'] = a['display_h']
    if a['map'] in sp.get('oxidation', {}):
        out['oxidation'] = sp['oxidation'][a['map']]
    return out


def geometry_layout(sp, xy):
    """Rotate each ligand branch about the center, keeping its internal bond lengths."""
    if set(xy) <= set(sp['xy']):
        for mp, cfg in sp.get('geometry', {}).items():
            for ligand, (_, style) in zip(cfg['ligands'], GEOMETRIES[cfg['kind']]):
                if style != 'plain':
                    sp['bond_style'].setdefault((mp, ligand), style)
        return dict(sp['xy'])
    for mp, cfg in sp.get('geometry', {}).items():
        x, y = xy[mp]
        adj = collections.defaultdict(list)
        for b in sp['graph']['bonds']:
            a, c = (sp['graph']['atoms'][b[k]]['map'] for k in ('a', 'b'))
            adj[a].append(c)
            adj[c].append(a)
        moved = set()
        for ligand, (degrees, style) in zip(cfg['ligands'], GEOMETRIES[cfg['kind']]):
            branch, todo = set(), [ligand]
            while todo:
                i = todo.pop()
                if i == mp or i in branch:
                    continue
                branch.add(i)
                todo.extend(adj[i])
            if moved & branch:
                fail('%s.geometry: a chelating ligand needs explicit xy coordinates' % sp['id'])
            moved |= branch
            dx, dy = xy[ligand][0] - x, xy[ligand][1] - y
            turn = math.radians(-degrees) - math.atan2(dy, dx)
            c, s = math.cos(turn), math.sin(turn)
            for i in branch:
                dx, dy = xy[i][0] - x, xy[i][1] - y
                xy[i] = (x + c * dx - s * dy, y + s * dx + c * dy)
            if style != 'plain':
                sp['bond_style'][(mp, ligand)] = style
    return xy


def assemble_panel(panel, atoms, bonds, lay):
    def ref(r):
        return '%s:%s' % (r['sid'], r['atom'])
    panel['resolved_pseudobonds'] = [[ref(r) for r in pair] for pair in panel.get('pseudobonds', [])]
    panel['resolved_eta'] = []
    for i, eta in enumerate(panel.get('eta', [])):
        members = [ref(r) for r in eta['atoms']]
        points = [a for a in atoms if a['ref'] in members]
        center = '%s.__eta:%d' % (panel['id'], i + 1)
        row = {'metal': ref(eta['metal']), 'atoms': members, 'center': center, 'delocalized': eta['delocalized'], 'path': [ref(r) for r in eta['path']]}
        panel['resolved_eta'].append(row)
        if eta['delocalized']:
            for b in bonds:
                if b['a'] in members and b['b'] in members:
                    b['haptic_order'] = b['order']
                    b['order'], b['haptic'] = 1.5, True
        atoms.append({'ref': center, 'el': 'C', 'label': None, 'x': sum(a['x'] for a in points) / len(points),
                      'y': sum(a['y'] for a in points) / len(points), 'kind': 'center', 'h': 0, 'charge': 0,
                      'species': panel['id'] + '.__eta', 'center': members})
        bonds.append({'a': row['metal'], 'b': center, 'order': 1, 'style': 'coord', 'color': None, 'move': None})


def roman(n):
    if n == 0:
        return '0'
    parts, value = ['−'] if n < 0 else [], abs(n)
    for number, text in ((100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'), (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        count, value = divmod(value, number)
        parts.append(text * count)
    return ''.join(parts)
