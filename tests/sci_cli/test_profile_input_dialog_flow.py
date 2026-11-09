"""Real model transport → clarify → CLI form → answer, in main and native profiles."""

import json
import os
from pathlib import Path
import subprocess
import sys

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall, write_sci_home


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = r'''
import contextlib, ipaddress, json, socket, sys, threading
connect = socket.socket.connect
def loopback_only(sock, address):
    if isinstance(address, tuple) and not ipaddress.ip_address(address[0]).is_loopback:
        raise OSError('Only the test model is reachable')
    return connect(sock, address)
socket.socket.connect = loopback_only
with contextlib.redirect_stdout(sys.stderr):
    import sci_bootstrap
    from agent.memory_provider import spawn_context_thread
    from cli import SciCLI, CLI_CONFIG
    from sci_cli.tools_config import _get_platform_tools
    from tools.clarify_tool import INPUT_DIALOG_GUIDANCE
    instance = SciCLI(toolsets=sorted(_get_platform_tools(CLI_CONFIG, 'cli')), compact=True)
    shown = threading.Event()
    instance._paint_now = lambda: shown.set() if instance._clarify_state else None
    instance._ring_bell = lambda **kw: None
    assert instance._init_agent()
    assert 'clarify' in instance.agent.valid_tool_names
    assert not any(n.startswith(('boltzmann_', 'mcp_')) for n in instance.agent.valid_tool_names)
    outcome = {}
    frozen = None
    try:
        for cancelled in (False, True):
            shown.clear()
            def turn():
                try:
                    outcome['value'] = instance.agent.run_conversation(
                        'Collect inputs for the next sample workflow.',
                        conversation_history=instance.conversation_history, task_id=instance.session_id)
                except BaseException as exc:
                    outcome['error'] = repr(exc)
                    shown.set()
            thread = spawn_context_thread(turn, name='fixture-dialog-turn')
            thread.start()
            assert shown.wait(25), ('The model tool call never opened the input panel', outcome)
            assert 'error' not in outcome, outcome
            state = instance._clarify_state
            assert state and len(state['questions']) == 2
            assert instance._clarify_freetext and not state['choices']
            text_panel = ''.join(text for _, text in instance._get_clarify_display_fragments())
            assert 'Input label' in text_panel and 'Type your answer' in text_panel
            if cancelled:
                state['response_queue'].put(None)
                instance._clarify_teardown()
            else:
                instance._clarify_batch_lock(state, 'sample-user-input', meta={'kind': 'text'})
                assert not instance._clarify_freetext and state['active'] == 1
                picker = ''.join(text for _, text in instance._get_clarify_display_fragments())
                assert 'csv' in picker and 'json' in picker
                state['selected'] = 1
                instance._clarify_batch_enter(state)
            thread.join(25)
            assert not thread.is_alive() and 'error' not in outcome, outcome
            result = outcome['value']
            assert not result.get('failed'), result.get('final_response')
            instance.conversation_history = result['messages']
            reply = next(m for m in reversed(result['messages']) if m['role'] == 'tool' and m.get('name') == 'clarify')
            body = json.loads(reply['content'])
            if cancelled:
                assert body['outcome'] == 'cancelled'
                assert all(r['user_response'] is None for r in body['responses'])
            else:
                assert body['outcome'] == 'submitted'
                assert [r['user_response'] for r in body['responses']] == ['sample-user-input', 'json']
            assert INPUT_DIALOG_GUIDANCE in instance.agent._cached_system_prompt
            current = (instance.agent._cached_system_prompt, json.dumps(instance.agent.tools, sort_keys=True))
            if frozen is not None:
                assert current == frozen
            frozen = current
    finally:
        if instance._clarify_state:
            instance._clarify_state['response_queue'].put(None)
        instance.agent.close()
print(json.dumps({'dialogs': 2, 'cancelled_without_inputs': True}))
'''


def test_input_forms_round_trip_across_main_existing_and_new_profiles(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, read_user_config_raw

    root = tmp_path / '.sci'
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(root))
    homes = [root, root / 'profiles/a', root / 'profiles/b']
    questions = [{'question': 'Input label?'}, {'question': 'Output format?', 'choices': ['csv', 'json']}]
    def respond(record):
        messages = record['body']['messages']
        if messages[-1]['role'] == 'tool':
            return Text('Input collection complete; no workflow executed.')
        return ToolCall('clarify', {'questions': questions})

    with FakeLLMServer(respond) as server:
        for home in homes:
            write_sci_home(home, server.base_url)
            cfg = read_user_config_raw(home / 'config.yaml')
            cfg['platform_toolsets'] = {'cli': ['file', 'skills', 'no_mcp']}
            if home == homes[2]:
                cfg['platform_toolsets']['cli'].append('clarify')
            else:
                cfg.setdefault('agent', {})['disabled_toolsets'] = ['clarify']
            atomic_config_replace(home / 'config.yaml', cfg)
        before = {p: p.read_bytes() for home in homes for p in home.iterdir() if p.is_file()}
        for home in (root, homes[1], homes[2], homes[1]):
            env = {k: v for k, v in os.environ.items() if k in {'PATH', 'LANG', 'TZ', 'TMPDIR', 'SYSTEMROOT'}}
            env.update(HOME=str(tmp_path), SCI_HOME=str(home), SCI_DISABLE_LAZY_INSTALLS='1',
                       SCI_TEST_ISOLATION=str(root), SCI_STATE_DB_GUARD_BYPASS='1',
                       NO_PROXY='127.0.0.1,localhost')
            start = len(server.main_requests())
            result = subprocess.run([sys.executable, '-c', SCRIPT], cwd=ROOT, env=env,
                                    capture_output=True, text=True, timeout=80)
            assert result.returncode == 0, result.stderr[-6000:]
            assert json.loads(result.stdout)['cancelled_without_inputs']
            requests = server.main_requests()[start:]
            assert len(requests) == 4
            assert all(r['tools'] == requests[0]['tools'] for r in requests)
            systems = [[m for m in r['messages'] if m['role'] == 'system'] for r in requests]
            assert all(s == systems[0] for s in systems)
            # Only the input UI is exercised. There is no scientific submit, upload or auth request.
            calls = [c['function']['name'] for m in requests[-1]['messages'] for c in m.get('tool_calls', [])]
            assert calls and set(calls) == {'clarify'}
        assert all(p.read_bytes() == data for p, data in before.items())
