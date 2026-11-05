"""A private Add_tool request uses a separate real model conversation, not the parent queue."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
import json
import shlex
import sys
import threading

import pytest

from agent.specialist_store import Specialist
from agent.specialist_extensions import capability_scope
from sci_cli.specialist_private_setup import setup, prepare_home
from sci_cli.specialist_tool_setup import add_tool


class UI:
    def __init__(self, answers):
        self.answers, self.messages = iter(answers), []
    def ask(self, question, *args, **kwargs):
        from sci_cli.skill_add import Cancelled
        answer = next(self.answers)
        if answer == 'Cancel':
            raise Cancelled()
        return answer
    def choose(self, question, choices):
        answer = self.ask(question)
        assert answer in choices, (question, answer, choices)
        return answer
    def show(self, message):
        self.messages.append(message)


@contextmanager
def server(plan):
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            step = len(calls)
            calls.append(request)
            message = {'role': 'assistant', 'content': 'Private fixture integration prepared. No business tool was executed.'}
            finish = 'stop'
            if step < len(plan):
                name, arguments = plan[step]
                message = {'role': 'assistant', 'content': None, 'tool_calls': [
                    {'index': 0, 'id': f'fixture-{step}', 'type': 'function',
                     'function': {'name': name, 'arguments': json.dumps(arguments)}}]}
                finish = 'tool_calls'
            chunks = [{'id': 'fixture', 'object': 'chat.completion.chunk', 'model': 'fixture',
                       'choices': [{'index': 0, 'delta': message, 'finish_reason': None}]},
                      {'id': 'fixture', 'object': 'chat.completion.chunk', 'model': 'fixture',
                       'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}],
                       'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}}]
            raw = (''.join('data: ' + json.dumps(chunk) + '\n\n' for chunk in chunks) + 'data: [DONE]\n\n').encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    http = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{http.server_port}/v1', calls
    finally:
        http.shutdown()
        http.server_close()
        thread.join(5)


def test_private_add_tool_model_setup_plugin_discovery_and_no_parent_mutation(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from run_agent import AIAgent
    from sci_constants import get_sci_home
    from tools.registry import registry
    import model_tools
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    owner = get_sci_home()
    atomic_config_replace(owner / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'delegation']}})
    item, home = prepare_home(Specialist('reviewer', 'Review fixture', automatic=True))
    config = read_user_config_raw(home / 'config.yaml')
    config['plugins']['enabled'] = ['private-fixture']
    config['tool_search'] = {'enabled': 'off'}
    plugin = home / 'plugins' / 'private-fixture'
    module = """def register(ctx):
    ctx.register_tool(name='private_fixture_echo', toolset='private-fixture',
        schema={'name':'private_fixture_echo','description':'Harmless fixture echo','parameters':{'type':'object','properties':{}}},
        handler=lambda args: '{"ok":true}')
"""
    repo = Path(__file__).resolve().parents[2]
    code = (f'import sys;sys.path.insert(0,{str(repo)!r});'
            'from sci_cli.config import atomic_config_replace;from pathlib import Path;'
            f'atomic_config_replace(Path({str(home / "config.yaml")!r}),{config!r})')
    plan = [('read_file', {'path': str(home / 'config.yaml')}),
            ('write_file', {'path': str(plugin / 'plugin.yaml'), 'content': 'name: private-fixture\nversion: 1.0.0\ndescription: Fixture\nprovides_tools: [private_fixture_echo]\n'}),
            ('write_file', {'path': str(plugin / '__init__.py'), 'content': module}),
            ('terminal', {'command': shlex.join([sys.executable, '-c', code]), 'timeout': 30})]
    with server(plan) as (url, calls):
        parent = AIAgent(model='fixture', provider='custom', api_key='fixture-key', base_url=url,
                         api_mode='chat_completions', enabled_toolsets=['file', 'delegation'],
                         quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=3)
        try:
            from tools.terminal_tool import set_approval_callback
            set_approval_callback(lambda *a, **k: 'once')
            parent._cached_system_prompt = 'Parent cache stays frozen'
            before = json.dumps(parent.tools, sort_keys=True), (owner / 'config.yaml').read_bytes()
            resolved = list(model_tools._last_resolved_tool_names)
            from gateway.session_context import get_session_env
            session_before = get_session_env('SCI_SESSION_ID')
            cli = SimpleNamespace(agent=parent, _init_agent=lambda: True, _pending_agent_seed=None)
            ui = UI(['Add tool (link or request)', 'add this tool: https://example.org/fixture',
                     'Start private tool setup', 'Review private additions', 'Select all', 'Done'])
            result = setup(cli, ui, item)
            assert result.private_tools == ('private_fixture_echo',)
            assert len(calls) == len(plan) + 1
            assert 'Parent cache stays frozen' not in json.dumps(calls)
            assert cli._pending_agent_seed is None
            assert parent._cached_system_prompt == 'Parent cache stays frozen'
            assert (json.dumps(parent.tools, sort_keys=True), (owner / 'config.yaml').read_bytes()) == before
            assert registry.get_entry('private_fixture_echo') is None
            with capability_scope(home):
                assert json.loads(registry.dispatch('private_fixture_echo', {}))['ok']
            assert model_tools._last_resolved_tool_names == resolved
            assert get_session_env('SCI_SESSION_ID') == session_before
        finally:
            set_approval_callback(None)
            parent.close()


def test_private_add_tool_cancel_makes_no_model_request(tmp_path):
    from sci_cli.skill_add import Cancelled
    parent = SimpleNamespace(model='fixture', provider='custom', base_url='https://unused.example/v1',
                             api_key='fixture-key', request_overrides={})
    cli = SimpleNamespace(agent=parent, _init_agent=lambda: True)
    destination = tmp_path / 'private-destination'
    with pytest.raises(Cancelled):
        add_tool(cli, UI(['add a tool', 'Cancel']), destination)
    assert not destination.exists()
