"""Supplied inputs and code outputs keep their identity through delegation and resume."""
from copy import deepcopy
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Thread
from types import SimpleNamespace

import pytest

from agent.specialist_assignment import (
    evidence, persist, prepare, verified_artifacts,
)
from agent.specialist_policy import SpecialistPolicy, specialist_scope
from agent.specialist_store import Specialist, save
from sci_cli.config import atomic_config_replace
from sci_cli.native_profile_creation import profile_scope


def configure(home):
    home.mkdir(exist_ok=True)
    atomic_config_replace(home / 'config.yaml', {
        'platform_toolsets': {'cli': ['file', 'delegation', 'code_execution']},
        'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
        'terminal': {'env_type': 'local'},
        'code_execution': {'mode': 'project', 'timeout': 30},
        'delegation': {'max_iterations': 12, 'max_spawn_depth': 2},
    })


def test_code_artifact_provenance_survives_resume_and_profile_switches(tmp_path, monkeypatch):
    from tools.registry import registry
    from model_tools import discover_builtin_tools
    from tools.code_kernel import shutdown_all_kernels
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    discover_builtin_tools()
    homes = [tmp_path / 'a', tmp_path / 'b']
    for home in homes:
        configure(home)
    previous = None
    multiplex = set_multiplex_context(True)
    try:
        for index, home in enumerate([*homes, homes[0]]):
            with profile_scope(home):
                source = home / 'supplied table.csv'
                source.write_text('id,value\nA,1\n', encoding='utf-8')
                output = home / f'output-{index}.json'
                parent = SimpleNamespace(_specialist_snapshot={},
                    _specialist_user_request=f'Analyze "{source}" and preserve it.')
                prepare(parent, [{'specialist': 'lead', 'artifacts': [str(source)]}], {'inputs': [str(source)]})
                persist(parent)
                assignment = parent._specialist_assignment
                assert verified_artifacts(assignment, [str(source)]) == (str(source),)
                policy = SpecialistPolicy('worker', str(home), 'fixture', frozenset({'execute_code'}),
                    frozenset(), frozenset(), ('lead', 'worker'), float('inf'), assignment=assignment,
                    owner_multiplex=True)
                worker = SimpleNamespace(_specialist_policy=policy)
                code = (f'import json, sys\nfrom pathlib import Path\n'
                        f'Path({str(output)!r}).write_text("created once", encoding="utf-8")\n'
                        'print("harmless stderr", file=sys.stderr)\n'
                        f'print(json.dumps({{"files_modified": [{str(output)!r}], "detail": "x" * 1010000}}))')
                with specialist_scope(policy):
                    result = json.loads(registry.dispatch('execute_code', {'code': code}, task_id=f'file-test-{index}'))
                    assert result['status'] == 'success', result
                    assert not result.get('assignment_evidence_warning'), result
                    assert result['files_modified'] == [str(output)]
                    assert result['stdout_truncated']
                    assert verified_artifacts(assignment, [str(source), str(output)]) == (str(source), str(output))
                    recorded = evidence(worker)['recorded_effects']
                    assert recorded[0]['sha256'] == hashlib.sha256(output.read_bytes()).hexdigest()
                    assert recorded[0]['producer_tool'] == 'execute_code'
                    completed = home / 'saved-before-error.json'
                    failed = json.loads(registry.dispatch('execute_code', {'code':
                        f'Path({str(completed)!r}).write_text("42", encoding="utf-8")\n'
                        f'print(json.dumps({{"files_modified": [{str(completed)!r}]}}))\n'
                        'raise RuntimeError("after saving the output")'}, task_id=f'file-test-{index}'))
                    assert failed['status'] == 'error' and failed['error']
                    assert verified_artifacts(assignment, [str(completed)]) == (str(completed),)
                    assert evidence(worker)['recorded_effects'][-1]['producer_status'] == 'error'
                    # A path mentioned in prose is not a declared output.
                    unrelated = home / 'unrelated.txt'
                    unrelated.write_text('historical', encoding='utf-8')
                    registry.dispatch('execute_code', {'code': f'print({str(unrelated)!r})'}, task_id=f'file-test-{index}')
                    with pytest.raises(ValueError, match='not a frozen input'):
                        verified_artifacts(assignment, [str(unrelated)])
                    invalid = json.loads(registry.dispatch('execute_code', {
                        'code': 'print(\'{"files_modified": ["relative.json"]}\')'}, task_id=f'file-test-{index}'))
                    assert invalid['status'] == 'success' and invalid.get('assignment_evidence_warning'), invalid
                    before = evidence(worker)['recorded_effects']
                    with monkeypatch.context() as unattended:
                        unattended.setenv('SCI_SINGLE_QUERY_SESSION', '1')
                        blocked = json.loads(registry.dispatch('execute_code', {'code': code}, task_id=f'file-test-{index}'))
                    assert blocked.get('error'), blocked
                    assert evidence(worker)['recorded_effects'] == before
                    from agent.specialist_assignment import record_artifacts
                    raw = home / 'original-result.bin'
                    raw.write_bytes(b'original service result')
                    record_artifacts([str(raw)], job_id='fixture')
                    declaration = {'code': f'import json; print(json.dumps({{"files_modified": [{str(raw)!r}]}}))'}
                    registry.dispatch('execute_code', declaration, task_id=f'file-test-{index}')
                    raw.write_bytes(b'changed service result')
                    refused = json.loads(registry.dispatch('execute_code', declaration, task_id=f'file-test-{index}'))
                    assert refused.get('assignment_evidence_warning'), refused
                    with pytest.raises(ValueError, match='bytes changed'):
                        verified_artifacts(assignment, [str(raw)])
                restored = SimpleNamespace(_specialist_snapshot={})
                # Preparing execution after an informational pass keeps its ID and outputs.
                prepare(parent, [{'specialist': 'lead'}], {'inputs': [str(source)],
                    'tool_arguments': {'fixture': {'value': 42}}})
                assert parent._specialist_assignment.id == assignment.id
                assignment = parent._specialist_assignment
                receipt = home / 'subagent-runs' / f'assignment-{assignment.id}.json'
                receipt.write_bytes(b'\xef\xbb\xbf' + receipt.read_bytes())
                prepare(restored, [{'specialist': 'lead'}], {'resume': assignment.id,
                    'inputs': [str(source), str(output)], 'tool_arguments': {}, 'max_submissions': {}})
                assert restored._specialist_assignment == assignment
                nested = SimpleNamespace(_specialist_policy=SimpleNamespace(assignment=assignment))
                prepare(nested, [{'specialist': 'worker'}], {'resume': assignment.id,
                    'inputs': [str(source), str(output)], 'tool_arguments': {}, 'max_submissions': {}})
                assert nested._specialist_assignment == assignment
                with pytest.raises(ValueError, match='parameters or limits'):
                    prepare(restored, [{'specialist': 'lead'}], {'resume': assignment.id,
                        'tool_arguments': {'fixture': {'value': 99}}})
                with pytest.raises(ValueError, match='not a frozen input'):
                    prepare(restored, [{'specialist': 'lead'}], {'resume': assignment.id,
                        'inputs': [str(unrelated)]})
                with pytest.raises(ValueError, match='parameters or limits'):
                    prepare(restored, [{'specialist': 'lead'}], {'resume': assignment.id,
                        'max_submissions': {'fixture': 2}})
                assert verified_artifacts(assignment, [str(output)]) == (str(output),)
                if previous:
                    with pytest.raises(ValueError, match='not a frozen input'):
                        verified_artifacts(assignment, [str(previous)])
                output.write_text('changed', encoding='utf-8')
                with pytest.raises(ValueError, match='bytes changed'):
                    verified_artifacts(assignment, [str(output)])
                output.unlink()
                with pytest.raises(ValueError, match='unavailable'):
                    verified_artifacts(assignment, [str(output)])
                previous = unrelated
    finally:
        shutdown_all_kernels()
        reset_multiplex_context(multiplex)


