"""Real SDK discovery and native catalog/grant checks, no inference or science.

Run only via the SDK scripts/run_tests.sh. A private fixture metadata file in the
pytest cache points at state created by the qualified scoring Python.
"""
from argparse import Namespace
from dataclasses import replace
import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import time

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from specialist.test_native import isolated_home  # noqa: F401
from integration.install import install

BUNDLE = Path(__file__).resolve().parents[1]


def test_real_profile_discovery_main_catalog_and_specialist_grants(isolated_home, tmp_path, request, monkeypatch):
    metadata = Path(request.config.getini('cache_dir')) / 'smallmol-entry-fixture.json'
    if not metadata.is_file():
        pytest.skip('Qualified private campaign fixture required; missing fixture is not a pass')
    fixture = json.loads(metadata.read_text())
    source_state = Path(fixture['state_dir'])
    state = tmp_path / 'campaign'
    state.mkdir(mode=0o700)
    with sqlite3.connect(source_state / 'campaign.sqlite') as source:
        with sqlite3.connect(state / 'campaign.sqlite') as target:
            source.backup(target)
    shutil.copy(source_state / 'workflow.json', state / 'workflow.json')
    task = dict(fixture['task'], workflow_state=str(state))
    taskfile = state / 'task.md'
    taskfile.write_text('# Local SDK integration fixture\n\n```json\n' + json.dumps(task) + '\n```\n')
    home_b = tmp_path / 'profile-b'; home_b.mkdir(mode=0o700)
    state_root = tmp_path
    from sci_constants import set_sci_home_override, reset_sci_home_override
    from sci_cli.plugins import discover_plugins, get_plugin_manager
    from sci_cli.config import atomic_config_write, get_config_path, read_user_config_raw
    from agent.specialist_policy import SpecialistPolicy, specialist_scope
    from agent.specialist_store import load
    from agent.specialist_runtime import context_for, resolve
    from model_tools import handle_function_call
    from run_agent import AIAgent
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    receipts = {}
    for home in (isolated_home, home_b, isolated_home):
        receipt = install(Namespace(owner_home=home, host_root=Path(fixture['host_root']),
            state_root=state_root, scoring_python=Path('/usr/bin/python3'),
            environment_source=Path(fixture['environment_source'])))
        receipts[str(home)] = receipt
        token = set_sci_home_override(home)
        try:
            config = read_user_config_raw()
            config.update({'tools': {'tool_search': {'enabled': 'off'}}, 'memory': {'enabled': False},
                           'model': {'default': 'fixture-model', 'provider': 'custom', 'context_length': 131072}})
            atomic_config_write(get_config_path(), config)
            discover_plugins(force=True)
            parent = AIAgent(model='fixture-model', provider='custom', api_key='local-only-fixture',
                base_url='http://127.0.0.1:9/v1', api_mode='chat_completions',
                enabled_toolsets=['delegation', 'skills', 'smallmol_optimization'],
                quiet_mode=True, skip_memory=True, skip_context_files=True, max_iterations=3)
            try:
                names = {t['function']['name'] for t in parent.tools}
                assert {'delegate_task', 'smallmol_campaign'} <= names
                catalog = json.loads(parent._dispatch_delegate_task({'action': 'catalog', 'query': 'smallmol-investigation'}))
                assert any(s['name'] == 'smallmol-investigation' and s['automatic'] for s in catalog['specialists'])
                item, policy = resolve(parent, {'specialist': 'smallmol-investigation'})
                assert item.revision == receipt['specialist_revision']
                assert policy.tools == frozenset({'smallmol_campaign', 'skill_view', 'skills_list'})
                with specialist_scope(policy):
                    loaded = context_for(item, 'Task file: ' + str(taskfile))
                assert 'Main-agent delegation through the campaign bridge' in loaded
                assert 'Lipophilicity' in loaded and str(taskfile) in loaded
                inspect = json.loads(handle_function_call('smallmol_campaign',
                    {'operation': 'inspect', 'task_file': str(taskfile)}, enabled_tools=['smallmol_campaign']))
                diagnostic = inspect
                if inspect.get('private_rpc_directory'):
                    diagnostic = {**inspect, 'fixture_process': json.loads((Path(inspect['private_rpc_directory']) / 'process.json').read_text())}
                    print(diagnostic['fixture_process'].get('stderr', ''))
                assert inspect['phase'] == 'ready', diagnostic
                denied = json.loads(handle_function_call('smallmol_campaign',
                    {'operation': 'evidence', 'task_file': str(taskfile)}, enabled_tools=['smallmol_campaign']))
                assert denied['phase'] == 'blocked', denied
                assert 'episodes_started' in inspect and inspect['episodes_started'] == 0
            finally:
                parent.close()
        finally:
            reset_sci_home_override(token)
    assert receipts[str(isolated_home)]['specialist_revision'] != receipts[str(home_b)]['specialist_revision']
