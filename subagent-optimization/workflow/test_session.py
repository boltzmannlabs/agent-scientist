"""Real environment/SQLite integration with explicit synthetic chemistry fixtures.

No network, model inference, profile changes or scientific submissions occur.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from rdkit import Chem, DataStructs, rdBase
from rdkit.Chem import QED, rdFingerprintGenerator
from leadopt_env.core import CampaignStore
from pilot.bridge import BINDING, JOB_NAME, _request
from pilot.property_assessment import KIND
from workflow.context import GENERIC_SMILES_WARNING, episode_context, from_property_protocol
from workflow.session import WorkflowSession, digest, native_status


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.reference = {'id': 'fixture-original', 'form_id': 'fixture-ethanol',
                          'representation': 'CCO', 'source': 'ENGINEERING FIXTURE'}
        self.protocol = {
            'reference': deepcopy(self.reference),
            'generation_parameters': {'global_models': [{'name': 'Lipophilicity', 'min_threshold': 0, 'max_threshold': 3}]},
            'assessor': {'kind': KIND, 'reference': deepcopy(self.reference), 'rdkit_version': rdBase.rdkitVersion,
                         'property_column': 'Lipophilicity', 'target_min': 0, 'target_max': 3,
                         'baseline': {'lipophilicity': -1, 'qed': QED.qed(Chem.MolFromSmiles('CCO')), 'lead_similarity': 1.0}},
            'libraries': [], 'partial_validation_approvals': []}
        for name, smiles in [('a', 'CCO'), ('b', 'CCN')]:
            path = self.folder / (name + '.csv')
            path.write_text('SMILES\n' + smiles + '\n')
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            self.protocol['libraries'].append({'id': name, 'csv_path': str(path), 'content_sha256': sha})
        first = self.protocol['libraries'][0]
        self.protocol['partial_validation_approvals'] = [{
            'library_id': first['id'], 'library_content_sha256': first['content_sha256'],
            'approved': True, 'only_warning': GENERIC_SMILES_WARNING}]
        self.limits = {'max_scientific_submissions': 2, 'max_episodes': 3,
                       'deadline_utc': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}
        self.store = CampaignStore(self.folder / 'campaign.sqlite3')

    def create(self, limits=None):
        spec, task = from_property_protocol(self.protocol, 'engineering-assignment', self.folder / 'artifacts', limits or self.limits)
        return WorkflowSession.create(self.store, spec, task)

    def artifact(self, rows, name='results.csv'):
        path = self.folder / name
        with path.open('w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['SMILES', 'Lipophilicity'])
            writer.writerows(rows)
        return path, {'source': 'ENGINEERING FIXTURE JOB A', 'artifact_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def accepted(self, session, library='a', doc='FIXTURE_NOT_A_LIVE_JOB'):
        action = session.reserve(self.reference['id'], library)
        key = action['action_key']
        _, binding = _request(action['request'], verify_file=False)
        session.receipt(key, 'upload_intent', {}, 'uploading')
        session.receipt(key, 'upload', {BINDING: binding, 'status': 'uploaded', 'sha256': action['request']['library_content_sha256'],
                                       's3_path': 'fixture-storage/library'}, 'uploaded')
        session.receipt(key, 'submit_intent', {}, 'submitting')
        session.receipt(key, 'submit', {BINDING: binding, 'status': 'accepted', 'doc_id': doc, 'job_name': JOB_NAME}, 'accepted')
        return action, binding

    def test_factory_preserves_input_and_encodes_strict_original_rules(self):
        before = deepcopy(self.protocol)
        spec, task = from_property_protocol(self.protocol, 'engineering-assignment', self.folder / 'artifacts', self.limits)
        self.assertEqual(self.protocol, before)
        self.assertEqual(task['allowed_jobs'], [JOB_NAME])
        constraints = {c['endpoint']: c for c in task['constraints']}
        self.assertEqual(constraints['qed']['minimum'], math.nextafter(spec['assessor']['baseline']['qed'], math.inf))
        self.assertEqual(constraints['lead_similarity']['minimum'], math.nextafter(.7, math.inf))
        self.assertEqual((constraints['lipophilicity']['minimum'], constraints['lipophilicity']['maximum']), (0, 3))
        self.assertEqual(len(task['objectives']), 1)
        session = WorkflowSession.create(self.store, spec, task)
        self.assertEqual(session.candidates()[0]['values']['lipophilicity'], -1)
        self.assertTrue(spec['libraries'][0]['approved_generic_smiles_warning'])
        self.assertFalse(spec['libraries'][1]['approved_generic_smiles_warning'])

    def test_approval_does_not_transfer_across_hash_or_warning(self):
        for field, value in [('library_content_sha256', '0' * 64), ('only_warning', 'different warning')]:
            changed = deepcopy(self.protocol)
            changed['partial_validation_approvals'][0][field] = value
            spec, _ = from_property_protocol(changed, 'engineering-assignment', self.folder / 'artifacts', self.limits)
            self.assertFalse(spec['libraries'][0]['approved_generic_smiles_warning'])

    def test_objective_mismatch_rejected_before_campaign_creation(self):
        bad = deepcopy(self.protocol)
        bad['generation_parameters'] = {}
        with self.assertRaises(ValueError):
            from_property_protocol(bad, 'engineering-assignment', self.folder / 'artifacts', self.limits)
        spec, task = from_property_protocol(self.protocol, 'engineering-assignment', self.folder / 'artifacts', self.limits)
        spec['objective']['target_max'] = 4
        with self.assertRaises(ValueError):
            WorkflowSession.create(self.store, spec, task)
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM campaigns').fetchone()[0], 0)

    def test_restart_and_episode_allowance_do_not_reset(self):
        session = self.create({**self.limits, 'max_episodes': 1})
        context = episode_context(session, {'job_name': JOB_NAME, 'scope': 'ENGINEERING FIXTURE CONTRACT'})
        self.assertEqual(context['input_digest'], digest({k: v for k, v in context.items() if k != 'input_digest'}))
        self.assertEqual(context['task_digest'], digest(context['task']))
        reopened = WorkflowSession(CampaignStore(self.store.path), session.assignment_id)
        with self.assertRaisesRegex(ValueError, 'Episode allowance'):
            episode_context(reopened, {'job_name': JOB_NAME})
        self.assertEqual(len(context['helper_summaries']['rows']), len(context['parent_options']))

    def test_immutable_assignment_and_campaign_ownership(self):
        session = self.create()
        altered = deepcopy(session.spec)
        altered['limits']['max_episodes'] += 1
        with self.assertRaisesRegex(ValueError, 'Immutable assignment'):
            WorkflowSession.create(self.store, altered, session.report()['task'])
        altered = deepcopy(session.spec)
        altered['assignment_id'] = 'another-assignment'
        with self.assertRaisesRegex(ValueError, 'Campaign already'):
            WorkflowSession.create(self.store, altered, session.report()['task'])

    def test_unknown_submission_blocks_other_work_and_wrong_binding_is_rejected(self):
        session = self.create()
        action = session.reserve(self.reference['id'], 'a')
        with self.assertRaisesRegex(ValueError, 'Resolve existing'):
            session.reserve(self.reference['id'], 'b')
        session.receipt(action['action_key'], 'upload_intent', {}, 'uploading')
        with self.assertRaisesRegex(ValueError, 'binding'):
            session.receipt(action['action_key'], 'upload', {'status': 'uploaded'}, 'uploaded')
        reopened = WorkflowSession(self.store, session.assignment_id)
        with self.assertRaises(ValueError):
            reopened.reserve(self.reference['id'], 'b')

    def test_terminal_receipt_cannot_regress_and_submission_allowance_is_cumulative(self):
        session = self.create({**self.limits, 'max_scientific_submissions': 1})
        action, binding = self.accepted(session)
        receipt = {BINDING: binding, 'status': 'failed', 'doc_id': 'FIXTURE_NOT_A_LIVE_JOB', 'job_name': JOB_NAME}
        session.receipt(action['action_key'], 'monitor', receipt, 'failed')
        session.receipt(action['action_key'], 'monitor', {**receipt, 'status': 'pending'}, 'accepted')
        self.assertEqual(session.attempts()[0]['state'], 'failed')
        with self.assertRaises(ValueError):
            session.reserve(self.reference['id'], 'a')
        with self.assertRaisesRegex(ValueError, 'allowance'):
            WorkflowSession(self.store, session.assignment_id).reserve(self.reference['id'], 'b')
        self.assertEqual(native_status({'service_status': 'failed', 'error': 'transport error'}), 'unknown')

    def test_wrong_method_and_wrong_form_never_supply_task_evidence(self):
        session = self.create()
        baseline = session.report()['observations'][0]
        for label, change in [('wrong-method', {'method': 'unrelated predictor'}), ('wrong-form', {'form_id': 'another-form'})]:
            self.store.dispatch('observation', session.campaign_id, {**baseline, **change, 'id': label, 'value': 2})
        row = session.candidates()[0]
        self.assertEqual(row['values']['lipophilicity'], -1)
        self.assertFalse(row['property_prediction_conflict'])

    def test_identical_artifact_replay_and_cross_job_provenance(self):
        session = self.create()
        path, provenance = self.artifact([('CCCO', -.5)])
        session.import_csv(path, provenance, parent_id=self.reference['id'])
        count = len(session.report()['observations'])
        session.import_csv(path, provenance, parent_id=self.reference['id'])
        self.assertEqual(len(session.report()['observations']), count)
        session.import_csv(path, {**provenance, 'source': 'ENGINEERING FIXTURE JOB B'}, parent_id=self.reference['id'])
        self.assertEqual(len(session.report()['observations']), count + 3)
        row = next(r for r in session.candidates() if r['candidate_id'] != self.reference['id'])
        self.assertFalse(row['property_prediction_conflict'])
        retained = Path(session.spec['artifact_directory']) / ('artifact-' + provenance['artifact_sha256'] + '.csv')
        self.assertEqual(retained.read_bytes(), path.read_bytes())

    def test_reference_conflict_persists_and_blocks_search_after_restart(self):
        session = self.create()
        path, provenance = self.artifact([('CCO', 2), ('CCCO', 1)])
        intake = session.import_csv(path, provenance, parent_id=self.reference['id'])
        self.assertIn('original_reference_property_conflict', intake['evaluation_blockers'])
        reopened = WorkflowSession(self.store, session.assignment_id)
        self.assertTrue(reopened.search_view()['evaluation_blockers'])
        self.assertEqual(reopened.search_view()['qualified_candidate_ids'], [])
        with self.assertRaises(ValueError):
            reopened.reserve(self.reference['id'], 'a')

    def test_new_parent_provenance_never_reanchors_similarity(self):
        session = self.create()
        alternative = {'id': 'another-parent', 'form_id': 'another-parent-form', 'representation': 'CCCC', 'source': 'ENGINEERING FIXTURE'}
        self.store.dispatch('candidate', session.campaign_id, alternative)
        path, provenance = self.artifact([('CCCO', -.5)])
        session.import_csv(path, provenance, parent_id=alternative['id'])
        row = next(r for r in session.search_view()['rows'] if r.get('canonical_form') == 'CCCO')
        generator = rdFingerprintGenerator.GetMorganGenerator(radius=2)
        expected = DataStructs.TanimotoSimilarity(generator.GetSparseCountFingerprint(Chem.MolFromSmiles('CCO')),
                                                  generator.GetSparseCountFingerprint(Chem.MolFromSmiles('CCCO')))
        self.assertEqual(row['values']['lead_similarity'], expected)
        record = next(c for c in session.report()['candidates'] if c['id'] == row['candidate_id'])
        self.assertEqual(record['parent_id'], alternative['id'])
        self.assertEqual(session.spec['reference']['representation'], 'CCO')

    def test_host_qualified_success_stops_dispatch_without_more_reservations(self):
        session = self.create()
        # Isolate workflow terminal admission. Actual chemistry qualification is
        # tested separately; this positive host-view double is not molecule evidence.
        view = session.search_view()
        view['qualified_candidate_ids'] = ['ENGINEERING_HOST_VIEW_DOUBLE']
        with patch('workflow.search.build_search_view', return_value=view):
            self.assertEqual(session.search_view()['eligible_actions'], [])
            with self.assertRaises(ValueError):
                session.reserve(self.reference['id'], 'a')
        self.assertEqual(session.attempts(), [])

    def test_changed_artifact_bytes_rejected_before_observation_intake(self):
        session = self.create()
        path, provenance = self.artifact([('CCCO', -.5)])
        path.write_text('SMILES,Lipophilicity\nCCCO,2\n')
        with self.assertRaisesRegex(ValueError, 'artifact identity'):
            session.import_csv(path, provenance)
        self.assertEqual(len(session.report()['observations']), 3)

    def test_context_projection_preserves_all_candidates_evidence_and_actions(self):
        session = self.create()
        path, provenance = self.artifact([('CCCO', -.5)])
        session.import_csv(path, provenance, parent_id=self.reference['id'])
        view = session.search_view()
        context = episode_context(session, {'job_name': JOB_NAME})
        helper = context['helper_summaries']
        identities = {p['candidate_id']: (p['form_id'], p['representation']) for p in context['parent_options']}
        for cid, representation, override in helper['nonparent_identities']:
            identities[cid] = (override or 'canonical-isomeric-' + cid[len('candidate-'):], representation)
        self.assertEqual(identities, {r['candidate_id']: (r['form_id'], r['representation']) for r in view['rows']})
        self.assertEqual({a['action_key'] for a in helper['eligible_actions']}, {a['action_key'] for a in view['eligible_actions']})
        self.assertEqual(len(helper['rows']), len(view['rows']))
        before = {r['candidate_id']: r for r in view['rows']}
        for row in helper['rows']:
            facts = dict(zip(helper['row_columns'], row['facts']))
            self.assertEqual(facts['parent_admissible'], before[row['candidate_id']]['parent_admissible'])
            self.assertEqual(facts['lipophilicity'], before[row['candidate_id']]['values']['lipophilicity'])
            self.assertEqual(facts['lead_similarity'], before[row['candidate_id']]['values']['lead_similarity'])
        cited = {eid for row in helper['rows'] for eid in row['evidence_ids']}
        self.assertEqual(cited, {o['id'] for o in session.report()['observations']})
        self.assertEqual(context['capability_contract']['execution_mode'], 'host_mediated')
        self.assertEqual(context['resources']['remaining_scientific_submissions'], 2)

    def test_host_mediated_request_schema_requires_real_action_and_no_invented_job(self):
        from jsonschema import Draft202012Validator
        schema = json.loads((Path(__file__).resolve().parents[1] / 'specialist/optimization-v1/outcome.schema.json').read_text())
        validate = Draft202012Validator(schema)
        output = {'schema_version': 1, 'assignment_id': 'engineering-assignment', 'episode_id': 'episode-1',
                  'input_digest': 'a' * 64, 'status': 'action_requested',
                  'chosen_action': {'kind': 'generate', 'parent_id': 'parent', 'library_id': 'library', 'action_key': 'b' * 64},
                  'evidence_ids': [], 'final_candidate_ids': [], 'pending_jobs': [], 'artifact_refs': [],
                  'rationale': 'Explicit engineering fixture, not a model result.', 'stop_reason': 'host_execution_requested',
                  'limitations': ['No job submitted.'], 'information_requests': []}
        validate.validate(output)
        for change in ({'chosen_action': None}, {'final_candidate_ids': ['invented']},
                       {'pending_jobs': [{'job_name': JOB_NAME, 'doc_id': 'invented', 'status': 'pending'}]}):
            self.assertTrue(list(validate.iter_errors({**output, **change})))


if __name__ == '__main__':
    unittest.main()
