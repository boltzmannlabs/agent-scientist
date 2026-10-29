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
            assert fork._session_db is None and fork._persist_disabled
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
            side.close()
            assert side._agent is None
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

    url, requests, entered, release = provider
    parent = parent_agent(url)
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
    assert not parent._interrupt_requested
    with pytest.raises(ValueError, match='closed'):
        side.answer('no restart')
    parent.tools = [{'type': 'function', 'function': {'name': 'terminal', 'description': 'Fixture command',
                    'parameters': {'type': 'object', 'properties': {'command': {'type': 'string'}}, 'required': ['command']}}}]
    parent.valid_tool_names = {'terminal'}
    tool_side = SideConversation(parent, history)
    assert tool_side.answer('try-a-tool') == 'Fixture side answer.'
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
