"""Real child construction + HTTP provider adapter + transcript/receipt, with a loopback model fixture."""
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading


from agent.specialist_store import Specialist, save
from sci_constants import get_sci_home

REPORT = 'Protocol: FIXTURE-V1\n\n1. Calculation\n\n| Check | Result |\n|---|---|\n| 2 + 2 = 4 | Correct |\n\n2. Verdict\nComplete.'


@contextmanager
def model_server(tool_name=None, tool_args=None):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            contents = json.dumps(payload)
            reply = ('Outcome: BLOCKED BEFORE EXECUTION\nA required input is missing; no target program ran.'
                     if 'BLOCKED_FIXTURE' in contents else
                     "I'll start by reading the instruction file to follow the required format."
                     if 'PLAN_ONLY_FIXTURE' in contents else REPORT)
            message = {'role': 'assistant', 'content': reply}
            finish = 'stop'
            result = {'id': 'fixture-response', 'object': 'chat.completion', 'model': 'fixture-model',
                      'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                      'usage': {'prompt_tokens': 40, 'completion_tokens': 12, 'total_tokens': 52}}
            if tool_name and not any(m.get('role') == 'tool' for m in payload.get('messages', [])):
                direct = tool_name in {t['function']['name'] for t in payload.get('tools', [])}
                result['choices'][0]['message'] = {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'id': 'fixture-tool', 'type': 'function', 'function': {
                        'name': tool_name if direct else 'tool_call',
                        'arguments': json.dumps(tool_args or {}) if direct else json.dumps({'calls': [
                            {'name': tool_name, 'arguments': tool_args or {}}]})}}]}
                result['choices'][0]['finish_reason'] = 'tool_calls'
                message = result['choices'][0]['message']
                finish = 'tool_calls'
            if payload.get('stream'):
                delta = dict(message)
                if 'tool_calls' in delta:
                    delta['tool_calls'] = [{**delta['tool_calls'][0], 'index': 0}]
                chunks = [
                    {'id': 'fixture-response', 'object': 'chat.completion.chunk', 'model': 'fixture-model',
                     'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]},
                    {'id': 'fixture-response', 'object': 'chat.completion.chunk', 'model': 'fixture-model',
                     'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}], 'usage': result['usage']},
                ]
                raw = (''.join('data: ' + json.dumps(c) + '\n\n' for c in chunks) + 'data: [DONE]\n\n').encode()
            else:
                raw = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if payload.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', calls
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_real_child_permissions_provider_result_and_parent_cache(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task
    from agent.specialist_runs import history
    from sci_state import SessionDB
    home = get_sci_home()
    # Metadata lookup isn't the inference path under test; prevent unrelated public model-directory calls.
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    with model_server() as (url, calls):
        atomic_config_replace(home / 'config.yaml', {
            'model': {'default': 'fixture-model', 'provider': 'custom', 'base_url': url, 'context_length': 131072},
            'tool_search': {'enabled': 'off'}, 'delegation': {'max_iterations': 3, 'child_timeout_seconds': 120},
            'agent': {'max_iterations': 3}, 'memory': {'enabled': False},
        })
        from agent.specialist_sources import instruction_fields, load_reference
        instruction = tmp_path / 'instructions.md'
        instruction.write_text('# Calculator\nCheck arithmetic. Instruction marker LOADED_BEFORE_INFERENCE.')
        reference = tmp_path / 'reference.txt'
        reference.write_text('Approved reference marker: ARITHMETIC_REFERENCE.')
        saved = save(Specialist('calculator', **instruction_fields(str(instruction)), automatic=True,
                                sources=(str(reference),), source_documents=load_reference(str(reference)),
                                tools=('browser_back',), max_iterations=3, timeout_seconds=120))
        save(Specialist('planner', 'Check a short task', instructions='PLAN_ONLY_FIXTURE', automatic=True))
        save(Specialist('blocked-reviewer', 'Report missing inputs', instructions='BLOCKED_FIXTURE', automatic=True))
        instruction.unlink()  # Reviewed instructions must survive moving/deleting the source file.
        reference.unlink()
        db = SessionDB(home / 'state.db')
        parent = AIAgent(model='fixture-model', provider='custom', api_key='fixture-key', base_url=url,
                         api_mode='chat_completions', enabled_toolsets=['file', 'delegation'],
                         quiet_mode=True, skip_context_files=True, skip_memory=True, session_db=db, max_iterations=3)
        try:
            parent._cached_system_prompt = 'Parent cached prompt must stay byte-stable.'
            before = json.dumps(parent.tools, sort_keys=True)
            parent._ensure_db_session()
            save(Specialist('later-reviewer', 'Added after the conversation started', automatic=True))
            resumed = AIAgent(model='fixture-model', provider='custom', api_key='fixture-key', base_url=url,
                              api_mode='chat_completions', enabled_toolsets=['file', 'delegation'],
                              quiet_mode=True, skip_context_files=True, skip_memory=True, session_db=db,
                              session_id=parent.session_id, max_iterations=3)
            try:
                assert 'later-reviewer' not in resumed._specialist_snapshot
                assert json.dumps(resumed.tools, sort_keys=True) == before
            finally:
                resumed.close()
            result = json.loads(delegate_task(tasks=[{'specialist': 'calculator', 'goal': 'Calculate two plus two'}],
                                              parent_agent=parent))
            assert result['results'][0]['status'] == 'completed', result
            assert '2 + 2 = 4' in result['results'][0]['summary']
            assert result['results'][0]['specialist'] == 'calculator'
            assert calls
            assert {t['function']['name'] for t in calls[-1].get('tools', [])} <= {'read_file', 'search_files'}
            assert 'LOADED_BEFORE_INFERENCE' in json.dumps(calls[-1])
            assert 'ARITHMETIC_REFERENCE' in json.dumps(calls[-1])
            assert 'Unavailable tools in this conversation: browser_back' in json.dumps(calls)
            assert parent._cached_system_prompt == 'Parent cached prompt must stay byte-stable.'
            assert json.dumps(parent.tools, sort_keys=True) == before
            rows = history()
            assert len(rows) == 1 and rows[0]['status'] == 'completed'
            assert rows[0]['model'] == 'fixture-model'
            assert rows[0]['provider'] == 'custom'
            assert Path(rows[0]['transcript']).is_file()
            assert rows[0]['result']['summary']
            # A real async-notification carrier delivers the saved report with no parent inference/reformatting.
            from tools.process_registry_notifications import TimelineNotification
            from sci_cli.cli_chat_turn_mixin import CLIChatTurnMixin
            from types import SimpleNamespace
            evt = {'type': 'async_delegation', 'delegation_id': 'fixture-delivery', 'is_batch': True,
                   'status': 'completed', 'results': result['results'], 'goals': ['Calculate two plus two']}
            notification = TimelineNotification.for_delegation('Fixture completion event', evt)
            cli = SimpleNamespace(conversation_history=list(getattr(parent, '_session_messages', [])))
            CLIChatTurnMixin._chat_stage_user_message(cli, parent, notification)
            count_before_delivery = len(calls)
            delivered = parent.run_conversation(str(notification), conversation_history=cli.conversation_history[:-1])
            assert delivered['api_calls'] == 0 and len(calls) == count_before_delivery
            assert delivered['final_response'] == rows[0]['result']['summary'] == REPORT
            assert delivered['messages'][-1]['role'] == 'assistant'
            assert delivered['messages'][-1]['content'] == REPORT
            assert parent._cached_system_prompt == 'Parent cached prompt must stay byte-stable.'
            assert json.dumps(parent.tools, sort_keys=True) == before
            # Editing/disable blocks a subsequent spawn without a single provider request.
            save(replace(saved, enabled=False), expected_revision=saved.revision)
            count = len(calls)
            result = json.loads(delegate_task(tasks=[{'specialist': 'calculator', 'goal': 'Calculate two plus two'}],
                                              parent_agent=parent))
            assert 'error' in result and len(calls) == count
            result = json.loads(delegate_task(tasks=[{'specialist': 'planner', 'goal': 'Review the supplied material'}],
                                              parent_agent=parent))
            planned = result['results'][0]
            assert planned['status'] == 'failed' and planned['exit_reason'] == 'incomplete_response'
            assert planned['task_outcome'] == 'incomplete'
            assert "I'll start" in planned['summary']
            assert len(calls) == count + 1  # Report incomplete work without unapproved repeated attempts.
            assert history()[0]['status'] == 'failed'
            result = json.loads(delegate_task(tasks=[{'specialist': 'blocked-reviewer', 'goal': 'Check the missing input'}],
                                              parent_agent=parent))
            blocked = result['results'][0]
            assert blocked['status'] == 'failed' and blocked['task_outcome'] == 'blocked'
            assert blocked['exit_reason'] == 'blocked' and blocked['run_id'].startswith('sa-')
            assert history()[0]['result']['task_outcome'] == 'blocked'
            assert f'Authoritative subagent run ID: {blocked["run_id"]}' in json.dumps(calls[-1])
        finally:
            parent.close()
            db.close()


def test_named_child_runtime_limit_does_not_reset_on_progress(monkeypatch):
    from types import SimpleNamespace
    from agent.specialist_policy import SpecialistPolicy
    from tools.delegate_tool_child_run import _ChildRun
    import time
    policy = SpecialistPolicy('bounded', str(get_sci_home().resolve()), 'revision', frozenset(), frozenset(),
                              frozenset(), ('bounded',), time.monotonic() - 1)
    event = threading.Event()
    run = _ChildRun(SimpleNamespace(_specialist_policy=policy), None, 0, 'fixture', None, None)
    # The reviewed total deadline is exhausted; do not wait for the ordinary inactivity timeout.
    run.wait_liveness_aware(event, None, 100)
    assert not event.is_set()


def test_real_child_private_mcp_and_skill_do_not_expand_parent(tmp_path, monkeypatch):
    import sys
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.specialist_private_setup import prepare_home
    from agent.specialist_extensions import capability_scope, fingerprint, private_definitions
    from tools.delegate_tool import delegate_task
    from tools.registry import registry
    from run_agent import AIAgent
    from agent.specialist_runs import history
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers
    from agent.secret_scope import get_secret
    home = get_sci_home()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    script = tmp_path / 'mcp.py'
    script.write_text('''import json,sys
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 if m['method']=='initialize': r={'protocolVersion':m['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}}
 elif m['method']=='tools/list': r={'tools':[{'name':'echo','description':'Harmless echo','inputSchema':{'type':'object','properties':{}}}]}
 elif m['method']=='tools/call': r={'content':[{'type':'text','text':'PRIVATE_MCP_EXECUTED'}]}
 else: r={}
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}),flush=True)
''')
    atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'delegation']},
        'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
        'delegation': {'max_iterations': 3, 'child_timeout_seconds': 120}})
    (home / '.env').write_text('INHERITED_FIXTURE_KEY=owner-value\n')
    registry.register(name='inherited_scope_fixture', toolset='file',
                      schema={'name': 'inherited_scope_fixture', 'description': 'Scoped credential fixture',
                              'parameters': {'type': 'object', 'properties': {}}},
                      handler=lambda args: json.dumps({'key': get_secret('INHERITED_FIXTURE_KEY')}))
    item, private = prepare_home(Specialist('private-reviewer', 'Use the harmless private fixture', automatic=True,
                                          max_iterations=3, timeout_seconds=120))
    cfg = read_user_config_raw(private / 'config.yaml')
    cfg.update(tool_search={'enabled': 'off'}, memory={'enabled': False},
               mcp_servers={'onlyhere': {'command': sys.executable, 'args': [str(script)],
                                        'tools': {'include': ['echo']}, 'sampling': {'enabled': False}}})
    cfg['platform_toolsets']['cli'].append('mcp-onlyhere')
    atomic_config_replace(private / 'config.yaml', cfg)
    (private / '.env').write_text('INHERITED_FIXTURE_KEY=private-value\n')
    skill = private / 'skills' / 'private-check'
    skill.mkdir(parents=True)
    (skill / 'SKILL.md').write_text('---\nname: private-check\ndescription: Harmless check\n---\nPRIVATE_SKILL_PRELOADED\n')
    names = [t['function']['name'] for t in private_definitions(item) if t['function']['name'].startswith('mcp_')]
    assert len(names) == 1
    item = save(replace(item, tools=tuple([*names, 'inherited_scope_fixture']), private_tools=tuple(names), skills=('private-check',),
                        private_skills=('private-check',), extension_revision=fingerprint(private)))
    try:
        with model_server(names[0]) as (url, calls):
            parent = AIAgent(model='fixture-model', provider='custom', api_key='fixture-key', base_url=url,
                api_mode='chat_completions', enabled_toolsets=['file', 'delegation'],
                quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=3)
            try:
                parent._cached_system_prompt = 'Frozen parent prompt'
                before = json.dumps(parent.tools, sort_keys=True)
                import model_tools
                resolved_before = list(model_tools._last_resolved_tool_names)
                result = json.loads(delegate_task(tasks=[{'specialist': item.name, 'goal': 'Run the harmless fixture once'}],
                                                  parent_agent=parent))
                assert result['results'][0]['status'] == 'completed', result
                assert len(calls) == 2, calls
                assert 'PRIVATE_SKILL_PRELOADED' in json.dumps(calls[0])
                assert 'PRIVATE_MCP_EXECUTED' in json.dumps(calls[-1])
                assert names[0] not in before and json.dumps(parent.tools, sort_keys=True) == before
                assert parent._cached_system_prompt == 'Frozen parent prompt'
                assert model_tools._last_resolved_tool_names == resolved_before
                assert registry.get_entry(names[0]) is None
                from agent.specialist_runtime import resolve
                from agent.specialist_policy import specialist_scope
                _, policy = resolve(parent, {'specialist': item.name})
                with capability_scope(private), specialist_scope(policy):
                    assert json.loads(registry.dispatch('inherited_scope_fixture', {}))['key'] == 'owner-value'
                assert history()[0]['specialist'] == item.name
            finally:
                parent.close()
    finally:
        shutdown_mcp_servers(scope=str(private.resolve()))


