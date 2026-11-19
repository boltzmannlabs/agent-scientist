"""Whole hierarchy with real MCP, native Python/files and controlled Boltzmann responses.

No production model, network service, credentials or scientific submission is used.
"""
from copy import deepcopy
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import sys
from threading import Thread

from agent.specialist_store import Specialist, save
from sci_cli.config import atomic_config_replace
from sci_cli.native_profile_creation import profile_scope


def test_hybrid_hierarchy_finishes_and_resumes_without_repeating_scientific_work(tmp_path, monkeypatch):
    import model_tools  # noqa: F401 -- initialize real built-in handlers before fixture registration
    from agent.specialist_runs import history
    from plugins.boltzmann import _call, auth, preflight, tools
    from plugins.boltzmann.schemas import SCHEMAS
    from run_agent import AIAgent
    from tools.code_kernel import shutdown_all_kernels
    from tools.delegate_tool import delegate_task
    from tools.mcp_tool_discovery import discover_mcp_tools
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers
    from tools.registry import registry
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    home = tmp_path / 'profile'; home.mkdir()
    monkeypatch.setenv('SCI_HOME', str(home))
    monkeypatch.setenv('SCI_SINGLE_QUERY_SESSION', '1')
    from tools import approval, approval_context
    session_key = 'hybrid-authorized-code'
    approval_token = approval_context.set_current_session_key(session_key)
    approval.approve_session(session_key, 'execute_code')
    source = home / 'water.xyz'
    source.write_text('3\nwater\nO 0 0 0\nH 0 0 1\nH 0 1 0\n')
    original = source.read_bytes()
    output, report = home / 'outputs' / 'fixture.csv', home / 'audit.json'
    script = home / 'fixture_mcp.py'
    script.write_text('''import json, sys
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 if m['method']=='initialize': r={'protocolVersion':m['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}}
 elif m['method']=='tools/list': r={'tools':[{'name':'lookup','description':'Controlled reference lookup','inputSchema':{'type':'object','properties':{}}}]}
 elif m['method']=='tools/call': r={'content':[{'type':'text','text':'REFERENCE_VALUE=42'}]}
 else: r={}
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}),flush=True)
''')
    toolsets = ['file', 'code_execution', 'delegation', 'reference', 'boltzmann']
    atomic_config_replace(home / 'config.yaml', {
        'platform_toolsets': {'cli': [t for t in toolsets if t != 'reference']},
        'memory': {'enabled': False}, 'tool_search': {'enabled': 'on'},
        'terminal': {'backend': 'local', 'cwd': str(home)}, 'code_execution': {'mode': 'strict', 'timeout': 30},
        'delegation': {'max_iterations': 40, 'max_spawn_depth': 3, 'max_concurrent_children': 1},
        'mcp_servers': {'reference': {'command': sys.executable, 'args': [str(script)],
                                    'tools': {'include': ['lookup']}, 'sampling': {'enabled': False}}}})
    monkeypatch.setattr(auth, 'available', lambda: True)
    monkeypatch.setattr(tools, 'require_authorized', lambda: None)
    monkeypatch.setattr(tools, 'current_key', lambda: 'controlled-fixture')
    monkeypatch.setattr(preflight, 'current_key', lambda: 'controlled-fixture')
    uploads, submissions, status_calls, downloads, requests = [], [], [], [], []
    def upload(*args, **kwargs):
        uploads.append(args)
        return 'fixture/water.xyz'
    def submit(payload, job, name, **kwargs):
        submissions.append((payload, job, name))
        return 'fixture-job'
    def status(job, doc, **kwargs):
        status_calls.append((job, doc))
        return {'status': 'Success', 'job_name': job, 'doc_id': doc, 'job_terminal_confirmed': True,
                'OutputData': {'url': 'https://fixture.invalid/result.csv'}}
    def download(urls, folder, **kwargs):
        downloads.extend(urls)
        output.parent.mkdir(exist_ok=True)
        output.write_text('molecule,energy\nwater,-76\n')
        return {'output_paths': [str(output)]}
    monkeypatch.setattr(tools, 'file_upload', upload)
    monkeypatch.setattr(tools, 'submit_request', submit)
    monkeypatch.setattr(tools, 'fetch_status', status)
    monkeypatch.setattr(tools, 'download_from_signed_url', download)
    for schema in SCHEMAS:
        registry.register(name=schema['name'], toolset='boltzmann', schema=schema,
                          handler=partial(_call, getattr(tools, 'handle_' + schema['name'])), check_fn=lambda: True)
    job = 'Single_Point_Energy'
    payload = {'task_name': 'water', 'molecule_path': 'fixture/water.xyz', 'method': 'B3LYP',
               'basis': 'def2-TZVP', 'charge': 0, 'spin_multiplicity': '1', 'dispersion': 'D3BJ'}
    actions = {
        'director': [('delegate_task', {'tasks': [{'specialist': 'lead', 'goal': 'Perform all stages.', 'delivery': 'intermediate'}]})],
        'lead': [('delegate_task', {'tasks': [{'specialist': name, 'goal': goal, 'delivery': 'intermediate', **extra}]})
                 for name, goal, extra in [('reference', 'Retrieve the controlled reference.', {}),
                    ('runner', 'Run the frozen scientific step once.', {}),
                    ('auditor', 'Read the exact output, execute Python and finish the audit.', {'artifacts': [str(source), str(output)]})]],
        'reference': [('mcp__reference__lookup', {})],
        'runner': [('boltzmann_upload', {'job_name': job, 'input_field': 'molecule_path', 'local_path': str(source), 'allow_partial_validation': True}),
                   ('boltzmann_submit', {'job_name': job, 'experiment_name': 'hybrid-fixture', 'experiment_data': payload, 'allow_partial_validation': True}),
                   ('boltzmann_status', {'job_name': job, 'doc_id': 'fixture-job'}),
                   ('boltzmann_download', {'download_url': 'https://fixture.invalid/result.csv', 'output_folder': str(output.parent)})],
        'auditor': [('read_file', {'path': str(output)}), ('execute_code', {'code': 'print("PYTHON_CHECK", 6 * 7)'}),
                    ('write_file', {'path': str(report), 'content': '{"verdict":"IN_PROGRESS"}'}),
                    ('write_file', {'path': str(report), 'content': '{"verdict":"PASS"}'})],
    }
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(body)
            name = re.search(r'Saved specialist: ([\w-]+)', body['messages'][0]['content'])[1]
            results = [m for m in body['messages'] if m['role'] == 'tool']
            message = {'role': 'assistant', 'content': name + ': completed.'}
            finish = 'stop'
            if len(results) < len(actions[name]):
                tool, args = actions[name][len(results)]
                if tool not in {t['function']['name'] for t in body.get('tools', [])}:
                    args, tool = {'calls': [{'name': tool, 'arguments': args}]}, 'tool_call'
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'{name}-{len(results)}',
                    'type': 'function', 'function': {'name': tool, 'arguments': json.dumps(args)}}]}
                finish = 'tool_calls'
            response = {'id': 'fixture', 'object': 'chat.completion', 'model': 'fixture',
                'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
            if body.get('stream'):
                delta = deepcopy(message)
                if 'tool_calls' in delta:
                    delta['tool_calls'][0]['index'] = 0
                response['object'] = 'chat.completion.chunk'
                response['choices'][0] = {'index': 0, 'delta': delta, 'finish_reason': finish}
            raw = (('data: ' + json.dumps(response) + '\n\ndata: [DONE]\n\n') if body.get('stream') else json.dumps(response)).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if body.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with profile_scope(home):
            discover_mcp_tools(allowed_mcp_names=['mcp-reference'])
            save(Specialist('reference', 'Read external references.', tools=('mcp__reference__lookup',)))
            save(Specialist('runner', 'Execute the frozen job.', tools=tuple(schema['name'] for schema in SCHEMAS)))
            save(Specialist('auditor', 'Audit the actual result.', tools=('read_file', 'execute_code', 'write_file')))
            save(Specialist('lead', 'Coordinate sequential stages.', children=('reference', 'runner', 'auditor'), max_iterations=40))
            save(Specialist('director', 'Supervise the workflow.', children=('lead',), automatic=True, max_iterations=40))
            settings = dict(model='fixture', provider='custom', api_key='fixture', api_mode='chat_completions',
                base_url=f'http://127.0.0.1:{server.server_port}/v1', platform='cli', enabled_toolsets=toolsets,
                quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=40)
            parent = AIAgent(**settings)
            try:
                from agent.reporting import RESULT_REPORTING_GUIDANCE
                from agent.system_prompt import build_system_prompt
                main_prompt = build_system_prompt(parent)
                assert RESULT_REPORTING_GUIDANCE in main_prompt
                frozen = json.dumps(parent.tools, sort_keys=True)
                contract = {'inputs': [str(source)], 'max_submissions': {job: 1}, 'tool_arguments': {'boltzmann_submit': {
                    'job_name': job, 'experiment_name': 'hybrid-fixture',
                    'experiment_data': {**payload, 'molecule_path': {'$input': str(source)}}}}}
                result = json.loads(delegate_task(tasks=[{'specialist': 'director', 'goal': 'Run the hybrid workflow.'}],
                                                  assignment=contract, parent_agent=parent))
                assert result['results'][0]['status'] == 'completed', result
                rows = history()
                assert {row['specialist'] for row in rows} == set(actions) and all(row['status'] == 'completed' for row in rows), rows
                assert len(uploads) == len(submissions) == len(status_calls) == len(downloads) == 1
                assert submissions[0] == (payload, job, 'hybrid-fixture')
                assert source.read_bytes() == original and json.loads(report.read_text()) == {'verdict': 'PASS'}
                tool_results = '\n'.join(str(m['content']) for r in requests for m in r['messages'] if m['role'] == 'tool')
                assert 'REFERENCE_VALUE=42' in tool_results and 'PYTHON_CHECK 42' in tool_results
                assert 'assignment_evidence_warning' not in tool_results
                assert all(RESULT_REPORTING_GUIDANCE in r['messages'][0]['content'] for r in requests)
                assert build_system_prompt(parent) == main_prompt
                assert json.dumps(parent.tools, sort_keys=True) == frozen
                identity = next(row['assignment_id'] for row in rows)
                effects = json.loads((home / 'subagent-runs' / f'assignment-{identity}.json').read_text())['effects'].values()
                assert any(row.get('doc_id') == 'fixture-job' and row.get('terminal_confirmed') is True for row in effects)
            finally:
                parent.close()
            # Restart and use the same assignment to re-audit existing artifacts.
            actions['director'] = [('delegate_task', {'tasks': [{'specialist': 'lead', 'goal': 'Audit existing output.', 'delivery': 'intermediate'}]})]
            actions['lead'] = actions['lead'][-1:]
            parent = AIAgent(**settings)
            try:
                resumed = json.loads(delegate_task(tasks=[{'specialist': 'director', 'goal': 'Recover existing evidence.'}],
                                    assignment={'resume': identity}, parent_agent=parent))
                assert resumed['results'][0]['status'] == 'completed', resumed
                assert len(uploads) == len(submissions) == 1
                assert {row['assignment_id'] for row in history()} == {identity}
            finally:
                parent.close()
    finally:
        approval.clear_session(session_key)
        approval_context.reset_current_session_key(approval_token)
        shutdown_all_kernels()
        shutdown_mcp_servers()
        server.shutdown(); server.server_close(); thread.join(5)
