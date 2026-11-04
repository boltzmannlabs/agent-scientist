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
def model_server():
    calls = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(payload)
            reply = ("I'll start by reading the instruction file to follow the required format."
                     if 'PLAN_ONLY_FIXTURE' in json.dumps(payload) else REPORT)
            message = {'role': 'assistant', 'content': reply}
            finish = 'stop'
            result = {'id': 'fixture-response', 'object': 'chat.completion', 'model': 'fixture-model',
                      'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                      'usage': {'prompt_tokens': 40, 'completion_tokens': 12, 'total_tokens': 52}}
            if payload.get('stream'):
                delta = dict(message)
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
