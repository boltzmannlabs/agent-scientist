"""Portable file launch checks; no SDK import, credentials or network access."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from workflow.runtime_launch import launch_spec, run_script


class RuntimeLaunchTests(unittest.TestCase):
    def test_requires_real_script_and_preserves_caller_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'run_agent.py').touch(); (root / 'pm').mkdir()
            home = root / 'isolated'; home.mkdir()
            environment = {'KEEP': 'yes', '__SCI_ACTIVATED': '/wrong/profile/facts.json',
                           'VIRTUAL_ENV': '/wrong/venv', 'PYTHONPATH': '/wrong/source'}
            script = root / 'probe.py'; script.write_text('print("unused")')
            command, env = launch_spec(host_root=root, interpreter=sys.executable, sci_home=home,
                                       script=script, environment=environment)
            self.assertEqual(command[2], str(script))
            self.assertEqual(environment['PYTHONPATH'], '/wrong/source')
            self.assertEqual(env['SCI_HOME'], str(home))
            self.assertEqual(env['SCI_RUNTIME_DIR'], str(home / 'tools'))
            self.assertNotIn('__SCI_ACTIVATED', env)
            self.assertNotIn('VIRTUAL_ENV', env)
            self.assertEqual(env['KEEP'], 'yes')
            with self.assertRaises(ValueError):
                launch_spec(host_root=root, interpreter=sys.executable, sci_home=home, script='-')

    def test_child_observes_selected_home_and_literal_arguments(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / 'run_agent.py').touch(); (root / 'pm').mkdir()
            home = root / 'isolated'; home.mkdir()
            script = root / 'probe.py'
            script.write_text('import json,os,sys\nprint(json.dumps({"home":os.environ["SCI_HOME"],"args":sys.argv[1:]}))\n')
            result = run_script(host_root=root, interpreter=sys.executable, sci_home=home, script=script,
                                arguments=['$(must-not-execute)', 'literal value'], environment={})
            self.assertEqual(result.returncode, 0)
            self.assertEqual(json.loads(result.stdout), {'home':str(home), 'args':['$(must-not-execute)', 'literal value']})


if __name__ == '__main__':
    unittest.main()
