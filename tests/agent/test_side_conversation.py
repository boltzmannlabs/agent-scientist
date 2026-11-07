"""Side conversations use the real agent/fork/provider path against a local fixture server."""

import json
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread

import pytest

from agent.side_conversation import SideConversation, completed_snapshot


@pytest.fixture
def provider(tmp_path):
    requests = []
    entered, release = Event(), Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if not self.path.endswith('/chat/completions'):
                self.send_response(404)
                self.end_headers()
                return
            requests.append(body)
            if 'reject-side-auth' in json.dumps(body):
                raw = json.dumps({'error': {'message': 'Fixture authentication rejected', 'type': 'authentication_error'}}).encode()
                self.send_response(401)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)
                return
            if 'wait-for-cancellation' in json.dumps(body):
                entered.set()
                release.wait(10)
            response = {'id': 'fixture', 'object': 'chat.completion', 'created': 1, 'model': 'fixture',
                        'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'Fixture side answer.'},
                                     'finish_reason': 'stop'}],
                        'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
            if ('try-a-tool' in json.dumps(body)
                    and not any(m.get('role') == 'tool' for m in body.get('messages', []))):
                response['choices'][0] = {'index': 0, 'message': {'role': 'assistant', 'content': '', 'tool_calls': [
                    {'index': 0, 'id': 'denied-command', 'type': 'function', 'function': {
                        'name': 'terminal', 'arguments': json.dumps({'command': f'touch {tmp_path / "side-fixture-output"}'})}}]},
                    'finish_reason': 'tool_calls'}
            if body.get('stream'):
                response['object'] = 'chat.completion.chunk'
                response['choices'][0]['delta'] = response['choices'][0].pop('message')
                raw = ('data: ' + json.dumps(response) + '\n\ndata: [DONE]\n\n').encode()
                content_type = 'text/event-stream'
            else:
                raw = json.dumps(response).encode()
                content_type = 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f'http://127.0.0.1:{server.server_port}/v1', requests, entered, release
    release.set()
    server.shutdown()
    server.server_close()
    thread.join(5)


def parent_agent(url):
    from run_agent import AIAgent
    agent = AIAgent(api_key='fixture-key', base_url=url, provider='custom', model='fixture',
                    skip_memory=True, skip_context_files=True, enabled_toolsets=[], quiet_mode=True)
    agent._cached_system_prompt = 'Stable parent prompt.\n'
    return agent


def test_real_multiturn_fork_profile_isolation_and_no_parent_writes(provider, tmp_path, monkeypatch):
    from sci_constants import reset_sci_home_override, set_sci_home_override
    from sci_state import SessionDB
    from sci_cli.plugins import _get_pre_tool_call_directive_details

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    url, requests, _, _ = provider
    parents = {}
    for name in ('A', 'B', 'A'):
        home = tmp_path / name
        home.mkdir(exist_ok=True)
        monkeypatch.setenv('SCI_HOME', str(home))
        token = set_sci_home_override(home)
        try:
            if name not in parents:
                parent = parent_agent(url)
                db = SessionDB(home / 'state.db')
                db.create_session(parent.session_id, 'cli', system_prompt=parent._cached_system_prompt)
                db.append_message(parent.session_id, 'user', f'{name} earliest question')
                db.append_message(parent.session_id, 'assistant', f'{name} earliest answer')
                db.append_message(parent.session_id, 'user', f'{name} private context')
                db.append_message(parent.session_id, 'assistant', f'{name} response')
                parent._session_db = db
                parents[name] = parent
            parent = parents[name]
            history = parent._session_db.get_messages_as_conversation(parent.session_id)
            original = deepcopy(history)
            original_prompt = parent._cached_system_prompt
            original_tools = deepcopy(parent.tools)
            side = SideConversation(parent, history)
            history.append({'role': 'user', 'content': 'later parent activity'})
            assert side.answer('Explain the previous answer.') == 'Fixture side answer.'
            fork = side._agent
            assert fork.session_id != parent.session_id
            assert fork._session_db is parent._session_db and not fork._persist_disabled
            assert fork._cached_system_prompt == original_prompt
            assert side.answer('And what are the assumptions?') == 'Fixture side answer.'
            outbound = json.dumps(requests[-1])
            assert 'Explain the previous answer.' in outbound and 'Fixture side answer.' in outbound
            assert f'{name} private context' in outbound
            assert f'{name} earliest question' in outbound and f'{name} earliest answer' in outbound
            assert f'{"B" if name == "A" else "A"} private context' not in outbound
            assert 'later parent activity' not in outbound
            assert parent._cached_system_prompt == original_prompt and parent.tools == original_tools
            assert parent._session_db.get_messages_as_conversation(parent.session_id) == original
            saved_id = side.id
            side.close()
            assert side._agent is None
            assert parent._session_db.get_session_model_config_value(saved_id, '_side_from') == parent.session_id
            failed = SideConversation(parent, original)
            count_before = len(requests)
            with pytest.raises(RuntimeError, match='failed'):
                failed.answer('reject-side-auth')
            assert len(requests) == count_before + 1  # no provider fallback or auth retry
            assert failed.transcript == []
            failed.close()
            # Side execution does not install a restriction on the parent thread.
            assert _get_pre_tool_call_directive_details('read_file', {}).action != 'block'
        finally:
            reset_sci_home_override(token)
    for parent in parents.values():
        parent.close()


