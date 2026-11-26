"""Controlled native orchestration regressions; scripted replies do not test LLM reasoning."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.usefixtures('released_sci_version')


@contextmanager
def scripted_model(reply):
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            request = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            requests.append(request)
            message, finish = reply(request)
            usage = {'prompt_tokens': 30, 'completion_tokens': 10, 'total_tokens': 40}
            if request.get('stream'):
                delta = dict(message)
                if delta.get('tool_calls'):
                    delta['tool_calls'] = [{**call, 'index': n} for n, call in enumerate(delta['tool_calls'])]
                chunks = [
                    {'id': 'fixture', 'object': 'chat.completion.chunk', 'model': 'fixture',
                     'choices': [{'index': 0, 'delta': delta, 'finish_reason': None}]},
                    {'id': 'fixture', 'object': 'chat.completion.chunk', 'model': 'fixture',
                     'choices': [{'index': 0, 'delta': {}, 'finish_reason': finish}], 'usage': usage},
                ]
                body = (''.join('data: ' + json.dumps(chunk) + '\n\n' for chunk in chunks)
                        + 'data: [DONE]\n\n').encode()
                content_type = 'text/event-stream'
            else:
                body = json.dumps({'id': 'fixture', 'object': 'chat.completion', 'model': 'fixture',
                    'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                    'usage': usage}).encode()
                content_type = 'application/json'
            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}/v1', requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def call_tool(request, name, arguments):
    direct = name in {row['function']['name'] for row in request.get('tools', [])}
    function = {'name': name, 'arguments': json.dumps(arguments)} if direct else {
        'name': 'tool_call', 'arguments': json.dumps({'calls': [{'name': name, 'arguments': arguments}]})}
    return {'role': 'assistant', 'content': None, 'tool_calls': [
        {'id': f"call-{len(request['messages'])}", 'type': 'function', 'function': function}]}, 'tool_calls'


@pytest.mark.parametrize('role', ['method', 'recovery'])
def test_installed_discovery_review_returns_to_parent_and_writes_artifact(tmp_path, monkeypatch, role):
    """Exercise package grants, native file discovery, intermediate delivery and parent execution."""
    from sci_cli.config import atomic_config_replace
    from sci_cli.subagent_package_install import install
    from sci_constants import get_sci_home
    from run_agent import AIAgent
    from agent.specialist_runs import history

    home = get_sci_home()
    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    catalog = tmp_path / 'approved-catalog'
    catalog.mkdir()
    contract = catalog / 'route.txt'
    contract.write_text('TOOL_CONTRACT\nroute=compatible\nrequires=whole-assembly\n')
    original = contract.read_bytes()
    output = tmp_path / 'review-result.json'
    specialist = f'installed-enzyme-{role}'
    decision = {'route': 'compatible', 'required_output': 'whole-assembly', 'execution': 'pending'}
    parent_replies = []

    def reply(request):
        tool_results = [m for m in request['messages'] if m.get('role') == 'tool']
        child = f'Saved specialist: {specialist}' in request['messages'][0]['content']
        if child:
            if not tool_results:
                return call_tool(request, 'search_files', {'path': str(catalog), 'pattern': 'TOOL_CONTRACT'})
            if len(tool_results) == 1:
                assert 'route.txt' in str(tool_results[0]['content'])
                return call_tool(request, 'read_file', {'path': str(contract)})
            assert 'requires=whole-assembly' in str(tool_results[-1]['content'])
            return {'role': 'assistant', 'content': json.dumps(decision)}, 'stop'
        parent_replies.append(len(tool_results))
        if not tool_results:
            return call_tool(request, 'delegate_task', {'tasks': [{'specialist': specialist,
                'goal': 'Inspect the approved catalog and return a compatible route.',
                'context': f'Approved catalog directory: {catalog}', 'delivery': 'intermediate'}]})
        if len(tool_results) == 1:
            assert 'whole-assembly' in str(tool_results[0]['content'])
            return call_tool(request, 'write_file', {'path': str(output), 'content': json.dumps(decision)})
        return {'role': 'assistant', 'content': f'Completed review. Artifact: {output}'}, 'stop'

    class ReviewChoices:
        def show(self, message):
            pass

        def choose(self, question, choices):
            approved = {'Prepare package', 'Save and enable for the next conversation'}
            return next(choice for choice in choices if choice in approved)

    with scripted_model(reply) as (url, requests):
        atomic_config_replace(home / 'config.yaml', {
            'model': {'default': 'fixture', 'provider': 'custom', 'base_url': url, 'context_length': 131072},
            'platform_toolsets': {'cli': ['file', 'skills', 'delegation', 'web']},
            'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
            'delegation': {'max_iterations': 8},
        })
        package = Path(__file__).resolve().parents[2] / 'subagent-catalog' / f'enzyme-{role}'
        item = install(package, home, SimpleNamespace(agent=None), ReviewChoices(), name=specialist)
        assert {'read_file', 'search_files', 'web_search', 'web_extract'} <= set(item.tools)
        assert item.timeout_seconds == 0
        parent = AIAgent(model='fixture', provider='custom', api_key='fixture', base_url=url,
            api_mode='chat_completions', platform='cli', enabled_toolsets=['file', 'skills', 'delegation', 'web'],
            quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=8)
        try:
            result = parent.run_conversation(f'Obtain the required review using {specialist}. Approved catalog: {catalog}.')
            assert output.is_file(), result
            assert json.loads(output.read_text()) == decision
            assert contract.read_bytes() == original
            rows = [row for row in history() if row['specialist'] == specialist]
            assert len(rows) == 1 and rows[0]['status'] == 'completed'
            record = rows[0]['result']
            assert record['delivery'] == 'intermediate'
            assert json.loads(record['summary']) == decision
            assert [entry['tool'] for entry in record['tool_trace']] == ['search_files', 'read_file']
            assert all(entry['status'] == 'ok' for entry in record['tool_trace'])
            assert parent_replies == [0, 1, 2]
            child_requests = [r for r in requests if f'Saved specialist: {specialist}' in r['messages'][0]['content']]
            assert child_requests and all('write_file' not in json.dumps(r.get('tools', [])) for r in child_requests)
        finally:
            parent.close()


def test_unknown_submission_survives_reopen_and_prevents_duplicate(tmp_path):
    """Use SCI's durable assignment receipt fingerprint, without submitting any remote job."""
    from agent.specialist_assignment import Assignment
    from plugins.boltzmann import receipt_store
    from agent.specialist_policy import SpecialistPolicy, specialist_scope
    from sci_constants import get_sci_home

    assignment = Assignment('enzyme-recovery-fixture', str(tmp_path / 'assignment-home'), 'Finish the original workflow',
                            json.dumps({'max_submissions': {}}))
    policy = SpecialistPolicy('recovery', str(get_sci_home()), 'fixture', frozenset(), frozenset(),
        frozenset(), ('recovery',), float('inf'), assignment=assignment)
    with specialist_scope(policy):
        payload = {'parent': 'frozen', 'measurement': 'required-endpoint'}
        first = receipt_store.ReceiptStore().begin_submission('fixture-tool', [], payload=payload)
        with pytest.raises(receipt_store.ReceiptStorageError, match='Reconcile that attempt'):
            receipt_store.ReceiptStore().begin_submission('fixture-tool', [], payload=dict(payload))
        record, = receipt_store.ReceiptStore().inspect()['records']
        assert record['id'] == first and record['state'] == 'unknown' and record['doc_id'] is None
        reopened = receipt_store.ReceiptStore()
        reopened.accept_submission(first, 'reconciled-original-id')
        with pytest.raises(receipt_store.ReceiptStorageError, match='reconciled-original-id'):
            reopened.begin_submission('fixture-tool', [], payload=payload)
        reopened.observe('fixture-tool', 'reconciled-original-id', {
            'status': 'success', 'job_terminal_confirmed': True,
            'job_name': 'fixture-tool', 'doc_id': 'reconciled-original-id'})
        # Native cleanup retires terminal attempts with no retained upload receipts.
        assert receipt_store.ReceiptStore().inspect()['records'] == []

