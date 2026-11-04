"""Default specialist execution uses the real profile config, tool registry and Python kernel."""
from pathlib import Path
from types import SimpleNamespace
import json

from sci_cli.native_profile_creation import profile_scope


def test_main_profile_migration_and_new_specialist_defaults_a_b_a(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, migrate_config, read_user_config_raw
    from sci_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions
    from sci_cli.specialist_defaults import BASELINE_TOOLSETS
    from sci_cli.specialist_wizard import _capabilities
    from agent.specialist_store import Specialist
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('main', 'project')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    for home in homes:
        home.mkdir()
        atomic_config_replace(home / 'config.yaml', {'_config_version': 50,
            'platform_toolsets': {'cli': ['skills'], 'webhook': []},
            'agent': {'disabled_toolsets': ['terminal', 'code_execution', 'web']},
            'model': {'default': 'fixture'}, 'terminal': {'backend': 'local'}})
    for home in (homes[0], homes[1], homes[0]):
        with profile_scope(home):
            migrate_config(interactive=False, quiet=True)
            cfg = read_user_config_raw(home / 'config.yaml')
            assert set(BASELINE_TOOLSETS) <= set(cfg['platform_toolsets']['cli'])
            assert cfg['agent']['disabled_toolsets'] == ['web'] and cfg['platform_toolsets']['webhook'] == []
            tools = get_tool_definitions(sorted(_get_platform_tools(cfg, 'cli')), quiet_mode=True,
                                         skip_tool_search_assembly=True)
            names = {row['function']['name'] for row in tools}
            assert {'read_file', 'search_files', 'terminal', 'execute_code', 'delegate_task'} <= names
            selected = {name: 'fixture' for name in names if name != 'delegate_task'}
            monkeypatch.setattr('sci_cli.specialist_wizard.choices', lambda cli: ({}, selected))
            class UI:
                def show(self, text):
                    pass
                def choose(self, question, choices):
                    assert 'Done' in choices
                    return 'Done'
            item = _capabilities(SimpleNamespace(agent=None), UI(), Specialist('analyst', 'Analyse local data'))
            assert {'terminal', 'execute_code', 'read_file', 'search_files'} <= set(item.tools)
    with profile_scope(homes[1]):
        from agent.specialist_store import save, load
        from sci_cli.specialist_commands import dispatch
        save(Specialist('old-reviewer', 'Review data', tools=('read_file',)))
        class EditorUI:
            answers = iter(['Use standard tools', 'Save and enable for the next conversation'])
            def show(self, message):
                pass
            def choose(self, question, options):
                value = next(self.answers)
                assert value in options
                return value
        dispatch(SimpleNamespace(agent=None), '/Update_subagent old-reviewer', EditorUI())
        assert {'terminal', 'execute_code', 'read_file', 'search_files'} <= set(load('old-reviewer').tools)


def test_python_reference_executes_only_when_explicitly_called(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    from agent.specialist_sources import load_reference
    from tools.code_execution_tool import execute_code, check_sandbox_requirements
    from tools.code_kernel import shutdown_all_kernels
    from agent.specialist_policy import SpecialistPolicy, specialist_scope
    import time
    from sci_constants import get_sci_home
    home = get_sci_home()
    atomic_config_replace(home / 'config.yaml', {'terminal': {'backend': 'local', 'cwd': str(tmp_path)},
        'code_execution': {'mode': 'strict', 'timeout': 30}})
    marker = tmp_path / 'executed.txt'
    script = tmp_path / 'fixture.py'
    script.write_text(f'from pathlib import Path\nPath({str(marker)!r}).write_text("42")\nprint("RESULT", 6*7)\n')
    doc = load_reference(str(script))[0]
    assert not marker.exists()  # inspection never imports/runs a script
    assert check_sandbox_requirements()
    policy = SpecialistPolicy('analyst', str(home.resolve()), 'r', frozenset({'execute_code'}),
                              frozenset(), frozenset(), ('analyst',), time.monotonic() + 60)
    try:
        with specialist_scope(policy):
            result = json.loads(execute_code(doc['text'], task_id='approved-specialist-fixture', enabled_tools=[]))
        assert result['status'] == 'success', result
        assert 'RESULT 42' in result['output'] and marker.read_text() == '42'
    finally:
        shutdown_all_kernels()
