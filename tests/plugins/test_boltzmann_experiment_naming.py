"""Generated labels preserve explicit names and the submission admission boundary."""
import json

from plugins.boltzmann import tools
from plugins.boltzmann.contracts import ValidationReport


def test_submission_generates_labels_preserves_explicit_names_and_reports_unknown(monkeypatch):
    calls = []
    monkeypatch.setattr(tools, 'preflight_submission', lambda *args: ValidationReport())
    monkeypatch.setattr(tools, '_get_api_key', lambda: 'fixture-key')
    monkeypatch.setattr(tools.time, 'sleep', lambda *args: None)
    def submit(payload, job, name, **kwargs):
        calls.append((payload, job, name))
        return 'fixture-job-id' if len(calls) < 3 else {'error': 'fixture ambiguous response'}
    monkeypatch.setattr(tools, 'submit_request', submit)
    generated = json.loads(tools._handle_boltzmann_submit_inner(
        job_name='fixture_job', experiment_data={'input': 'fixture'}))
    explicit = json.loads(tools._handle_boltzmann_submit_inner(
        job_name='fixture_job', experiment_data={'input': 'fixture'}, experiment_name='Chosen label'))
    unknown = json.loads(tools._handle_boltzmann_submit_inner(
        job_name='fixture_job', experiment_data={'input': 'fixture'}))
    assert generated['status'] == explicit['status'] == 'accepted'
    assert generated['experiment_name'].startswith('fixture job - ')
    assert explicit['experiment_name'] == 'Chosen label'
    assert unknown['experiment_name'] != generated['experiment_name']
    assert unknown['error'] == 'fixture ambiguous response' and 'status' not in unknown
    assert len(calls) == 3
    assert [row[2] for row in calls] == [row['experiment_name'] for row in (generated, explicit, unknown)]
    long_names = [tools._generated_experiment_name('fixture_' * 40, {'project': 'x' * 100}) for _ in range(2)]
    assert all(len(name) <= 120 for name in long_names)
    assert long_names[0] != long_names[1]  # truncating a label must preserve its unique suffix


def test_generated_label_does_not_bypass_invalid_input_admission(monkeypatch):
    report = ValidationReport()
    report.errors.append('fixture invalid input')
    monkeypatch.setattr(tools, 'preflight_submission', lambda *args: report)
    def submit(*args, **kwargs):
        raise AssertionError('Invalid inputs must not reach submission')
    monkeypatch.setattr(tools, 'submit_request', submit)
    result = json.loads(tools._handle_boltzmann_submit_inner(
        job_name='fixture_job', experiment_data={'input': 'invalid'}))
    assert result['status'] == 'not_started'
    assert result['experiment_name'].startswith('fixture job - ')
    assert result['validation']['errors'] == report.errors
