"""Optimization requires a global objective without requiring custom models."""

from copy import deepcopy
import json


PAYLOADS = {
    'Fragment_Based_Optimization': {'ref_mol': 'CCO', 'library_path': 'users/fixture/library.csv'},
    'Lead_Generation_Graph_GA': {'smiles': 'CCO', 'n_mols': 10, 'n_steps': 1},
    'Lead_Optimization_Mcts': {'hit_smile': 'CCO', 'n_mols': 10},
    'Lead_Generation_Mars_Plus': {'smiles': 'CCO', 'n_mols': 10, 'n_steps': 1},
}
MODEL = {'name': 'CaCo2 permeability', 'min_threshold': 0, 'max_threshold': 1}


def test_optimization_missing_or_empty_global_models_never_reaches_submission(monkeypatch):
    from plugins.boltzmann import tools

    monkeypatch.setattr(tools, 'require_authorized', lambda: None)

    def unexpected_submit(*args, **kwargs):
        raise AssertionError('Invalid model selection reached the service')

    monkeypatch.setattr(tools, 'submit_request', unexpected_submit)
    for job, base in PAYLOADS.items():
        for selection in (
            {}, {'global_models': []}, {'global_models': None},
            *({'global_models': [{**MODEL, field: ''}]} for field in ('min_threshold', 'max_threshold')),
        ):
            payload = {**base, **selection,
                       'custom_models': [{'id': 'fixture-custom', 'min_threshold': '', 'max_threshold': ''}]}
            original = deepcopy(payload)
            result = json.loads(tools.handle_boltzmann_submit(
                job_name=job, experiment_data=payload, allow_partial_validation=True,
            ))
            assert result['status'] == 'not_started', result
            assert result['stage'] == 'validation', result
            assert any('global_models' in error for error in result['validation']['errors'])
            assert payload == original


def test_optimization_global_models_submit_without_custom_models(tmp_path, monkeypatch):
    from plugins.boltzmann import preflight, tools

    monkeypatch.setattr(tools, 'require_authorized', lambda: None)
    monkeypatch.setattr(tools, '_get_api_key', lambda: 'fixture-key')
    monkeypatch.setattr(preflight, 'current_key', lambda: 'fixture-key')
    monkeypatch.setattr(tools.time, 'sleep', lambda _: None)
    sent = []

    def submit(payload, job, label, **kwargs):
        sent.append((job, deepcopy(payload)))
        return f'fixture-job-{len(sent)}'

    monkeypatch.setattr(tools, 'submit_request', submit)
    source = tmp_path / 'library.csv'
    source.write_text('SMILES\nCCO\nCC(=O)O\n')
    upload = preflight.validated_upload(
        str(source), 'Fragment_Based_Optimization', 'library_path', {}, True,
        lambda _: PAYLOADS['Fragment_Based_Optimization']['library_path'],
    )
    assert upload['status'] == 'uploaded', upload
    for job, base in PAYLOADS.items():
        for custom in ({}, {'custom_models': []}):
            payload = {**base, 'global_models': [deepcopy(MODEL)], **custom}
            original = deepcopy(payload)
            result = json.loads(tools.handle_boltzmann_submit(
                job_name=job, experiment_name=f'fixture-{job}-{len(sent)}', experiment_data=payload,
                # The CSV's optional RDKit check can require approval in the test environment.
                allow_partial_validation=job == 'Fragment_Based_Optimization',
            ))
            assert result['status'] == 'accepted', result
            assert not result['validation']['errors']
            if job != 'Fragment_Based_Optimization':
                assert not result['validation']['warnings']
            assert sent[-1] == (job, original)
            assert payload == original
