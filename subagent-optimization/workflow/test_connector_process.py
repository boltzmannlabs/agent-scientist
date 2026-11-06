"""Private RPC checks with an explicit fixture SDK, never the live connector."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from workflow.connector_process import OwningHostDispatcher, ProcessOutcomeUnknown


class ConnectorProcessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.host = self.root / 'fixture-sdk'; self.host.mkdir()
        self.owner = self.root / 'fixture-owner'; self.owner.mkdir()
        self.private = self.root / 'private'
        self.put('sci_cli/__init__.py', '')
        self.put('sci_cli/config.py', '''
def load_config_readonly():
    return {'platform_toolsets': {'cli': ['fixture-boltzmann']}, 'agent': {'disabled_toolsets': ['fixture-disabled']}}
''')
        self.put('model_tools.py', '''
import os
from pathlib import Path
def _select_tool_names(enabled, disabled, quiet_mode):
    assert enabled == ['fixture-boltzmann'] and disabled == ['fixture-disabled']
    if (Path(os.environ['SCI_HOME']) / 'deny-fixture-grants').exists():
        return set()
    return {'boltzmann_upload', 'boltzmann_submit', 'boltzmann_status', 'boltzmann_download'}
def handle_function_call(name, args, **kwargs):
    home = Path(os.environ['SCI_HOME'])
    with (home / 'fixture-dispatch-count').open('a') as stream:
        stream.write(name + '\\n')
    print('PRIVATE_FIXTURE_SDK_DIAGNOSTIC')
    if args.get('fixture_raise'):
        raise RuntimeError('DO_NOT_PRINT_PRIVATE_EXCEPTION_TEXT')
    return {'status': 'EXPLICIT_TRANSPORT_FIXTURE', 'tool': name, 'arguments': args,
            'owner_home': str(home), 'lazy_installs_disabled': os.environ.get('SCI_DISABLE_LAZY_INSTALLS'),
            'inherited_activation': os.environ.get('__SCI_ACTIVATED'),
            'inherited_profile': os.environ.get('SCI_PROFILE'),
            'grants': kwargs['enabled_tools']}
''')
        self.put('plugins/__init__.py', '')
        self.put('plugins/boltzmann/__init__.py', '')
        self.put('plugins/boltzmann/contracts.py', '''
class ContractStore:
    def file_rule(self, job, field):
        return {'job': job, 'field': field}
''')
        self.put('plugins/boltzmann/file_validation.py', '''
class Report:
    def as_dict(self):
        return {'errors': [], 'warnings': ['EXPLICIT_VALIDATION_FIXTURE']}
def validate_file(path, rule, payload):
    assert path.is_file() and rule['field'] == 'library_path'
    return Report()
''')
        self.put('plugins/boltzmann/preflight.py', '''
class Report:
    def as_dict(self):
        return {'errors': [], 'warnings': ['EXPLICIT_SUBMISSION_VALIDATION_FIXTURE']}
def preflight_submission(job, payload):
    assert job == 'Fragment_Based_Optimization'
    return Report()
''')
        self.dispatch = OwningHostDispatcher(self.host, sys.executable, self.owner, self.private, timeout_seconds=5)

    def put(self, path, content):
        destination = self.host / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content)

    def count(self):
        path = self.owner / 'fixture-dispatch-count'
        return path.read_text().splitlines() if path.exists() else []

    def test_real_script_transport_calls_fixture_wrapper_once_and_keeps_output_private(self):
        (self.owner / '.env').write_text('OWNER_ONLY_TEST_MARKER=NOT_A_REAL_CREDENTIAL\n')
        standard_output = io.StringIO()
        with contextlib.redirect_stdout(standard_output), contextlib.redirect_stderr(standard_output):
            result = self.dispatch('boltzmann_status', {'job_name': 'Fragment_Based_Optimization', 'doc_id': 'FIXTURE-JOB'})
        self.assertEqual(standard_output.getvalue(), '')
        self.assertEqual(result['status'], 'EXPLICIT_TRANSPORT_FIXTURE')
        self.assertEqual(result['tool'], 'boltzmann_status')
        self.assertEqual(self.count(), ['boltzmann_status'])
        folder = next(self.private.iterdir())
        self.assertIn('PRIVATE_FIXTURE_SDK_DIAGNOSTIC', (folder / 'process.log').read_text())
        self.assertEqual({p.name for p in folder.iterdir()}, {'request.json', 'response.json', 'process.log'})
        for path in folder.iterdir():
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertNotIn('OWNER_ONLY_TEST_MARKER', path.read_text())
        self.assertEqual(folder.stat().st_mode & 0o777, 0o700)
        self.assertFalse(list(self.private.rglob('.env')))

    def test_process_selects_original_owner_and_removes_inherited_profile_activation(self):
        with patch.dict(os.environ, {'SCI_HOME': str(self.root / 'isolated-reasoning'),
                                     'SCI_PROFILE': 'wrong-profile', '__SCI_ACTIVATED': 'wrong-activation',
                                     'PYTHONPATH': '/untrusted/inherited/pythonpath'}):
            result = self.dispatch('boltzmann_status', {'doc_id': 'FIXTURE'})
        self.assertEqual(result['owner_home'], str(self.owner))
        self.assertEqual(result['lazy_installs_disabled'], '1')
        self.assertIsNone(result['inherited_activation'])
        self.assertIsNone(result['inherited_profile'])

    def test_validation_uses_existing_named_validators_without_scientific_dispatch(self):
        csv = self.root / 'library.csv'; csv.write_text('SMILES\nCCO\n')
        upload = self.dispatch.validate('upload', {'job_name': 'Fragment_Based_Optimization',
            'input_field': 'library_path', 'local_path': str(csv), 'experiment_data': {}})
        submission = self.dispatch.validate('submit', {'job_name': 'Fragment_Based_Optimization',
            'experiment_data': {'library_path': 'FIXTURE-STORAGE'}})
        self.assertEqual(upload['warnings'], ['EXPLICIT_VALIDATION_FIXTURE'])
        self.assertEqual(submission['warnings'], ['EXPLICIT_SUBMISSION_VALIDATION_FIXTURE'])
        self.assertEqual(self.count(), [])

    def test_tool_whitelist_and_credential_fields_reject_before_process_launch(self):
        with patch('workflow.connector_process.subprocess.run') as run:
            with self.assertRaises(ValueError):
                self.dispatch('terminal', {'command': 'forbidden'})
            for args in [{'api_key': 'NOT_REAL'}, {'metadata': {'Authorization': 'NOT_REAL'}},
                         {'BOLTZMANN_API_KEY': 'NOT_REAL'}]:
                with self.assertRaises(ValueError):
                    self.dispatch('boltzmann_status', args)
            with self.assertRaises(ValueError):
                self.dispatch.validate('unsupported-stage', {})
        run.assert_not_called()
        self.assertEqual(list(self.private.iterdir()), [])

    def test_owning_profile_grants_are_required_before_the_existing_wrapper(self):
        (self.owner / 'deny-fixture-grants').touch()
        with self.assertRaises(ProcessOutcomeUnknown):
            self.dispatch('boltzmann_submit', {'job_name': 'FIXTURE'})
        self.assertEqual(self.count(), [])

    def test_timeout_is_single_attempt_and_unknown_without_raw_exception_output(self):
        with patch('workflow.connector_process.subprocess.run', side_effect=subprocess.TimeoutExpired('PRIVATE', 5)) as run:
            with self.assertRaisesRegex(ProcessOutcomeUnknown, 'timed out'):
                self.dispatch('boltzmann_submit', {'job_name': 'FIXTURE'})
        self.assertEqual(run.call_count, 1)
        command = run.call_args.args[0]
        self.assertTrue(command[2].endswith('connector_process.py'))
        self.assertIn('--worker', command)
        self.assertNotIn('-c', command)
        self.assertEqual(len(list(self.private.iterdir())), 1)

    def test_dispatch_exception_returns_unknown_and_does_not_retry_or_expose_text(self):
        with self.assertRaises(ProcessOutcomeUnknown) as failure:
            self.dispatch('boltzmann_submit', {'fixture_raise': True})
        self.assertNotIn('DO_NOT_PRINT_PRIVATE_EXCEPTION_TEXT', str(failure.exception))
        self.assertEqual(self.count(), ['boltzmann_submit'])
        response = json.loads(next(self.private.glob('*/response.json')).read_text())
        self.assertFalse(response['ok'])
        self.assertTrue(response['dispatch_may_have_started'])
        self.assertEqual(response['error_type'], 'RuntimeError')

    def test_missing_malformed_or_symlink_response_never_establishes_success(self):
        def no_receipt(command, **kwargs):
            return subprocess.CompletedProcess(command, 0)
        with patch('workflow.connector_process.subprocess.run', side_effect=no_receipt) as run:
            with self.assertRaises(ProcessOutcomeUnknown):
                self.dispatch('boltzmann_status', {})
        self.assertEqual(run.call_count, 1)
        def malformed(command, **kwargs):
            response = Path(command[command.index('--response') + 1]); response.write_text('not-json')
            return subprocess.CompletedProcess(command, 0)
        with patch('workflow.connector_process.subprocess.run', side_effect=malformed):
            with self.assertRaises(ProcessOutcomeUnknown):
                self.dispatch('boltzmann_status', {})
        def linked(command, **kwargs):
            target = self.root / 'foreign-response.json'; target.write_text('{"ok":true,"result":{}}')
            response = Path(command[command.index('--response') + 1]); response.symlink_to(target)
            return subprocess.CompletedProcess(command, 0)
        with patch('workflow.connector_process.subprocess.run', side_effect=linked):
            with self.assertRaises(ProcessOutcomeUnknown):
                self.dispatch('boltzmann_status', {})

    def test_private_paths_cannot_be_in_source_or_symlinked(self):
        with self.assertRaisesRegex(ValueError, 'outside source'):
            OwningHostDispatcher(self.host, sys.executable, self.owner, self.host / 'private')
        link = self.root / 'private-link'; link.symlink_to(self.private)
        with self.assertRaisesRegex(ValueError, 'symlinks'):
            OwningHostDispatcher(self.host, sys.executable, self.owner, link / 'nested')


if __name__ == '__main__':
    unittest.main()
