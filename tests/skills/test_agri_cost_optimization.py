"""Baseline/grade/supplier decisions from real saved scientific and cost records."""
from copy import deepcopy
import csv
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest
from agri_tool import execute
from agri_tool.storage import Store
from agri_tool import cost_comparison as helper


@pytest.fixture(scope='module')
def saved(tmp_path_factory):
    workspace = tmp_path_factory.mktemp('agri-cost-optimization')
    pid = None
    entries = []
    cases = [('B0', 95, 'Supplier A', 100, 'Dispersant A', 3, 10, .8),
             ('G98', 98, 'Supplier A', 90, 'Dispersant A', 3, 10, .7),
             ('S95', 95, 'Supplier B', 80, 'Dispersant A', 3, 10, .8),
             ('CHEAP_FAIL', 90, 'Supplier C', 50, 'Dispersant B', 2, 7, 1.1),
             ('JOINT', 98, 'Supplier B', 70, 'Dispersant B', 2, 7, .6)]
    for label, purity, supplier, price, dispersant, dose, dispersant_price, consistency in cases:
        active_pct = 20 / (purity / 100)
        raw = {'name': label, 'format': 'SC', 'batch_g': 1000, 'currency': 'INR', 'ingredients': [
            {'name': 'Tebuconazole technical', 'role': 'active', 'pct': active_pct, 'purity_pct': purity,
             'supplier': supplier, 'grade_source': 'Synthetic test fixture, not a real quote'},
            {'name': dispersant, 'role': 'dispersant', 'pct': dose},
            {'name': 'Water', 'role': 'solvent', 'pct': 100 - active_pct - dose}]}
        made = execute({'operation': 'recipes', 'action': 'manual', 'project_id': pid,
                        'payload': {'recipe': raw}}, workspace)
        assert made['status'] == 'completed', made
        pid = made['project_id']
        recipe = made['result']['recipes'][0]
        run = execute({'operation': 'simulate', 'model': 'rheology', 'project_id': pid,
                       'payload': {'recipe_id': recipe['recipe_id'], 'inputs': {'yield_stress_pa': 0,
                                   'flow_index': 1, 'consistency_pa_sn': consistency},
                                   'assumptions': ['Declared synthetic properties only']}}, workspace)
        assert run['status'] == 'completed', run
        active_price = {'cost_per_kg': price}
        if label == 'G98':
            active_price = {'price_estimate': {'currency': 'INR', 'low': 80, 'base': 90, 'high': 100,
                                              'source': 'Synthetic quote-range fixture'}}
        cost = execute({'operation': 'cost', 'action': 'estimate', 'project_id': pid,
                        'payload': {'recipe_id': recipe['recipe_id'], 'prices': {
                            'Tebuconazole technical': active_price, dispersant: {'cost_per_kg': dispersant_price},
                            'Water': {'cost_per_kg': 1}}, 'assumptions': {'currency': 'INR', 'yield_pct': 100,
                            'processing_per_input_kg': 10, 'packaging_per_saleable_kg': 2, 'fixed_batch_cost': 0,
                            'overhead_pct': 0, 'freight_per_batch': 0, 'tax_pct': 0}}}, workspace)
        assert cost['status'] == 'completed', cost
        entries.append({'id': label, 'recipe_id': recipe['recipe_id'], 'cost_id': cost['result']['cost_id'],
                        'runs': {'flow': run['result']['scenario_id']}, 'grades': {'Tebuconazole technical': str(purity) + '% technical'}})
    request = {'project_id': pid, 'baseline': entries[0], 'candidates': entries[1:], 'scenarios': [{
        'id': 'flow', 'model': 'rheology', 'varying_inputs': ['consistency_pa_sn'], 'criteria': [
            {'metric': 'pressure_bar', 'unit': 'bar', 'goal': 'minimize', 'maximum': 3},
            {'metric': 'viscosity_at_100_s_pa_s', 'unit': 'Pa s', 'goal': 'range', 'minimum': .5, 'maximum': 1}]}]}
    return workspace, Store(workspace).load(pid)['document'], request


def rows(result):
    return {r['id']: r for r in result['iterations']}


