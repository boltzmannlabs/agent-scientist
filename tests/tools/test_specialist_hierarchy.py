"""Regression for #55: named descendants retain their own grants and owner profile.

Real agents, loopback model responses and a local stdio MCP; no production calls.
"""
from contextlib import contextmanager
from contextvars import copy_context
from copy import deepcopy
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
from threading import Event, Thread
import time
from types import SimpleNamespace

import pytest

from agent.specialist_extensions import capability_scope, fingerprint, private_definitions
from agent.specialist_policy import specialist_scope
from agent.specialist_store import Specialist, save
from sci_cli.config import atomic_config_replace, read_user_config_raw
from sci_cli.native_profile_creation import profile_scope
from sci_cli.specialist_private_setup import prepare_home
from sci_constants import get_sci_home


@pytest.fixture
def hierarchy_env(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    multiplex = set_multiplex_context(True)
    script = tmp_path / 'fixture_mcp.py'
    script.write_text('''import json, os, sys
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 if m['method']=='initialize': r={'protocolVersion':m['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}}
 elif m['method']=='tools/list': r={'tools':[{'name':'echo','description':'Harmless scoped fixture','inputSchema':{'type':'object','properties':{}}}]}
 elif m['method']=='tools/call': r={'content':[{'type':'text','text':os.environ['HIERARCHY_FIXTURE_MARKER']}]}
 else: r={}
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}),flush=True)
''')
    try:
        yield script
    finally:
        from tools.mcp_tool_lifecycle import shutdown_mcp_servers
        shutdown_mcp_servers()
        reset_multiplex_context(multiplex)


def private_specialist(name, children, script):
    item, private = prepare_home(Specialist(name, f'Perform {name} work', children=children,
        instructions=f'INSTRUCTIONS_{name}', automatic=name == 'lead', max_iterations=12, timeout_seconds=120))
    cfg = read_user_config_raw(private / 'config.yaml')
    cfg.update(tool_search={'enabled': 'off'}, memory={'enabled': False},
        mcp_servers={'hierarchy': {'command': sys.executable, 'args': [str(script)],
            'env': {'HIERARCHY_FIXTURE_MARKER': '${HIERARCHY_FIXTURE_MARKER}'},
            'tools': {'include': ['echo']}, 'sampling': {'enabled': False}}})
    cfg['platform_toolsets']['cli'] += ['mcp-hierarchy']
    # Old private setup must not override the owning profile's reviewed depth.
    cfg['delegation']['max_spawn_depth'] = 1
    atomic_config_replace(private / 'config.yaml', cfg)
    (private / '.env').write_text(f'HIERARCHY_FIXTURE_MARKER={get_sci_home().name}_{name}_PRIVATE\n')
    skill = private / 'skills' / 'private-evidence'
    (skill / 'references').mkdir(parents=True)
    (skill / 'SKILL.md').write_text('---\nname: private-evidence\ndescription: Scoped evidence\n---\n' + name + '_SKILL')
    (skill / 'references' / 'module.md').write_text(name + '_MODULE')
    names = [t['function']['name'] for t in private_definitions(item) if t['function']['name'].startswith('mcp_')]
    assert len(names) == 1
    return save(replace(item, tools=tuple(names), private_tools=tuple(names), skills=('private-evidence',),
        private_skills=('private-evidence',), skill_files=('private-evidence#references/module.md',),
        extension_revision=fingerprint(private))), private, names[0]


@contextmanager
def hierarchy_model(tool_name, private_lead, search=False):
    calls, block_worker = [], Event()
    worker_entered, release_worker = Event(), Event()

    def result_text(value):
        if isinstance(value, str):
            try:
                return result_text(json.loads(value))
            except (ValueError, TypeError):
                return value
        if isinstance(value, dict):
            for key in ('summary', 'error'):
                if key in value:
                    return str(value[key])
            return ' '.join(result_text(value[key]) for key in ('results', 'result', 'content', 'text') if key in value)
        if isinstance(value, list):
            return ' '.join(result_text(part) for part in value)
        return str(value)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                self.respond()
            except Exception as exc:
                calls.append({'fixture_error': f'{type(exc).__name__}: {exc}'})
                self.send_error(400, 'Controlled fixture failed')

        def respond(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            prompt = str(payload['messages'][0]['content'])
            name = re.search(r'Saved specialist: ([a-z-]+)', prompt)[1]
            results = [m for m in payload['messages'] if m['role'] == 'tool']
            if name == 'worker' and block_worker.is_set():
                worker_entered.set()
                release_worker.wait(10)
            target = {'lead': 'coordinator', 'coordinator': 'worker'}.get(name)
            report = ''
            if results:
                report = ' '.join(result_text(row['content']) for row in results)
            message = {'role': 'assistant', 'content': f'{name} finished. ' + report}
            finish = 'stop'
            own_check = target and len(results) == 1 and (name != 'lead' or private_lead)
            searching = search and name == 'worker' and len(results) < 3
            if not results or own_check or searching:
                tool = 'delegate_task' if target and not results else tool_name
                args = {'tasks': [{'specialist': target, 'goal': 'Check the exact inline value 42.',
                    'context': 'ASSIGNMENT_VALUE=42', 'delivery': 'intermediate'}]} if tool == 'delegate_task' else {}
                if searching and len(results) == 0:
                    tool, args = 'tool_search', {'query': 'hierarchy echo', 'limit': 5}
                elif searching and len(results) == 1:
                    tool, args = 'tool_describe', {'names': [tool_name]}
                elif tool not in {t['function']['name'] for t in payload.get('tools', [])}:
                    args, tool = {'calls': [{'name': tool, 'arguments': args}]}, 'tool_call'
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'call-{name}-{len(results)}',
                    'type': 'function', 'function': {'name': tool, 'arguments': json.dumps(args)}}]}
                finish = 'tool_calls'
            response = {'id': 'fixture', 'object': 'chat.completion', 'model': 'fixture',
                'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
            if payload.get('stream'):
                delta = deepcopy(message)
                if 'tool_calls' in delta:
                    delta['tool_calls'][0]['index'] = 0
                response['object'] = 'chat.completion.chunk'
                response['choices'][0] = {'index': 0, 'delta': delta, 'finish_reason': finish}
                raw = ('data: ' + json.dumps(response) + '\n\ndata: [DONE]\n\n').encode()
            else:
                raw = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if payload.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass  # An interrupted model request legitimately closes its transport.

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', calls, block_worker, worker_entered, release_worker
    finally:
        release_worker.set()
        server.shutdown()
        server.server_close()
        thread.join(5)


def configure(home):
    home.mkdir(parents=True, exist_ok=True)
    atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'skills', 'delegation']},
        'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
        'delegation': {'max_iterations': 12, 'max_spawn_depth': 3, 'max_concurrent_children': 1}})
    (home / '.env').write_text('HIERARCHY_FIXTURE_MARKER=OWNER_ONLY\n')