def test_midturn_snapshot_cancellation_and_tool_execution(provider, monkeypatch, tmp_path):
    from sci_cli.plugins import _get_pre_tool_call_directive_details
    from run_agent import AIAgent
    from sci_state import SessionDB

    url, requests, entered, release = provider
    parent = parent_agent(url)
    parent._session_db = SessionDB(tmp_path / 'state.db')
    parent._session_db.create_session(parent.session_id, 'cli', system_prompt=parent._cached_system_prompt)
    history = [{'role': 'user', 'content': 'earlier'}, {'role': 'assistant', 'content': 'complete'},
               {'role': 'user', 'content': 'working'},
               {'role': 'assistant', 'tool_calls': [{'id': 'unfinished'}], 'content': ''}]
    assert completed_snapshot(history) == history[:2]
    side = SideConversation(parent, history)
    original_run = AIAgent.run_conversation
    denied = []

    def run(self, *args, **kwargs):
        denied.append(_get_pre_tool_call_directive_details('terminal', {'command': 'touch forbidden'}).action)
        return original_run(self, *args, **kwargs)

    monkeypatch.setattr(AIAgent, 'run_conversation', run)
    result = []
    worker = Thread(target=lambda: result.append(side.answer('wait-for-cancellation')), daemon=True)
    worker.start()
    assert entered.wait(15)
    with pytest.raises(ValueError, match='still answering'):
        side.answer('second request must not run')
    side.close()
    release.set()
    worker.join(15)
    assert not worker.is_alive()
    assert denied != ['block'] and len(requests) == 1
    assert side._agent is None and side.transcript == []
    assert any(m.get('content') == 'wait-for-cancellation'
               for m in parent._session_db.get_messages_as_conversation(side.id))
    assert not parent._interrupt_requested
    with pytest.raises(ValueError, match='closed'):
        side.answer('no restart')
    parent.tools = [{'type': 'function', 'function': {'name': 'terminal', 'description': 'Fixture command',
                    'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}]
    parent.valid_tool_names = {'terminal'}
    tool_side = SideConversation(parent, history)
    assert tool_side.answer('try-a-tool') == 'Fixture side answer.'
    assert any(m.get('role') == 'tool' for m in parent._session_db.get_messages_as_conversation(tool_side.id))
    assert (tmp_path / 'side-fixture-output').exists()
    assert any(m.get('role') == 'tool' and 'exit_code' in str(m.get('content'))
               for m in requests[-1]['messages'])
    tool_side.close()
    from sci_cli.plugins import clear_thread_tool_whitelist, set_thread_tool_whitelist
    (tmp_path / 'side-fixture-output').unlink()
    restriction = set_thread_tool_whitelist({'read_file'})
    restricted_side = SideConversation(parent, history)
    try:
        assert restricted_side.answer('try-a-tool') == 'Fixture side answer.'
        assert not (tmp_path / 'side-fixture-output').exists()
        assert any(m.get('role') == 'tool' and 'denied' in str(m.get('content')).lower()
                   for m in requests[-1]['messages'])
    finally:
        restricted_side.close()
        clear_thread_tool_whitelist(restriction)
    parent.close()
    parent._session_db.close()


def test_btw_real_reply_keeps_main_and_profile_queues_and_prompts_unchanged(provider, monkeypatch, tmp_path):
    from queue import Queue
    from types import SimpleNamespace
    from unittest.mock import Mock

    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from sci_cli import side_commands
    from sci_cli.cli_tui_mixin import CLITuiMixin
    from sci_constants import get_sci_home
    from sci_state import SessionDB
    from tui_gateway import server

    home = tmp_path / '.sci'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(home))
    url, requests, _, _ = provider
    clients, homes, output = {}, {}, []
    monkeypatch.setattr(side_commands, '_show', lambda cli, text: output.append(
        (str(get_sci_home()), cli.session_id, text)))
    multiplex = set_multiplex_context(True)
    try:
        for name in ('main', 'A', 'B', 'A'):
            scoped_home = home if name == 'main' else home / 'profiles' / name
            scoped_home.mkdir(parents=True, exist_ok=True)
            (scoped_home / 'config.yaml').write_text('{}\n')
            session = {'profile_home': str(scoped_home)}
            with server._session_profile_runtime_scope(session, hydrate_secrets=False):
                if name not in clients:
                    parent = parent_agent(url)
                    db = SessionDB(scoped_home / 'state.db')
                    db.create_session(parent.session_id, 'cli', system_prompt=parent._cached_system_prompt)
                    db.append_message(parent.session_id, 'user', f'{name} private question')
                    db.append_message(parent.session_id, 'assistant', f'{name} private answer')
                    parent._session_db = db
                    cli = SimpleNamespace(agent=parent, session_id=parent.session_id, _agent_running=True,
                                          conversation_history=db.get_messages_as_conversation(parent.session_id),
                                          _pending_input=Queue(), _app=Mock(),
                                          _clarify_state={'question': 'parent approval'})
                    cli._pending_input.put(f'{name} queued task')
                    clients[name], homes[name] = cli, session
                cli = clients[name]
                parent = cli.agent
                history, prompt, tools = deepcopy(cli.conversation_history), parent._cached_system_prompt, deepcopy(parent.tools)
                event = SimpleNamespace(app=SimpleNamespace(
                    current_buffer=SimpleNamespace(text='/BTW\tExplain the previous answer.', reset=Mock()),
                    invalidate=Mock()))
                assert CLITuiMixin._tui_enter_overlay(cli, event) is False
                assert CLITuiMixin._tui_enter_inline_command(cli, event, event.app.current_buffer.text, False)
                side = cli._side_controller
                side.worker.join(30)
                assert not side.worker.is_alive() and side.outcome == 'ready'
                assert output[-1] == (str(scoped_home), cli.session_id, 'Fixture side answer.')
                outbound = json.dumps(requests[-1])
                assert f'{name} private question' in outbound
                assert all(f'{other} private question' not in outbound for other in ('main', 'A', 'B') if other != name)
                assert side.conversation._agent.provider == parent.provider
                assert side.conversation._agent.model == parent.model
                assert not parent._interrupt_requested
                assert list(cli._pending_input.queue) == [f'{name} queued task']
                assert cli._clarify_state == {'question': 'parent approval'}
                assert cli.conversation_history == history
                assert parent._cached_system_prompt == prompt and parent.tools == tools
                assert parent._session_db.get_messages_as_conversation(cli.session_id) == history
                side_commands.toggle(cli)
                assert not side_commands.route_input(cli, 'next main task')
        assert len(requests) == 4
    finally:
        for name, cli in clients.items():
            with server._session_profile_runtime_scope(homes[name], hydrate_secrets=False):
                side_commands.shutdown(cli)
                cli.agent.close()
                cli.agent._session_db.close()
        reset_multiplex_context(multiplex)


def test_saved_side_fork_resumes_with_captured_live_context_and_no_parent_changes(provider, tmp_path, monkeypatch):
    from sci_state import SessionDB
    from sci_cli.session_picker import SessionPicker
    from types import SimpleNamespace
    from run_agent import AIAgent

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    home = tmp_path / '.sci'
    home.mkdir()
    monkeypatch.setenv('SCI_HOME', str(home))
    url, requests, _, _ = provider
    db = SessionDB(home / 'state.db')
    parent = parent_agent(url)
    parent._session_db = db
    db.create_session(parent.session_id, 'cli', system_prompt=parent._cached_system_prompt)
    db.append_message(parent.session_id, 'user', 'earliest main context')
    db.append_message(parent.session_id, 'assistant', 'completed main answer')
    old_cli_history = db.get_messages_as_conversation(parent.session_id)
    # Current main turn has reached the store, but the CLI still shows its old history.
    db.append_message(parent.session_id, 'user', 'current main request')
    db.append_message(parent.session_id, 'assistant', 'currently checking files', tool_calls=[
        {'id': 'pending', 'type': 'function', 'function': {'name': 'read_file', 'arguments': '{"path":"pending.txt"}'}}])
    side = SideConversation(parent, old_cli_history, require_durable=True)
    # Later progress never enters this captured fork.
    db.append_message(parent.session_id, 'tool', 'later main result', tool_call_id='pending')
    before = db.get_messages_as_conversation(parent.session_id, repair_alternation=False)
    assert side.answer('What was happening when I opened this?') == 'Fixture side answer.'
    sent = json.dumps(requests[-1])
    assert 'earliest main context' in sent and 'current main request' in sent
    assert 'currently checking files' in sent and 'incomplete' in sent
    assert 'later main result' not in sent
    assert not any(m.get('tool_calls') for m in requests[-1]['messages'])
    saved_id = side.id
    assert SessionDB.session_gateway_runtime(db.get_session(saved_id))['base_url'] == parent.base_url
    assert saved_id in [row['id'] for row in SessionPicker(SimpleNamespace(
        _session_db=db, session_id=parent.session_id)).rows]
    from sci_cli.active_sessions import active_session_registry_snapshot
    assert any(row['session_id'] == saved_id for row in active_session_registry_snapshot(home))
    prompt = parent._cached_system_prompt
    side.close()
    assert not any(row['session_id'] == saved_id for row in active_session_registry_snapshot(home))
    assert db.get_messages_as_conversation(parent.session_id, repair_alternation=False) == before
    parent.close()
    db.close()
    reopened = SessionDB(home / 'state.db')
    reopened.reopen_session(saved_id)
    restored = reopened.get_messages_as_conversation(saved_id)
    assert any(m.get('content') == 'What was happening when I opened this?' for m in restored)
    resumed = AIAgent(api_key='fixture-key', base_url=url, provider='custom', model='fixture',
                      session_id=saved_id, session_db=reopened, enabled_toolsets=[],
                      skip_memory=True, skip_context_files=True, quiet_mode=True)
    try:
        result = resumed.run_conversation(user_message='Continue my side question.', conversation_history=restored)
        assert result['final_response'] == 'Fixture side answer.'
        sent = json.dumps(requests[-1])
        assert 'current main request' in sent and 'What was happening when I opened this?' in sent
        assert 'later main result' not in sent
        assert resumed._cached_system_prompt == prompt
        assert reopened.get_messages_as_conversation(parent.session_id, repair_alternation=False) == before
    finally:
        resumed.close()
        reopened.close()


def test_failed_side_seed_stops_before_model_request(provider, tmp_path, monkeypatch):
    from sci_state import SessionDB
    from agent.side_persistence import SidePersistenceError

    url, requests, _, _ = provider
    parent = parent_agent(url)
    db = SessionDB(tmp_path / 'state.db')
    parent._session_db = db
    db.create_session(parent.session_id, 'cli', system_prompt=parent._cached_system_prompt)
    history = [{'role': 'user', 'content': 'parent question'}, {'role': 'assistant', 'content': 'parent answer'}]
    db.append_messages_batch(parent.session_id, history)
    side = SideConversation(parent, history, require_durable=True)
    original_append = db.append_messages_batch
    def fail_child(session_id, *args, **kwargs):
        if session_id != parent.session_id:
            raise OSError('fixture disk full')
        return original_append(session_id, *args, **kwargs)
    monkeypatch.setattr(db, 'append_messages_batch', fail_child)
    try:
        with pytest.raises(SidePersistenceError, match='No side request was sent'):
            side.answer('side question')
        assert requests == []
        assert [m['content'] for m in db.get_messages_as_conversation(parent.session_id)] == [m['content'] for m in history]
    finally:
        side.close()
        parent.close()
        db.close()