def test_goal_pause_resume_preserves_objective_and_requirements():
    from sci_cli.goals import GoalContract, GoalManager
    from sci_cli.goal_command import dispatch_goal_command

    contract = GoalContract(outcome='Complete required assessments', verification='Inspect independent review and original artifacts')
    manager = GoalManager(session_id='enzyme-autonomy-fixture')
    kickoff = dispatch_goal_command(manager, 'Finish the existing enzyme workflow', authorize_gate=lambda: None)
    assert kickoff.kickoff and kickoff.prompt and not kickoff.error
    assert 'Finish the existing enzyme workflow' in kickoff.prompt
    manager.set_contract(contract)
    manager.pause('review temporarily unavailable')
    reopened = GoalManager(session_id='enzyme-autonomy-fixture')
    assert reopened.state.status == 'paused'
    assert reopened.next_continuation_prompt() is None
    reopened.resume(reset_budget=False)
    resumed = GoalManager(session_id='enzyme-autonomy-fixture')
    assert resumed.is_active()
    assert resumed.state.contract == contract
    assert resumed.state.goal == manager.state.goal
    assert resumed.next_continuation_prompt()


def test_completion_gate_rejects_missing_evidence_and_timed_out_review(tmp_path, monkeypatch):
    """A prose completion claim cannot bypass required artifacts or independent review."""
    import os
    import shlex
    import subprocess
    import sys
    from sci_cli import goals

    outcome = tmp_path / 'outcome.json'
    gate = tmp_path / 'verify.py'
    gate.write_text(
        "import json, pathlib, sys\n"
        "p = pathlib.Path(sys.argv[1])\n"
        "assert p.is_file(), 'Mandatory assessment is missing'\n"
        "r = json.loads(p.read_text())\n"
        "assert r['assessment_complete'] is True\n"
        "assert r['independent_review_status'] == 'completed', 'Independent review is unfinished'\n"
        "assert isinstance(r['qualifying_candidates'], int)\n"
    )
    manager = goals.GoalManager(session_id='enzyme-gated-completion')
    manager.set('Complete all mandatory assessments and independent review')
    arguments = [sys.executable, str(gate), str(outcome)]
    command = subprocess.list2cmdline(arguments) if os.name == 'nt' else shlex.join(arguments)
    manager.add_gate(command)
    judged = []

    def done(*args, **kwargs):
        judged.append(True)
        return 'done', 'All mandatory evidence is present', False, None, False

    monkeypatch.setattr(goals, 'judge_goal', done)
    first = manager.evaluate_after_turn('The entire workflow is complete.')
    assert first['verdict'] == 'gate_failed' and not judged
    assert first['should_continue'] is True
    outcome.write_text(json.dumps({'assessment_complete': True, 'independent_review_status': 'timeout',
                                   'qualifying_candidates': 0}))
    second = manager.evaluate_after_turn('The parent reviewed the result. Everything is complete.')
    assert second['verdict'] == 'gate_failed' and not judged
    assert second['should_continue'] is True
    outcome.write_text(json.dumps({'assessment_complete': True, 'independent_review_status': 'completed',
                                   'qualifying_candidates': 0}))
    final = manager.evaluate_after_turn('All required assessments and independent review completed with zero qualifiers.')
    assert judged and final['status'] == 'done'


