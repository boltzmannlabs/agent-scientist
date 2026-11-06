"""Normal-dispatch gate checks with the actual environment DB; no network/jobs.

Connector results below are explicit fixtures, never live scientific evidence.
The global qualified scoring interpreter supplies RDKit for task admission.
"""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ENV_SRC = Path('/home/boltzmann13/science-environments/environments/small-molecule-lead-optimization/src')
sys.path.insert(0, str(ENV_SRC))
from leadopt_env.core import CampaignStore
from pilot.bridge import JOB_NAME
from pilot.test_property_assessment import configuration
from workflow.admission import APPROVED_WARNING, AdmissionGate, install
from workflow.session import WorkflowSession


class AdmissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        config = configuration()
        self.ref = config['reference']
        self.library = self.folder / 'library.csv'
        self.library.write_text('SMILES\nCCO\n')
        self.sha = hashlib.sha256(self.library.read_bytes()).hexdigest()
        signatures = {endpoint: {'unit': 'provider_score_unverified' if endpoint == 'lipophilicity' else 'dimensionless',
                                'method': 'TEST_FIXTURE', 'method_version': '1', 'kind': 'predicted', 'context': 'TEST_FIXTURE'}
                      for endpoint in ('lipophilicity', 'qed', 'lead_similarity')}
        observations = [{'id': 'fixture-' + endpoint, 'candidate_id': self.ref['id'], 'form_id': self.ref['form_id'],
                         'endpoint': endpoint, 'value': value, 'qualifier': '=', 'status': 'completed',
                         'source': 'TEST_FIXTURE', **signatures[endpoint]}
                        for endpoint, value in config['baseline'].items()]
        task = {'schema_version': 1, 'id': 'fixture-task', 'version': '1', 'allowed_jobs': [JOB_NAME],
                'starting_candidates': [self.ref], 'initial_observations': observations,
                'constraints': [{'id': 'lip-range', 'endpoint': 'lipophilicity', 'minimum': 0, 'maximum': 3,
                                 **signatures['lipophilicity']},
                                {'id': 'qed-bound', 'endpoint': 'qed',
                                 'minimum': math.nextafter(config['baseline']['qed'], math.inf), **signatures['qed']},
                                {'id': 'sim-bound', 'endpoint': 'lead_similarity',
                                 'minimum': math.nextafter(.7, math.inf), **signatures['lead_similarity']}]}
        self.spec = {'assignment_id': 'fixture-assignment', 'campaign_id': 'fixture-campaign',
                     'reference': self.ref, 'assessor': config,
                     'objective': {'target_min': 0, 'target_max': 3, 'qed_min_exclusive': config['baseline']['qed'],
                                   'similarity_min_exclusive': .7,
                                   'generation_parameters': {'global_models': [
                                       {'name': 'Lipophilicity', 'min_threshold': 0, 'max_threshold': 3}]}},
                     'libraries': [{'id': 'fixture-library', 'csv_path': str(self.library), 'content_sha256': self.sha,
                                    'approved_generic_smiles_warning': True}],
                     'observation_signatures': signatures,
                     'artifact_directory': str(self.folder / 'artifacts'),
                     'limits': {'max_scientific_submissions': 2, 'max_episodes': 3,
                                'deadline_utc': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()}}
        self.store = CampaignStore(self.folder / 'campaign.sqlite3')
        self.session = WorkflowSession.create(self.store, self.spec, task)
        self.gate = AdmissionGate(self.session, warning_validator=lambda stage, args: {
            'warnings': [APPROVED_WARNING], 'errors': []})
        self.calls = []

    def call(self, tool, args, result=None, effect=None):
        def downstream(actual):
            self.calls.append((tool, deepcopy(actual)))
            return effect(actual) if effect else deepcopy(result)
        return self.gate(tool_name=tool, args=deepcopy(args), next_call=downstream)

    def upload_args(self):
        return {'job_name': JOB_NAME, 'input_field': 'library_path', 'local_path': str(self.library),
                'experiment_data': {**deepcopy(self.spec['objective']['generation_parameters']), 'ref_mol': self.ref['representation']}}

    def upload(self):
        def uploaded(args):
            self.assertEqual(self.session.attempts()[0]['state'], 'uploading')
            return {'status': 'uploaded', 'sha256': self.sha, 's3_path': 'users/TEST_FIXTURE/library.csv'}
        return self.call('boltzmann_upload', self.upload_args(), effect=uploaded)

    def submit(self):
        upload = self.upload()
        def accepted(args):
            self.assertEqual(self.session.attempts()[0]['state'], 'submitting')
            return {'status': 'accepted', 'job_name': JOB_NAME, 'doc_id': 'TEST-JOB'}
        return upload, self.call('boltzmann_submit', upload['workflow_next_submit'], effect=accepted)

    def status(self, status='Success'):
        return self.call('boltzmann_status', {'job_name': JOB_NAME, 'doc_id': 'TEST-JOB'}, result={
            'status': status, 'job_name': JOB_NAME, 'doc_id': 'TEST-JOB',
            'OutputData': {'output_path': {'download_link': ['https://fixture.invalid/output?sig=TEST']}}})

    def test_actual_store_intent_precedes_native_upload_submit_and_repeat_is_blocked(self):
        upload, submit = self.submit()
        self.assertEqual(submit['status'], 'accepted')
        self.assertEqual(self.session.attempts()[0]['state'], 'accepted')
        self.assertTrue(self.calls[0][1]['allow_partial_validation'])
        self.assertEqual(self.session.report()['actions'][-1]['job_id'], 'TEST-JOB')
        count = len(self.calls)
        repeated = self.call('boltzmann_submit', upload['workflow_next_submit'])
        self.assertEqual(repeated['status'], 'blocked')
        self.assertEqual(len(self.calls), count)

    def test_wrong_job_parent_library_and_changed_objective_never_dispatch(self):
        variants = []
        for key, value in [('job_name', 'Other_Job'), ('local_path', str(self.folder / 'unknown.csv')),
                           ('input_field', 'other_field')]:
            args = self.upload_args(); args[key] = value; variants.append(args)
        args = self.upload_args(); args['experiment_data']['ref_mol'] = 'CCO'; variants.append(args)
        args = self.upload_args(); args['experiment_data']['global_models'][0]['max_threshold'] = 4; variants.append(args)
        for args in variants:
            with self.subTest(args=args):
                self.assertEqual(self.call('boltzmann_upload', args)['status'], 'blocked')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.session.attempts(), [])

    def test_model_partial_flag_cannot_grant_approval_and_other_native_warnings_are_not_bypassed(self):
        self.session.spec['libraries'][0]['approved_generic_smiles_warning'] = False
        args = self.upload_args(); args['allow_partial_validation'] = True
        self.assertEqual(self.call('boltzmann_upload', args)['status'], 'blocked')
        self.assertEqual(self.calls, [])
        self.session.spec['libraries'][0]['approved_generic_smiles_warning'] = True
        self.gate.warning_validator = lambda stage, args: {'warnings': [APPROVED_WARNING, 'DIFFERENT_WARNING'], 'errors': []}
        self.assertEqual(self.call('boltzmann_upload', self.upload_args())['status'], 'blocked')
        self.assertEqual(self.calls, [])
        self.gate.warning_validator = lambda stage, args: {'warnings': [APPROVED_WARNING], 'errors': []}
        result = self.call('boltzmann_upload', self.upload_args(), result={
            'status': 'approval_required', 'error': 'A different unchecked aspect requires review',
            'validation': {'warnings': ['DIFFERENT_WARNING']}})
        self.assertEqual(result['status'], 'approval_required')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.session.attempts()[0]['state'], 'upload_blocked')

    def test_internal_error_returns_blocked_instead_of_allowing_middleware_fallback(self):
        def framework(args):
            try:
                return self.gate(tool_name='boltzmann_upload', args=args,
                                 next_call=lambda payload: self.calls.append(payload))
            except Exception:
                self.calls.append('UNSAFE_FAIL_OPEN_FALLBACK')
        with patch.object(self.session, 'reserve', side_effect=RuntimeError('injected local DB failure')):
            result = framework(self.upload_args())
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.calls, [])

    def test_deadline_or_new_objective_success_before_submit_blocks_the_scientific_call(self):
        upload = self.upload()
        self.session.spec['limits']['deadline_utc'] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        self.assertEqual(self.call('boltzmann_submit', upload['workflow_next_submit'])['status'], 'blocked')
        self.assertEqual(len(self.calls), 1)
        self.assertEqual(self.session.attempts()[0]['state'], 'uploaded')
        self.session.spec['limits']['deadline_utc'] = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        view = self.session.search_view()
        view['qualified_candidate_ids'] = ['TEST_ONLY_OBJECTIVE_SUCCESS']
        with patch.object(self.session, 'search_view', return_value=view):
            self.assertEqual(self.call('boltzmann_submit', upload['workflow_next_submit'])['status'], 'blocked')
        self.assertEqual(len(self.calls), 1)

    def test_changed_library_bytes_and_zero_reservation_allowance_block_before_dispatch(self):
        self.library.write_text('SMILES\nCCN\n')
        self.assertEqual(self.call('boltzmann_upload', self.upload_args())['status'], 'blocked')
        self.library.write_text('SMILES\nCCO\n')
        self.session.spec['limits']['max_scientific_submissions'] = 0
        self.assertEqual(self.call('boltzmann_upload', self.upload_args())['status'], 'blocked')
        self.assertEqual(self.calls, [])

    def test_submit_ambiguity_is_retained_and_not_automatically_repeated(self):
        upload = self.upload()
        def uncertain(args):
            raise RuntimeError('Transport failed after dispatch')
        result = self.call('boltzmann_submit', upload['workflow_next_submit'], effect=uncertain)
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(self.session.attempts()[0]['state'], 'unknown')
        count = len(self.calls)
        self.assertEqual(self.call('boltzmann_submit', upload['workflow_next_submit'])['status'], 'blocked')
        self.assertEqual(len(self.calls), count)

    def test_submit_with_invented_storage_or_wrong_experiment_identity_is_blocked(self):
        upload = self.upload()
        args = deepcopy(upload['workflow_next_submit']); args['experiment_data']['library_path'] = 'invented-storage'
        self.assertEqual(self.call('boltzmann_submit', args)['status'], 'blocked')
        args = deepcopy(upload['workflow_next_submit']); args['experiment_name'] = 'invented-name'
        self.assertEqual(self.call('boltzmann_submit', args)['status'], 'blocked')
        self.assertEqual(len(self.calls), 1)

    def test_missing_accepted_job_id_is_ambiguous_not_success(self):
        upload = self.upload()
        result = self.call('boltzmann_submit', upload['workflow_next_submit'], result={'status': 'accepted'})
        self.assertEqual(result['status'], 'unknown')
        self.assertEqual(self.session.attempts()[0]['state'], 'unknown')
        self.assertEqual(self.session.attempts()[0]['dispatch_error']['raw_returned_receipt'], {'status': 'accepted'})

    def test_receipt_persistence_failure_preserves_private_recovery_evidence(self):
        upload = self.upload()
        receipt = self.session.receipt
        def faulty(key, kind, value, state):
            if kind == 'submit':
                raise RuntimeError('injected receipt persistence failure')
            return receipt(key, kind, value, state)
        with patch.object(self.session, 'receipt', side_effect=faulty):
            result = self.call('boltzmann_submit', upload['workflow_next_submit'], result={
                'status': 'accepted', 'job_name': JOB_NAME, 'doc_id': 'TEST-JOB'})
        self.assertEqual(result['status'], 'unknown')
        files = list(Path(self.spec['artifact_directory']).glob('receipt-recovery-*.json'))
        self.assertTrue(files)
        self.assertEqual(json.loads(files[0].read_text())['value']['doc_id'], 'TEST-JOB')
        self.assertEqual(files[0].stat().st_mode & 0o777, 0o600)

    def test_native_success_is_preserved_and_failed_job_never_reopens(self):
        self.submit()
        result = self.status()
        action = self.session.attempts()[0]
        self.assertEqual(result['status'], 'Success')
        self.assertEqual(action['monitor']['status'], 'Success')
        self.assertEqual(action['state'], 'results_ready')
        self.status('Failed')
        self.assertEqual(self.session.attempts()[0]['state'], 'failed')
        self.status('Success')
        self.assertEqual(self.session.attempts()[0]['state'], 'failed')

    def test_only_owned_job_status_and_original_download_reference_are_admitted(self):
        self.submit()
        count = len(self.calls)
        result = self.call('boltzmann_status', {'job_name': JOB_NAME, 'doc_id': 'OTHER-JOB'})
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(len(self.calls), count)
        ready = self.status()
        for url, folder in [('https://fixture.invalid/other', ready['workflow_download_folder']),
                            ('https://fixture.invalid/output?sig=TEST', str(self.folder / 'outside'))]:
            count = len(self.calls)
            result = self.call('boltzmann_download', {'download_url': url, 'output_folder': folder})
            self.assertEqual(result['status'], 'blocked')
            self.assertEqual(len(self.calls), count)

    def test_read_only_status_transport_error_preserves_known_scientific_state(self):
        self.submit()
        def broken(args):
            raise RuntimeError('Observation transport failed')
        result = self.call('boltzmann_status', {'job_name': JOB_NAME, 'doc_id': 'TEST-JOB'}, effect=broken)
        self.assertEqual(result['status'], 'blocked')
        self.assertEqual(self.session.attempts()[0]['state'], 'accepted')
        self.assertEqual(self.session.attempts()[0]['submit']['doc_id'], 'TEST-JOB')
        self.assertTrue(list(Path(self.spec['artifact_directory']).glob('receipt-recovery-*.json')))

    def test_download_records_exact_bytes_and_waits_for_host_assessment(self):
        self.submit(); ready = self.status()
        def downloaded(args):
            folder = Path(args['output_folder']); folder.mkdir(parents=True)
            output = folder / 'result.csv'; output.write_text('SMILES,Lipophilicity\nCCO,1\n')
            return {'status': 'downloaded', 'output_paths': [str(output)], 'errors': []}
        result = self.call('boltzmann_download', {'download_url': 'https://fixture.invalid/output?sig=TEST',
                           'output_folder': ready['workflow_download_folder']}, effect=downloaded)
        self.assertEqual(result['workflow_state'], 'downloaded')
        action = self.session.attempts()[0]
        self.assertEqual(action['state'], 'downloaded')
        self.assertEqual(len(action['download']['_workflow_manifest']), 1)
        manifest = action['download']['_workflow_manifest'][0]
        self.assertEqual(hashlib.sha256(Path(manifest['path']).read_bytes()).hexdigest(), manifest['sha256'])
        self.assertNotEqual(action['state'], 'complete')

    def test_environment_measurement_writes_and_foreign_campaign_reads_are_blocked(self):
        for args in [{'operation': 'observation', 'campaign_id': self.session.campaign_id, 'payload': {}},
                     {'operation': 'report', 'campaign_id': 'other-campaign'},
                     {'operation': 'report', 'campaign_id': self.session.campaign_id, 'payload': {'candidate': 'invented'}}]:
            self.assertEqual(self.call('leadopt_campaign', args)['status'], 'blocked')
        self.assertEqual(self.calls, [])
        result = self.call('leadopt_campaign', {'operation': 'report', 'campaign_id': self.session.campaign_id},
                           effect=lambda args: self.store.dispatch(args['operation'], args['campaign_id']))
        self.assertEqual(result['campaign_id'], self.session.campaign_id)

    def test_registration_and_unrelated_tools_keep_the_normal_dispatch_path(self):
        registrations = []
        class Context:
            def register_middleware(self, kind, callback):
                registrations.append((kind, callback)); return 'registration'
        self.assertEqual(install(Context(), self.session), 'registration')
        self.assertEqual(registrations[0][0], 'tool_execution')
        self.assertTrue(callable(registrations[0][1]))
        denied = json.loads(registrations[0][1](tool_name='leadopt_campaign',
            args={'operation':'record_batch','campaign_id':self.session.campaign_id},
            next_call=lambda args: self.fail('SDK registration must block model-written measurements')))
        self.assertEqual(denied['status'], 'blocked')
        self.assertEqual(self.call('some_existing_read_tool', {'x': 1}, result={'normal': True}), {'normal': True})


if __name__ == '__main__':
    unittest.main()
