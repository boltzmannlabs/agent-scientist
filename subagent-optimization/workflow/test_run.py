"""Bounded driver checks: real private campaign state, fixture science only.

No SDK process, model inference, credentials, live connector or scientific job is
used. Fake time avoids real waiting; deterministic fixture handlers test polling.
"""
from argparse import Namespace
from contextlib import redirect_stdout
from copy import copy
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from workflow import run
from workflow import test_admission as fixture_admission
from workflow.test_controller import FixtureDispatcher


class Clock:
    def __init__(self):
        self.base = datetime.now(timezone.utc)
        self.elapsed = 0
        self.sleeps = []

    def now(self):
        return self.base + timedelta(seconds=self.elapsed)

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds


class RunTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_admission.AdmissionTests('test_actual_store_intent_precedes_native_upload_submit_and_repeat_is_blocked')
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.session, self.state = self.fixture.session, self.fixture.folder
        self.clock = Clock()
        self.dispatch = FixtureDispatcher()
        self.stdout = io.StringIO()
        self.args = Namespace(execute=True, poll_seconds=30, max_wait_seconds=900,
                              native_timeout=None, episode=1, invoke=False)

    def drive(self, *, collect=None, prepare=None, execute_effect=None, sleep=None, **changes):
        args = copy(self.args)
        for key, value in changes.items():
            setattr(args, key, value)
        normal_collect = run._collect
        with redirect_stdout(self.stdout), \
                patch.object(run, '_dispatcher', return_value=self.dispatch), \
                patch.object(run, '_now', side_effect=self.clock.now), \
                patch.object(run.time, 'monotonic', side_effect=self.clock.monotonic), \
                patch.object(run.time, 'sleep', side_effect=sleep or self.clock.sleep), \
                patch.object(run, '_prepare', side_effect=prepare or AssertionError('Unexpected new model episode')) as native, \
                patch.object(run, '_execute', side_effect=execute_effect or AssertionError('Unexpected new scientific action')) as action, \
                patch.object(run, '_collect', side_effect=collect or normal_collect) as observation:
            result = run._run(args, self.state, self.session)
            self.native_calls, self.action_calls, self.collect_calls = native.call_count, action.call_count, observation.call_count
        self.assertFalse(any(name in {'boltzmann_upload', 'boltzmann_submit'} for name, args in self.dispatch.calls))
        return result

    def final_selection(self):
        with self.session.store._db() as db:
            row = db.execute("SELECT data FROM events WHERE campaign=? AND kind='freeze' ORDER BY seq DESC LIMIT 1",
                             (self.session.campaign_id,)).fetchone()
        return json.loads(row[0])['request']['candidate_ids']

    def pending(self):
        self.fixture.submit()  # Explicit fixture receipts, not a scientific call.
        self.dispatch.pending = True

    def test_run_requires_optin_and_never_creates_another_campaign(self):
        result = self.drive(execute=False)
        self.assertEqual(result['phase'], 'execution_disabled')
        self.assertEqual((self.native_calls, self.action_calls, self.collect_calls), (0, 0, 0))
        self.assertEqual(self.session.report()['freezes'], [])
        with self.session.store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM campaigns').fetchone()[0], 1)
        self.assertEqual(Path(result['private_paths']['run_report']).stat().st_mode & 0o777, 0o600)

    def test_pending_polls_then_settles_and_closes_without_another_model_call(self):
        self.pending()
        original = run._collect
        calls = []
        def observed(args, state, session):
            calls.append(1)
            self.dispatch.pending = len(calls) == 1
            return original(args, state, session)
        result = self.drive(collect=observed)
        self.assertEqual(result['phase'], 'stopped')
        self.assertEqual(result['stop_reason'], 'no_admissible_action')
        self.assertEqual((self.native_calls, self.action_calls), (0, 0))
        self.assertEqual(self.collect_calls, 2)
        self.assertEqual(self.clock.sleeps, [30])
        self.assertTrue(result['assignment_frozen'])
        self.assertFalse(result['objective_satisfied'])
        self.assertEqual(self.session.attempts()[0]['state'], 'complete')
        self.assertEqual(self.final_selection(), [])

    def test_maximum_wait_preserves_outstanding_receipts_and_never_freezes(self):
        self.pending()
        result = self.drive(max_wait_seconds=3)
        self.assertEqual(result['phase'], 'max_wait_reached')
        self.assertEqual(self.collect_calls, 1)
        self.assertEqual(self.clock.sleeps, [3])
        self.assertEqual((self.native_calls, self.action_calls), (0, 0))
        self.assertEqual(self.session.attempts()[0]['submit']['doc_id'], 'TEST-JOB')
        self.assertEqual(self.session.report()['freezes'], [])

    def test_sleep_is_bounded_and_pending_has_no_repeated_reasoning(self):
        self.pending()
        result = self.drive(poll_seconds=999, max_wait_seconds=61)
        self.assertEqual(result['phase'], 'max_wait_reached')
        self.assertEqual(self.clock.sleeps, [30, 30, 1])
        self.assertEqual(self.collect_calls, 3)
        self.assertEqual(self.native_calls, 0)

    def test_assignment_deadline_stops_pending_work_without_freezing(self):
        self.pending()
        deadline = datetime.fromisoformat(self.session.spec['limits']['deadline_utc'])
        self.clock.base = deadline - timedelta(seconds=5)
        result = self.drive(poll_seconds=30, max_wait_seconds=100)
        self.assertEqual(result['phase'], 'deadline_reached')
        self.assertEqual(self.clock.sleeps, [5])
        self.assertEqual(self.collect_calls, 1)
        self.assertEqual(self.session.report()['freezes'], [])

    def test_settled_deadline_closes_with_empty_selection(self):
        self.clock.base = datetime.fromisoformat(self.session.spec['limits']['deadline_utc']) + timedelta(seconds=1)
        result = self.drive()
        self.assertEqual(result['phase'], 'stopped')
        self.assertEqual(result['stop_reason'], 'deadline_reached')
        self.assertEqual(self.final_selection(), [])
        self.assertEqual((self.collect_calls, self.native_calls, self.action_calls), (0, 0, 0))

    def test_host_checked_success_closes_without_model_or_execution(self):
        winner = self.fixture.ref['representation'].replace('OC)', 'O)')
        path = self.state / 'ENGINEERING_WINNER.csv'
        path.write_text('SMILES,Lipophilicity\n' + winner + ',1\n')
        self.session.import_csv(path, {'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                                      'source': 'ENGINEERING FIXTURE score, not a model measurement'})
        qualified = self.session.search_view()['qualified_candidate_ids']
        self.assertEqual(len(qualified), 1)
        result = self.drive()
        self.assertEqual(result['phase'], 'completed')
        self.assertTrue(result['objective_satisfied'])
        self.assertEqual(self.final_selection(), qualified)
        self.assertEqual((self.collect_calls, self.native_calls, self.action_calls), (0, 0, 0))

    def test_unknown_submit_halts_for_attention_without_poll_or_new_reasoning(self):
        upload = self.fixture.upload()
        self.fixture.call('boltzmann_submit', upload['workflow_next_submit'], effect=lambda args: (_ for _ in ()).throw(RuntimeError('fixture transport failure')))
        result = self.drive()
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertEqual(result['stop_reason'], 'original_attempt_requires_reconciliation')
        self.assertEqual((self.collect_calls, self.native_calls, self.action_calls), (0, 0, 0))
        self.assertEqual(self.session.report()['freezes'], [])

    def test_blocked_native_outcome_is_not_repeated(self):
        def prepared(*args):
            return {'phase': 'decision_ready', 'episode_directory': str(self.state / 'episodes/episode-0001')}
        result = self.drive(prepare=prepared, execute_effect=lambda *args: {'phase': 'blocked'})
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertEqual((self.native_calls, self.action_calls), (1, 1))
        self.assertEqual(self.clock.sleeps, [])
        self.assertEqual(self.session.report()['freezes'], [])

    def test_artifact_mapping_problem_halts_instead_of_spinning(self):
        self.pending()
        result = self.drive(collect=lambda *args: {'phase': 'collection_finished',
            'outcomes': [{'phase': 'artifact_mapping_required'}], 'private_result': str(self.state / 'private-collection.json')})
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertEqual(self.collect_calls, 1)
        self.assertEqual(self.clock.sleeps, [])
        self.assertEqual(self.native_calls, 0)

    def test_local_failure_halts_and_never_prints_exception_secrets(self):
        self.pending()
        result = self.drive(collect=lambda *args: (_ for _ in ()).throw(RuntimeError('https://private.invalid/?key=DO_NOT_PRINT')))
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertEqual(self.collect_calls, 1)
        self.assertNotIn('DO_NOT_PRINT', self.stdout.getvalue() + json.dumps(result))
        self.assertEqual(self.session.report()['freezes'], [])

    def test_ctrl_c_leaves_original_job_for_resume(self):
        self.pending()
        result = self.drive(sleep=lambda seconds: (_ for _ in ()).throw(KeyboardInterrupt()))
        self.assertEqual(result['phase'], 'interrupted')
        self.assertEqual(self.collect_calls, 1)
        self.assertEqual(self.session.attempts()[0]['submit']['doc_id'], 'TEST-JOB')
        self.assertEqual(self.session.report()['freezes'], [])

    def test_episode_allowance_closes_settled_assignment_without_new_reasoning(self):
        for _ in range(self.session.spec['limits']['max_episodes']):
            self.session.begin_episode()
        result = self.drive()
        self.assertEqual(result['phase'], 'stopped')
        self.assertEqual(result['stop_reason'], 'episode_allowance_reached')
        self.assertEqual(self.native_calls, 0)

    def test_valid_saved_decision_is_executed_without_repeating_model_reasoning(self):
        self.session.begin_episode()
        folder = self.state / 'episodes/episode-0001'; folder.mkdir(parents=True)
        (folder / 'native-result.json').write_text(json.dumps({'validation_status': 'passed', 'mode': 'host_mediated',
                                                            'outcome': {'status': 'action_requested'}}))
        result = self.drive(execute_effect=lambda *args: {'phase': 'blocked'})
        self.assertEqual(result['phase'], 'needs_attention')
        self.assertEqual((self.native_calls, self.action_calls), (0, 1))

    def test_already_frozen_assignment_is_not_frozen_again(self):
        self.session.finish([], 'ENGINEERING STOP')
        result = self.drive()
        self.assertEqual(result['phase'], 'frozen')
        self.assertEqual(len(self.session.report()['freezes']), 1)
        self.assertEqual((self.native_calls, self.action_calls, self.collect_calls), (0, 0, 0))

    def test_invalid_wait_settings_fail_before_any_operation(self):
        for changes in ({'poll_seconds': 0}, {'max_wait_seconds': 0}, {'max_wait_seconds': float('nan')}, {'native_timeout': -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.drive(**changes)
        self.assertEqual(self.session.attempts(), [])


if __name__ == '__main__':
    unittest.main()
