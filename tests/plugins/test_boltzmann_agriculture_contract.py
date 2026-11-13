"""Enabled agriculture contract preserves input modes and profile upload ownership."""

from copy import deepcopy
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2] / 'plugins/boltzmann'
REFS = ROOT / 'skills/boltzmann-tools/references'


def distributed_store(tmp_path):
    from plugins.boltzmann.contracts import ContractStore

    refs = tmp_path / 'distributed-references'
    refs.mkdir()
    for filename in ('tool-contracts.v1.json', 'file-input-contracts.v1.json', 'input-limits.v1.json'):
        shutil.copy2(REFS / filename, refs / filename)
    return ContractStore(refs)


def test_agriculture_enabled_contract_enforces_input_modes_without_exposing_runtime_identity(tmp_path):
    from plugins.boltzmann.contracts import ContractStore
    from sci_cli.science_catalog_view import catalog_rows

    store = distributed_store(tmp_path)
    job = 'global_agriculture_properties'
    payload = {'smiles': 'CCO', 'properties': ['water_half_life', 'ready_biodegradability'], 'input_csv': ''}
    original = deepcopy(payload)
    report = store.validate_payload(job, payload)
    assert not report.errors and not report.warnings
    assert payload == original
    for unused in ({}, {'smiles': ''}):
        assert not store.validate_payload(job, {'input_csv': 'users/fixture/input.csv',
                                               'properties': 'all', **unused}).errors
    for property_id in store.tool(job)['request_schema']['properties']['properties']['anyOf'][0]['enum']:
        assert not store.validate_payload(job, {'smiles': 'CCO', 'input_csv': '', 'properties': property_id}).errors
    for payload in (
        {}, {'properties': 'all'}, {'smiles': [], 'properties': 'all'},
        {'smiles': None, 'properties': 'all'}, {'smiles': '', 'properties': 'all'},
        {'smiles': 'CCO', 'input_csv': 'users/fixture/input.csv', 'properties': 'all'},
        {'smiles': 'CCO', 'properties': 'all'},
        {'smiles': 'CCO', 'input_csv': None, 'properties': 'all'},
        {'smiles': ['CCO', 'CC(=O)O'], 'input_csv': '', 'properties': 'all'},
        {'smiles': 'CCO', 'properties': []}, {'smiles': 'CCO', 'properties': ['all']},
        {'smiles': 'CCO', 'properties': ['invented']},
        *({'smiles': 'CCO', 'properties': 'all', key: 'invented'}
          for key in ('experiment_id', 'user_id', 'tokenid')),
    ):
        assert store.validate_payload(job, payload).errors, payload
    for bad in ([], ['all'], ['invented']):
        assert store.validate_payload(job, {**original, 'properties': bad}).errors
    for key in ('experiment_id', 'user_id', 'tokenid'):
        assert store.validate_payload(job, {**original, key: 'invented'}).errors
    assert store.diagnostic_collection(job) == 'Agriculture_Properties'
    assert ContractStore(REFS).tool(job) == store.tool(job)
    catalog = json.loads((REFS / 'tool-contracts.v1.json').read_text())
    assert not any(x.get('job_name') == job for x in catalog['unavailable_entries'])
    assert store.tool(job)['backend_metadata']['identifier_injection_verified'] is False
    rows = catalog_rows(REFS / 'tool-contracts.v1.json', query='Agriculture Properties')
    assert rows and all(row['status'] == 'active' for row in rows)
    assert all(row['domain'] == 'Small Molecule Design' and row['module'] == 'QSPR Modelling' for row in rows)


def test_agriculture_csv_receipts_bind_checked_bytes_and_profile(tmp_path, monkeypatch):
    from plugins.boltzmann import preflight

    store = distributed_store(tmp_path)
    monkeypatch.setattr(preflight, 'ContractStore', lambda: store)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.mkdir(); b.mkdir()
    source = tmp_path / 'molecules.csv'
    contents = 'ID,SMILES,NOTE\nethanol,CCO,fixture\nacetic-acid,CC(=O)O,fixture\n'
    source.write_text(contents)
    uploads = []

    def upload(path):
        uploads.append(Path(path).read_text())
        return 'users/fixture/molecules.csv'

    job = 'global_agriculture_properties'
    monkeypatch.setenv('SCI_HOME', str(a))
    result = preflight.validated_upload(str(source), job, 'input_csv', {'properties': 'all'}, True, upload)
    assert result['status'] == 'uploaded', result
    assert uploads == [contents] and source.read_text() == contents
    payload = {'input_csv': result['s3_path'], 'properties': 'all', 'smiles': ''}
    for home, owns_receipt in ((a, True), (b, False), (a, True)):
        monkeypatch.setenv('SCI_HOME', str(home))
        report = preflight.preflight_submission(job, payload)
        assert not report.errors, report.errors
        assert bool(report.upload_receipt_ids) == owns_receipt
        assert any('no current-profile validation receipt' in x for x in report.warnings) != owns_receipt
    source.write_text('smiles\nCCO\n')
    rejected = preflight.validated_upload(str(source), job, 'input_csv', {'properties': 'all'}, True, upload)
    assert rejected['status'] == 'not_started'
    assert len(uploads) == 1