@pytest.mark.parametrize('private_lead', [False, True])
def test_single_profile_inherited_mcp_remains_available_through_deferred_nested_delegation(tmp_path, hierarchy_env, monkeypatch, private_lead):
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from tools.mcp_tool_discovery import discover_mcp_tools
    from tools.delegate_tool import delegate_task
    from run_agent import AIAgent
    home = tmp_path / 'owner'
    configure(home)
    monkeypatch.setenv('SCI_HOME', str(home))
    cfg = read_user_config_raw(home / 'config.yaml')
    cfg['tool_search'] = {'enabled': 'on'}
    cfg['mcp_servers'] = {'hierarchy': {'command': sys.executable, 'args': [str(hierarchy_env)],
        'env': {'HIERARCHY_FIXTURE_MARKER': '${HIERARCHY_FIXTURE_MARKER}'},
        'tools': {'include': ['echo']}, 'sampling': {'enabled': False}}}
    # Exercise the configured alias, not only its canonical mcp-* spelling.
    # A session may explicitly select a connection without changing profile defaults.
    session_toolsets = [*cfg['platform_toolsets']['cli'], 'hierarchy']
    atomic_config_replace(home / 'config.yaml', cfg)
    token = set_multiplex_context(False)
    try:
        with profile_scope(home):
            from tools.mcp_tool import _mcp_registry_scope
            assert _mcp_registry_scope() is None
            discover_mcp_tools(allowed_mcp_names=['hierarchy'])
            tool = 'mcp__hierarchy__echo'
            for name, children in [('worker', ()), ('coordinator', ('worker',)), ('lead', ('coordinator',))]:
                item = Specialist(name, 'Check the inherited MCP', tools=(tool,), children=children,
                    automatic=True, instructions='INSTRUCTIONS_' + name, max_iterations=16)
                if name == 'lead' and private_lead:
                    item, private = prepare_home(item)
                    item = replace(item, extension_revision=fingerprint(private))
                save(item)
            with hierarchy_model(tool, private_lead, search=True) as (url, calls, *_):
                parent = AIAgent(model='fixture', provider='custom', api_key='fixture-only', base_url=url,
                    api_mode='chat_completions', platform='cli', enabled_toolsets=session_toolsets,
                    quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=16)
                try:
                    frozen = json.dumps(parent.tools, sort_keys=True)
                    result = json.loads(delegate_task(tasks=[{'specialist': 'lead', 'goal': 'Check the MCP.'}], parent_agent=parent))
                    assert result['results'][0]['status'] == 'completed', result
                    assert 'OWNER_ONLY' in result['results'][0]['summary'], result
                    assert 'Unknown tool' not in result['results'][0]['summary'], result
                    assert not [c for c in calls if 'fixture_error' in c], calls
                    worker_calls = [c for c in calls if 'Saved specialist: worker\n' in str(c.get('messages', [{}])[0].get('content', ''))]
                    assert len(worker_calls) == 4, worker_calls
                    assert json.dumps(parent.tools, sort_keys=True) == frozen
                finally:
                    parent.close()
            # Entering a different profile must not expose the unscoped connection.
            with capability_scope(tmp_path / 'other'):
                import model_tools
                names = model_tools.get_tool_definitions(['hierarchy'], quiet_mode=True, skip_tool_search_assembly=True)
                assert tool not in {entry['function']['name'] for entry in names}
    finally:
        from tools.mcp_tool_lifecycle import shutdown_mcp_servers
        shutdown_mcp_servers()
        reset_multiplex_context(token)


