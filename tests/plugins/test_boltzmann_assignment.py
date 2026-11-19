"""Specialist scientific writes preserve task identity across branches and failures."""
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from dataclasses import replace
import json
from pathlib import Path
from threading import Barrier
import time
from types import SimpleNamespace

import pytest

from agent.specialist_assignment import evidence, prepare, record_artifacts, verified_artifacts
from agent.specialist_policy import SpecialistPolicy, specialist_scope
from plugins.boltzmann import preflight, tools
from plugins.boltzmann.receipt_store import ReceiptStore
from sci_cli.native_profile_creation import profile_scope


@pytest.mark.parametrize('outcome', ['accepted', 'unknown', 'exception'])
def test_real_upload_submit_handlers_reject_substitution_and_racing_replays_across_profiles(tmp_path, monkeypatch, outcome):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(tools, 'require_authorized', lambda: None)
    monkeypatch.setattr(tools, 'current_key', lambda: 'fixture-key')
    monkeypatch.setattr(preflight, 'current_key', lambda: 'fixture-key')
    monkeypatch.setattr(tools, 'time', SimpleNamespace(sleep=lambda _: None))
    uploads, submissions = [], []
    def upload(*args, **kwargs):
        uploads.append(args)
        return f'fixture/upload-{len(uploads)}.xyz'
    monkeypatch.setattr(tools, 'file_upload', upload)
    homes = [tmp_path / 'a', tmp_path / 'b']
    seen_assignments = []
    for home in (homes[0], homes[1], homes[0]):
        home.mkdir(exist_ok=True)
        with profile_scope(home):
            source = home / 'water.xyz'
            original = '3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n'
            source.write_text(original)
            parent = SimpleNamespace(_specialist_user_request='Use this exact water file once.', _specialist_snapshot={})
            prepare(parent, [{'specialist': 'worker'}], {'inputs': [str(source)],
                'tool_arguments': {'boltzmann_submit': {'job_name': 'Single_Point_Energy',
                    'experiment_data': {'charge': 0, 'method': 'B3LYP',
                                        'molecule_path': {'$input': str(source)} if outcome == 'accepted'
                                        else '<reference returned by the validated upload>'}}},
                'max_submissions': {'Single_Point_Energy': 1}})
            assignment = parent._specialist_assignment
            policy = SpecialistPolicy('worker', str(home), 'r', frozenset(), frozenset(), frozenset(),
                                      ('worker',), time.monotonic() + 60, assignment=assignment)
            incomplete = json.loads(assignment.contract)
            incomplete['tool_arguments'] = {}
            with specialist_scope(replace(policy, assignment=replace(assignment, contract=json.dumps(incomplete)))):
                before_upload = len(uploads)
                rejected = json.loads(tools.handle_boltzmann_upload(local_path=str(source), job_name='Single_Point_Energy',
                    input_field='molecule_path', allow_partial_validation=True))
                assert rejected['uploaded'] is False and len(uploads) == before_upload
            with specialist_scope(policy):
                start = len(uploads)
                source.write_text(original.replace('H 0 0 1', 'H 0 0 2'))
                blocked = json.loads(tools.handle_boltzmann_upload(local_path=str(source), job_name='Single_Point_Energy',
                    input_field='molecule_path', allow_partial_validation=True))
                assert blocked['status'] == 'not_started' and len(uploads) == start
                source.write_text(original)
                first = json.loads(tools.handle_boltzmann_upload(local_path=str(source), job_name='Single_Point_Energy',
                    input_field='molecule_path', allow_partial_validation=True))
                # Reproduce a pre-upgrade assignment: upload receipt exists, but
                # the old implementation never recorded future-argument bindings.
                location = home / 'subagent-runs' / f'assignment-{assignment.id}.json'
                stored = json.loads(location.read_text())
                stored['effects'] = {key: row for key, row in stored['effects'].items() if row.get('kind') != 'input_binding'}
                from utils import atomic_json_write
                atomic_json_write(location, stored, mode=0o600)
                restored = SimpleNamespace(_specialist_user_request='Recover the assignment.', _specialist_snapshot={})
                prepare(restored, [{'specialist': 'worker'}], {'resume': assignment.id})
                uploaded_count = len(uploads)
                with specialist_scope(replace(policy, assignment=restored._specialist_assignment)):
                    reused = json.loads(tools.handle_boltzmann_upload(local_path=str(source), job_name='Single_Point_Energy',
                        input_field='molecule_path', allow_partial_validation=True))
                assert reused['reused'] and reused['s3_path'] == first['s3_path'] and len(uploads) == uploaded_count
                objects = [reused, json.loads(tools.handle_boltzmann_upload(local_path=str(source), job_name='Single_Point_Energy',
                    input_field='molecule_path', allow_partial_validation=True))]
                assert all(row['status'] == 'uploaded' for row in objects)
                assert objects[0]['s3_path'] != objects[1]['s3_path']
                def payload(obj):
                    return {'task_name': 'water', 'molecule_path': obj['s3_path'], 'method': 'B3LYP',
                            'basis': 'def2-TZVP', 'charge': 0, 'spin_multiplicity': '1', 'dispersion': 'D3BJ'}
                wrong = payload(objects[0]); wrong['charge'] = 1
                from agent.specialist_policy import check_call
                with specialist_scope(replace(policy, tools=frozenset({'boltzmann_submit'}))):
                    assert check_call('boltzmann_submit', {'job_name': 'Single_Point_Energy', 'experiment_data': payload(objects[0])}) is None
                    assert check_call('boltzmann_submit', {'job_name': 'Single_Point_Energy', 'experiment_data': {
                        **payload(objects[0]), 'molecule_path': 'unrelated/file.xyz'}}) is not None
                assert json.loads(tools.handle_boltzmann_submit(job_name='Single_Point_Energy', experiment_data=wrong,
                    experiment_name='fixture', allow_partial_validation=True))['submitted'] is False
                before = len(submissions)
                def submit(*args, **kwargs):
                    # Both durable records exist BEFORE even this controlled external action.
                    effects = evidence(SimpleNamespace(_specialist_policy=policy))['recorded_effects']
                    attempts = [row for row in effects if row.get('kind') != 'input_binding']
                    assert len(attempts) == 1 and attempts[0]['state'] == 'unknown'
                    assert any(r['kind'] == 'submission' and r['state'] == 'unknown'
                               for r in ReceiptStore().inspect()['records'])
                    submissions.append(args)
                    if outcome == 'exception':
                        raise ConnectionError('controlled transport loss after possible acceptance')
                    return 'fixture-job' if outcome == 'accepted' else None
                monkeypatch.setattr(tools, 'submit_request', submit)
                barrier = Barrier(2)
                def run(obj):
                    barrier.wait(5)
                    return json.loads(tools.handle_boltzmann_submit(job_name='Single_Point_Energy', experiment_data=payload(obj),
                        experiment_name='different-label-' + obj['receipt_id'], allow_partial_validation=True))
                with ThreadPoolExecutor(2) as pool:
                    futures = [pool.submit(copy_context().run, run, obj) for obj in objects]
                    results = [future.result(10) for future in futures]
                assert len(submissions) == before + 1
                assert sum(row['status'] == 'not_started' for row in results) == 1
                assert any(row['status'] == ('accepted' if outcome == 'accepted' else 'unknown') for row in results)
                # A restart-style fresh store still rejects the reserved work.
                again = json.loads(tools.handle_boltzmann_submit(job_name='Single_Point_Energy', experiment_data=payload(objects[0]),
                    experiment_name='another-name', allow_partial_validation=True))
                assert again['status'] == 'not_started' and len(submissions) == before + 1
                restored = SimpleNamespace(_specialist_user_request='Recover the previous assignment.', _specialist_snapshot={})
                prepare(restored, [{'specialist': 'worker'}], {'resume': assignment.id})
                assert restored._specialist_assignment == assignment
                with specialist_scope(replace(policy, assignment=restored._specialist_assignment)):
                    resumed = json.loads(tools.handle_boltzmann_submit(job_name='Single_Point_Energy',
                        experiment_data=payload(objects[0]), experiment_name='resumed', allow_partial_validation=True))
                    assert resumed['status'] == 'not_started' and len(submissions) == before + 1
                facts = evidence(SimpleNamespace(_specialist_policy=policy))
                assert facts['assignment_id'] == assignment.id
                attempts = [row for row in facts['recorded_effects'] if row.get('kind') != 'input_binding']
                assert len(attempts) == 1
                assert attempts[0]['doc_id'] == ('fixture-job' if outcome == 'accepted' else None)
                seen_assignments.append(assignment.id)
                assert all(row.get('assignment_id') not in seen_assignments[:-1]
                           for row in ReceiptStore().inspect()['records'] if row.get('assignment_id') and home == homes[1])
    assert len(submissions) == 3