def test_native_goal_exhausts_twenty_turns_and_resumes_same_contract(monkeypatch):
    from sci_cli import goals
    from sci_cli.goal_command import dispatch_goal_command

    monkeypatch.setattr(goals, 'judge_goal', lambda *a, **k: ('continue', 'Required review remains open', False, None, False))
    manager = goals.GoalManager(session_id='enzyme-twenty-turn-fixture', default_max_turns=20)
    dispatch_goal_command(manager, 'Finish the original workflow', authorize_gate=lambda: None)
    for _ in range(19):
        assert manager.evaluate_after_turn('Continuing the remaining work')['should_continue']
    exhausted = manager.evaluate_after_turn('The assessment remains open')
    assert exhausted['status'] == 'paused' and not exhausted['should_continue']
    assert manager.state.turns_used == manager.state.max_turns == 20
    reloaded = goals.GoalManager(session_id='enzyme-twenty-turn-fixture')
    result = dispatch_goal_command(reloaded, 'resume', authorize_gate=lambda: None)
    assert result.prompt and reloaded.is_active()
    assert reloaded.state.turns_used == 0 and reloaded.state.max_turns == 20
    assert reloaded.state.goal == manager.state.goal


def test_plain_goal_queue_uses_native_command_routing():
    from sci_cli.cli_tui_mixin import CLITuiMixin
    from sci_cli.cli_process_notifications import CLIProcessNotificationsMixin

    cli = SimpleNamespace(_seeded_first_message='/goal Complete the existing workflow', config={},
                          _install_tool_callbacks=lambda: None, _ensure_tirith_security=lambda: None)
    CLITuiMixin._tui_init_run_state(cli)
    queued = cli._pending_input.get_nowait()
    text, voice, seeded = CLIProcessNotificationsMixin._tui_unwrap_input(cli, queued)
    assert text.startswith('/goal ') and not voice and not seeded


