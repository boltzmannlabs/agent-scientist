"""Real program/MCP setup preserves private scope, exact grants and honest pending readiness."""
from pathlib import Path
from types import SimpleNamespace
import json
import shutil
import sys

import pytest

from sci_cli.subagent_package_install import install
from sci_cli.subagent_package_io import seal
from sci_cli.subagent_package_schema import validate
from sci_cli.native_profile_creation import profile_scope
from sci_cli.config import atomic_config_replace
from agent.specialist_extensions import extension_home, capability_scope
from agent.specialist_store import load


class UI:
    def __init__(self, answers):
        self.answers, self.messages = iter(answers), []
    def show(self, value):
        self.messages.append(str(value))
    def ask(self, question, *args, **kwargs):
        return next(self.answers)
    def choose(self, question, choices):
        answer = next(self.answers)
        assert answer in choices, (question, answer, choices)
        return answer


def package(tmp_path):
    import sci_yaml as yaml
    root = tmp_path / 'package'
    shutil.copytree(Path(__file__).resolve().parents[2] / 'contribution-templates/subagent', root)
    script = root / 'tests/server.py'
    script.write_text('''import json, sys, os
for line in sys.stdin:
    message = json.loads(line)
    with open(os.environ['CALL_LOG'], 'a') as f: f.write(json.dumps(message)+'\\n')
    if 'id' not in message: continue
    if message.get('method')=='initialize': result={'protocolVersion': message['params']['protocolVersion'], 'capabilities':{'tools':{}}, 'serverInfo':{'name':'echo','version':'1'}}
    elif message.get('method')=='tools/list': result={'tools':[{'name':'echo','description':'Echo fixture','inputSchema':{'type':'object','properties':{}}}, {'name':'unselected','description':'Not permitted','inputSchema':{'type':'object','properties':{}}}]}
    elif message.get('method')=='tools/call': result={'content':[{'type':'text','text':'private '+str(bool(os.environ.get('SERVICE_API_KEY')))}]}
    else: result={}
    print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}),flush=True)
''')
    manifest = yaml.safe_load((root / 'manifest.yaml').read_text())
    manifest['dependencies'] = [
        {'id':'python','kind':'program','version':sys.version.split()[0], 'version_args':['--version'], 'version_contains':sys.version.split()[0], 'artifacts':[]},
        {'id':'echo','kind':'mcp', 'tools':['echo'], 'config':{'command':'{{program.python}}', 'args':['{{resource.tests/server.py}}'],
            'env':{'CALL_LOG':'{{workspace}}/calls.jsonl', 'SERVICE_API_KEY':'${SERVICE_API_KEY}'}}}]
    manifest['tools'].append('mcp:echo/echo')
    (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
    seal(root); validate(root)
    return root


def test_real_mcp_package_private_credentials_discovery_and_execution_a_b_a(tmp_path, monkeypatch):
    from sci_cli import callbacks
    from agent.specialist_runtime import capture, resolve
    from agent.specialist_policy import specialist_scope
    from model_tools import handle_function_call
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    a, b = tmp_path / 'a', tmp_path / 'b'
    monkeypatch.setenv('SCI_HOME', str(a))
    for home in (a, b):
        home.mkdir(); atomic_config_replace(home / 'config.yaml', {'platform_toolsets':{'cli':['file','skills','delegation']}})
    root = package(tmp_path)
    monkeypatch.setattr(callbacks, 'prompt_for_secret', lambda *a, **k: {'success':True,'value':'fixture-secret'})
    cli = SimpleNamespace(agent=None)
    with profile_scope(a):
        before = (a / 'config.yaml').read_bytes()
        ui = UI(['Prepare package','Use installed executable',sys.executable,'Run version check',
                 'Create private connection','Enter new key for this profile','Approve execution','Check connection','Done',
                 'Save and enable for the next conversation'])
        item = install(root, a, cli, ui)
        assert item.enabled and item.package_info['state'] == 'ready'
        private = extension_home(item)
        log = private / 'workspace/calls.jsonl'
        assert not any(json.loads(line).get('method')=='tools/call' for line in log.read_text().splitlines())
        assert not (a / '.env').exists() and (a / 'config.yaml').read_bytes() == before
        assert 'fixture-secret' not in '\n'.join(ui.messages)
        parent = SimpleNamespace(enabled_toolsets=['file','skills','delegation'],disabled_toolsets=[],platform='cli')
        capture(parent); parent._specialist_parent_tools=frozenset({'read_file','delegate_task'})
        _, policy = resolve(parent, {'specialist':item.name})
        name = next(n for n in item.private_tools if n.startswith('mcp_'))
        with capability_scope(private), specialist_scope(policy):
            assert 'private True' in handle_function_call(name, {}, enabled_toolsets=list(policy.private_toolsets))
        with profile_scope(b):
            from tools.registry import registry
            assert registry.get_entry(name) is None
        assert load(item.name).extension_id == item.extension_id
        assert not any('unselected' in n for n in item.tools)


def test_deferred_setup_disabled_resumable_and_not_bypassed_by_enable(tmp_path, monkeypatch):
    from agent.specialist_runtime import capture, resolve
    from agent.specialist_store import save
    from dataclasses import replace
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    owner = tmp_path / 'owner'; owner.mkdir()
    monkeypatch.setenv('SCI_HOME', str(owner))
    atomic_config_replace(owner / 'config.yaml', {'platform_toolsets':{'cli':['file','skills','delegation']}})
    root = package(tmp_path)
    import sci_yaml as yaml
    manifest = yaml.safe_load((root / 'manifest.yaml').read_text())
    # A single program is sufficient to verify defer/resume without any network service.
    manifest['dependencies'] = manifest['dependencies'][:1]
    manifest['tools'] = ['read_file']
    (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest)); seal(root)
    cli = SimpleNamespace(agent=None)
    pending = install(root, owner, cli, UI(['Prepare package','Defer setup','Save disabled; setup required']))
    assert not pending.enabled and pending.package_info['state']=='setup_required'
    private = extension_home(pending)
    save(replace(pending,enabled=True,needs_review=False), expected_revision=pending.revision)
    parent = SimpleNamespace(enabled_toolsets=['file','skills','delegation'],disabled_toolsets=[],platform='cli')
    capture(parent); parent._specialist_parent_tools=frozenset({'read_file','delegate_task'})
    with pytest.raises(ValueError, match='setup'):
        resolve(parent, {'specialist':pending.name})
    # Restore exactly the reviewed pending definition before resuming the managed setup.
    current = load(pending.name)
    save(replace(pending, revision=current.revision), expected_revision=current.revision)
    ready = install(root, owner, cli, UI(['Resume setup','Prepare package','Use installed executable',sys.executable,'Run version check','Save and enable for the next conversation']))
    assert ready.enabled and ready.package_info['state']=='ready'
    assert extension_home(ready)==private