@pytest.mark.parametrize('csv_text,expected,partial', [
    ('id,value\nA,10\nB,\nA,10\n', (3, 1, 1), False),
    ('id,value,group\nA,10,x\nB,,y\nC,30,\nA,10,x\n', (4, 2, 1), False),
    ('id,value,group\nA,,\nB,20,x\nA,,\n', (3, 4, 1), True),
])
def test_real_hierarchy_hands_off_exact_code_outputs_and_resumes_without_reanalysis(
        tmp_path, monkeypatch, csv_text, expected, partial):
    from run_agent import AIAgent
    from agent.specialist_runs import history
    from tools.code_kernel import shutdown_all_kernels
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    home = tmp_path / 'profile'
    configure(home)
    source = tmp_path / 'input panel.csv'
    source.write_text(csv_text, encoding='utf-8')
    input_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    reader, reviewer, final = [tmp_path / p for p in ('reader.json', 'reviewer.json', 'final.md')]
    requests, fixture_errors, executions, prefixes = [], [], [], {}
    phase = {'resume': False, 'assignment': None}
    calculation = '''import csv, hashlib, json
from pathlib import Path
source = Path(SOURCE)
with source.open(encoding='utf-8', newline='') as f:
    rows = list(csv.reader(f))
data = {'data_rows': len(rows)-1, 'columns': rows[0],
        'empty_cells': sum(cell == '' for row in rows[1:] for cell in row),
        'duplicate_rows': len(rows)-1-len({tuple(row) for row in rows[1:]}),
        'source_path': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
REVIEW
Path(OUTPUT).write_text(json.dumps(data), encoding='utf-8')
print(json.dumps({'files_modified': [OUTPUT], 'findings': data}))
'''.replace('SOURCE', repr(str(source)))

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                self.respond()
            except Exception as exc:
                fixture_errors.append(repr(exc))
                self.send_error(400, 'Controlled fixture error')

        def respond(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if 'messages' not in payload:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', '2')
                self.end_headers()
                self.wfile.write(b'{}')
                return
            requests.append(payload)
            prompt = str(payload['messages'][0]['content'])
            match = re.search(r'Saved specialist: ([\w-]+)', prompt)
            name = match[1] if match else 'main'
            prefixes.setdefault((name, phase['resume']), []).append(payload['messages'][0])
            results = [m for m in payload['messages'] if m['role'] == 'tool']
            for row in results:
                data = json.loads(row['content'])
                assert not data.get('error'), data
            tool, args = None, {}
            if name == 'main' and not results:
                args = {'tasks': [{'specialist': 'lead', 'goal': 'Complete the reader, reviewer and final report workflow.',
                                  'artifacts': [str(source)]}]}
                if phase['resume']:
                    args['assignment'] = {'resume': phase['assignment'], 'inputs': [str(source), str(reader)],
                                          'tool_arguments': {}, 'max_submissions': {}}
                tool = 'delegate_task'
            elif name == 'lead':
                if not results and not phase['resume']:
                    tool, args = 'delegate_task', {'tasks': [{'specialist': 'reader', 'goal': 'Calculate the requested CSV counts.',
                        'artifacts': [str(source)], 'delivery': 'intermediate'}]}
                elif (not results and phase['resume']) or (len(results) == 1 and not partial):
                    tool, args = 'delegate_task', {'tasks': [{'specialist': 'reviewer', 'goal': 'Check the exact reader report.',
                        'artifacts': [str(source), str(reader)], 'delivery': 'intermediate'}]}
                elif len(results) == (1 if phase['resume'] else 2):
                    tool, args = 'write_file', {'path': str(final), 'content': 'Requested CSV findings are in reader.json and reviewer.json.\n'}
            elif name in {'reader', 'reviewer'} and not results:
                executions.append(name)
                check = f"assert data == json.loads(Path({str(reader)!r}).read_text(encoding='utf-8-sig'))" if name == 'reviewer' else ''
                tool, args = 'execute_code', {'code': calculation.replace('REVIEW', check).replace('OUTPUT', repr(str(reader if name == 'reader' else reviewer)))}
            message = {'role': 'assistant', 'content': f'{name}: saved requested results.'}
            finish = 'stop'
            if tool:
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'{name}-{len(results)}',
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
            self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with profile_scope(home):
            for name in ('reader', 'reviewer'):
                save(Specialist(name, 'Calculate and report the assigned CSV.', tools=('read_file', 'execute_code'), automatic=False))
            save(Specialist('lead', 'Manage the complete CSV workflow.', tools=('read_file', 'write_file'),
                            children=('reader', 'reviewer'), automatic=True))
            settings = dict(model='fixture', provider='custom', api_key='fixture',
                base_url=f'http://127.0.0.1:{server.server_port}/v1', enabled_toolsets=['file', 'delegation', 'code_execution'],
                quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=12)
            for recovering in ([False, True] if partial else [False]):
                phase['resume'] = recovering
                parent = AIAgent(**settings)
                try:
                    result = parent.run_conversation(f'Use my saved specialist lead through delegate_task. Analyze "{source}"; produce reader, reviewer and final report.')
                    assert not fixture_errors, '\n'.join(fixture_errors)
                    assert not result.get('failed'), result
                    current = parent._specialist_assignment.id
                    assert phase['assignment'] in (None, current)
                    phase['assignment'] = current
                    if partial and not recovering:
                        assert reader.exists() and not reviewer.exists()
                finally:
                    parent.close()
            for path in (reader, reviewer):
                data = json.loads(path.read_text(encoding='utf-8-sig'))
                assert tuple(data[k] for k in ('data_rows', 'empty_cells', 'duplicate_rows')) == expected
                assert data['source_sha256'] == input_hash
            assert final.exists() and executions == ['reader', 'reviewer']
            assert hashlib.sha256(source.read_bytes()).hexdigest() == input_hash
            runs = history()
            assert {r['assignment_id'] for r in runs} == {phase['assignment']}
            for prompts in prefixes.values():
                assert all(p == prompts[0] for p in prompts)
            assert not fixture_errors
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)
        shutdown_all_kernels()