def test_joint_grade_supplier_ingredient_search_selects_feasible_total_cost_minimum(saved):
    _, document, request = saved
    result = helper.compare(document, request)
    records = rows(result)
    assert result['best_evaluated_id'] == 'JOINT'
    assert records['CHEAP_FAIL']['cost_per_saleable_kg'] < records['JOINT']['cost_per_saleable_kg']
    assert records['CHEAP_FAIL']['status'] == 'excluded_or_unresolved'
    assert any('constraint failed' in x for x in records['CHEAP_FAIL']['reasons'])
    assert records['JOINT']['savings_per_kg'] == pytest.approx(records['B0']['cost_per_saleable_kg'] - records['JOINT']['cost_per_saleable_kg'])
    assert result['pareto_ids'] == ['JOINT']
    assert result['product_performance_established'] is False
    assert len(result['iterations']) == len(request['candidates']) + 1


def test_grade_purity_supplier_and_price_range_are_preserved_without_double_purity_correction(saved):
    _, document, request = saved
    result = helper.compare(document, request)
    grade = next(r for r in result['grade_comparison'] if r['iteration_id'] == 'JOINT' and r['ingredient'] == 'Tebuconazole technical')
    assert grade['supplier'] == 'Supplier B' and grade['purity_pct'] == 98
    assert grade['input_mass_kg'] == pytest.approx(.2 / .98)
    assert grade['material_cost_batch'] == pytest.approx(.2 / .98 * 70)
    assert grade['price_per_pure_kg'] == pytest.approx(70 / .98)
    assert rows(result)['G98']['cost_range']['low'] < rows(result)['G98']['cost_range']['high']
    assert all(r['active_fraction'] == pytest.approx(.2) for r in document['recipes'])


def test_a_feasible_baseline_is_retained_if_alternatives_cost_more_or_tie(saved):
    _, document, request = saved
    doc = deepcopy(document)
    baseline_total = helper.compare(document, request)['iterations'][0]['cost_per_saleable_kg']
    for cost in doc['cost_estimates'][1:]:
        cost['result']['final_cost_per_saleable_kg'] = baseline_total + 1
    assert helper.compare(doc, request)['best_evaluated_id'] == 'B0'
    for cost in doc['cost_estimates'][1:]:
        cost['result']['final_cost_per_saleable_kg'] = baseline_total
    assert helper.compare(doc, request)['best_evaluated_id'] == 'B0'


@pytest.mark.parametrize('pressure_limit, winner', [(.7, 'JOINT'), (.1, None)])
def test_new_performance_limit_never_relaxes_constraints_to_claim_savings(saved, pressure_limit, winner):
    _, document, request = saved
    doc, req = deepcopy(document), deepcopy(request)
    req['scenarios'][0]['criteria'][0]['maximum'] = pressure_limit
    baseline_cost = helper.compare(document, request)['iterations'][0]['cost_per_saleable_kg']
    candidate = next(e for e in req['candidates'] if e['id'] == 'JOINT')
    next(c for c in doc['cost_estimates'] if c['cost_id'] == candidate['cost_id'])['result']['final_cost_per_saleable_kg'] = baseline_cost + 1
    result = helper.compare(doc, req)
    assert rows(result)['B0']['status'] == 'excluded_or_unresolved'
    assert result['best_evaluated_id'] == winner
    if winner:
        assert rows(result)[winner]['savings_per_kg'] == pytest.approx(-1)
        assert rows(result)[winner]['savings_pct'] < 0
    else:
        assert all(row['status'] == 'excluded_or_unresolved' for row in result['iterations'])
        assert result['selection_status'] == 'no fully assessed feasible option'


def test_cost_performance_tradeoffs_remain_on_pareto_front(saved):
    _, document, request = saved
    doc = deepcopy(document)
    cheaper = next(e for e in request['candidates'] if e['id'] == 'S95')
    next(c for c in doc['cost_estimates'] if c['cost_id'] == cheaper['cost_id'])['result']['final_cost_per_saleable_kg'] = 20
    result = helper.compare(doc, request)
    assert result['best_evaluated_id'] == 'S95'
    assert set(result['pareto_ids']) == {'S95', 'JOINT'}