@pytest.mark.parametrize('selector', ['hierarchy', 'mcp-hierarchy'])
def test_mcp_startup_selector_discovers_and_dispatches_in_the_owning_profile(tmp_path, hierarchy_env, selector):
    from model_tools import get_tool_definitions, handle_function_call
    from tools.mcp_tool_discovery import discover_mcp_tools
    homes = [tmp_path / name for name in ('a', 'b')]
    for home in homes:
        configure(home)
        (home / '.env').write_text(f'HIERARCHY_FIXTURE_MARKER={home.name}_ONLY\n')
        cfg = read_user_config_raw(home / 'config.yaml')
        cfg['mcp_servers'] = {'hierarchy': {'command': sys.executable, 'args': [str(hierarchy_env)],
            'env': {'HIERARCHY_FIXTURE_MARKER': '${HIERARCHY_FIXTURE_MARKER}'},
            'tools': {'include': ['echo']}, 'sampling': {'enabled': False}}}
        atomic_config_replace(home / 'config.yaml', cfg)
    for home in (homes[0], homes[1], homes[0]):
        with profile_scope(home):
            discover_mcp_tools(allowed_mcp_names=[selector])
            definitions = get_tool_definitions(enabled_toolsets=[selector], quiet_mode=True, skip_tool_search_assembly=True)
            assert 'mcp__hierarchy__echo' in {t['function']['name'] for t in definitions}
            result = handle_function_call('mcp__hierarchy__echo', {}, enabled_toolsets=[selector])
            assert home.name + '_ONLY' in str(result), result


