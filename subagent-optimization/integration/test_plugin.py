"""Portable native-bridge boundary checks; no SDK, model or scientific service."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import patch


def load_plugin():
    path = Path(__file__).with_name('plugin') / '__init__.py'
    spec = importlib.util.spec_from_file_location('smallmol_plugin_portable', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.plugin = load_plugin()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.owner = self.root / 'owner'; self.owner.mkdir()
        self.other = self.root / 'other'; self.other.mkdir()
        self.active_home, self.policy = self.owner, None
        self.session_id = 'fixture-native-child-session'
        self.bundle = self.root / 'bundle'; self.bundle.mkdir()
        (self.bundle / 'workflow').mkdir()
        (self.bundle / 'workflow/delegated_bridge.py').write_text('# fixture only\n')
        self.environment = self.root / 'environment'; self.environment.mkdir()
        (self.environment / 'leadopt_env').mkdir()
        (self.environment / 'leadopt_env/core.py').write_text('# fixture only\n')
        self.state = self.root / 'private-state'; self.state.mkdir(mode=0o700)
        self.runtime = {'bundle_root': str(self.bundle), 'environment_source': str(self.environment),
                        'host_root': str(self.bundle), 'sdk_python': sys.executable,
                        'scoring_python': sys.executable, 'owner_home': str(self.owner),
                        'state_root': str(self.state), 'specialist_revision': 'actual-native-store-revision'}
        self.config = self.root / 'runtime.json'
        self.config.write_text(json.dumps(self.runtime))
        self.plugin.RUNTIME_FILE = self.config
        self.task = self.root / 'task.md'; self.task.write_text('# Initialized fixture task\n')
        agent = ModuleType('agent'); agent.__path__ = []
        policy = ModuleType('agent.specialist_policy'); policy.current_policy = lambda: self.policy
        constants = ModuleType('sci_constants'); constants.get_sci_home = lambda: self.active_home
        gateway = ModuleType('gateway'); gateway.__path__ = []
        session = ModuleType('gateway.session_context')
        session.get_session_env = lambda name, default=None: self.session_id if name == 'SCI_SESSION_ID' else default
        self.modules = patch.dict(sys.modules, {'agent': agent, 'agent.specialist_policy': policy,
                                                'sci_constants': constants, 'gateway': gateway,
                                                'gateway.session_context': session})
        self.modules.start(); self.addCleanup(self.modules.stop)
        self.requests = []

    def specialist(self, **changes):
        values = {'name': self.plugin.EXPECTED_SPECIALIST,
                  'revision': self.runtime['specialist_revision'], 'home': str(self.owner),
                  'deadline': time.monotonic() + 60}
        values.update(changes); self.policy = SimpleNamespace(**values)

    def process(self, command, **kwargs):
        request_path = Path(command[command.index('--request') + 1])
        response = Path(command[command.index('--response') + 1])
        request = json.loads(request_path.read_text())
        self.requests.append((command, kwargs, request, request_path))
        response.write_text(json.dumps({'phase': 'fixture_observation', 'scientific_jobs': 0}))
        return SimpleNamespace(returncode=0, stdout='', stderr='')

    def call(self, operation, **extra):
        args = {'operation': operation, 'task_file': str(self.task), **extra}
        return json.loads(self.plugin.handle(args))

    def test_main_inspects_collects_without_domain_decision_permission(self):
        with patch.object(self.plugin.subprocess, 'run', side_effect=self.process) as process:
            for operation in ('inspect', 'collect'):
                self.assertEqual(self.call(operation)['phase'], 'fixture_observation')
            for operation in ('evidence', 'evidence_part', 'apply'):
                extra = {'episode': 1, 'outcome': {}} if operation == 'apply' else {'episode': 1, 'part': 1} if operation == 'evidence_part' else {}
                self.assertEqual(self.call(operation, **extra)['phase'], 'blocked')
            self.assertEqual(process.call_count, 2)
        for _, _, request, _ in self.requests:
            self.assertEqual(request['caller'], {'transport': 'main-agent-tool', 'home': str(self.owner)})

    def test_native_identity_is_captured_from_scope_and_fixed_runtime(self):
        self.specialist()
        with patch.object(self.plugin.subprocess, 'run', side_effect=self.process):
            self.assertEqual(self.call('evidence')['phase'], 'fixture_observation')
            self.assertEqual(self.call('evidence_part', episode=1, part=2)['phase'], 'fixture_observation')
            self.assertEqual(self.call('apply', episode=2, outcome={'status': 'action_requested'})['phase'], 'fixture_observation')
        request = self.requests[-1][2]
        self.assertEqual(request['episode'], 2)
        self.assertEqual(request['runtime'], self.runtime)
        self.assertEqual(request['caller'], {'transport': 'native-specialist-tool',
                         'specialist': self.plugin.EXPECTED_SPECIALIST,
                         'revision': self.runtime['specialist_revision'], 'home': str(self.owner),
                         'session_id': self.session_id})

    def test_foreign_profile_specialist_revision_and_expiry_never_dispatch(self):
        with patch.object(self.plugin.subprocess, 'run') as process:
            for changes in ({'name': 'another-role'}, {'revision': 'old'}, {'home': str(self.other)},
                            {'deadline': time.monotonic()-1}):
                self.specialist(**changes)
                self.assertEqual(self.call('evidence')['phase'], 'blocked')
                self.assertEqual(self.call('inspect')['phase'], 'blocked')
            self.policy = None
            for home, expected in ((self.owner, 'fixture_observation'), (self.other, 'blocked'),
                                   (self.owner, 'fixture_observation')):
                self.active_home = home
                process.side_effect = self.process
                self.assertEqual(self.call('inspect')['phase'], expected)
            self.assertEqual(process.call_count, 2)

    def test_model_cannot_supply_paths_runtime_or_caller_grants(self):
        self.specialist()
        with patch.object(self.plugin.subprocess, 'run') as process:
            for supplied in ({'caller': {'specialist': self.plugin.EXPECTED_SPECIALIST}},
                             {'runtime': self.runtime}, {'owner_home': str(self.other)},
                             {'episode': True, 'outcome': {}}, {'episode': 0, 'outcome': {}},
                             {'episode': 1, 'outcome': 'unvalidated-text'},
                             {'episode': 1, 'part': 1, 'outcome': {}}, {'session_id': 'forged'}):
                self.assertEqual(self.call('apply', **supplied)['phase'], 'blocked')
            self.assertEqual(self.call('inspect', outcome={})['phase'], 'blocked')
            self.assertEqual(self.call('evidence', task_file='relative.md')['phase'], 'blocked')
            process.assert_not_called()

    def test_evidence_parts_require_manifest_identifiers_and_live_child_session(self):
        self.specialist()
        with patch.object(self.plugin.subprocess, 'run') as process:
            for extra in ({}, {'episode': 1}, {'episode': True, 'part': 1},
                          {'episode': 1, 'part': 0}, {'episode': 1, 'part': True},
                          {'episode': 1, 'part': 1, 'outcome': {}}):
                self.assertEqual(self.call('evidence_part', **extra)['phase'], 'blocked')
            self.session_id = ''
            self.assertEqual(self.call('evidence')['phase'], 'blocked')
            self.assertEqual(self.call('evidence_part', episode=1, part=1)['phase'], 'blocked')
            self.assertEqual(self.call('apply', episode=1, outcome={})['phase'], 'blocked')
            process.assert_not_called()

    def test_private_file_transport_no_shell_or_lazy_installs_and_timeout_bound(self):
        self.specialist()
        with patch.dict(os.environ, {'__SCI_ACTIVATED': 'fixture', 'PYTHONPATH': 'foreign', 'VIRTUAL_ENV': 'foreign'}):
            with patch.object(self.plugin.subprocess, 'run', side_effect=self.process):
                self.call('evidence')
        command, kwargs, request, request_path = self.requests[0]
        self.assertEqual(command[:4], [sys.executable, '-B', '-m', 'workflow.delegated_bridge'])
        self.assertEqual(kwargs['cwd'], str(self.bundle))
        self.assertNotIn('shell', kwargs)
        self.assertGreater(kwargs['timeout'], 0)
        self.assertLessEqual(kwargs['timeout'], 60)
        for name in ('__SCI_ACTIVATED', 'PYTHONPATH', 'VIRTUAL_ENV'):
            self.assertNotIn(name, kwargs['env'])
        self.assertEqual(kwargs['env']['SCI_DISABLE_LAZY_INSTALLS'], '1')
        self.assertEqual(request_path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(request_path.parent.stat().st_mode & 0o777, 0o700)
        self.assertNotIn('api_key', json.dumps(request))

    def test_timeout_nonzero_and_missing_response_are_unknown_without_retry(self):
        self.specialist()
        for effect in (subprocess.TimeoutExpired(['fixture-host'], 1),
                       SimpleNamespace(returncode=1, stdout='', stderr='fixture failed'),
                       SimpleNamespace(returncode=0, stdout='', stderr='')):
            kwargs = {'side_effect': effect} if isinstance(effect, Exception) else {'return_value': effect}
            with patch.object(self.plugin.subprocess, 'run', **kwargs) as process:
                result = self.call('apply', episode=1, outcome={})
                self.assertEqual(result['phase'], 'needs_attention')
                self.assertEqual(result['execution_outcome'], 'unknown')
                self.assertEqual(process.call_count, 1)

    def test_installed_config_and_task_symlinks_never_dispatch(self):
        with patch.object(self.plugin.subprocess, 'run') as process:
            link = self.root / 'linked-runtime.json'; link.symlink_to(self.config)
            self.plugin.RUNTIME_FILE = link
            self.assertEqual(self.call('inspect')['phase'], 'blocked')
            self.plugin.RUNTIME_FILE = self.config
            link = self.root / 'linked-task.md'; link.symlink_to(self.task)
            self.assertEqual(self.call('inspect', task_file=str(link))['phase'], 'blocked')
            process.assert_not_called()

    def test_registration_uses_native_plugin_surface_and_scoped_owner(self):
        class Context:
            def __init__(self): self.tools = []; self.skills = []; self.sections = []
            def register_tool(self, **kwargs): self.tools.append(kwargs)
            def register_skill(self, *args, **kwargs): self.skills.append((args, kwargs))
            def register_system_prompt_section(self, *args, **kwargs): self.sections.append((args, kwargs))
        context = Context(); self.plugin.register(context)
        self.assertEqual(len(context.tools), 1)
        self.assertEqual(context.tools[0]['name'], 'smallmol_campaign')
        self.assertEqual(context.tools[0]['toolset'], 'smallmol_optimization')
        self.assertEqual(context.tools[0]['schema']['parameters']['additionalProperties'], False)
        self.assertEqual(context.skills[0][0][0], 'smallmol-routing')
        render = context.sections[0][0][1]
        self.assertLess(len(render({})), 1200)
        self.assertIn('smallmol-routing', render({}))
        self.specialist()
        self.assertEqual(render({}), '')
        self.policy = None
        self.active_home = self.other
        with self.assertRaises(ValueError): self.plugin.register(Context())


if __name__ == '__main__':
    unittest.main()
