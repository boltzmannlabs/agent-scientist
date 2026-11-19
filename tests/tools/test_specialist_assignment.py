"""Immutable task handoffs, explicit roots and dependent artifact delivery."""
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
from threading import Thread
from types import SimpleNamespace

import pytest

from agent.specialist_assignment import prepare, record_artifacts
from agent.specialist_store import Specialist, save
from sci_cli.config import atomic_config_replace
from sci_cli.native_profile_creation import profile_scope


def test_explicit_root_and_overlapping_tree_rejected_before_construction(tmp_path, monkeypatch):
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task
    from tools.registry import registry
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    home = tmp_path / 'profile'; home.mkdir()
    with profile_scope(home):
        atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'delegation']},
            'delegation': {'max_spawn_depth': 3, 'max_concurrent_children': 4}})
        save(Specialist('runner', 'Execute the assigned task', automatic=True))
        save(Specialist('lead', 'Coordinate the runner', children=('runner',), automatic=True))
        parent = AIAgent(model='fixture', provider='custom', api_key='fixture', base_url='http://127.0.0.1:1/v1',
                         enabled_toolsets=['file', 'delegation'], quiet_mode=True, skip_context_files=True, skip_memory=True)
        try:
            parent._specialist_user_request = 'Use my saved specialist lead for this assignment through delegate_task. Assignment: calculate 42'
            result = json.loads(registry.dispatch('delegate_task', {'tasks': [
                {'specialist': 'lead', 'goal': 'Complete the exact assignment.'},
                {'specialist': 'runner', 'goal': 'Complete the exact assignment.'}]}, parent_agent=parent))
            assert 'descendants in parallel' in result['error']
            result = json.loads(delegate_task(tasks=[{'specialist': 'runner', 'goal': 'Compute the value.'}], parent_agent=parent))
            assert 'explicitly selects lead' in result['error']
            result = json.loads(registry.dispatch('delegate_task', {'tasks': [{'goal': 'Execute the exact assignment.'}],
                'assignment': {'max_submissions': {'fixture': 1}, 'tool_arguments': {}}}, parent_agent=parent))
            assert 'Missing submission parameters for fixture' in result['error']
            assert not list((home / 'subagent-runs').glob('sa-*.json'))
            # Informational planning can be frozen for execution afterward, but not altered again.
            prepare(parent, [{'specialist': 'lead'}])
            from agent.specialist_policy import SpecialistPolicy, specialist_scope
            from agent.specialist_assignment import record_artifacts
            planning_output = home / 'plan.txt'
            planning_output.write_text('Prepared scientific parameters: value=42.')
            planning_policy = SpecialistPolicy('lead', str(home), 'fixture', frozenset(), frozenset(),
                frozenset(), ('lead',), float('inf'), assignment=parent._specialist_assignment)
            with specialist_scope(planning_policy):
                record_artifacts([str(planning_output)])
            contract = {'max_submissions': {'fixture': 1}, 'tool_arguments': {
                'fixture_submit': {'job_name': 'fixture', 'experiment_data': {'value': 42}}}}
            prepare(parent, [{'specialist': 'lead'}], contract)
            assignment = parent._specialist_assignment
            prepare(parent, [{'specialist': 'lead'}], contract)
            assert parent._specialist_assignment is assignment
            with pytest.raises(ValueError, match='frozen contract'):
                prepare(parent, [{'specialist': 'lead'}], {**contract, 'max_submissions': {'fixture': 2}})
            nested = SimpleNamespace(_specialist_policy=SimpleNamespace(assignment=assignment))
            prepare(nested, [{'specialist': 'runner'}], {'resume': assignment.id})
            assert nested._specialist_assignment is assignment
            with pytest.raises(ValueError, match='cannot replace'):
                prepare(nested, [{'specialist': 'runner'}], {'inputs': []})
        finally:
            parent.close()


