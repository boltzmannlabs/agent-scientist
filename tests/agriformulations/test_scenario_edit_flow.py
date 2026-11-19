"""Native Run choice -> Edit -> confirmation -> actual saved physics result."""
from copy import deepcopy
import json
from pathlib import Path
from queue import Queue
import subprocess
import sys
import pytest
from agri_tool import execute
from agri_tool.catalogue import EXAMPLE_RECIPE
from agri_tool.storage import Store

HELPER=Path(__file__).resolve().parents[2]/'skills/science/agri-models-and-design/scripts/scenario_draft.py'

def test_edit_review_returns_to_run_and_uses_exact_changed_conditions(tmp_path):
    from cli import SciCLI
    from tools.clarify_tool import clarify_tool
    path=tmp_path/'draft.json';workspace=tmp_path/'workspace'
    def command(action,payload):
        r=subprocess.run([sys.executable,str(HELPER),action,'--draft',str(path)],input=json.dumps(payload),capture_output=True,text=True,timeout=10)
        assert r.returncode==0,r.stdout+r.stderr
        return json.loads(r.stdout)
    def choose(selector,index):
        def callback(entries):
            q=entries[0];assert not q['multi_select']
            view=SciCLI.__new__(SciCLI);view._persist_prompt_summary=lambda *a:None
            state={'questions':entries,'active':0,'answers':{},'choices':q['choices'],'selected':index,'multi_select':False,'response_queue':Queue()}
            view._clarify_batch_enter(state)
            return {'answers':state['response_queue'].get_nowait(),'outcome':'submitted'}
        reply=json.loads(clarify_tool([selector],callback=callback))
        return reply['responses'][0]['user_response']
    made=execute({'operation':'recipes','action':'manual','payload':{'recipe':deepcopy(EXAMPLE_RECIPE)}},workspace)
    assert made['status']=='completed',made
    pid=made['project_id'];rid=made['result']['recipes'][0]['recipe_id']
    inputs={'yield_stress_pa':0,'consistency_pa_sn':.8,'flow_index':1,'pipe_length_m':5}
    initial=command('create',{'project_id':pid,'mode':'design','scenarios':[
        {'id':'S1','name':'Pumping','model':'rheology','recipe_ids':[rid],'shared_inputs':inputs},
        {'id':'S2','name':'Storage','model':'stability','recipe_ids':[rid]}]})
    # Unreviewed S1 can take the explicitly chosen without-review route.
    choice=choose(initial['run_selector'],0)
    route=command('run-choice',{'scenario_ids':['S1'],'answer':choice,'outcome':'submitted'})
    assert route['status']=='run'
    def run(values):
        r=execute({'operation':'simulate','action':'run','model':'rheology','project_id':pid,'payload':{'recipe_id':rid,'inputs':values}},workspace)
        assert r['status']=='completed',r
        return r['result']
    baseline=run(inputs)
    # Choose Edit from the same single native question; no backend runs on this choice.
    assert command('run-choice',{'scenario_ids':['S1'],'answer':choose(initial['run_selector'],1),'outcome':'submitted'})['status']=='edit'
    new_inputs={**inputs,'pipe_length_m':7}
    edited=command('upsert',{'expected_revision':initial['revision'],'scenario':{**initial['scenarios'][0],'shared_inputs':new_inputs,'status':'review_required'}})
    finish={'question':'Finish reviewing this scenario?','choices':edited['edit_actions'],'multi_select':False}
    answer=choose(finish,1);assert answer=='Confirm review'
    confirmed=command('confirm-review',{'expected_revision':edited['revision'],'scenario_ids':['S1'],'confirmation':answer})
    assert confirmed['scenarios'][0]['status']=='ready'
    assert confirmed['scenarios'][1]==initial['scenarios'][1]
    assert len(Store(workspace).load(pid)['document']['analysis_runs'])==1
    assert confirmed['actions']==initial['actions']  # back at parent, no implicit execution
    answer=choose(confirmed['run_selector'],2)
    assert answer=='Agent Choice'
    assert command('run-choice',{'scenario_ids':['S1'],'answer':answer,'outcome':'submitted'})['status']=='agent_choice'
    recorded=command('record-decision',{'expected_revision':confirmed['revision'],'answer':answer,'outcome':'submitted','decision':{
        'question':confirmed['run_selector']['question'],'options':confirmed['run_selector']['base_choices'],
        'selected_option':'Run without review','reason':'The edited 7 m setup has been confirmed; run it to evaluate the requested pumping condition.',
        'inputs_used':new_inputs,'scenario_ids':['S1'],'recipe_ids':[rid]}})
    assert recorded['agent_decisions'][0]['inputs_used']['pipe_length_m']==7
    # Resolve the delegated choice directly; there is no second manual question.
    assert command('run-choice',{'scenario_ids':['S1'],'answer':recorded['agent_decisions'][0]['selected_option'],'outcome':'submitted'})['status']=='run'
    result=run(confirmed['scenarios'][0]['shared_inputs'])
    assert result['inputs']['pipe_length_m']==7
    assert result['result']['metrics']['pressure_bar']==pytest.approx(baseline['result']['metrics']['pressure_bar']*7/5)
    assert result['recipe_id']==rid
    assert len(Store(workspace).load(pid)['document']['analysis_runs'])==2
