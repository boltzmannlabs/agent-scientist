"""Private imports and real MCP discovery/dispatch stay outside the owning profile."""
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from agent.specialist_store import Specialist, save, copy_to
from agent.specialist_sources import DEFAULT_TOOLS
from agent.specialist_extensions import capability_scope, extension_home
from sci_cli.native_profile_creation import profile_scope
from sci_cli.specialist_private_setup import setup


class UI:
    def __init__(self, answers):
        self.answers, self.messages = iter(answers), []
    def show(self, text):
        self.messages.append(text)
    def ask(self, question, *args, **kwargs):
        from sci_cli.skill_add import Cancelled
        answer = next(self.answers)
        if answer == 'Cancel':
            raise Cancelled()
        return answer
    def choose(self, question, choices):
        answer = self.ask(question)
        assert answer in choices, (answer, choices)
        return answer


def test_private_skill_import_review_copy_and_scope_a_b_a(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    from tools.skills_tool import _find_all_skills
    from agent.specialist_runtime import context_for
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'SKILL.md').write_text('---\nname: private-evidence\ndescription: Review provided evidence\n---\nPRIVATE INSTRUCTIONS\n')
    (source / 'reference.md').write_text('Supporting evidence')
    cli = SimpleNamespace(agent=None)
    for home in homes:
        home.mkdir()
        atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['skills', 'file']}})
    for home in (homes[0], homes[1], homes[0]):
        with profile_scope(home):
            before = (home / 'config.yaml').read_bytes()
            item = Specialist('reviewer', 'Review', automatic=True, tools=tuple(sorted(DEFAULT_TOOLS)))
            # A fresh scope every time; same private name can be installed independently.
            item = setup(cli, UI(['External skill', str(source), 'Save', 'Save and enable for the next session']), item)
            assert item.private_skills == ('private-evidence',)
            assert (extension_home(item) / 'skills/private-evidence/reference.md').read_text() == 'Supporting evidence'
            assert 'PRIVATE INSTRUCTIONS' in context_for(item, 'Review this')
            assert 'private-evidence' not in {r['name'] for r in _find_all_skills()}
            assert (home / 'config.yaml').read_bytes() == before
            program = tmp_path / 'example.py'
            program.write_text("raise AssertionError('Setup must not execute this program')\n")
            item = setup(cli, UI(['Use an already-installed program', 'private-program', str(program), sys.executable,
                                  'none', str(tmp_path), 'Inspect fixture data', 'User-supplied text',
                                  'A fixture report', 'Only use approved fixtures',
                                  'Save', 'Save and enable for the next session']), item)
            assert 'private-program' in item.private_skills
            assert {'terminal', 'process_manage'} <= set(item.private_tools)
            assert {'terminal', 'process_manage'} <= set(item.shared_tools)
            assert (home / 'config.yaml').read_bytes() == before
            copied = copy_to(item, home, 'copy-' + item.extension_id[:8])
            assert not copied.extension_id and not copied.private_skills and 'private-evidence' not in copied.skills
            assert set(copied.tools) == DEFAULT_TOOLS


def test_private_mcp_real_handshake_credentials_and_dispatch(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    from tools.registry import registry
    from model_tools import handle_function_call
    from agent.specialist_runtime import capture, resolve
    from agent.specialist_policy import specialist_scope
    from sci_cli import callbacks
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    owner = tmp_path / 'main'
    owner.mkdir()
    monkeypatch.setenv('SCI_HOME', str(owner))
    atomic_config_replace(owner / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'delegation']}})
    script = tmp_path / 'server.py'
    log = tmp_path / 'calls.jsonl'
    script.write_text('''import json, sys, os
for line in sys.stdin:
    m=json.loads(line)
    with open(os.environ['FIXTURE_LOG'], 'a') as f: f.write(json.dumps(m)+'\\n')
    if 'id' not in m: continue
    method=m.get('method')
    if method=='initialize': r={'protocolVersion':m['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}}
    elif method=='tools/list': r={'tools':[{'name':'echo','description':'Fixture echo','inputSchema':{'type':'object','properties':{}}}]}
    elif method=='tools/call': r={'content':[{'type':'text','text':'private credential present: '+str(bool(os.environ.get('SERVICE_API_KEY')))}]}
    else: r={}
    print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}), flush=True)
''')
    config = tmp_path / 'connection.json'
    config.write_text(json.dumps({'mcpServers': {'privatefixture': {'command': sys.executable,
        'args': [str(script)], 'env': {'SERVICE_API_KEY': '${SERVICE_API_KEY}', 'FIXTURE_LOG': str(log)}}}}))
    monkeypatch.setattr(callbacks, 'prompt_for_secret', lambda *a, **k: {'success': True, 'value': 'private-fixture-key'})
    cli = SimpleNamespace(agent=None)
    ui = UI(['MCP service', str(config), 'privatefixture', 'Enter new key for this profile',
             'Approve execution', 'Check connection', 'Select all', 'Done', 'Save private connection'])
    before = (owner / 'config.yaml').read_bytes()
    item = setup(cli, ui, Specialist('reviewer', 'Review', automatic=True))
    assert item.private_tools and 'private-fixture-key' not in '\n'.join(ui.messages)
    assert (owner / 'config.yaml').read_bytes() == before and not (owner / '.env').exists()
    messages = [json.loads(line) for line in log.read_text().splitlines()]
    assert not any(m.get('method') == 'tools/call' for m in messages)
    assert registry.get_entry(item.private_tools[0]) is None
    save(item)
    parent = SimpleNamespace(enabled_toolsets=['file', 'delegation'], disabled_toolsets=[], platform='cli')
    capture(parent)
    parent._specialist_parent_tools = frozenset({'delegate_task', 'read_file'})
    _, policy = resolve(parent, {'specialist': 'reviewer'})
    assert item.private_tools[0] in policy.tools
    with capability_scope(extension_home(item)), specialist_scope(policy):
        result = handle_function_call(item.private_tools[0], {}, enabled_toolsets=list(policy.private_toolsets))
        assert 'private credential present: True' in result
    assert 'error' in json.loads(handle_function_call(item.private_tools[0], {}))
    other = tmp_path / 'other-profile'
    other.mkdir()
    with profile_scope(other):
        assert registry.get_entry(item.private_tools[0]) is None
        assert 'error' in json.loads(handle_function_call(item.private_tools[0], {}))
    # A second specialist with no private grants cannot discover/call the first one's tool.
    sibling = save(Specialist('sibling', 'Review', automatic=True))
    capture(parent)
    parent._specialist_parent_tools = frozenset({'delegate_task', 'read_file'})
    _, sibling_policy = resolve(parent, {'specialist': sibling.name})
    with specialist_scope(sibling_policy):
        assert 'error' in json.loads(handle_function_call(item.private_tools[0], {}))
    from sci_cli.skill_add import Cancelled
    with pytest.raises(Cancelled):
        setup(cli, UI(['MCP service', str(config), 'privatefixture', 'Cancel']),
              Specialist('cancelled', 'No execution', automatic=True))
    assert (owner / 'config.yaml').read_bytes() == before
    assert not (owner / '.env').exists()
    # Changing credentials invalidates the reviewed scope until a new review/save.
    (extension_home(item) / '.env').write_text('SERVICE_API_KEY=rotated\n')
    with pytest.raises(ValueError, match='Private capabilities changed'):
        resolve(parent, {'specialist': 'reviewer'})