def test_native_reviewer_timeout_resumes_original_assignment(tmp_path, monkeypatch):
    from dataclasses import replace
    from agent.specialist_store import Specialist, save
    from sci_cli.config import atomic_config_replace
    from sci_constants import get_sci_home
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task

    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    artifact = tmp_path / 'sealed.json'
    artifact.write_text(json.dumps({'assessment_complete': True, 'qualifying_candidates': 0}))
    original = artifact.read_bytes()
    release = threading.Event()
    blocked = {'value': True}
    report = 'Independent review complete. All required assessments ran; zero qualifying candidates.'

    def reply(request):
        outputs = [m for m in request['messages'] if m.get('role') == 'tool']
        if not outputs:
            return call_tool(request, 'read_file', {'path': str(artifact)})
        assert 'assessment_complete' in str(outputs[-1]['content'])
        if blocked['value']:
            release.wait(8)
        return {'role': 'assistant', 'content': report}, 'stop'

    with scripted_model(reply) as (url, requests):
        atomic_config_replace(get_sci_home() / 'config.yaml', {
            'model': {'default': 'fixture', 'provider': 'custom', 'base_url': url, 'context_length': 131072},
            'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
            'delegation': {'max_iterations': 4},
        })
        saved = save(Specialist('timeout-reviewer', 'Review the supplied artifact independently',
            instructions='Read the supplied artifact before returning the completed assessment.',
            tools=('read_file',), automatic=True, max_iterations=4, timeout_seconds=1))
        parent = AIAgent(model='fixture', provider='custom', api_key='fixture', base_url=url,
            api_mode='chat_completions', enabled_toolsets=['file', 'delegation'],
            quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=4)
        parent._specialist_user_request = 'Review the exact sealed artifact independently.'
        try:
            task = {'specialist': saved.name, 'goal': 'Review the exact sealed artifact.',
                    'artifacts': [str(artifact)], 'delivery': 'intermediate'}
            first = json.loads(delegate_task(tasks=[task], assignment={'inputs': [str(artifact)]}, parent_agent=parent))
            failed = first['results'][0]
            assert failed['status'] == 'timeout', first
            assert failed['assignment_id']
            assert any(any(m.get('role') == 'tool' and 'assessment_complete' in str(m.get('content'))
                           for m in request['messages']) for request in requests)
            blocked['value'] = False
            release.set()
            # Publish a reviewed deadline amendment and start a fresh parent snapshot for the same assignment.
            save(replace(saved, timeout_seconds=0), expected_revision=saved.revision)
            resumed_parent = AIAgent(model='fixture', provider='custom', api_key='fixture', base_url=url,
                api_mode='chat_completions', enabled_toolsets=['file', 'delegation'], quiet_mode=True,
                skip_context_files=True, skip_memory=True, max_iterations=4)
            resumed_parent._specialist_user_request = parent._specialist_user_request
            try:
                second = json.loads(delegate_task(tasks=[task], assignment={'resume': failed['assignment_id']}, parent_agent=resumed_parent))
                completed = second['results'][0]
                assert completed['status'] == 'completed', second
                assert completed['summary'] == report
                assert completed['assignment_id'] == failed['assignment_id']
                assert completed['run_id'] != failed['run_id']
                assert artifact.read_bytes() == original
                assert all('read_file' in json.dumps(request.get('tools', [])) for request in requests)
            finally:
                resumed_parent.close()
        finally:
            release.set()
            parent.close()