def test_incomplete_execution_contract_is_rejected_before_freezing_or_construction(tmp_path):
    rules = {'job_name': 'fixture', 'experiment_data': {'value': 42}}
    for arguments in ({}, {'submit': {}}, {'submit': {**rules, 'job_name': 'other'}},
                      {'submit': {**rules, 'experiment_data': {}}}):
        parent = SimpleNamespace(_specialist_snapshot={}, _specialist_user_request='Execute the requested task.')
        with pytest.raises(ValueError, match='submission parameters.*fixture'):
            prepare(parent, [{'specialist': 'lead'}], {'max_submissions': {'fixture': 1},
                                                      'tool_arguments': arguments})
        assert not getattr(parent, '_specialist_assignment', None)
    # Existing informational and ordinary delegation do not require execution metadata.
    parent = SimpleNamespace(_specialist_snapshot={}, _specialist_user_request='Review this explanation.')
    prepare(parent, [{'goal': 'Review independently.'}])
    assert not getattr(parent, '_specialist_assignment', None)
    with pytest.raises(ValueError, match='require tasks'):
        prepare(parent, [{'goal': 'Review independently.'}], {'inputs': []})
    prepare(parent, [{'specialist': 'lead'}])
    assert parent._specialist_assignment
    parent._specialist_assignment = None
    prepare(parent, [{'specialist': 'lead'}], {'max_submissions': {'fixture': 1, 'next': 2},
        'tool_arguments': {'submit': [rules, {'job_name': 'next', 'experiment_data': {'mode': 'derived'}}]}})
    assert parent._specialist_assignment


def test_handoff_accepts_frozen_inputs_and_outputs_but_never_replaces_the_input_digest(tmp_path, monkeypatch):
    from agent.specialist_assignment import verified_artifacts
    from agent.specialist_policy import SpecialistPolicy, specialist_scope
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('a', 'b')]
    previous = None
    for home in (homes[0], homes[1], homes[0]):
        home.mkdir(exist_ok=True)
        with profile_scope(home):
            source, output, foreign = (home / name for name in ('input.csv', 'output.csv', 'foreign.csv'))
            source.write_text('value\n42\n'); output.write_text('result\n84\n'); foreign.write_text('unrelated\n')
            parent = SimpleNamespace(_specialist_snapshot={}, _specialist_user_request='Audit the exact input and output.')
            prepare(parent, [{'specialist': 'auditor'}], {'inputs': [str(source)]})
            assignment = parent._specialist_assignment
            policy = SpecialistPolicy('auditor', str(home), 'r', frozenset(), frozenset(), frozenset(),
                                      ('auditor',), float('inf'), assignment=assignment)
            with specialist_scope(policy):
                record_artifacts([str(output)])
                assert verified_artifacts(assignment, [str(source), str(output)]) == (str(source), str(output))
                for invalid in [foreign, home / 'missing.csv', *([previous] if previous else [])]:
                    with pytest.raises(ValueError, match=re.escape(str(invalid))):
                        verified_artifacts(assignment, [str(invalid)])
                source.write_text('value\n99\n')
                record_artifacts([str(source)])  # recording new bytes must not override the frozen input
                with pytest.raises(ValueError, match='changed.*' + re.escape(str(source))):
                    verified_artifacts(assignment, [str(source)])
                source.write_text('value\n42\n')
                assert verified_artifacts(assignment, [str(source)]) == (str(source),)
            previous = output