def test_effect_evidence_survives_worker_timeout_and_only_exact_outputs_can_be_handed_off(tmp_path, monkeypatch):
    from agent.specialist_runs import record, history
    from tools.delegate_tool_dispatch import _Batch
    from agent.specialist_delivery import reports_from_results, stage_sync
    from plugins.boltzmann.assignment_evidence import save
    from sci_constants import get_sci_home
    home = get_sci_home()
    parent = SimpleNamespace(_specialist_user_request='Run and audit the returned artifact.', _specialist_snapshot={},
                             _current_turn_id='turn')
    prepare(parent, [{'specialist': 'lead'}])
    policy = SpecialistPolicy('worker', str(home), 'r', frozenset(), frozenset(), frozenset(), ('worker',),
                              time.monotonic() + 60, assignment=parent._specialist_assignment)
    child = SimpleNamespace(_specialist_policy=policy, _subagent_id='sa-0-fixture')
    record(child, 'Run fixture')
    output = tmp_path / 'actual-output.bin'; output.write_bytes(b'\x00fixture\xff')
    stale = tmp_path / 'old-output.bin'; stale.write_bytes(output.read_bytes())
    with specialist_scope(policy):
        save('attempt', required=True, job_name='fixture', state='accepted', doc_id='known-job')
        record_artifacts([str(output)])
        assert verified_artifacts(policy.assignment, [str(output)]) == (str(output),)
        with pytest.raises(ValueError, match='not a frozen input or recorded output'):
            verified_artifacts(policy.assignment, [str(stale)])
        output.write_bytes(b'changed')
        with pytest.raises(ValueError, match='bytes changed'):
            verified_artifacts(policy.assignment, [str(output)])
    monkeypatch.setattr('tools.delegate_tool._run_single_child', lambda **kw: {
        'status': 'timeout', 'summary': None, 'error': 'Controlled timeout', 'task_index': 0})
    batch = _Batch([], [], parent, {}, None, 'leaf', 1, None, [], [], '', '', None, None, False, 0)
    result = batch.run_child(0, {'goal': 'Run fixture'}, child)
    assert result['recorded_effects'][0]['doc_id'] == 'known-job'
    assert history()[0]['result']['recorded_effects'] == result['recorded_effects']
    assert 'known-job' in reports_from_results([result])
    stage_sync(parent, [result])
    assert parent._specialist_intermediate_turn == ('turn',)
    # A science execution cannot substitute a foreign job or a historical download URL.
    from plugins.boltzmann.assignment_evidence import download_origin, observe_outputs, tracked_job
    contract = json.dumps({'inputs': {}, 'tool_arguments': {}, 'max_submissions': {'fixture': 1}})
    scoped = replace(policy, assignment=replace(policy.assignment, contract=contract))
    with specialist_scope(scoped):
        assert tracked_job('fixture', 'known-job')
        assert not tracked_job('fixture', 'historical-job')
        with pytest.raises(RuntimeError, match='not an output'):
            download_origin('https://fixture.invalid/old.bin?secret=not-saved')
        observe_outputs('fixture', 'known-job', {'OutputData': {'url': 'https://fixture.invalid/new.bin?signature=secret'}})
        with pytest.raises(RuntimeError, match='not an output'):
            download_origin('https://fixture.invalid/new.bin?signature=rotated')
        assert download_origin('https://fixture.invalid/new.bin?signature=secret') == {
            'job_name': 'fixture', 'doc_id': 'known-job'}
        contents = (home / 'subagent-runs' / f'assignment-{policy.assignment.id}.json').read_text()
        assert 'signature' not in contents and 'secret' not in contents
    # Native writes can prepare downstream inputs, but only after a confirmed prior job.
    from agent.specialist_assignment import check_input, _digest
    import model_tools  # noqa: F401 -- real native-tool registration
    from tools.registry import registry
    generated = tmp_path / 'derived.csv'
    with specialist_scope(replace(scoped, tools=frozenset({'write_file'}))):
        written = json.loads(registry.dispatch('write_file', {'path': str(generated), 'content': 'value\n42\n'}))
        assert not written.get('error'), written
        assert check_input(generated, _digest(generated)) is not None
        save('attempt', required=True, job_name='fixture', state='terminal', doc_id='known-job', terminal_confirmed=True)
        assert check_input(generated, _digest(generated)) is None
        # A confirmed stage's recorded output can resolve the next stage's
        # future-input marker too; no pre-existing file or guessed URL is needed.
        from agent.specialist_assignment import check_arguments
        from agent.specialist_assignment_bindings import record_input_binding
        downstream = json.dumps({'inputs': {}, 'max_submissions': {'next': 1}, 'tool_arguments': {
            'fixture_submit': {'job_name': 'next', 'data': {'$input': str(generated)}}}})
        with specialist_scope(replace(scoped, assignment=replace(scoped.assignment, contract=downstream))):
            record_input_binding('fixture_submit', ('data',), 'fixture/derived.csv',
                                 sha256=_digest(generated), selectors={'job_name': 'next'})
            assert check_arguments('fixture_submit', {'job_name': 'next', 'data': 'fixture/derived.csv'}) is None
        # A native report can evolve without invalidating the assignment's latest
        # handoff. Raw scientific downloads remain immutable.
        from agent.specialist_assignment import artifact_snapshot
        from agent.specialist_inputs import check_read
        review = replace(scoped, tools=frozenset({'read_file'}), artifact_hashes=artifact_snapshot([str(generated)]))
        updated = json.loads(registry.dispatch('write_file', {'path': str(generated), 'content': 'value\n43\n'}))
        assert not updated.get('assignment_evidence_warning'), updated
        assert verified_artifacts(scoped.assignment, [str(generated)]) == (str(generated),)
        assert 'changed after dispatch' in check_read(review, 'read_file', {'path': str(generated)})
        current = next(row for row in evidence(child)['recorded_effects'] if row.get('path') == str(generated))
        assert current['sha256'] == _digest(generated) and current['previous_sha256']
        # A subsequent unrecorded write is still rejected.
        generated.write_text('tampered')
        with pytest.raises(ValueError, match='bytes changed'):
            verified_artifacts(scoped.assignment, [str(generated)])
