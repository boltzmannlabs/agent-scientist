"""Native handoff host checks with real state and explicitly fixture science.

No SDK process, model, live connector, network or profile is used.
"""
from argparse import Namespace
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from workflow import delegated_bridge as bridge
from workflow import run
from workflow import test_session as fixtures
from workflow.test_controller import FixtureDispatcher

ENV_SOURCE = '/home/boltzmann13/science-environments/environments/small-molecule-lead-optimization/src'
HOST_ROOT = '/home/boltzmann13/agent-scientist'


class DelegatedBridgeTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.SessionTests('test_restart_and_episode_allowance_do_not_reset')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root = self.fixture.folder
        self.state = self.root / 'delegated-state'
        self.owner = self.root / 'unused-owning-profile'
        self.owner.mkdir()
        protocol = self.root / 'protocol.json'
        protocol.write_text(json.dumps(self.fixture.protocol))
        args = Namespace(state_dir=self.state, environment_source=ENV_SOURCE,
                         protocol=protocol, assignment_id='engineering-delegated',
                         max_submissions=2, max_episodes=3,
                         deadline_utc=self.fixture.limits['deadline_utc'],
                         common_csv=None, common_sha256=None, common_stage=None)
        run.initialize(args)
        self.args = Namespace(state_dir=self.state, environment_source=ENV_SOURCE)
        self.session = run._load(self.args)[1]
        self.runtime = {'environment_source': ENV_SOURCE, 'host_root': HOST_ROOT,
                        'sdk_python': HOST_ROOT + '/.venv/bin/python', 'owner_home': str(self.owner),
                        'specialist_revision': 'fixture-reviewed-revision', 'state_root': str(self.root)}
        self.task = {'schema_version': 1, 'workflow_state': str(self.state),
                     'assignment_id': self.session.assignment_id,
                     'reference_representation': self.session.spec['reference']['representation'],
                     'objective': self.session.spec['objective'], 'limits': self.session.spec['limits']}
        self.task_path = self.root / 'task.md'
        self.write_task()
        self.dispatcher = FixtureDispatcher()
        self.native_session_id = 'fixture-native-child-1'

    def write_task(self, task=None, prefix='# Engineering fixture task\n\n'):
        self.task_path.write_text(prefix + '```json\n' + json.dumps(task or self.task, indent=2) + '\n```\n')

    def request(self, operation, **extra):
        return {'operation': operation, 'task_file': str(self.task_path), 'runtime': self.runtime,
                'caller': {'specialist': 'smallmol-investigation', 'revision': 'fixture-reviewed-revision',
                           'home': str(self.owner), 'transport': 'native-specialist-tool',
                           'session_id': self.native_session_id}, **extra}

    def call(self, operation, **extra):
        with patch.object(run, '_dispatcher', return_value=self.dispatcher):
            return bridge.handle_request(self.request(operation, **extra))

    def outcome(self, prepared, status='action_requested'):
        assignment = prepared['evidence']['assignment']
        action = assignment['helper_summaries']['eligible_actions'][0]
        return {'schema_version': 1, 'assignment_id': assignment['assignment_id'],
                'episode_id': assignment['episode_id'], 'input_digest': assignment['input_digest'],
                'status': status, 'chosen_action': {'kind': 'generate', 'parent_id': action['parent_candidate_id'],
                    'library_id': action['library_id'], 'action_key': action['action_key']},
                'evidence_ids': [assignment['parent_options'][0]['candidate_id']],
                'final_candidate_ids': [], 'pending_jobs': [], 'artifact_refs': [],
                'rationale': 'ENGINEERING FIXTURE only: investigate original neighborhood.',
                'stop_reason': 'Host action requested.', 'limitations': ['No live science or model evidence.'],
                'information_requests': []}

    def test_inspect_is_read_only_and_context_reuses_one_episode(self):
        self.assertEqual(self.call('inspect')['episodes_started'], 0)
        first = self.call('evidence')
        self.assertEqual(first['phase'], 'evidence_ready')
        self.assertEqual(first, self.call('evidence'))
        self.assertEqual(self.call('inspect')['episodes_started'], 1)
        self.assertEqual(self.dispatcher.calls, [])
        self.assertEqual((self.state / 'episodes/episode-0001/wire.json').stat().st_mode & 0o777, 0o600)

    def test_evidence_transport_splits_large_packets_below_sdk_result_budget_losslessly(self):
        packet = {'assignment': {'opaque_id': 'M001', 'evidence': 'x' * 125_000,
                                 'molecules': [{'candidate': i, 'smiles': 'C' * (i % 40 + 1)} for i in range(3000)]},
                  'outcome_schema': {'type': 'object'}}
        canonical, parts = bridge._parts(packet)
        self.assertGreater(len(parts), 1)
        self.assertEqual(''.join(parts), canonical)
        self.assertEqual(json.loads(canonical), packet)
        for index, content in enumerate(parts, 1):
            response = {'phase': 'evidence_part', 'episode': 1, 'part': index,
                        'total_parts': len(parts), 'content': content,
                        'sha256': hashlib.sha256(content.encode()).hexdigest(),
                        'packet_sha256': hashlib.sha256(canonical.encode()).hexdigest(),
                        'input_digest': 'a' * 64, 'all_parts_delivered': False}
            self.assertLess(len(json.dumps(response)), bridge.MAX_PART_JSON_CHARACTERS)

    def test_apply_real_controller_collect_and_resume_without_duplicate_job(self):
        first = self.call('evidence')
        outcome = self.outcome(first)
        result = self.call('apply', episode=first['episode'], outcome=outcome)
        self.assertEqual(result['phase'], 'waiting')
        self.assertEqual(result['decision_provenance']['transport'], 'native-specialist-tool')
        self.assertEqual(sum(name == 'boltzmann_submit' for name, args in self.dispatcher.calls), 1)
        self.assertEqual(self.call('apply', episode=first['episode'], outcome=outcome)['phase'], 'needs_attention')
        self.dispatcher.pending = True
        self.assertEqual(self.call('evidence')['phase'], 'waiting_or_reconciliation')
        self.assertEqual(self.call('collect')['next']['phase'], 'waiting_or_reconciliation')
        self.assertEqual(self.call('inspect')['episodes_started'], 1)
        self.dispatcher.pending = False
        self.assertEqual(self.call('collect')['phase'], 'collection_finished')
        second = self.call('evidence')
        self.assertEqual(second['phase'], 'evidence_ready')
        self.assertEqual(second['episode'], 2)
        self.assertEqual(sum(name == 'boltzmann_submit' for name, args in self.dispatcher.calls), 1)
        self.assertFalse((self.state / 'episodes/episode-0001/native-result.json').exists())

    def test_main_agent_cannot_request_scientific_evidence_or_apply(self):
        for operation in ('evidence', 'apply'):
            request = self.request(operation)
            request['caller'] = {'home': str(self.owner), 'transport': 'main-agent-tool'}
            with self.assertRaises(ValueError):
                bridge.handle_request(request)
        self.assertEqual(self.call('inspect')['episodes_started'], 0)

    def test_foreign_profile_and_wrong_reviewed_revision_rejected(self):
        for key, value in [('home', str(self.root)), ('revision', 'another-revision')]:
            request = self.request('evidence')
            request['caller'][key] = value
            with self.assertRaises(ValueError):
                bridge.handle_request(request)
        self.assertEqual(self.call('inspect')['episodes_started'], 0)

    def test_task_identity_objective_reference_and_limits_must_match(self):
        for key, value in [('assignment_id', 'foreign'), ('reference_representation', 'CCN'),
                           ('objective', {}), ('limits', {})]:
            changed = deepcopy(self.task)
            changed[key] = value
            self.write_task(changed)
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.call('inspect')
        self.write_task()
        self.assertEqual(self.call('inspect')['episodes_started'], 0)

    def test_changed_task_bytes_block_application_without_dispatch(self):
        first = self.call('evidence')
        self.write_task(prefix='# Changed prose with identical structured assignment\n\n')
        result = self.call('apply', episode=1, outcome=self.outcome(first))
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertEqual(self.dispatcher.calls, [])
        self.assertEqual(self.call('evidence')['phase'], 'needs_attention')

    def test_ambiguous_markdown_and_symlink_are_rejected(self):
        original = self.task_path.read_text()
        self.task_path.write_text(original + original)
        with self.assertRaises(ValueError):
            self.call('inspect')
        self.write_task()
        alias = self.root / 'alias.md'
        alias.symlink_to(self.task_path)
        request = self.request('inspect')
        request['task_file'] = str(alias)
        with self.assertRaises(ValueError):
            bridge.handle_request(request)

    def test_unknown_original_submit_prevents_context_and_monitor_calls(self):
        action = self.session.reserve(self.session.spec['reference']['id'], 'a')
        self.session.receipt(action['action_key'], 'upload_intent', {}, 'uploading')
        self.assertEqual(self.call('evidence')['phase'], 'needs_attention')
        self.assertEqual(self.call('collect')['phase'], 'needs_attention')
        self.assertEqual(self.call('inspect')['episodes_started'], 0)
        self.assertEqual(self.dispatcher.calls, [])

    def test_stale_context_never_replaced_or_dispatched(self):
        first = self.call('evidence')
        self.session.store.dispatch('decision', self.session.campaign_id,
            {'id': 'fixture-external-change', 'question': 'Fixture intervention', 'outcome': 'inconclusive',
             'evidence_ids': [], 'rationale': 'Fixture state change', 'next_action': 'none'})
        self.assertEqual(self.call('evidence')['phase'], 'needs_attention')
        self.assertEqual(self.call('apply', episode=1, outcome=self.outcome(first))['phase'], 'needs_attention')
        self.assertEqual(self.call('inspect')['episodes_started'], 1)
        self.assertEqual(self.dispatcher.calls, [])

    def test_nonblocking_host_lock_rejects_concurrent_operations(self):
        with bridge._locked(self.state), self.assertRaises(ValueError):
            self.call('inspect')

    def test_post_dispatch_local_failure_retains_intent_and_never_reapplies(self):
        first = self.call('evidence')
        original = run._write
        def fail_execution(path, value):
            if Path(path).name == 'execution.json':
                raise OSError('ENGINEERING FIXTURE local write failure')
            return original(path, value)
        with patch.object(run, '_write', side_effect=fail_execution):
            result = self.call('apply', episode=1, outcome=self.outcome(first))
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertTrue((self.state / 'episodes/episode-0001/delegated-apply-intent.json').is_file())
        self.assertEqual(self.call('apply', episode=1, outcome=self.outcome(first))['phase'], 'needs_attention')
        self.assertEqual(sum(name == 'boltzmann_submit' for name, args in self.dispatcher.calls), 1)


if __name__ == '__main__':
    unittest.main()