def test_real_agent_tree_runs_execution_then_exact_artifact_review_with_stable_prompts(tmp_path, monkeypatch):
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task
    from tools.registry import registry
    from agent.specialist_runs import history
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr('agent.title_generator.maybe_auto_title', lambda *a, **kw: None)
    home = tmp_path / 'profile'; home.mkdir()
    output = tmp_path / 'fresh-result.json'
    requests, executions = [], []
    resume = {'id': None}
    def execute(args, **kw):
        executions.append(dict(args))
        output.write_text(json.dumps({'value': args['value']}))
        record_artifacts([str(output)])
        return json.dumps({'output_paths': [str(output)], 'value': args['value']})
    registry.register(name='assignment_fixture_execute', toolset='mcp-assignment-fixture',
        schema={'name': 'assignment_fixture_execute', 'description': 'Write a controlled local fixture.',
                'parameters': {'type': 'object', 'properties': {'value': {'type': 'integer'}}, 'required': ['value']}},
        handler=execute, check_fn=lambda: True)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if 'messages' not in payload:
                raw = b'{}'
                self.send_response(200); self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)
                return
            requests.append(payload)
            prompt = str(payload['messages'][0]['content'])
            match = re.search(r'Saved specialist: ([\w-]+)', prompt)
            name = match[1] if match else 'main'
            results = [m for m in payload['messages'] if m['role'] == 'tool']
            tool, args = None, {}
            recovering = any('RECONCILE_EXISTING_ASSIGNMENT' in str(m.get('content', ''))
                             for m in payload['messages'] if m['role'] == 'user')
            if name == 'main' and not results:
                # Reproduce the observed model omission: the explicit user-selected root must still be used.
                tool, args = 'delegate_task', {'tasks': [{'goal': 'RECONCILE_EXISTING_ASSIGNMENT' if recovering else 'Execute and audit 42.'}],
                    'assignment': {'resume': resume['id']} if recovering else
                                  {'max_submissions': {'fixture': 1}, 'tool_arguments': {}}}
            elif name == 'main' and len(results) == 1 and not recovering:
                # The parent corrects rejected metadata in the same turn; no child or upload ran first.
                assert not executions
                assert 'Missing submission parameters for fixture' in str(results[0]['content'])
                tool, args = 'delegate_task', {'tasks': [{'goal': 'Execute and audit 42.'}], 'assignment': {
                    'max_submissions': {'fixture': 1}, 'tool_arguments': {
                        'fixture_submit': {'job_name': 'fixture', 'experiment_data': {'value': 42}},
                        'assignment_fixture_execute': {'value': 42}}}}
            elif name == 'lead' and not results and recovering:
                tool, args = 'delegate_task', {'tasks': [{'specialist': 'auditor', 'goal': 'Audit the existing output only.',
                    'artifacts': [str(output)], 'delivery': 'intermediate'}]}
            elif name == 'lead' and not results:
                tool, args = 'delegate_task', {'tasks': [{'specialist': 'runner', 'goal': 'Execute the input value.',
                    'context': 'The handoff accidentally says 43; original assignment remains authoritative.', 'delivery': 'intermediate'}]}
            elif name == 'lead' and len(results) == 1 and not recovering:
                tool, args = 'delegate_task', {'tasks': [{'specialist': 'auditor', 'goal': 'Audit the exact output.',
                    'artifacts': [str(output)], 'delivery': 'intermediate'}]}
            elif name == 'runner' and not results:
                tool, args = 'assignment_fixture_execute', {'value': 42}
            elif name == 'auditor' and not results:
                tool, args = 'read_file', {'path': str(output)}
            message = {'role': 'assistant', 'content': f'{name}: verified 42.'}
            finish = 'stop'
            if tool:
                if tool not in {t['function']['name'] for t in payload.get('tools', [])}:
                    args, tool = {'calls': [{'name': tool, 'arguments': args}]}, 'tool_call'
                message = {'role': 'assistant', 'content': None, 'tool_calls': [{'id': f'call-{name}-{len(results)}',
                    'type': 'function', 'function': {'name': tool, 'arguments': json.dumps(args)}}]}
                finish = 'tool_calls'
            response = {'id': 'fixture', 'object': 'chat.completion', 'model': 'fixture',
                'choices': [{'index': 0, 'message': message, 'finish_reason': finish}],
                'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}
            stream = payload.get('stream')
            if stream:
                delta = deepcopy(message)
                if 'tool_calls' in delta:
                    delta['tool_calls'][0]['index'] = 0
                response['object'] = 'chat.completion.chunk'
                response['choices'][0] = {'index': 0, 'delta': delta, 'finish_reason': finish}
            raw = (('data: ' + json.dumps(response) + '\n\ndata: [DONE]\n\n') if stream else json.dumps(response)).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if stream else 'application/json')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        with profile_scope(home):
            atomic_config_replace(home / 'config.yaml', {'platform_toolsets': {'cli': ['file', 'delegation', 'mcp-assignment-fixture']},
                'tool_search': {'enabled': 'off'}, 'memory': {'enabled': False},
                'delegation': {'max_iterations': 12, 'max_spawn_depth': 3, 'max_concurrent_children': 2}})
            save(Specialist('runner', 'Execute only the assigned value.', tools=('assignment_fixture_execute',)))
            save(Specialist('auditor', 'Read and audit identified outputs.', tools=('read_file',)))
            save(Specialist('lead', 'Execute then audit.', children=('runner', 'auditor'), automatic=True))
            settings = dict(model='fixture', provider='custom', api_key='fixture',
                base_url=f'http://127.0.0.1:{server.server_port}/v1', enabled_toolsets=['file', 'delegation', 'mcp-assignment-fixture'],
                quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=12)
            parent = AIAgent(**settings)
            try:
                frozen = json.dumps(parent.tools, sort_keys=True)
                explicit = 'Use my saved specialist lead for this assignment through delegate_task. '
                result = parent.run_conversation(explicit + 'ORIGINAL_VALUE=42. Execute then audit the exact fresh result.')
                assert not result.get('failed') and 'lead: verified 42.' in result['final_response'], result
                assert json.loads(output.read_text()) == {'value': 42}
                assert len(requests) == 9
                main_prefixes = [row['messages'][0] for row in requests if 'Saved specialist:' not in row['messages'][0]['content']]
                assert len(main_prefixes) == 2 and main_prefixes[0] == main_prefixes[1]
                for name in ('lead', 'runner', 'auditor'):
                    prompts = [row['messages'][0] for row in requests if f'Saved specialist: {name}\n' in row['messages'][0]['content']]
                    assert len(prompts) >= 2 and all(p == prompts[0] for p in prompts)
                    assert 'ORIGINAL_VALUE=42' in prompts[0]['content']
                assert str(output) in next(row['messages'][0]['content'] for row in requests
                                          if 'Saved specialist: auditor\n' in row['messages'][0]['content'])
                assert json.dumps(parent.tools, sort_keys=True) == frozen
                rows = history()
                assert {r['specialist'] for r in rows} == {'lead', 'runner', 'auditor'}
                assert len({r['assignment_id'] for r in rows}) == 1
                lead = next(row for row in rows if row['specialist'] == 'lead')
                assert all(row['root_run_id'] == lead['run_id'] for row in rows)
                resume['id'] = lead['assignment_id']
                parent.close()
                parent = AIAgent(**settings)
                start = len(requests)
                recovered = parent.run_conversation(explicit + 'RECONCILE_EXISTING_ASSIGNMENT. Audit existing output; do not execute again.')
                assert not recovered.get('failed') and 'lead: verified 42.' in recovered['final_response'], recovered
                assert len(executions) == 1
                assert {row['assignment_id'] for row in history()} == {resume['id']}
                assert [re.search(r'Saved specialist: ([\w-]+)', row['messages'][0]['content'])[1]
                        for row in requests[start:] if 'Saved specialist:' in row['messages'][0]['content']] == [
                            'lead', 'auditor', 'auditor', 'lead']
                assert json.dumps(parent.tools, sort_keys=True) == frozen
            finally:
                parent.close()
    finally:
        server.shutdown(); server.server_close(); thread.join(5)
