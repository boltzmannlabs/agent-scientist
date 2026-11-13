"""#53: script failures remain repairable without replaying completed work.

The local model fixture chooses inspection and repair after receiving recovery
guidance. Real tool dispatch and session kernels execute the scripts; no model
service or scientific service is contacted.
"""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest

from sci_cli.native_profile_creation import profile_scope

FAILURES = {
    "field": "record['specialist_ledger']",
    "column": "db.execute('SELECT created_at FROM messages').fetchall()",
    "message": "assert record['message']['content'] == 'Continue'",
    "anchor": "change_root_fields(record, {'metadata_status': 'complete'})",
    "attribute": "record.specialist_calls",
    "json": "json.loads('{')",
    "file": "(root / 'missing-tracking.json').read_text()",
    "type": "len(None)",
    "custom": "raise RuntimeError('Unrecognized fixture failure')",
}


def _scripts(root, failure):
    head = f"from pathlib import Path\nimport json, sqlite3, os\nroot = Path({str(root)!r})\n"
    helper = '''def change_root_fields(data, changes):
    if set(changes) - data.keys() and 'final_field' not in changes:
        raise ValueError('New fields require existing final field anchor in changes.')
    current = json.loads((root / 'campaign.json').read_text())
    if current != data:
        raise ValueError('Concurrent metadata change; inspect before retrying.')
    updated = dict(data, **changes)
    temporary = root / 'campaign.pending'
    temporary.write_text(json.dumps(updated))
    os.replace(temporary, root / 'campaign.json')
'''
    setup = head + helper + '''
assert os.environ['SCI_HOME'] == str(root.parent.parent)
assert globals().get('_fixture_profile', str(root.parent.parent)) == str(root.parent.parent)
_fixture_profile = str(root.parent.parent)
root.mkdir(parents=True, exist_ok=True)
counter = root / 'producer-count'
counter.write_text(str(int(counter.read_text()) + 1) if counter.exists() else '1')
(root / 'predictions.csv').write_text('id,solubility\\nfixture,0.8\\n')
record = {'step_id': 'fixture-step', 'execution_status': 'complete', 'specialist_calls': [],
          'message': {'id': 'message-1', 'role': 'user', 'content': 'Continue\\n'},
          'usage': {'status': 'unavailable', 'tokens': None}, 'final_field': 'unchanged'}
(root / 'campaign.json').write_text(json.dumps(record))
(root / 'helper.py').write_text(''' + repr(helper) + ''')
db = sqlite3.connect(root / 'tracking.sqlite')
db.execute('CREATE TABLE IF NOT EXISTS messages (id TEXT, timestamp REAL)')
db.commit()
''' + FAILURES[failure]
    inspect = head + '''
record = json.loads((root / 'campaign.json').read_text())
db = sqlite3.connect(root / 'tracking.sqlite')
print('INSPECTED', sorted(record), db.execute('PRAGMA table_info(messages)').fetchall())
print((root / 'helper.py').read_text())
print(record['message'])
'''
    repair = head + '''
record = json.loads((root / 'campaign.json').read_text())
assert record['step_id'] == 'fixture-step' and record['execution_status'] == 'complete'
assert isinstance(record['specialist_calls'], list)
assert record['message']['id'] == 'message-1' and record['message']['role'] == 'user'
assert record['message']['content'].rstrip('\\r\\n') == 'Continue'
exec((root / 'helper.py').read_text())
change_root_fields(record, {'final_field': record['final_field'], 'metadata_status': 'complete'})
assert (root / 'predictions.csv').read_text() == 'id,solubility\\nfixture,0.8\\n'
assert (root / 'producer-count').read_text() == '1'
print('REPAIRED', json.loads((root / 'campaign.json').read_text()))
'''
    return setup, inspect, repair


@pytest.mark.parametrize("failure", FAILURES)
def test_agent_inspects_repairs_and_continues_in_owning_profile_without_repeating_producer(tmp_path, monkeypatch, failure):
    from run_agent import AIAgent
    from sci_cli.config import atomic_config_replace
    from agent.secret_scope import set_multiplex_active
    from tools.code_kernel import shutdown_all_kernels
    requests, roots = [], []
    scenario = {}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            tools = [m for m in body['messages'] if m['role'] == 'tool']
            code, answer = None, 'Completed the task and repaired tracking.'
            if not tools:
                code = scenario['scripts'][0]
            else:
                value = json.loads(tools[-1]['content'])
                if value.get('status') == 'error':
                    if value.get('hint'):
                        code = scenario['scripts'][1]
                    else:
                        answer = 'Tracking failed; recovery guidance unavailable.'
                elif 'INSPECTED' in value.get('output', ''):
                    code = scenario['scripts'][2]
            message = {'role': 'assistant', 'content': answer}
            if code:
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{
                    'id': 'call-' + str(len(tools)), 'type': 'function',
                    'function': {'name': 'execute_code', 'arguments': json.dumps({'code': code})}}]}
            result = {'id': 'fixture', 'object': 'chat.completion', 'model': 'fixture',
                      'choices': [{'index': 0, 'message': message,
                                   'finish_reason': 'tool_calls' if code else 'stop'}],
                      'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}}
            raw = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f'http://127.0.0.1:{server.server_port}/v1'
    try:
        for index, name in enumerate(('a', 'b', 'a')):
            home = tmp_path / name
            with profile_scope(home):
                set_multiplex_active(True)
                atomic_config_replace(home / 'config.yaml', {
                    'code_execution': {'mode': 'strict'}, 'tool_search': {'enabled': 'off'},
                    'memory': {'enabled': False}, 'terminal': {'backend': 'local'}})
                root = home / 'workspace' / f'run-{index}'
                roots.append(root)
                scenario['scripts'] = _scripts(root, failure)
                parent = AIAgent(model='fixture', provider='custom', base_url=url, api_key='fixture',
                    api_mode='chat_completions', enabled_toolsets=['code_execution'],
                    quiet_mode=True, skip_memory=True, skip_context_files=True, max_iterations=5)
                parent._disable_streaming = True
                parent._cached_system_prompt = 'Complete the authorized fixture and repair its bookkeeping if needed.'
                prompt, schemas = parent._cached_system_prompt, deepcopy(parent.tools)
                start = len(requests)
                try:
                    result = parent.run_conversation('Run the controlled pipeline and finish its tracking.')
                    assert result['final_response'] == 'Completed the task and repaired tracking.', result
                    assert (root / 'producer-count').read_text() == '1'
                    assert (root / 'predictions.csv').read_text() == 'id,solubility\nfixture,0.8\n'
                    record = json.loads((root / 'campaign.json').read_text())
                    assert record['metadata_status'] == 'complete'
                    assert record['final_field'] == 'unchanged' and record['usage']['tokens'] is None
                    assert 'specialist_ledger' not in record
                    assert len(requests) - start == 4  # failed producer cell, inspect, repair, answer
                    assert all(sum(m['role'] == 'user' for m in r['messages']) == 1 for r in requests[start:])
                    prefix = [m for m in requests[start]['messages'] if m['role'] == 'system']
                    assert all([m for m in r['messages'] if m['role'] == 'system'] == prefix
                               and r.get('tools') == requests[start].get('tools') for r in requests[start:])
                    assert parent._cached_system_prompt == prompt and parent.tools == schemas
                finally:
                    parent.close()
        assert len({str(root) for root in roots}) == 3
    finally:
        set_multiplex_active(False)
        shutdown_all_kernels()
        server.shutdown()
        server.server_close()
        thread.join(5)