def test_reconciled_program_executes_in_private_backend_with_standard_tools_already_selected(tmp_path, monkeypatch):
    import shlex
    import sys
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.specialist_private_setup import prepare_home
    from sci_cli.specialist_private_inventory import reconcile
    from agent.specialist_sources import DEFAULT_TOOLS
    from tools.delegate_tool import delegate_task
    from run_agent import AIAgent
    home = get_sci_home()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'terminal', 'skills', 'delegation']},
        'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
        'delegation': {'max_iterations': 3, 'child_timeout_seconds': 120, 'subagent_auto_approve': True}})
    item, private = prepare_home(Specialist('program-reviewer', 'Run the provided harmless fixture', automatic=True,
                                          tools=tuple(DEFAULT_TOOLS), max_iterations=3, timeout_seconds=120))
    cfg = read_user_config_raw(private / 'config.yaml')
    cfg['platform_toolsets']['cli'].append('terminal')
    atomic_config_replace(private / 'config.yaml', cfg)
    for name in ('quality-review', 'program-local'):
        folder = private / 'skills' / name
        folder.mkdir(parents=True)
        (folder / 'SKILL.md').write_text(f'---\nname: {name}\ndescription: Run the fixture only\n---\n'
                                      f'PRIVATE_INSTRUCTIONS_{name}\nNo substitute inputs or programs.\n')
    program = private / 'tools' / 'fixture.py'
    program.parent.mkdir()
    program.write_text("import os\nprint('PRIVATE_PROGRAM_EXECUTED', os.getcwd())\n")
    before = program.read_bytes(), program.stat().st_mtime_ns
    saved = save(reconcile(item))
    assert {'terminal', 'process_manage'} <= set(saved.shared_tools)
    command = shlex.join([sys.executable, str(program)])
    with model_server('terminal', {'command': command, 'timeout': 30}) as (url, calls):
        parent = AIAgent(model='fixture-model', provider='custom', api_key='fixture-key', base_url=url,
                         api_mode='chat_completions', enabled_toolsets=['file', 'terminal', 'skills', 'delegation'],
                         quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=3)
        try:
            parent._cached_system_prompt = 'Frozen parent'
            schemas_before = json.dumps(parent.tools, sort_keys=True)
            result = json.loads(delegate_task(tasks=[{'specialist': saved.name, 'goal': 'Execute the approved fixture program once'}],
                                              parent_agent=parent))
            assert result['results'][0]['status'] == 'completed', result
            assert len(calls) == 2
            assert 'PRIVATE_PROGRAM_EXECUTED' in json.dumps(calls[-1])
            assert str(private / 'workspace') in json.dumps(calls[-1])
            assert 'PRIVATE_INSTRUCTIONS_program-local' in json.dumps(calls[0])
            assert 'PRIVATE_INSTRUCTIONS_quality-review' in json.dumps(calls[0])
            assert (program.read_bytes(), program.stat().st_mtime_ns) == before
            assert parent._cached_system_prompt == 'Frozen parent'
            assert json.dumps(parent.tools, sort_keys=True) == schemas_before
        finally:
            parent.close()