def test_http_accepted_503_reconciles_original_job_without_resubmission(monkeypatch):
    from agent.specialist_assignment import prepare
    from agent.specialist_policy import SpecialistPolicy, specialist_scope
    from plugins.boltzmann import tools, receipt_store, nodeapi_helpers
    from plugins.boltzmann.contracts import ValidationReport
    from sci_constants import get_sci_home

    posts = []
    reads = []
    original_id = 'fixture-original-accepted-job'

    class Backend(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            posts.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body = json.dumps({'message': 'Acknowledgement lost after acceptance'}).encode()
            self.send_response(503)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            reads.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))))
            body = json.dumps({'status': 'success', 'docId': original_id, 'job_name': 'fixture-tool'}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Backend)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        endpoint = f'http://127.0.0.1:{server.server_port}'
        monkeypatch.setattr(nodeapi_helpers, '_SUBMIT_URL', endpoint + '/submit')
        monkeypatch.setattr(nodeapi_helpers, '_FETCH_URL', endpoint + '/fetch')
        monkeypatch.setattr(tools, '_get_api_key', lambda: 'fixture-key')
        monkeypatch.setattr(tools, 'preflight_submission', lambda *a: ValidationReport())
        parent = SimpleNamespace(_specialist_snapshot={}, _specialist_user_request='Execute the authorized frozen assessment.')
        payload = {'frozen_input': 'fixture'}
        prepare(parent, [{'specialist': 'recovery'}], {
            'inputs': [], 'max_submissions': {'fixture-tool': 1},
            'tool_arguments': {'boltzmann_submit': {'job_name': 'fixture-tool', 'experiment_data': payload}},
        })
        assignment = parent._specialist_assignment
        policy = SpecialistPolicy('recovery', str(get_sci_home()), 'fixture', frozenset({'boltzmann_submit'}),
            frozenset(), frozenset(), ('recovery',), float('inf'), assignment=assignment)
        with specialist_scope(policy):
            first = json.loads(tools._handle_boltzmann_submit_inner(job_name='fixture-tool', experiment_data=payload))
            assert first['safe_to_retry'] is False and first['receipt_attempt_id']
            second = json.loads(tools._handle_boltzmann_submit_inner(job_name='fixture-tool', experiment_data=payload))
            assert second.get('submitted') is False or second.get('safe_to_retry') is False
            assert len(posts) == 1
            attempt = first['receipt_attempt_id']
            row, = receipt_store.ReceiptStore().inspect()['records']
            assert row['state'] == 'unknown' and row['doc_id'] is None
            # The controlled backend's acceptance record identifies this original calculation.
            receipt_store.ReceiptStore().accept_submission(attempt, original_id)
            result = nodeapi_helpers.fetch_status('fixture-tool', original_id, token='fixture-key', poll_once=True)
            assert result['status'].lower() == 'success'
            receipt_store.ReceiptStore().observe('fixture-tool', original_id, result)
            assert reads == [{'docId': original_id, 'job_name': 'fixture-tool'}]
            assert len(posts) == 1
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def test_environment_start_goal_persists_native_goal_in_selected_profile(tmp_path, monkeypatch):
    """Cross-repository check of the actual environment wrapper; no model request is made."""
    import importlib.util
    import hashlib
    import os
    import queue
    import shutil
    import sys

    environment = os.environ.get('ENZYME_ENVIRONMENT_SOURCE')
    if not environment:
        pytest.skip('Set ENZYME_ENVIRONMENT_SOURCE to exercise the separate environment launcher.')
    environment = Path(environment).resolve()
    wrapper = environment / 'scripts/start_goal.py'
    assert wrapper.is_file()
    source = Path(__file__).resolve().parents[2]
    from sci_cli.profiles import create_profile
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.config import atomic_config_replace
    from sci_cli.subagent_package_install import install
    from sci_cli.goals import GoalManager
    from sci_cli.cli_commands_mixin import CLICommandsMixin
    import cli

    profile = create_profile('enzyme-startup-fixture', no_skills=True, no_alias=True)
    config = {
        'goals': {'max_turns': 20},
        'model': {'default': 'fixture', 'provider': 'custom',
                  'base_url': 'http://127.0.0.1:1/v1', 'context_length': 131072},
        'memory': {'enabled': False},
    }
    atomic_config_replace(profile / 'config.yaml', config)
    coordinator = profile / 'skills/enzyme-coordinator'
    shutil.copytree(environment / 'src/skills/enzyme-coordinator', coordinator)

    class ReviewChoices:
        def show(self, message):
            pass

        def choose(self, question, options):
            reviewed = {'Prepare package', 'Save and enable for the next conversation'}
            return next(option for option in options if option in reviewed)

    with profile_scope(profile):
        for role in ('method', 'recovery', 'evaluator'):
            install(source / 'subagent-catalog' / f'enzyme-{role}', profile,
                    SimpleNamespace(agent=None), ReviewChoices(), name=f'enzyme-{role}')

    workspace = tmp_path / 'workflow'
    workspace.mkdir()
    goal = workspace / 'START_SCI_TASK.txt'
    objective = 'Complete the frozen task and independent review using actual evidence.'
    goal.write_text('/goal ' + objective)
    settings_file = tmp_path / 'settings.json'
    settings_file.write_text(json.dumps({'llm': {'model': 'fixture', 'provider': 'custom', 'reasoning_effort': 'xhigh'}}))
    settings_original = settings_file.read_bytes()
    manifest_path = workspace / 'PREPARED_LAUNCH.json'
    manifest = {
        'profile': 'enzyme-startup-fixture',
        'sci_source': str(source),
        'sci_python': str(Path(sys.executable).absolute()),
        'goal_sha256': hashlib.sha256(goal.read_bytes()).hexdigest(),
        'settings_path': str(settings_file),
        'config_sha256': hashlib.sha256(settings_original).hexdigest(),
        'model': 'fixture', 'provider': 'custom', 'reasoning': 'xhigh',
        'approach': 'agent_with_specialist',
    }
    manifest_path.write_text(json.dumps(manifest))
    observed = {'run_count': 0}

    def run_without_ui(self):
        from sci_constants import get_sci_home
        observed['run_count'] += 1
        observed['session_id'] = self.session_id
        assert Path.cwd() == workspace
        assert get_sci_home() == profile
        assert self.model == 'fixture'
        self.finalize_preloaded_skills()
        assert 'enzyme-coordinator' in self.preloaded_skills
        assert 'version: 1.2.0' in self.system_prompt
        assert isinstance(self._seeded_first_message, str)
        self._pending_input = queue.Queue()
        self.conversation_history = []
        manager = GoalManager(self.session_id, default_max_turns=20)
        self._session_manager = lambda factory, label: manager
        self._get_goal_manager = lambda: manager
        CLICommandsMixin._handle_goal_command(self, self._seeded_first_message)
        reopened = GoalManager(self.session_id)
        assert reopened.is_active() and reopened.state.max_turns == 20
        assert reopened.state.goal == objective
        assert self._pending_input.get_nowait()
        observed['saved_goal'] = reopened.state.goal
        observed['coordinator'] = coordinator.read_text() if coordinator.is_file() else (coordinator / 'SKILL.md').read_text()
        assert 'version: 1.2.0' in observed['coordinator']

    monkeypatch.setattr(cli.SciCLI, 'run', run_without_ui)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, 'argv', [str(wrapper), '--sci-source', str(source),
        '--profile', 'enzyme-startup-fixture', '--run-dir', str(workspace),
        '--goal-file', str(goal), '--model', 'fixture', '--provider', 'custom', '--assisted'])
    spec = importlib.util.spec_from_file_location('enzyme_environment_start_goal_fixture', wrapper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Both configuration tampering checks must fail before session construction.
    goal.write_text('/goal Changed objective')
    with pytest.raises(SystemExit) as changed_goal:
        module.main()
    assert changed_goal.value.code == 2 and observed['run_count'] == 0
    assert not (workspace / 'LAUNCH_INTENT.json').exists()
    goal.write_text('/goal ' + objective)
    manifest_path.write_text(json.dumps({**manifest, 'sci_source': str(tmp_path / 'foreign-source')}))
    with pytest.raises(SystemExit) as changed_source:
        module.main()
    assert changed_source.value.code == 2 and observed['run_count'] == 0
    assert not (workspace / 'LAUNCH_INTENT.json').exists()
    manifest_path.write_text(json.dumps(manifest))
    original_args = list(sys.argv)
    for option, changed in (('--model', 'different'), ('--provider', 'different'), ('--reasoning', 'low')):
        changed_args = list(original_args)
        if option in changed_args:
            changed_args[changed_args.index(option) + 1] = changed
        else:
            changed_args.extend([option, changed])
        monkeypatch.setattr(sys, 'argv', changed_args)
        with pytest.raises(SystemExit) as changed_argument:
            module.main()
        assert changed_argument.value.code == 2 and observed['run_count'] == 0
        assert not (workspace / 'LAUNCH_INTENT.json').exists()
    monkeypatch.setattr(sys, 'argv', [arg for arg in original_args if arg != '--assisted'])
    with pytest.raises(SystemExit) as changed_approach:
        module.main()
    assert changed_approach.value.code == 2 and observed['run_count'] == 0
    assert not (workspace / 'LAUNCH_INTENT.json').exists()
    monkeypatch.setattr(sys, 'argv', original_args)
    settings_file.write_text('{}')
    with pytest.raises(SystemExit) as changed_settings:
        module.main()
    assert changed_settings.value.code == 2 and observed['run_count'] == 0
    assert not (workspace / 'LAUNCH_INTENT.json').exists()
    settings_file.write_bytes(settings_original)
    module.main()
    assert observed['saved_goal'] == objective and observed['run_count'] == 1
    intent_path = workspace / 'LAUNCH_INTENT.json'
    intent = intent_path.read_bytes()
    receipt = json.loads(intent)
    assert receipt['state'] == 'native_session_created'
    assert receipt['session_id'] == observed['session_id']
    with pytest.raises(SystemExit) as repeated:
        module.main()
    assert repeated.value.code == 2 and observed['run_count'] == 1
    assert intent_path.read_bytes() == intent


def test_explicit_assignment_resume_restores_only_original_file_grants(tmp_path, monkeypatch):
    from agent.specialist_assignment import prepare, persist
    from agent.specialist_inputs import check_read
    from agent.specialist_runtime import resolve
    from agent.specialist_store import Specialist, save
    from sci_cli.config import atomic_config_replace
    from sci_constants import get_sci_home
    from run_agent import AIAgent

    monkeypatch.setattr('agent.model_metadata.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.context_compressor.get_model_context_length', lambda *a, **k: 131072)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **k: None)
    original = tmp_path / 'approved.txt'
    original.write_text('Approved result: 42')
    foreign = tmp_path / 'unapproved.txt'
    foreign.write_text('Unapproved result: 99')
    saved = save(Specialist('resumable-reviewer', 'Review original evidence', automatic=True,
        tools=('read_file',), max_iterations=4, timeout_seconds=0))
    atomic_config_replace(get_sci_home() / 'config.yaml', {'tool_search': {'enabled': 'off'},
        'memory': {'enabled': False}})

    def new_parent():
        return AIAgent(model='fixture', provider='custom', api_key='fixture', base_url='http://127.0.0.1:1/v1',
            api_mode='chat_completions', enabled_toolsets=['file', 'delegation'], quiet_mode=True,
            skip_context_files=True, skip_memory=True, max_iterations=4)

    task = {'specialist': saved.name, 'goal': 'Review the original evidence.',
            'context': f'Model-written extra path {foreign}', 'delivery': 'intermediate'}
    parent = new_parent()
    try:
        parent._specialist_user_request = f'Review this approved input: {original}'
        prepare(parent, [task])
        persist(parent)
        assignment_id = parent._specialist_assignment.id
        _, policy = resolve(parent, task)
        assert 'read_file' in policy.tools
    finally:
        parent.close()
    resumed = new_parent()
    try:
        resumed._specialist_user_request = 'Continue the existing assignment.'
        prepare(resumed, [task], {'resume': assignment_id})
        _, policy = resolve(resumed, task)
        assert 'read_file' in policy.tools
        assert check_read(policy, 'read_file', {'path': str(original)}) is None
        assert check_read(policy, 'read_file', {'path': str(foreign)})
    finally:
        resumed.close()
    unscoped = new_parent()
    try:
        unscoped._specialist_user_request = 'Begin a separate assignment without files.'
        prepare(unscoped, [task])
        _, policy = resolve(unscoped, task)
        assert 'read_file' not in policy.tools
    finally:
        unscoped.close()


