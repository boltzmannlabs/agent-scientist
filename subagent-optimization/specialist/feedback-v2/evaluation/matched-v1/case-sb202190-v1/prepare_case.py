"""Offline proposed-case audit: no scientific services, profile edits or Git calls."""

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

from rdkit import Chem, rdBase
from rdkit.Chem import Crippen, Descriptors, QED, rdMolDescriptors


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
WORKSPACE = Path('/home/boltzmann13/.sci/profiles/ankith/workspace')
SOURCE_INCHI = (
    'InChI=1S/C20H14FN3O/c21-16-5-1-13(2-6-16)18-19(14-9-11-22-12-10-14)'
    '24-20(23-18)15-3-7-17(25)8-4-15/h1-12,25H,(H,23,24)'
)
EXPECTED_KEY = 'QHKYPYXTTXKZST-UHFFFAOYSA-N'
EXPECTED_FORM = 'Oc1ccc(-c2nc(-c3ccncc3)c(-c3ccc(F)cc3)[nH]2)cc1'
CONTROL_SMILES = 'C[S@](=O)c1ccc(-c2nc(-c3ccc(F)cc3)c(-c3ccncc3)[nH]2)cc1'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if rdBase.rdkitVersion != '2025.09.6':
        raise RuntimeError('Use /home/boltzmann13/drug_discovery_ml/ml_env/bin/python -B.')
    Chem.SetUseLegacyStereoPerception(True)
    Chem.SetAllowNontetrahedralChirality(True)
    mol = Chem.MolFromInchi(SOURCE_INCHI)
    assert mol is not None
    form = Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True)
    assert form == EXPECTED_FORM and Chem.MolToInchiKey(mol) == EXPECTED_KEY
    assert len(Chem.GetMolFrags(mol)) == 1

    # Consume identity columns only, never old property/score values.
    scans = []
    params = Chem.SmilesParserParams()
    params.parseName = False
    params.allowCXSMILES = False
    for path in sorted(WORKSPACE.glob('**/candidate_registry.csv')):
        if any('snapshot' in part or 'precollection' in part or 'pre_resume' in part
               or part == 'historical' for part in path.parts):
            continue
        before, unique, exact, key_matches, invalid = digest(path), set(), 0, 0, 0
        with path.open(newline='') as handle:
            reader = csv.DictReader(handle)
            field = next((f for f in ('canonical_identity', 'identity')
                          if f in (reader.fieldnames or [])), None)
            if field is None:
                raise ValueError(f'No identity field: {path}')
            for row in reader:
                value = row[field]
                if not value or value in unique:
                    continue
                unique.add(value)
                parsed = Chem.MolFromSmiles(value, params)
                if parsed is None:
                    invalid += 1
                    continue
                canonical = Chem.MolToSmiles(parsed, canonical=True, isomericSmiles=True)
                exact += canonical == form
                key_matches += Chem.MolToInchiKey(parsed) == EXPECTED_KEY
        assert digest(path) == before
        scans.append({'path': str(path), 'sha256': before, 'identity_column': field,
                      'distinct_nonempty_values': len(unique), 'unparseable_values': invalid,
                      'exact_form_matches': exact, 'standard_inchikey_matches': key_matches})
    if not scans:
        raise RuntimeError('No historical registries found.')

    target_dir = WORKSPACE / '08_results/target_conditioned_de_novo_design/p38_baseline_20261105T072302Z/inputs/derived'
    expected_assets = [
        (target_dir / 'receptor_observed_A.pdb', '54c71aeb21d1d528b9475a5d3f76014269ca5bb6de51f5ce07ced4c9a95f43e1'),
        (target_dir / 'control_native.sdf', 'db111b838854ff3658487d6c05b8e7f0dea8eaa682183ae6d4d7b3f00ebc9a34'),
        (REPO / 'research/library-alternatives/run-v1/mixed_reference.csv', '74305b33acad639b825b025956f7e91285fccdbc8a6f4671348b521ad7b073c0'),
        (REPO / 'research/library-alternatives/run-v1/hetero_rich_sources.csv', '5341ee432b4ab84c3e2c104fc2af11ccef26bcf812d260de4a8c29d6625fabd2'),
        (REPO / 'research/library-alternatives/run-v1/carbon_rich_sources.csv', '23fffbb53075321412eb35f39b24beb97c7881b4b74852f9622eb68d520cf9b6'),
    ]
    assets = []
    for path, expected in expected_assets:
        actual = digest(path)
        assert actual == expected, str(path)
        assets.append({'path': str(path), 'sha256': actual, 'bytes': path.stat().st_size})

    audit = {
        'status': 'LOCAL_PREPARATION_ONLY__NOT_FROZEN_FOR_EXECUTION',
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'rdkit_version': rdBase.rdkitVersion, 'script_sha256': digest(Path(__file__)),
        'source': {
            'name': 'SB202190', 'chebi_id': 'CHEBI:79090', 'pubchem_cid': 5169,
            'urls': ['https://www.ebi.ac.uk/chebi/CHEBI:79090',
                     'https://pubchem.ncbi.nlm.nih.gov/compound/sb-202190'],
            'inchi': SOURCE_INCHI,
            'retrieval_kind': 'Fields transcribed from primary web records, not archived raw downloads.',
            'raw_download_status': 'NOT_SAVED; direct shell PubChem API retrieval failed DNS resolution.',
        },
        'representation': {
            'method': 'RDKit MolFromInchi on ChEBI InChI, then canonical isomeric SMILES',
            'canonical_isomeric_smiles': form,
            'smiles_sha256_utf8_no_newline': hashlib.sha256(form.encode()).hexdigest(),
            'standard_inchikey': EXPECTED_KEY, 'formula': rdMolDescriptors.CalcMolFormula(mol),
            'components': len(Chem.GetMolFrags(mol)),
            'stereocenters': Chem.FindMolChiralCenters(mol, includeUnassigned=True),
            'limitation': 'InChI may merge tautomers. Freeze this explicit form; do not silently substitute or pool another tautomer. This is not a demonstrated preferred binding/protonation state.',
        },
        'local_descriptors': {
            'qed': QED.qed(mol), 'crippen_logp': Crippen.MolLogP(mol),
            'molecular_weight': Descriptors.MolWt(mol), 'heavy_atoms': mol.GetNumHeavyAtoms(),
            'rotatable_bonds': rdMolDescriptors.CalcNumRotatableBonds(mol),
            'tpsa': rdMolDescriptors.CalcTPSA(mol),
        },
        'historical_identity_scan': scans,
        'exact_matches_total': sum(r['exact_form_matches'] for r in scans),
        'standard_inchikey_matches_total': sum(r['standard_inchikey_matches'] for r in scans),
        'freshness_scope': 'Named local registries only; no global novelty/training-set/scaffold holdout claim.',
        'verified_reusable_assets': assets,
        'unmeasured': ['common PAMPA label', 'native Vina score', 'generated products', 'biological activity'],
        'remote_scientific_calls': 0, 'profile_changes': False,
    }
    (HERE / 'local_case_review.json').write_text(json.dumps(audit, indent=2, allow_nan=False) + '\n')
    with (HERE / 'proposed_references.csv').open('w', newline='') as handle:
        writer = csv.writer(handle)
        writer.writerow(['SMILES', 'NAMES'])
        writer.writerow([form, 'SB202190_lead'])
        writer.writerow([CONTROL_SMILES, 'SB2_control'])
    print(json.dumps({'rdkit': rdBase.rdkitVersion, 'form': form,
                      'qed': audit['local_descriptors']['qed'],
                      'crippen_logp': audit['local_descriptors']['crippen_logp'],
                      'registries': len(scans), 'exact_matches': audit['exact_matches_total'],
                      'standard_key_matches': audit['standard_inchikey_matches_total'],
                      'unparseable_historical_values': sum(r['unparseable_values'] for r in scans),
                      'assets_verified': len(assets), 'remote_scientific_calls': 0}))


if __name__ == '__main__':
    main()