@pytest.mark.parametrize('private_lead', [False, True])
def test_real_nested_specialists_preserve_private_scope_context_results_and_cancellation(tmp_path, hierarchy_env, private_lead):
    from agent.specialist_runs import history
    from tools.delegate_tool import delegate_task
    from tools.registry import registry
    from run_agent import AIAgent
    from sci_state import SessionDB
    homes = [tmp_path / name for name in ('a', 'b')]
    for home in homes:
        configure(home)
        if not private_lead:
            cfg = read_user_config_raw(home / 'config.yaml')
            cfg['platform_toolsets'] = {'cli': ['skills'], 'telegram': ['file', 'skills', 'delegation']}
            atomic_config_replace(home / 'config.yaml', cfg)
        with profile_scope(home):
            _, _, worker_tool = private_specialist('worker', (), hierarchy_env)
            private_specialist('coordinator', ('worker',), hierarchy_env)
            if private_lead:
                _, _, tool = private_specialist('lead', ('coordinator',), hierarchy_env)
            else:
                save(Specialist('lead', 'Coordinate the check', children=('coordinator',), automatic=True,
                    instructions='INSTRUCTIONS_lead', max_iterations=12, timeout_seconds=120))
                tool = worker_tool
    with hierarchy_model(tool, private_lead) as (url, calls, block, entered, release):
        for home in (homes[0], homes[1], homes[0]):
            with profile_scope(home):
                db = SessionDB(home / 'state.db')
                parent = AIAgent(model='fixture', provider='custom', api_key='fixture-only', base_url=url,
                    api_mode='chat_completions', enabled_toolsets=['file', 'skills', 'delegation'],
                    platform='cli' if private_lead else 'telegram', session_db=db,
                    quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=12)
                try:
                    frozen = json.dumps(parent.tools, sort_keys=True)
                    parent._cached_system_prompt = 'FROZEN MAIN PREFIX'
                    start = len(calls)
                    original_credentials = (home / '.env').read_bytes()
                    result = json.loads(delegate_task(tasks=[{'specialist': 'lead', 'goal': 'Check 42.'}], parent_agent=parent))
                    assert not [c for c in calls[start:] if 'fixture_error' in c], [c for c in calls[start:] if 'fixture_error' in c]
                    assert result['results'][0]['status'] == 'completed', result
                    assert len(calls) - start == (8 if private_lead else 7), calls[start:]
                    if home.name + '_worker_PRIVATE' not in result['results'][0]['summary']:
                        pytest.fail(result['results'][0]['summary'])
                    assert home.name + '_coordinator_PRIVATE' in result['results'][0]['summary']
                    if private_lead:
                        assert home.name + '_lead_PRIVATE' in result['results'][0]['summary']
                    assert 'OWNER_ONLY' not in result['results'][0]['summary']
                    for request in calls[start:]:
                        prompt = str(request['messages'][0]['content'])
                        who = re.search(r'Saved specialist: ([a-z-]+)', prompt)[1]
                        assert 'INSTRUCTIONS_' + who in prompt
                        if who != 'lead' or private_lead:
                            assert who + '_SKILL' in prompt and who + '_MODULE' in prompt
                        if who != 'lead':
                            assert 'ASSIGNMENT_VALUE=42' in prompt
                        if who == 'worker':
                            assert 'INSTRUCTIONS_lead' not in prompt and 'INSTRUCTIONS_coordinator' not in prompt
                    for who in ('lead', 'coordinator', 'worker'):
                        prefixes = [r['messages'][0] for r in calls[start:]
                                    if f'Saved specialist: {who}\n' in str(r['messages'][0]['content'])]
                        expected = 2 if who == 'worker' or (who == 'lead' and not private_lead) else 3
                        assert len(prefixes) == expected and all(prefix == prefixes[0] for prefix in prefixes)
                    rows = [row for row in history() if row['run_id'] == result['results'][0]['run_id']
                            or row.get('root_run_id') == result['results'][0]['run_id']]
                    assert {r['specialist'] for r in rows} == {'lead', 'coordinator', 'worker'}
                    by_name = {r['specialist']: r for r in rows}
                    assert by_name['worker']['parent_run_id'] == by_name['coordinator']['run_id']
                    assert by_name['coordinator']['parent_run_id'] == by_name['lead']['run_id']
                    for name, parent_name in (('worker', 'coordinator'), ('coordinator', 'lead')):
                        native = db.get_session(by_name[name]['session_id'])
                        assert native['parent_session_id'] == by_name[parent_name]['session_id']
                    assert all(r['status'] == 'completed' and r['model'] == 'fixture' for r in rows)
                    assert json.dumps(parent.tools, sort_keys=True) == frozen
                    assert parent._cached_system_prompt == 'FROZEN MAIN PREFIX'
                    assert registry.get_entry(tool) is None
                    assert (home / '.env').read_bytes() == original_credentials
                finally:
                    parent.close()
                    db.close()
        if private_lead:
            with profile_scope(homes[0]):
                parent = AIAgent(model='fixture', provider='custom', api_key='fixture-only', base_url=url,
                    api_mode='chat_completions', enabled_toolsets=['file', 'skills', 'delegation'],
                    quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=12)
                block.set()
                outcome = []
                context = copy_context()
                thread = Thread(target=lambda: context.run(lambda: outcome.append(json.loads(delegate_task(
                    tasks=[{'specialist': 'lead', 'goal': 'Check 42.'}], parent_agent=parent)))), daemon=True)
                thread.start()
                try:
                    assert entered.wait(10)
                    parent.interrupt('Controlled hierarchy cancellation')
                    release.set()
                    thread.join(15)
                    assert not thread.is_alive()
                    assert outcome[0]['results'][0]['status'] != 'completed'
                    assert not parent._active_children
                finally:
                    release.set()
                    thread.join(15)
                    parent.close()