def test_environment_launch_prepares_bound_command_without_starting(tmp_path, monkeypatch, capsys):
    import hashlib
    import importlib.util
    import os
    import shlex
    import sys

    environment = os.environ.get('ENZYME_ENVIRONMENT_SOURCE')
    if not environment:
        pytest.skip('Set ENZYME_ENVIRONMENT_SOURCE to exercise the separate environment launcher.')
    environment = Path(environment).resolve()
    source = Path(__file__).resolve().parents[2]
    wrapper = environment / 'scripts/launch_task.py'
    task = 'task_001_rml_stability'
    assert (environment / 'tasks' / (task + '.md')).is_file()
    settings = tmp_path / 'settings.json'
    settings.write_text(json.dumps({'llm': {'model': 'fixture', 'provider': 'custom', 'reasoning_effort': 'low'}}))
    contracts = tmp_path / 'approved-contracts'
    contracts.mkdir()
    workspace = tmp_path / 'prepared-run'
    interpreter = Path(sys.executable).absolute()
    monkeypatch.setattr(sys, 'argv', [str(wrapper), '--task', task, '--settings', str(settings),
        '--approach', 'agent_with_specialist', '--run-dir', str(workspace), '--profile', 'dedicated-test',
        '--sci-python', str(interpreter), '--sci-source', str(source), '--contract-root', str(contracts)])
    spec = importlib.util.spec_from_file_location('enzyme_environment_launch_fixture', wrapper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.main()
    command = shlex.split(capsys.readouterr().out.splitlines()[0])
    assert command[0] == str(interpreter)
    assert command[1] == str(environment / 'scripts/start_goal.py')
    assert command[command.index('--run-dir') + 1] == str(workspace)
    assert '--assisted' in command
    manifest = json.loads((workspace / 'PREPARED_LAUNCH.json').read_text())
    assert manifest['task'] == task and manifest['profile'] == 'dedicated-test'
    assert manifest['approach'] == 'agent_with_specialist'
    assert manifest['sci_source'] == str(source) and manifest['sci_python'] == str(interpreter)
    assert (manifest['model'], manifest['provider'], manifest['reasoning']) == ('fixture', 'custom', 'low')
    assert manifest['settings_path'] == str(settings)
    assert manifest['config_sha256'] == hashlib.sha256(settings.read_bytes()).hexdigest()
    goal = (workspace / 'START_SCI_TASK.txt').read_text()
    assert goal.startswith('/goal ') and str(contracts) in goal
    assert manifest['goal_sha256'] == hashlib.sha256(goal.encode()).hexdigest()
    assert not (workspace / 'LAUNCH_INTENT.json').exists()