def test_zero_baseline_cost_has_no_fabricated_percent_savings(saved):
    _, document, request = saved
    doc = deepcopy(document)
    next(c for c in doc['cost_estimates'] if c['cost_id'] == request['baseline']['cost_id'])['result']['final_cost_per_saleable_kg'] = 0
    result = helper.compare(doc, request)
    assert result['best_evaluated_id'] == 'B0'
    assert all(r['savings_pct'] is None for r in result['iterations'])


@pytest.mark.parametrize('missing', ['run', 'metric', 'cost'])
def test_missing_candidate_evidence_cannot_be_used_as_a_successful_cheap_winner(saved, missing):
    _, document, request = saved
    doc, req = deepcopy(document), deepcopy(request)
    candidate = req['candidates'][-1]
    if missing == 'run':
        candidate['runs'] = {}
    elif missing == 'metric':
        next(r for r in doc['analysis_runs'] if r['scenario_id'] == candidate['runs']['flow'])['result']['metrics'].pop('pressure_bar')
    else:
        next(r for r in doc['cost_estimates'] if r['cost_id'] == candidate['cost_id'])['result']['final_cost_per_saleable_kg'] = None
    result = helper.compare(doc, req)
    assert result['best_evaluated_id'] != 'JOINT'
    assert rows(result)['JOINT']['status'] == 'excluded_or_unresolved'


def test_missing_baseline_cost_prevents_savings_and_a_final_recommendation(saved):
    _, document, request = saved
    req = deepcopy(request)
    req['baseline'].pop('cost_id')
    result = helper.compare(document, req)
    assert result['best_evaluated_id'] is None
    assert all(r['savings_pct'] is None and r['savings_per_kg'] is None for r in result['iterations'])


@pytest.mark.parametrize('mismatch', ['conditions', 'engine', 'loading'])
def test_unfair_baseline_comparisons_are_excluded(saved, mismatch):
    _, document, request = saved
    doc = deepcopy(document)
    candidate = request['candidates'][-1]
    run = next(r for r in doc['analysis_runs'] if r['scenario_id'] == candidate['runs']['flow'])
    if mismatch == 'conditions':
        run['inputs']['pipe_length_m'] /= 2
    elif mismatch == 'engine':
        run['engine_version'] = 'another-engine'
    else:
        next(r for r in doc['recipes'] if r['recipe_id'] == candidate['recipe_id'])['active_components'][0]['active_fraction'] /= 2
    result = helper.compare(doc, request)
    assert rows(result)['JOINT']['status'] == 'excluded_or_unresolved'
    assert result['best_evaluated_id'] != 'JOINT'


@pytest.mark.parametrize('bad', ['currency', 'cost_owner', 'run_owner', 'vary_test_conditions', 'unit', 'metric', 'range', 'nonfinite', 'boolean'])
def test_invalid_or_mislinked_comparisons_fail_instead_of_silently_ranking(saved, bad):
    _, document, request = saved
    doc, req = deepcopy(document), deepcopy(request)
    candidate = req['candidates'][-1]
    cost = next(r for r in doc['cost_estimates'] if r['cost_id'] == candidate['cost_id'])
    if bad == 'currency':cost['result']['currency'] = 'USD'
    elif bad == 'cost_owner':candidate['cost_id'] = req['baseline']['cost_id']
    elif bad == 'run_owner':candidate['runs']['flow'] = req['baseline']['runs']['flow']
    elif bad == 'vary_test_conditions':req['scenarios'][0]['varying_inputs'].append('pipe_length_m')
    elif bad == 'unit':req['scenarios'][0]['criteria'][0]['unit'] = 'Pa'
    elif bad == 'metric':req['scenarios'][0]['criteria'][0]['metric'] = 'invented_metric'
    elif bad == 'range':req['scenarios'][0]['criteria'] = [{'metric': 'pressure_bar', 'unit': 'bar', 'goal': 'range'}]
    else:cost['result']['final_cost_per_saleable_kg'] = float('nan') if bad == 'nonfinite' else True
    with pytest.raises(ValueError):helper.compare(doc, req)


