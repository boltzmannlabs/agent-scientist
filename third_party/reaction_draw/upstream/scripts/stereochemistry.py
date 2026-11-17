#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare SMILES stereo with saved coordinates and directed wedges, independently of layout.

Atom maps identify corresponding atoms only: they are cleared before priority assignment.
Comparing the drawing with the SMILES, both graphs use a neutral, H-free dummy atom for every
abbreviation/residue stub.  R/S and E/Z of the real molecule (expected_stereo, STEREO lines) expand
the abbreviations in ABBREV_SMILES; a stub of unknown structure is ranked lowest and highest, and a
label that changes between the two depends on it.  CIP labels are computed with rdCIPLabeler, not
legacy mapped-SMILES _CIPCode values.
"""
import math


def _rdkit():
    try:
        from rdkit import Chem
        from rdkit.Chem import rdCIPLabeler
    except ImportError as exc:
        raise ValueError('stereochemistry checking needs RDKit') from exc
    return Chem, rdCIPLabeler


def _labels(mol, refs):
    Chem, labeler = _rdkit()
    # The legacy ranker intentionally treats atom maps as distinguishing properties.
    # Keep the correspondence in refs, outside the molecule used to calculate CIP.
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    Chem.AssignStereochemistry(mol, cleanIt=True, force=True)
    for obj in list(mol.GetAtoms()) + list(mol.GetBonds()):
        if obj.HasProp('_CIPCode'):
            obj.ClearProp('_CIPCode')
    labeler.AssignCIPLabels(mol)
    atoms = {refs[a.GetIdx()]: a.GetProp('_CIPCode') for a in mol.GetAtoms() if a.HasProp('_CIPCode')}
    bonds = {tuple(sorted((refs[b.GetBeginAtomIdx()], refs[b.GetEndAtomIdx()]))): b.GetProp('_CIPCode')
             for b in mol.GetBonds() if b.HasProp('_CIPCode') and b.GetBondTypeAsDouble() == 2.0}
    return atoms, bonds


def expected(sid, smiles, relaxed=False):
    """The specified CIP labels and correspondence, with explicit H atoms preserved."""
    Chem, _ = _rdkit()
    from iupac_features import METALS
    import re
    relaxed = relaxed or '->' in smiles or '<-' in smiles or any(e in METALS for e in re.findall(r'\[\d*([A-Z][a-z]?)', smiles))
    params = Chem.SmilesParserParams()
    params.removeHs = False
    params.sanitize = not relaxed
    mol = Chem.MolFromSmiles(smiles, params)
    if mol is None:
        raise ValueError('%s: RDKit cannot read the reference SMILES' % sid)
    if relaxed:
        mol.UpdatePropertyCache(strict=False)
        Chem.SanitizeMol(mol, sanitizeOps=Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
    refs = ['%s:%d' % (sid, a.GetAtomMapNum()) for a in mol.GetAtoms()]
    if any(a.GetAtomMapNum() <= 0 for a in mol.GetAtoms()) or len(set(refs)) != len(refs):
        raise ValueError('%s: the reference needs a unique atom map on every atom' % sid)
    stubs = {refs[a.GetIdx()] for a in mol.GetAtoms() if a.GetAtomicNum() == 0}
    for atom in mol.GetAtoms():
        if refs[atom.GetIdx()] in stubs:
            atom.SetFormalCharge(0)
            atom.SetNumExplicitHs(0)
            atom.SetNoImplicit(True)
    return _labels(mol, refs), refs, stubs


def potential_centers(sid, smiles, relaxed=False, names=None):
    """Tetrahedral stereogenic atoms, including unspecified centers; maps only identify atoms.  With names (stub_names),
    the stubs in ABBREV_SMILES are expanded first, as chemical() does."""
    Chem, _ = _rdkit()
    params = Chem.SmilesParserParams()
    params.removeHs, params.sanitize = False, not relaxed and names is None
    mol = Chem.MolFromSmiles(smiles, params)
    if mol is None:
        raise ValueError('%s: cannot read stereogenic-atom reference' % sid)
    refs = ['%s:%d' % (sid, a.GetAtomMapNum()) for a in mol.GetAtoms()]
    if names is not None:
        mol, refs, _ = _expand(sid, mol, names)
        if not relaxed:
            Chem.SanitizeMol(mol)
    for atom in mol.GetAtoms():
        atom.SetAtomMapNum(0)
    if relaxed:
        mol.UpdatePropertyCache(strict=False)
        Chem.FastFindRings(mol)
    return {refs[i] for i, _ in Chem.FindMolChiralCenters(mol, includeUnassigned=True, useLegacyImplementation=False)
            if ':~' not in refs[i]}


_AROMATIC = {}


def aromatic_pairs(smiles):
    """Aromatic bonds of a SMILES as {frozenset(('map', 'map'))}; a Kekule form and its aromatic ring give the same set."""
    if smiles not in _AROMATIC:
        Chem, _ = _rdkit()
        from rdkit import rdBase
        params = Chem.SmilesParserParams()
        params.removeHs, params.sanitize = False, False
        out = set()
        with rdBase.BlockLogs():
            mol = Chem.MolFromSmiles(smiles, params)
            if mol is not None:
                try:
                    mol.UpdatePropertyCache(strict=False)
                    Chem.SanitizeMol(mol, sanitizeOps=Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
                except (ValueError, RuntimeError):
                    mol = None
            if mol is not None:
                out = {frozenset((str(b.GetBeginAtom().GetAtomMapNum()), str(b.GetEndAtom().GetAtomMapNum())))
                       for b in mol.GetBonds() if b.GetIsAromatic()}
        _AROMATIC[smiles] = out
    return _AROMATIC[smiles]


def ring_junctions(sid, smiles, relaxed=False):
    """Fused bonds and bridged-ring atoms from the reference graph, without coordinates."""
    Chem, _ = _rdkit()
    params = Chem.SmilesParserParams()
    params.removeHs, params.sanitize = False, not relaxed
    mol = Chem.MolFromSmiles(smiles, params)
    if mol is None:
        raise ValueError('%s: cannot read ring-junction reference' % sid)
    if relaxed:
        mol.UpdatePropertyCache(strict=False)
        Chem.GetSymmSSSR(mol)
    refs = ['%s:%d' % (sid, a.GetAtomMapNum()) for a in mol.GetAtoms()]
    rings = [set(r) for r in mol.GetRingInfo().AtomRings()]
    fused, bridged = set(), set()
    for i, ring in enumerate(rings):
        for other in rings[i + 1:]:
            shared = ring & other
            if len(shared) == 2:
                a, b = sorted(shared)
                if mol.GetBondBetweenAtoms(a, b):
                    fused.add(tuple(sorted((refs[a], refs[b]))))
            elif len(shared) > 2:
                bridged.update(refs[a] for a in shared)
    return fused, bridged


# One-attachment abbreviations with a fixed structure; the first atom attaches. Used to rank substituents for R/S.
ABBREV_SMILES = {
    'Me': 'C', 'Et': 'CC', 'Pr': 'CCC', 'nPr': 'CCC', 'iPr': 'C(C)C', 'Bu': 'CCCC', 'nBu': 'CCCC', 'iBu': 'CC(C)C',
    'sBu': 'C(C)CC', 's-Bu': 'C(C)CC', 'tBu': 'C(C)(C)C', 't-Bu': 'C(C)(C)C', 'Ph': 'c1ccccc1', 'Bn': 'Cc1ccccc1',
    'Ac': 'C(C)=O', 'Ts': 'S(=O)(=O)c1ccc(C)cc1', 'Ms': 'S(C)(=O)=O', 'Tf': 'S(=O)(=O)C(F)(F)F',
    'OMe': 'OC', 'OEt': 'OCC', 'OAc': 'OC(C)=O', 'OBn': 'OCc1ccccc1', 'OTs': 'OS(=O)(=O)c1ccc(C)cc1',
    'OMs': 'OS(C)(=O)=O', 'OTf': 'OS(=O)(=O)C(F)(F)F', 'OTBS': 'O[Si](C)(C)C(C)(C)C',
    'OP': 'OP(=O)(O)O', 'OPP': 'OP(=O)(O)OP(=O)(O)O', 'OPPP': 'OP(=O)(O)OP(=O)(O)OP(=O)(O)O',
    'NHAc': 'NC(C)=O', 'NHBoc': 'NC(=O)OC(C)(C)C'}


def stub_names(sid, spec):
    """{ref: text} of the abbreviation and residue stubs of one species appearance in the raw input."""
    import re
    names = {}
    for index, panel in enumerate((spec or {}).get('panels') or []):
        if not isinstance(panel, dict):
            continue
        for species in panel.get('species') or []:
            if not isinstance(species, dict) or str(panel.get('id', 'P%d' % (index + 1))) + '.' + str(species.get('id')) != sid:
                continue
            for block in (species.get('residue'), species.get('abbrev')):
                for key, value in (block or {}).items() if isinstance(block, dict) else ():
                    text = value.get('text') if isinstance(value, dict) else value
                    if isinstance(text, str):
                        names['%s:%s' % (sid, key)] = re.sub(r'[^A-Za-z0-9-]', '', text)
    return names


def _expand(sid, base, names):
    """A writable copy of base whose stubs named in ABBREV_SMILES are expanded in place, its refs (added atoms are
    "sid:~n"), and the indices of the other stubs (neutral, H-free dummies)."""
    Chem, _ = _rdkit()
    refs = ['%s:%d' % (sid, a.GetAtomMapNum()) for a in base.GetAtoms()]
    unknown = []
    rw = Chem.RWMol(base)
    for atom in base.GetAtoms():
        if atom.GetAtomicNum() != 0:
            continue
        stub = rw.GetAtomWithIdx(atom.GetIdx())
        stub.SetFormalCharge(0)
        stub.SetNumExplicitHs(0)
        stub.SetNoImplicit(True)
        text = ABBREV_SMILES.get(names.get(refs[atom.GetIdx()], ''))
        if not text:
            unknown.append(atom.GetIdx())
            continue
        frag = Chem.MolFromSmiles(text)
        Chem.Kekulize(frag, clearAromaticFlags=True)
        index = {0: atom.GetIdx()}
        first = frag.GetAtomWithIdx(0)
        stub.SetAtomicNum(first.GetAtomicNum())
        stub.SetNoImplicit(False)
        for fa in list(frag.GetAtoms())[1:]:
            index[fa.GetIdx()] = rw.AddAtom(Chem.Atom(fa.GetAtomicNum()))
            refs.append('%s:~%d' % (sid, len(refs)))
        for fb in frag.GetBonds():
            rw.AddBond(index[fb.GetBeginAtomIdx()], index[fb.GetEndAtomIdx()], fb.GetBondType())
    return rw, refs, unknown


def chemical(sid, smiles, names, relaxed=False):
    """R/S and E/Z of the real molecule, and the labels that depend on a stub of unknown structure.

    Stubs named in ABBREV_SMILES are expanded in place (the stub becomes the attaching atom, so the
    chirality tags keep their neighbor order).  Other stubs are ranked lowest (dummy) and highest.
    """
    Chem, _ = _rdkit()
    from iupac_features import METALS
    import re
    relaxed = relaxed or '->' in smiles or '<-' in smiles or any(e in METALS for e in re.findall(r'\[\d*([A-Z][a-z]?)', smiles))
    params = Chem.SmilesParserParams()
    params.removeHs = False
    params.sanitize = False
    base = Chem.MolFromSmiles(smiles, params)
    if base is None:
        raise ValueError('%s: RDKit cannot read the reference SMILES' % sid)
    rw, refs, unknown = _expand(sid, base, names)

    def labels(z):
        mol = Chem.RWMol(rw)
        for i in unknown:
            mol.GetAtomWithIdx(i).SetAtomicNum(z)
        if relaxed:
            mol.UpdatePropertyCache(strict=False)
            Chem.SanitizeMol(mol, sanitizeOps=Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
        else:
            Chem.SanitizeMol(mol)
        atoms, bonds = _labels(mol, refs)
        return ({k: v for k, v in atoms.items() if ':~' not in k},
                {k: v for k, v in bonds.items() if not any(':~' in r for r in k)})

    low = labels(0)
    high = labels(118) if unknown else low
    depends = {k for part in (0, 1) for k in set(low[part]) | set(high[part]) if low[part].get(k) != high[part].get(k)}
    return low, depends


def _covered_stereo(sid, spec):
    """Expected labels applying to this appearance, including global and local keys."""
    covered = set()
    def add(block, local=False):
        if not isinstance(block, dict):
            return
        for key, label in block.items():
            if label not in ('R', 'S', 'r', 's', 'E', 'Z'):
                continue
            target = str(key)
            if ':' in target:
                species, target = target.rsplit(':', 1)
                if species != sid and species != sid.split('.', 1)[-1]:
                    continue
            elif not local:
                continue
            try:
                maps = [int(m) for m in target.split('=')]
            except ValueError:
                continue
            if len(maps) in (1, 2):
                covered.add(tuple(sorted(maps)))
    add(spec.get('expected_stereo'))
    panels = spec.get('panels')
    for index, panel in enumerate(panels if isinstance(panels, list) else []):
        if not isinstance(panel, dict):
            continue
        species_list = panel.get('species')
        for species in species_list if isinstance(species_list, list) else []:
            if not isinstance(species, dict):
                continue
            key = str(species.get('id'))
            own = str(panel.get('id', 'P%d' % (index + 1))) + '.' + key
            if own == sid:
                add(species.get('expected_stereo'), local=True)
    return covered


def report(sources, spec=None):
    """Map-free CIP labels once per species; retain panel names when labels differ."""
    groups = {}
    for sid, smiles in sources.items():
        ts = any((s.get('ts') or 'coord' in (s.get('bond_style') or {}).values()) and sid == str(p.get('id')) + '.' + str(s.get('id'))
                 for p in (spec or {}).get('panels', []) for s in p.get('species', [])
                 if isinstance(s, dict))
        (atoms, bonds), depends = chemical(sid, smiles, stub_names(sid, spec), relaxed=ts)
        key = sid.split('.', 1)[-1]
        local = lambda ref: key + ref[len(sid):]
        labels = ['%s %s' % (local(ref), '?' if ref in depends else label) for ref, label in sorted(atoms.items())]
        labels += ['%s=%s %s' % (local(pair[0]), pair[1].rsplit(':', 1)[1], '?' if pair in depends else label)
                   for pair, label in sorted(bonds.items())]
        group = groups.setdefault(key, {'labels': {}, 'appearances': set(), 'missing': False, 'depends': False})
        group['depends'] = group['depends'] or bool(depends)
        group['appearances'].add(tuple(labels))
        for label in labels:
            group['labels'].setdefault(label, []).append(sid.split('.', 1)[0])
        if labels and spec is not None:
            covered = _covered_stereo(sid, spec)
            required = {(int(ref.rsplit(':', 1)[1]),) for ref in atoms}
            required.update(tuple(sorted(int(ref.rsplit(':', 1)[1]) for ref in pair)) for pair in bonds)
            if required - covered:
                group['missing'] = True
    lines = []
    for key, group in groups.items():
        if not group['labels']:
            continue
        if not lines:
            lines.append('STEREO (SMILES; atom maps cleared before CIP assignment):')
        labels = [label + (' (panels %s)' % ', '.join(panels) if len(group['appearances']) > 1 else '')
                  for label, panels in group['labels'].items()]
        lines.append('STEREO: ' + '; '.join(labels))
        if group['depends']:
            lines.append('STEREO: note: in %s, ? marks R/S or E/Z that depends on an abbreviation or residue stub; '
                         'write that group in full in the SMILES to fix the label' % key)
        if group['missing']:
            lines.append('STEREO: note: %s has specified stereocenters or stereo double bonds without expected_stereo; '
                         'add the missing entries from the compound\'s standard name or a database entry' % key)
    return lines


def perceived(atoms, bonds, stubs=(), relaxed=False):
    """CIP labels inferred only from drawn atoms/bonds, x/y (y down) and wedge tips.

    atoms: {ref: {el, charge, h, x, y}}; bonds: [{a, b, order, style}].
    No chirality tag or double-bond stereo from the reference is copied here.
    """
    Chem, _ = _rdkit()
    refs = sorted(atoms)
    indices = {ref: i for i, ref in enumerate(refs)}
    rw = Chem.RWMol()
    for ref in refs:
        a = atoms[ref]
        stub = ref in stubs
        atom = Chem.Atom(0 if stub else a['el'])
        atom.SetFormalCharge(0 if stub else int(a.get('charge') or 0))
        atom.SetIsotope(int(a.get('isotope') or 0))
        atom.SetNumRadicalElectrons(int(a.get('radical') or 0))
        h = 0 if stub else a.get('h')
        if h is not None:
            atom.SetNoImplicit(True)
            atom.SetNumExplicitHs(int(h))
        rw.AddAtom(atom)
    types = {1.0: Chem.BondType.SINGLE, 2.0: Chem.BondType.DOUBLE, 3.0: Chem.BondType.TRIPLE,
             1.5: Chem.BondType.AROMATIC}
    for b in bonds:
        i, j = indices[b['a']], indices[b['b']]
        order = float(b['order'])
        if order not in types:
            raise ValueError('unsupported stereo bond order %s' % order)
        rw.AddBond(i, j, Chem.BondType.ZERO if b.get('coord') else types[order])
        bond = rw.GetBondBetweenAtoms(i, j)
        if order == 1.5:
            bond.SetIsAromatic(True)
            rw.GetAtomWithIdx(i).SetIsAromatic(True)
            rw.GetAtomWithIdx(j).SetIsAromatic(True)
        bond.SetBondDir({'wedge': Chem.BondDir.BEGINWEDGE, 'hash': Chem.BondDir.BEGINDASH}.get(
            b.get('style'), Chem.BondDir.NONE))
    mol = rw.GetMol()
    if relaxed:
        mol.UpdatePropertyCache(strict=False)
    Chem.SanitizeMol(mol, sanitizeOps=(Chem.SanitizeFlags.SANITIZE_ALL ^ Chem.SanitizeFlags.SANITIZE_PROPERTIES)
                     if relaxed else Chem.SanitizeFlags.SANITIZE_ALL)
    conf = Chem.Conformer(len(refs))
    conf.Set3D(False)
    for ref, i in indices.items():
        a = atoms[ref]
        x, y = float(a['x']), float(a['y'])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError('%s: non-finite saved coordinates' % ref)
        conf.SetAtomPosition(i, (x, -y, 0.0))
    mol.AddConformer(conf, assignId=True)
    Chem.AssignChiralTypesFromBondDirs(mol, replaceExistingTags=True)
    Chem.DetectBondStereochemistry(mol)
    return _labels(mol, refs)


def compare(resolved, atoms, bonds, when):
    """Find stereo differences for every species; missing references/coordinates fail closed.

    Compare all R/S (also r/s) centers, including unexpected drawn centers.  For double
    bonds compare only E/Z specified by the SMILES: unspecified geometry is unconstrained.
    """
    sources = resolved.get('stereo_sources')
    if sources is None:
        return [when + ': no SMILES stereo reference; redraw from the input file']
    out = []
    species = {a['species'] for p in resolved['panels'] for a in p['atoms'] if a.get('kind') != 'center'}
    if species != set(sources):
        return [when + ': SMILES stereo references do not cover exactly the figure species']
    for sid, smiles in sources.items():
        try:
            is_ts = any((a.get('ts') or a.get('preserve_h')) and a.get('species') == sid for p in resolved['panels'] for a in p['atoms'])
            (want_a, want_b), refs, stubs = expected(sid, smiles, relaxed=is_ts)
            owners = {a['ref']: a['species'] for p in resolved['panels'] for a in p['atoms']}
            have_refs = {ref for ref in atoms if owners.get(ref) == sid}
            if set(refs) != have_refs:
                raise ValueError('saved atom correspondence differs from the SMILES')
            group = {ref: atoms[ref] for ref in refs}
            edges = [b for b in bonds if b['a'] in group and b['b'] in group]
            original_edges = {frozenset((b['a'], b['b'])): b for p in resolved['panels'] for b in p['bonds']}
            edges = [dict(b, order=original_edges[frozenset((b['a'], b['b']))]['haptic_order'])
                     if original_edges.get(frozenset((b['a'], b['b'])), {}).get('haptic') else b for b in edges]
            from iupac_features import METALS
            edges = [dict(b, coord=True) if original_edges.get(frozenset((b['a'], b['b'])), {}).get('style') == 'coord' or original_edges.get(frozenset((b['a'], b['b'])), {}).get('coord')
                     or group[b['a']]['el'] in METALS or group[b['b']]['el'] in METALS else b for b in edges]
            is_ts = is_ts or any(b.get('coord') for b in edges)
            # Dashed doubles are a display of the input single/double TS graph.
            # Their saved style and drawn order are checked independently.
            if is_ts:
                original = {frozenset((b['a'], b['b'])): b for p in resolved['panels'] for b in p['bonds']}
                edges = [dict(b, order=original[frozenset((b['a'], b['b']))]['order'])
                         if original.get(frozenset((b['a'], b['b'])), {}).get('style') == '1.5' else b for b in edges]
            got_a, got_b = perceived(group, edges, stubs, relaxed=is_ts)
            for ref in sorted(set(want_a) | set(got_a)):
                if want_a.get(ref) != got_a.get(ref):
                    out.append('%s: %s CIP %s, SMILES specifies %s' % (
                        when, ref, got_a.get(ref, 'unspecified'), want_a.get(ref, 'unspecified')))
            for pair, label in sorted(want_b.items()):
                if label != got_b.get(pair):
                    out.append('%s: %s=%s CIP %s, SMILES specifies %s' % (
                        when, pair[0], pair[1], got_b.get(pair, 'unspecified'), label))
        except (ValueError, KeyError, TypeError, RuntimeError) as exc:
            out.append('%s: %s stereochemistry could not be checked: %s' % (when, sid, exc))
    return out