def test_nested_specialist_preflight_rejects_unapproved_revoked_cycles_limits_and_wrong_profile(tmp_path, hierarchy_env):
    from agent.specialist_runtime import resolve
    from agent.specialist_store import load
    from tools.delegate_tool import delegate_task
    from run_agent import AIAgent
    home = tmp_path / 'owner'
    configure(home)
    with profile_scope(home):
        _, private, _ = private_specialist('lead', ('worker',), hierarchy_env)
        private_specialist('worker', (), hierarchy_env)
        save(Specialist('outsider', 'Unapproved', automatic=True))
        parent = AIAgent(model='fixture', provider='custom', api_key='fixture-only', base_url='http://127.0.0.1:1/v1',
            api_mode='chat_completions', enabled_toolsets=['file', 'skills', 'delegation'],
            quiet_mode=True, skip_context_files=True, skip_memory=True)
        try:
            _, policy = resolve(parent, {'specialist': 'lead'})
            def attempt(target='worker', *, active=private, grant=policy, depth=1):
                child = SimpleNamespace(_specialist_policy=grant, _specialist_home=policy.home,
                    _specialist_snapshot=parent._specialist_snapshot, _specialist_parent_tools=grant.owner_tools,
                    _delegate_depth=depth, enabled_toolsets=[], disabled_toolsets=[], platform='subagent',
                    model='fixture', provider='custom', base_url='http://127.0.0.1:1/v1', api_key='fixture-only',
                    api_mode='chat_completions', request_overrides={}, _specialist_user_request='')
                with capability_scope(active), specialist_scope(grant):
                    return json.loads(delegate_task(tasks=[{'specialist': target, 'goal': 'Controlled check'}], parent_agent=child))

            assert 'approved' in attempt('outsider')['error']
            assert 'approved named' in attempt(None)['error']
            assert 'cycle' in attempt('lead', grant=replace(policy, children=frozenset({'lead'})))['error']
            assert 'depth' in attempt(depth=3)['error']
            assert 'runtime' in attempt(grant=replace(policy, deadline=time.monotonic() - 1))['error'].lower()
            cfg = read_user_config_raw(home / 'config.yaml')
            cfg['delegation']['orchestrator_enabled'] = False
            atomic_config_replace(home / 'config.yaml', cfg)
            assert 'disabled' in attempt()['error']
            cfg['delegation']['orchestrator_enabled'] = True
            atomic_config_replace(home / 'config.yaml', cfg)
            other = tmp_path / 'other'
            configure(other)
            assert 'profile' in attempt(active=other)['error'].lower()
            worker = load('worker')
            from agent.specialist_extensions import extension_home
            credential = extension_home(worker) / '.env'
            original = credential.read_bytes()
            credential.write_bytes(original + b'CHANGED_FIXTURE_KEY=changed\n')
            assert 'Private capabilities changed' in attempt()['error']
            credential.write_bytes(original)
            save(replace(worker, enabled=False), expected_revision=worker.revision)
            assert 'disabled' in attempt()['error']
            worker = load('worker')
            save(replace(worker, enabled=True), expected_revision=worker.revision)
            assert 'edited' in attempt()['error']
            worker = load('worker')
            save(replace(worker, package_info={'state': 'setup_required', 'missing': ['fixture']}),
                 expected_revision=worker.revision)
            assert 'incomplete' in attempt()['error']
            worker = load('worker')
            save(replace(worker, package_info={}), expected_revision=worker.revision)
            lead = load('lead')
            save(replace(lead, enabled=False), expected_revision=lead.revision)
            assert 'Parent specialist was disabled' in attempt()['error']
            assert not list((home / 'subagent-runs').glob('*.json'))
        finally:
            parent.close()
        lead = load('lead')
        save(replace(lead, enabled=True), expected_revision=lead.revision)
        from sci_cli.specialist_children import hierarchy_depth
        from sci_cli.specialist_commands import dispatch
        from sci_cli.skill_add import Cancelled
        worker = load('worker')
        local = save(Specialist('local-lead', 'Coordinate approved checks', automatic=True))
        with pytest.raises(ValueError, match='cycle'):
            hierarchy_depth(replace(local, children=('worker',)),
                {'worker': replace(worker, children=(local.name,))})
        with pytest.raises(ValueError, match='missing'):
            hierarchy_depth(replace(local, children=('missing-child',)))

        class UI:
            def __init__(self, answers):
                self.answers = iter(answers)
            def show(self, text):
                pass
            def choose(self, question, choices):
                answer = next(self.answers)
                if answer == 'Cancel':
                    raise Cancelled()
                if answer == 'choose-worker':
                    answer = next(label for label in choices if label.startswith('worker —'))
                assert answer in choices
                return answer

        cfg = read_user_config_raw(home / 'config.yaml')
        cfg['delegation']['max_spawn_depth'] = 1
        atomic_config_replace(home / 'config.yaml', cfg)
        cli = SimpleNamespace(agent=None)
        dispatch(cli, '/Update_subagent local-lead', UI(['Approved children', 'choose-worker', 'Done',
            'Save and enable for the next conversation', 'Back', 'Cancel']))
        assert load('local-lead').children == ()
        assert read_user_config_raw(home / 'config.yaml')['delegation']['max_spawn_depth'] == 1
        dispatch(cli, '/Update_subagent local-lead', UI(['Resume draft',
            'Save and enable for the next conversation', 'Enable reviewed hierarchy']))
        assert load('local-lead').children == ('worker',)
        cfg_after = read_user_config_raw(home / 'config.yaml')
        assert cfg_after['delegation']['max_spawn_depth'] == 2
        assert cfg_after['delegation']['max_concurrent_children'] == cfg['delegation']['max_concurrent_children']
        assert read_user_config_raw(other / 'config.yaml')['delegation']['max_spawn_depth'] == 3