def test_cli_runtime_emits_traceable_comparison_and_grade_performance_csvs(saved, tmp_path):
    workspace, _, request = saved
    path = tmp_path / 'request.json'
    path.write_text(json.dumps({'operation': 'cost', 'action': 'compare', 'project_id': request['project_id'],
                                'payload': {k: v for k, v in request.items() if k != 'project_id'}}))
    completed = subprocess.run([sys.executable, '-I', '-m', 'agri_tool', '--full', '--request-file', str(path),
                                '--workspace', str(workspace)],
                               stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    response = json.loads(completed.stdout)
    assert response['status'] == 'completed', response
    result = response['result']
    assert result['best_evaluated_id'] == 'JOINT'
    assert result['project_id'] == request['project_id'] and result['inputs_revision'] > 0
    grade_file = next(a['path'] for a in response['artifacts'] if a['path'].endswith('-grades.csv'))
    with Path(grade_file).open() as stream:
        assert {r['iteration_id'] for r in csv.DictReader(stream)} == {'B0', 'G98', 'S95', 'CHEAP_FAIL', 'JOINT'}
    performance_file = next(a['path'] for a in response['artifacts'] if a['path'].endswith('-performance.csv'))
    with Path(performance_file).open() as stream:
        assert {r['metric'] for r in csv.DictReader(stream)} == {'pressure_bar', 'viscosity_at_100_s_pa_s'}
    saved_result = execute({'operation': 'project', 'action': 'result', 'project_id': request['project_id'],
                            'payload': {'id': result['comparison_id']}}, workspace)
    assert saved_result['result']['record'] == result


def test_saved_comparison_retries_and_pdf_zip_keep_every_iteration_and_grade(saved):
    workspace, _, request = saved
    call = {'operation': 'cost', 'action': 'compare', 'project_id': request['project_id'],
            'payload': {k: v for k, v in request.items() if k != 'project_id'}}
    first = execute(call, workspace)
    assert first['status'] == 'completed', first
    repeated = execute(call, workspace)
    assert repeated['result']['comparison_id'] == first['result']['comparison_id']
    doc = Store(workspace).load(request['project_id'])['document']
    assert len([c for c in doc['cost_comparisons'] if c['comparison_id'] == first['result']['comparison_id']]) == 1
    exported = execute({'operation': 'project', 'action': 'export', 'project_id': request['project_id']}, workspace)
    assert exported['status'] == 'completed', exported
    pdf = next(a for a in exported['artifacts'] if a['media_type'] == 'application/pdf')
    assert Path(pdf['path']).read_bytes().startswith(b'%PDF-')
    archive = next(a for a in exported['artifacts'] if a['media_type'] == 'application/zip')
    cid = first['result']['comparison_id']
    with zipfile.ZipFile(archive['path']) as z:
        assert z.testzip() is None and 'report.pdf' in z.namelist()
        assert any(name.endswith(cid + '-costs.png') for name in z.namelist())
        grades = next(name for name in z.namelist() if name.endswith(cid + '-grades.csv'))
        content = z.read(grades).decode()
        assert 'Supplier B' in content and '98% technical' in content
        comparison = next(name for name in z.namelist() if name.endswith(cid + '.json'))
        data = json.loads(z.read(comparison))
        assert {r['id'] for r in data['iterations']} == {request['baseline']['id'], *[c['id'] for c in request['candidates']]}
        assert data['best_evaluated_id'] == 'JOINT'


def test_concurrent_comparison_records_merge_without_losing_results(saved):
    from concurrent.futures import ThreadPoolExecutor
    workspace, _, request = saved
    def compute(label):
        payload = {k: deepcopy(v) for k, v in request.items() if k != 'project_id'}
        payload['candidates'][-1]['label'] = label
        return execute({'operation': 'cost', 'action': 'compare', 'project_id': request['project_id'], 'payload': payload}, workspace)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(compute, ['Concurrent A', 'Concurrent B']))
    assert all(r['status'] == 'completed' for r in results), results
    stored = Store(workspace).load(request['project_id'])['document']['cost_comparisons']
    assert {r['result']['comparison_id'] for r in results} <= {r['comparison_id'] for r in stored}
