"""Persisted recommendations and selective deletion share a single draft list."""
import json
import importlib.util
from pathlib import Path
import subprocess
import sys
import time

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'skills/science/agri-models-and-design/scripts/scenario_draft.py'


def call(path, action, payload=None):
    result = subprocess.run([sys.executable, str(SCRIPT), action, '--draft', str(path)],
                            input=json.dumps(payload or {}), capture_output=True, text=True,
                            timeout=10)
    return result.returncode, json.loads(result.stdout)


def draft(path):
    status, value = call(path, 'create', {'project_id': 'P1', 'mode': 'design', 'scenarios': [
        {'id': 'S1', 'name': 'Pumping', 'model': 'rheology', 'recipe_ids': ['A', 'B']},
        {'id': 'S2', 'name': 'Settling', 'model': 'suspension', 'recipe_ids': ['A', 'B']}]})
    assert status == 0, value
    return value


def test_request_file_runs_full_draft_lifecycle_without_interpreter_pipeline(tmp_path):
    path = tmp_path / 'draft.json'
    request = tmp_path / 'request.json'
    def file_call(action, payload):
        request.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
        result = subprocess.run([sys.executable, str(SCRIPT), action, '--draft', str(path),
                                 '--request-file', str(request)], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, result.stdout + result.stderr
        return json.loads(result.stdout)
    initial = file_call('create', {'project_id': 'P1', 'mode': 'design', 'scenarios': [
        {'id': 'S1', 'name': 'Évaluation A', 'model': 'rheology', 'recipe_ids': ['A']},
        {'id': 'S2', 'name': 'Settling', 'model': 'suspension', 'recipe_ids': ['A']}]})
    edited = file_call('upsert', {'expected_revision': initial['revision'],
        'scenario': {**initial['scenarios'][0], 'name': 'Edited flow'}})
    deleted = file_call('delete', {'expected_revision': edited['revision'], 'scenario_ids': ['S1']})
    assert [r['id'] for r in deleted['scenarios']] == ['S2']
    restored = file_call('undo', {'expected_revision': deleted['revision']})
    assert restored['scenarios'] == edited['scenarios']
    assert call(path, 'list')[1] == restored


@pytest.mark.parametrize('body', ['{broken', '[]', 'null'])
def test_invalid_request_file_cannot_change_an_existing_draft(tmp_path, body):
    path = tmp_path / 'draft.json'
    draft(path)
    before = path.read_bytes()
    request = tmp_path / 'request.json'
    request.write_text(body, encoding='utf-8')
    result = subprocess.run([sys.executable, str(SCRIPT), 'delete', '--draft', str(path),
                             '--request-file', str(request)], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=10)
    assert result.returncode == 1 and json.loads(result.stdout)['status'] == 'error'
    assert path.read_bytes() == before


def test_recommended_rows_exist_and_delete_only_selected_scenario(tmp_path):
    path = tmp_path / 'draft.json'
    original = draft(path)
    assert [s['id'] for s in original['scenarios']] == ['S1', 'S2']
    assert all(s['status'] == 'review_required' for s in original['scenarios'])
    status, after = call(path, 'delete', {'expected_revision': original['revision'], 'scenario_ids': ['S2']})
    assert status == 0
    assert [s['id'] for s in after['scenarios']] == ['S1']
    assert after['actions'] == original['actions']
    assert call(path, 'list')[1]['scenarios'] == after['scenarios']


@pytest.mark.parametrize('selection,revision', [(['missing'], 1), (['S1'], 0), ([], 1)])
def test_invalid_or_stale_deletion_preserves_the_saved_draft(tmp_path, selection, revision):
    path = tmp_path / 'draft.json'
    draft(path)
    before = path.read_bytes()
    status, result = call(path, 'delete', {'scenario_ids': selection, 'expected_revision': revision})
    assert status == 1 and result['status'] == 'error'
    assert path.read_bytes() == before


def test_empty_menu_undo_and_no_recreation_of_deleted_rows(tmp_path):
    path = tmp_path / 'draft.json'
    original = draft(path)
    status, empty = call(path, 'delete', {'expected_revision': original['revision'], 'scenario_ids': 'all', 'confirm_all': True})
    assert status == 0 and empty['scenarios'] == [] and not empty['can_run']
    assert empty['actions'] == original['actions']
    assert call(path, 'create', {'project_id': 'P1', 'mode': 'design', 'scenarios': []})[0] == 1
    status, restored = call(path, 'undo', {'expected_revision': empty['revision']})
    assert status == 0
    assert {s['id'] for s in restored['scenarios']} == {'S1', 'S2'}


def test_new_scenarios_do_not_reuse_deleted_labels(tmp_path):
    path = tmp_path / 'draft.json'
    original = draft(path)
    _, empty = call(path, 'delete', {'expected_revision': original['revision'], 'scenario_ids': 'all', 'confirm_all': True})
    status, after = call(path, 'upsert', {'expected_revision': empty['revision'],
        'scenario': {'name': 'New flow', 'model': 'rheology', 'recipe_ids': ['A'], 'status': 'review_required'}})
    assert status == 0 and [r['id'] for r in after['scenarios']] == ['S3']


@pytest.mark.parametrize('selection,confirmation', [
    ('all', None), ('all', False), ('all', 'true'), ('all', 1),
    (['S1', 'S2'], None), ([], True), ('[]', True), (None, True)])
def test_empty_selection_or_unconfirmed_bulk_clear_cannot_delete_anything(tmp_path, selection, confirmation):
    path = tmp_path / 'draft.json'
    original = draft(path)
    before = path.read_bytes()
    status, result = call(path, 'delete', {'expected_revision': original['revision'],
        'scenario_ids': selection, 'confirm_all': confirmation})
    assert status == 1 and result['status'] == 'error'
    assert path.read_bytes() == before


def test_delete_templates_are_single_selector_and_keep_first_bulk_confirmation(tmp_path):
    value = draft(tmp_path / 'draft.json')
    selector = value['delete_selector']
    assert selector['multi_select'] is False
    assert selector['choices'][0].startswith('S1')
    assert selector['choices'][0] != 'All scenarios'
    assert 'questions' not in selector
    assert value['bulk_delete_confirmation']['choices'][0] == 'Keep scenarios'


def test_three_scenarios_have_direct_enter_choices_without_checkboxes(tmp_path):
    rows = [{'id': f'S{i}', 'name': f'Scenario {i}', 'model': 'rheology', 'recipe_ids': ['A']}
            for i in range(1, 4)]
    _, value = call(tmp_path / 'draft.json', 'create', {'project_id': 'P1', 'mode': 'design', 'scenarios': rows})
    selector = value['delete_selector']
    assert selector['multi_select'] is False
    assert [choice.split(' — ')[0] for choice in selector['choices'][:3]] == [r['id'] for r in rows]
    assert selector['choices'][3] == 'More options'
    assert value['delete_more_selector']['choices'] == ['Choose multiple scenarios', 'All scenarios', 'Previous']
    assert value['delete_more_selector']['multi_select'] is False


def test_long_lists_and_multiple_deletion_use_typed_ids_not_checkboxes(tmp_path):
    rows = [{'id': f'S{i}', 'name': f'Scenario {i}', 'model': 'rheology', 'recipe_ids': ['A']}
            for i in range(1, 9)]
    _, value = call(tmp_path / 'draft.json', 'create', {'project_id': 'P1', 'mode': 'design', 'scenarios': rows})
    assert value['delete_selector']['choices'] == ['Choose a scenario', 'Choose multiple scenarios', 'All scenarios', 'Previous']
    assert value['delete_selector']['multi_select'] is False
    assert value['delete_id_selector']['multi_select'] is False
    assert not value['delete_id_selector'].get('choices')


def test_selecting_the_last_remaining_scenario_is_not_a_bulk_clear(tmp_path):
    path = tmp_path / 'draft.json'
    value = draft(path)
    _, value = call(path, 'delete', {'expected_revision': value['revision'], 'scenario_ids': ['S1']})
    status, value = call(path, 'delete', {'expected_revision': value['revision'], 'scenario_ids': ['S2']})
    assert status == 0 and value['scenarios'] == []
    assert value['delete_selector'] is None


@pytest.mark.parametrize('count', [0, 1, 2, 3, 4, 8, 21])
def test_menu_sizes_never_truncate_or_recommend_all(tmp_path, count):
    path = tmp_path / 'draft.json'
    rows = [{'id': f'S{i}', 'name': f'Scenario {i}', 'model': 'rheology', 'recipe_ids': ['A']}
            for i in range(1, count + 1)]
    status, value = call(path, 'create', {'project_id': 'P1', 'mode': 'design', 'scenarios': rows})
    assert status == 0
    assert len(value['scenarios']) == count
    assert len(value['actions']) == 4
    if count:
        selector = value['delete_selector']
        assert len(selector['choices']) <= 4
        assert selector['choices'][0] != 'All scenarios'
        assert value['bulk_delete_confirmation']['choices'][0] == 'Keep scenarios'
    else:
        assert value['delete_selector'] is None and value['can_run'] is False


@pytest.mark.parametrize('mask', range(1, 16))
def test_every_nonempty_subset_of_four_deletes_exactly_the_selected_rows(tmp_path, mask):
    path = tmp_path / 'draft.json'
    rows = [{'id': f'S{i}', 'name': f'Scenario {i}', 'model': 'rheology', 'recipe_ids': ['A', 'B'],
             'shared_inputs': {'pipe_length_m': i}, 'recipe_inputs': {'A': {'yield_stress_pa': i}}}
            for i in range(1, 5)]
    _, value = call(path, 'create', {'project_id': 'P1', 'mode': 'design', 'scenarios': rows})
    selected = [f'S{i + 1}' for i in range(4) if mask & (1 << i)]
    status, after = call(path, 'delete', {'expected_revision': value['revision'],
        'scenario_ids': selected, 'confirm_all': len(selected) == 4})
    assert status == 0
    assert after['scenarios'] == [r for r in value['scenarios'] if r['id'] not in selected]
    assert after['revision'] == value['revision'] + 1
    assert json.loads(path.read_text())['last_deleted'] == [r for r in value['scenarios'] if r['id'] in selected]


@pytest.mark.parametrize('payload', [None, [], 'bad', 3, True])
def test_malformed_payload_returns_structured_error_without_creating_a_draft(tmp_path, payload):
    path = tmp_path / 'draft.json'
    result = subprocess.run([sys.executable, str(SCRIPT), 'create', '--draft', str(path)],
                            input=json.dumps(payload), capture_output=True, text=True, timeout=10)
    assert result.returncode == 1
    assert json.loads(result.stdout)['status'] == 'error'
    assert 'Traceback' not in result.stderr
    assert not path.exists()


@pytest.mark.parametrize('revision', [True, False, 1.0, '1', None])
def test_revision_requires_an_integer_not_a_coercible_value(tmp_path, revision):
    path = tmp_path / 'draft.json'
    draft(path)
    before = path.read_bytes()
    status, _ = call(path, 'delete', {'expected_revision': revision, 'scenario_ids': ['S1']})
    assert status == 1 and path.read_bytes() == before


def test_edit_preserves_order_other_fields_and_survives_process_restart(tmp_path):
    path = tmp_path / 'draft.json'
    initial = draft(path)
    edited = dict(initial['scenarios'][0], name='Edited pumping', shared_inputs={'pipe_length_m': 7})
    status, after = call(path, 'upsert', {'expected_revision': initial['revision'], 'scenario': edited})
    assert status == 0
    assert [r['id'] for r in after['scenarios']] == ['S1', 'S2']
    assert after['scenarios'][1] == initial['scenarios'][1]
    assert call(path, 'list')[1] == after


def test_undo_restores_original_display_order_and_values(tmp_path):
    path = tmp_path / 'draft.json'
    initial = draft(path)
    _, after = call(path, 'delete', {'expected_revision': initial['revision'], 'scenario_ids': ['S1']})
    status, restored = call(path, 'undo', {'expected_revision': after['revision']})
    assert status == 0 and restored['scenarios'] == initial['scenarios']


def test_duplicate_targets_remove_once_and_never_expand_to_all(tmp_path):
    path = tmp_path / 'draft.json'
    initial = draft(path)
    status, after = call(path, 'delete', {'expected_revision': initial['revision'], 'scenario_ids': ['S1', 'S1']})
    assert status == 0 and [r['id'] for r in after['scenarios']] == ['S2']


def test_corrupt_request_json_leaves_existing_draft_unchanged(tmp_path):
    path = tmp_path / 'draft.json'
    draft(path)
    before = path.read_bytes()
    result = subprocess.run([sys.executable, str(SCRIPT), 'delete', '--draft', str(path)],
                            input='{bad', text=True, capture_output=True, timeout=10)
    assert result.returncode == 1 and json.loads(result.stdout)['status'] == 'error'
    assert path.read_bytes() == before


def test_undo_after_adding_another_scenario_retains_new_content(tmp_path):
    path = tmp_path / 'draft.json'
    initial = draft(path)
    _, deleted = call(path, 'delete', {'expected_revision': initial['revision'], 'scenario_ids': ['S1']})
    _, added = call(path, 'upsert', {'expected_revision': deleted['revision'],
        'scenario': {'name': 'Added', 'model': 'rheology', 'recipe_ids': ['B']}})
    status, restored = call(path, 'undo', {'expected_revision': added['revision']})
    assert status == 0 and [r['id'] for r in restored['scenarios']] == ['S1', 'S2', 'S3']


def test_two_modes_and_projects_keep_separate_draft_state(tmp_path):
    first = tmp_path / 'design.json'
    second = tmp_path / 'physics.json'
    original = draft(first)
    status, _ = call(second, 'create', {'project_id': 'P2', 'mode': 'ai_physics', 'scenarios': [
        {'id': 'S1', 'name': 'Search', 'model': 'rheology', 'recipe_ids': ['C']}]})
    assert status == 0
    other_bytes = second.read_bytes()
    call(first, 'delete', {'expected_revision': original['revision'], 'scenario_ids': ['S1']})
    assert second.read_bytes() == other_bytes


@pytest.mark.parametrize('invalid_id', [None, 0, [], 'bad', 'S0'])
def test_bad_edit_identifier_is_not_reinterpreted_as_add(tmp_path, invalid_id):
    path = tmp_path / 'draft.json'
    original = draft(path)
    before = path.read_bytes()
    status, _ = call(path, 'upsert', {'expected_revision': original['revision'],
        'scenario': {'id': invalid_id, 'name': 'Bad', 'model': 'rheology', 'recipe_ids': ['A']}})
    assert status == 1 and path.read_bytes() == before


def test_failed_atomic_replace_keeps_previous_draft_and_removes_temp_file(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('scenario_draft_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / 'draft.json'
    draft(path)
    before = path.read_bytes()
    def fail_replace(*args):
        raise OSError('Simulated storage failure')
    monkeypatch.setattr(module.os, 'replace', fail_replace)
    with pytest.raises(OSError, match='storage failure'):
        module.save(path, {'replacement': True})
    assert path.read_bytes() == before
    assert not list(tmp_path.glob('.scenario-*'))


def test_busy_lock_times_out_and_exception_releases_it(tmp_path):
    spec = importlib.util.spec_from_file_location('scenario_draft_lock_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    path = tmp_path / 'draft.json'
    with pytest.raises(RuntimeError, match='Interrupted writer'):
        with module.draft_lock(path):
            with pytest.raises(OSError, match='Draft is busy'):
                with module.draft_lock(path, timeout=0):
                    pytest.fail('Two writers acquired the same lock')
            raise RuntimeError('Interrupted writer')
    with module.draft_lock(path, timeout=0):
        pass


def test_concurrent_edits_with_the_same_revision_cannot_overwrite_each_other(tmp_path):
    path = tmp_path / 'draft.json'
    draft(path)
    marker, release = tmp_path / 'paused', tmp_path / 'release'
    # Pause the first writer after it reads/checks revision 1. A second process
    # must wait, then reject revision 1 rather than overwrite a concurrent edit.
    code = f'''
import importlib.util, io, json, sys, time
from pathlib import Path
spec = importlib.util.spec_from_file_location('draft', {str(SCRIPT)!r})
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
original = m.save
def pause(path, state):
    Path({str(marker)!r}).touch()
    while not Path({str(release)!r}).exists(): time.sleep(.01)
    original(path, state)
m.save = pause
sys.argv = ['draft', 'delete', '--draft', {str(path)!r}]
sys.stdin = io.StringIO(json.dumps({{'expected_revision': 1, 'scenario_ids': ['S1']}}))
raise SystemExit(m.main())
'''
    first = subprocess.Popen([sys.executable, '-c', code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    second = None
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert marker.exists(), 'First writer did not reach its save'
        second = subprocess.Popen([sys.executable, str(SCRIPT), 'delete', '--draft', str(path)],
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        second.stdin.write(json.dumps({'expected_revision': 1, 'scenario_ids': ['S2']}))
        second.stdin.close(); second.stdin = None
        deadline = time.monotonic() + .5
        while second.poll() is None and time.monotonic() < deadline:
            time.sleep(.01)
    finally:
        release.touch()
        first_output, first_error = first.communicate(timeout=10)
        if second is not None:
            second_output, second_error = second.communicate(timeout=10)
    assert first.returncode == 0, first_error + first_output
    assert second.returncode == 1, second_error + second_output
    assert json.loads(second_output)['status'] == 'error'
    assert [r['id'] for r in call(path, 'list')[1]['scenarios']] == ['S2']


@pytest.mark.parametrize('answer,expected', [('All eligible recipes',['R-a','R-b']),('1',['R-a']),('2',['R-b']),('1, 2',['R-a','R-b']),('R-b R-a',['R-b','R-a'])])
def test_recipe_selection_resolves_exact_ids_without_changing_draft(tmp_path,answer,expected):
    path=tmp_path/'draft.json';original=draft(path);before=path.read_bytes()
    payload={'recipes':[{'recipe_id':'R-a','name':'A'},{'recipe_id':'R-b','name':'B'}],'answer':answer,'outcome':'submitted'}
    status,value=call(path,'recipes',payload)
    assert status==0 and value['status']=='selected'
    assert value['recipe_ids']==expected
    assert path.read_bytes()==before
    status,added=call(path,'upsert',{'expected_revision':original['revision'],
        'scenario':{'name':'Release','model':'kinetics','recipe_ids':value['recipe_ids']}})
    assert status==0 and added['scenarios'][-1]['recipe_ids']==expected
    assert added['scenarios'][:-1]==original['scenarios']


@pytest.mark.parametrize('answer,outcome,status', [([], 'submitted','needs_input'),('[]','submitted','needs_input'),(None,'submitted','needs_input'),('All eligible recipes','cancelled','cancelled'),('All eligible recipes','timed_out','needs_input'),('Previous','submitted','previous')])
def test_empty_or_unconfirmed_recipe_selection_does_not_add_or_drop_scenarios(tmp_path,answer,outcome,status):
    path=tmp_path/'draft.json';draft(path);before=path.read_bytes()
    code,result=call(path,'recipes',{'recipes':[{'recipe_id':'R-a','name':'A'}],'answer':answer,'outcome':outcome})
    assert code==0 and result['status']==status and result['recipe_ids']==[]
    assert path.read_bytes()==before


def test_real_cli_enter_on_all_recipes_reaches_helper_and_saved_add(tmp_path):
    from queue import Queue
    from cli import SciCLI
    from tools.clarify_tool import clarify_tool
    path=tmp_path/'draft.json';original=draft(path)
    recipes=[{'recipe_id':'R-a','name':'A'},{'recipe_id':'R-b','name':'B'}]
    _,options=call(path,'recipes',{'recipes':recipes})
    def callback(entries):
        entry=entries[0];assert entry['multi_select'] is False
        view=SciCLI.__new__(SciCLI);view._persist_prompt_summary=lambda *a:None
        state={'questions':entries,'active':0,'answers':{},'choices':entry['choices'],
               'selected':0,'multi_select':False,'response_queue':Queue()}
        view._clarify_batch_enter(state)
        return {'answers':state['response_queue'].get_nowait(),'outcome':'submitted'}
    reply=json.loads(clarify_tool([options['selector']],callback=callback))
    answer=reply['responses'][0]['user_response']
    _,selected=call(path,'recipes',{'recipes':recipes,'answer':answer,'outcome':reply['outcome']})
    assert selected['recipe_ids']==['R-a','R-b']
    _,added=call(path,'upsert',{'expected_revision':original['revision'],
        'scenario':{'name':'Release','model':'kinetics','recipe_ids':selected['recipe_ids']}})
    assert call(path,'list')[1]['scenarios'][-1]['recipe_ids']==['R-a','R-b']
    assert added['actions']==original['actions']


@pytest.mark.parametrize('count', [1,2,3,8])
def test_recipe_picker_supports_large_catalogues_and_rejects_unknown_ids(tmp_path,count):
    path=tmp_path/'draft.json';draft(path);before=path.read_bytes()
    recipes=[{'recipe_id':f'R-{i}','name':'Same display name'} for i in range(count)]
    _,options=call(path,'recipes',{'recipes':recipes})
    assert options['selector']['multi_select'] is False
    assert len(options['selector']['choices'])<=4
    _,all_selected=call(path,'recipes',{'recipes':recipes,'answer':'All eligible recipes'})
    assert all_selected['recipe_ids']==[r['recipe_id'] for r in recipes]
    if count>2:
        _,typed=call(path,'recipes',{'recipes':recipes,'answer':'Choose recipes'})
        assert 'choices' not in typed['selector']
    code,invalid=call(path,'recipes',{'recipes':recipes,'answer':'R-missing'})
    assert code!=0 and invalid['status']=='error'
    assert path.read_bytes()==before


def test_completed_add_has_consistent_persisted_and_displayed_readiness(tmp_path):
    path=tmp_path/'draft.json'
    code,initial=call(path,'create',{'project_id':'P','mode':'design','scenarios':[]})
    assert code==0
    code,added=call(path,'upsert',{'expected_revision':initial['revision'],'scenario':{
        'name':'Release','model':'kinetics','recipe_ids':['R-a','R-b'],'ready':True,
        'reviewed_sections':['model','recipes','shared_conditions','recipe_properties','criteria']}})
    assert code==0 and added['can_run'] is True
    assert added['scenarios'][0]['status']=='ready'
    assert json.loads(path.read_text())['scenarios'][0]['status']=='ready'
    # Existing wizard drafts with a legacy boolean also remain usable via the reader.
    state=json.loads(path.read_text());state['scenarios'][0].pop('status');path.write_text(json.dumps(state))
    code,listed=call(path,'list')
    assert code==0 and listed['can_run'] is True
    assert listed['scenarios'][0]['status']=='ready'
    # Explicit review-required status takes priority over a stale legacy flag.
    code,edited=call(path,'upsert',{'expected_revision':listed['revision'],'scenario':{
        **listed['scenarios'][0],'status':'review_required'}})
    assert code==0 and edited['can_run'] is False
