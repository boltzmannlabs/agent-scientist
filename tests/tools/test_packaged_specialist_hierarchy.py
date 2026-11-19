"""#54: install a wheel-catalog hierarchy and execute private MCP children with real agents."""
import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import shutil
import sys
from threading import Thread
from types import SimpleNamespace

import pytest
import sci_yaml as yaml

from agent.specialist_store import load
from sci_cli.config import atomic_config_replace
from sci_cli.native_profile_creation import profile_scope

pytestmark = pytest.mark.usefixtures('released_sci_version')


@contextmanager
def model_server():
    routes, calls = {}, []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            try:
                self.respond()
            except Exception as exc:
                calls.append({'fixture_error': str(exc)})
                self.send_error(400, 'Controlled model fixture failed')

        def respond(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            calls.append(request)
            name = re.search(r'Saved specialist: ([\w-]+)', request['messages'][0]['content'])[1]
            results = [m for m in request['messages'] if m['role'] == 'tool']
            tool, args = routes[name]
            if results:
                text = results[-1]['content']
                try:
                    result = json.loads(text)
                except (ValueError, TypeError):
                    result = None  # MCP text results are already flattened by the real handler.
                if isinstance(result, dict) and 'results' in result:
                    text = result['results'][0]['summary']
                message, finish = {'role': 'assistant', 'content': str(text)}, 'stop'
            else:
                if tool not in {t['function']['name'] for t in request.get('tools', [])}:
                    args, tool = {'calls': [{'name': tool, 'arguments': args}]}, 'tool_call'
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': 'fixture-call',
                    'type': 'function', 'function': {'name': tool, 'arguments': json.dumps(args)}}]}
                finish = 'tool_calls'
            response = {'id': 'fixture', 'object': 'chat.completion', 'created': 1, 'model': 'fixture',
                'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                'usage': {'prompt_tokens': 20, 'completion_tokens': 10, 'total_tokens': 30}}
            if request.get('stream'):
                delta = dict(message)
                if 'tool_calls' in delta:
                    delta['tool_calls'] = [{**delta['tool_calls'][0], 'index': 0}]
                response.update(object='chat.completion.chunk', choices=[{'index': 0, 'delta': delta, 'finish_reason': finish}])
                raw = ('data: ' + json.dumps(response) + '\n\ndata: [DONE]\n\n').encode()
            else:
                raw = json.dumps(response).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if request.get('stream') else 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            self.end_headers(); self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', routes, calls
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


class UI:
    def show(self, value):
        pass

    def ask(self, *args, **kwargs):
        return sys.executable

    def choose(self, question, choices):
        return 'Done' if 'Done' in choices else choices[0]


def test_wheel_hierarchy_executes_nested_private_mcp_a_b_a(tmp_path, monkeypatch):
    import sci_cli.subagent_package_catalog as catalog
    from sci_cli import callbacks
    from sci_cli.specialist_commands import dispatch
    from sci_cli.subagent_package_io import LOCK, checksums
    from sci_cli.subagent_package_schema import validate
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from agent.specialist_extensions import extension_home
    from agent.specialist_runs import history
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task
    from tools.mcp_tool_lifecycle import shutdown_mcp_servers

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    source, snapshot = tmp_path / 'sources', tmp_path / 'catalog.json'
    template = Path(__file__).resolve().parents[2] / 'contribution-templates/subagent'
    encoded = {}
    for name, children in (('reader', []), ('coordinator', ['reader']), ('lead', ['coordinator'])):
        root = source / name
        shutil.copytree(template, root)
        manifest = yaml.safe_load((root / 'manifest.yaml').read_text())
        manifest.update(schema_version=2, id=name, name=name,
            automatic=name == 'lead',
            children=[{'role': n, 'package': n, 'version': '>=1,<2'} for n in children],
            tools=['delegate_task'] if children else ['mcp:echo/lookup'])
        manifest['limits'].update(timeout_seconds=0, max_iterations=12)
        (root / 'instructions.md').write_text('ROLE_' + name + (' delegate to {{child.' + children[0] + '}}' if children else ' use the selected lookup'))
        if not children:
            (root / 'tests/server.py').write_text('''import json, sys, os
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 if m['method']=='initialize': r={'protocolVersion':m['params']['protocolVersion'],'capabilities':{'tools':{}},'serverInfo':{'name':'echo','version':'1'}}
 elif m['method']=='tools/list': r={'tools':[{'name':'lookup','description':'Read the fixture value','inputSchema':{'type':'object','properties':{}}}]}
 elif m['method']=='tools/call': r={'content':[{'type':'text','text':'REFERENCE_'+os.environ['SERVICE_API_KEY']}]}
 else: r={}
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}),flush=True)
''')
            manifest['dependencies'] = [
                {'id': 'python', 'kind': 'program', 'version': sys.version.split()[0], 'version_args': ['--version'],
                 'version_contains': sys.version.split()[0], 'artifacts': []},
                {'id': 'echo', 'kind': 'mcp', 'tools': ['lookup'], 'config': {'command': '{{program.python}}',
                 'args': ['{{resource.tests/server.py}}'], 'env': {'SERVICE_API_KEY': '${SERVICE_API_KEY}'}}}]
        (root / 'manifest.yaml').write_text(yaml.safe_dump(manifest))
        value, files, digest = validate(root)
        files[LOCK] = json.dumps(checksums(files)).encode()
        encoded[name] = {'manifest': value, 'digest': digest,
                         'files': {path: base64.b64encode(data).decode() for path, data in files.items()}}
    snapshot.write_text(json.dumps(encoded))
    shutil.rmtree(source)  # Wheel install must not fall back to contributor source paths.
    monkeypatch.setattr(catalog, 'CATALOG', source)
    monkeypatch.setattr(catalog, 'SNAPSHOT', snapshot)
    a, b = tmp_path / 'a', tmp_path / 'b'
    monkeypatch.setenv('SCI_HOME', str(a))
    for home in (a, b):
        home.mkdir()
        atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'skills', 'delegation']},
            'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
            'delegation': {'max_spawn_depth': 3, 'max_iterations': 12}})
    secret = {'value': 'fixture-a'}
    monkeypatch.setattr(callbacks, 'prompt_for_secret', lambda *a, **k: {'success': True, 'value': secret['value']})
    token = set_multiplex_context(True)
    try:
        with model_server() as (url, routes, calls):
            for home in (a, b, a):
                with profile_scope(home):
                    if not (home / 'subagents/team.json').exists():
                        secret['value'] = 'fixture-' + home.name
                        dispatch(SimpleNamespace(agent=None), '/subagent package install catalog:lead --name team', UI())
                    lead = load('team')
                    middle, = [load(n) for n in lead.children]
                    reader, = [load(n) for n in middle.children]
                    tool, = [n for n in reader.private_tools if n.startswith('mcp__')]
                    routes.update({lead.name: ('delegate_task', {'tasks': [{'specialist': middle.name,
                        'goal': 'Retrieve REQUEST_MARKER=42', 'context': 'REQUEST_MARKER=42', 'delivery': 'intermediate'}]}),
                        middle.name: ('delegate_task', {'tasks': [{'specialist': reader.name,
                        'goal': 'Retrieve REQUEST_MARKER=42', 'context': 'REQUEST_MARKER=42', 'delivery': 'intermediate'}]}), reader.name: (tool, {})})
                    parent = AIAgent(model='fixture', provider='custom', api_key='fixture', base_url=url,
                        api_mode='chat_completions', platform='cli', enabled_toolsets=['file', 'skills', 'delegation'],
                        quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=12)
                    try:
                        parent._cached_system_prompt = 'Frozen parent prompt'
                        frozen = json.dumps(parent.tools, sort_keys=True)
                        assert tool not in parent.valid_tool_names
                        start = len(calls)
                        result = json.loads(delegate_task(tasks=[{'specialist': lead.name, 'goal': 'Retrieve REQUEST_MARKER=42'}], parent_agent=parent))
                        assert result['results'][0]['status'] == 'completed', result
                        assert 'REFERENCE_fixture-' + home.name in result['results'][0]['summary'], result
                        assert json.dumps(parent.tools, sort_keys=True) == frozen and parent._cached_system_prompt == 'Frozen parent prompt'
                        rows = history()
                        root_id = result['results'][0]['run_id']
                        family = [r for r in rows if r['run_id'] == root_id or r.get('root_run_id') == root_id]
                        assert len(family) == 3 and all(r['status'] == 'completed' for r in family)
                        assert not [r for r in calls[start:] if 'fixture_error' in r]
                        assert all('ROLE_' in request['messages'][0]['content'] for request in calls[start:])
                        assert (extension_home(reader) / '.env').exists() and not (home / '.env').exists()
                    finally:
                        parent.close()
    finally:
        shutdown_mcp_servers()
        reset_multiplex_context(token)
