"""Real child construction + HTTP provider adapter + transcript/receipt, with a loopback model fixture."""
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading


from agent.specialist_store import Specialist, save
from sci_constants import get_sci_home


@contextmanager
def model_server():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            result = {'id': 'fixture-response', 'object': 'chat.completion', 'model': 'fixture-model',
                      'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'Verified fixture result: 2 + 2 = 4.'},
                                   'finish_reason': 'stop'}],
                      'usage': {'prompt_tokens': 40, 'completion_tokens': 12, 'total_tokens': 52}}
            if payload.get('stream'):
                chunks = [
                    {'id': 'fixture-response', 'object': 'chat.completion.chunk', 'model': 'fixture-model',
                     'choices': [{'index': 0, 'delta': {'role': 'assistant', 'content': 'Verified fixture result: 2 + 2 = 4.'}, 'finish_reason': None}]},
                    {'id': 'fixture-response', 'object': 'chat.completion.chunk', 'model': 'fixture-model',
                     'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}], 'usage': result['usage']},
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
    with model_server() as (url, calls):
        atomic_config_replace(home / 'config.yaml', {
            'model': {'default': 'fixture-model', 'provider': 'custom', 'base_url': url, 'context_length': 131072},
            'tool_search': {'enabled': 'off'}, 'delegation': {'max_iterations': 3, 'child_timeout_seconds': 120},
            'agent': {'max_iterations': 3}, 'memory': {'enabled': False},
        })
        saved = save(Specialist('calculator', 'Check arithmetic supplied in the assignment', automatic=True,
                                tools=('browser_back',), max_iterations=3, timeout_seconds=120))
        db = SessionDB(home / 'state.db')
        parent = AIAgent(model='fixture-model', provider='custom', api_key='fixture-key', base_url=url,
                         api_mode='chat_completions', enabled_toolsets=['file', 'delegation'],
                         quiet_mode=True, skip_context_files=True, skip_memory=True, session_db=db)
        try:
            parent._cached_system_prompt = 'Parent cached prompt must stay byte-stable.'
            before = json.dumps(parent.tools, sort_keys=True)
            parent._ensure_db_session()
            save(Specialist('later-reviewer', 'Added after the conversation started', automatic=True))
            resumed = AIAgent(model='fixture-model', provider='custom', api_key='fixture-key', base_url=url,
                              api_mode='chat_completions', enabled_toolsets=['file', 'delegation'],
                              quiet_mode=True, skip_context_files=True, skip_memory=True, session_db=db,
                              session_id=parent.session_id)
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
            assert calls and not calls[-1].get('tools')
            assert 'Unavailable tools in this conversation: browser_back' in json.dumps(calls)
            assert parent._cached_system_prompt == 'Parent cached prompt must stay byte-stable.'
            assert json.dumps(parent.tools, sort_keys=True) == before
            rows = history()
            assert len(rows) == 1 and rows[0]['status'] == 'completed'
            assert Path(rows[0]['transcript']).is_file()
            assert rows[0]['result']['summary']
            # Editing/disable blocks a subsequent spawn without a single provider request.
            save(replace(saved, enabled=False), expected_revision=saved.revision)
            count = len(calls)
            result = json.loads(delegate_task(tasks=[{'specialist': 'calculator', 'goal': 'Calculate two plus two'}],
                                              parent_agent=parent))
            assert 'error' in result and len(calls) == count
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
