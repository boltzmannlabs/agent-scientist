"""Delegation is usable after science-profile creation and existing-profile upgrade."""
from pathlib import Path

from sci_cli.native_profile_creation import profile_scope


def test_upgrade_profiles_a_b_a_and_preserve_later_opt_out(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, migrate_config, read_user_config_raw
    from sci_cli.config_defaults import DEFAULT_CONFIG
    from sci_cli.tools_config import _get_platform_tools
    from model_tools import get_tool_definitions
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name for name in ('main', 'project')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    for index, home in enumerate(homes):
        home.mkdir()
        # Wizard-created profiles were unstamped; existing main configs may be versioned.
        config = {'platform_toolsets': {'cli': ['terminal', 'file', 'skills'], 'webhook': []},
                  'agent': {'disabled_toolsets': ['delegation', 'web']},
                  'model': {'default': f'model-{index}'}, 'research_note': f'keep-{index}'}
        if not index:
            config['_config_version'] = 49
        atomic_config_replace(home / 'config.yaml', config)
        (home / '.env').write_text('PRIVATE_FIXTURE_KEY=fixture-only\n')
    for index in (0, 1, 0):
        with profile_scope(homes[index]):
            other = (homes[1-index] / 'config.yaml').read_bytes()
            migrate_config(interactive=False, quiet=True)
            raw = read_user_config_raw(homes[index] / 'config.yaml')
            assert raw['_config_version'] == DEFAULT_CONFIG['_config_version']
            assert raw['platform_toolsets']['cli'].count('delegation') == 1
            assert raw['platform_toolsets']['webhook'] == []
            assert raw['agent']['disabled_toolsets'] == ['web']
            assert raw['research_note'] == f'keep-{index}'
            assert (homes[index] / '.env').read_text() == 'PRIVATE_FIXTURE_KEY=fixture-only\n'
            assert (homes[1-index] / 'config.yaml').read_bytes() == other
            selected = _get_platform_tools(raw, 'cli')
            definitions = get_tool_definitions(sorted(selected), disabled_toolsets=['web'], quiet_mode=True,
                                               skip_tool_search_assembly=True)
            assert 'delegate_task' in {t['function']['name'] for t in definitions}
    with profile_scope(homes[0]):
        raw['platform_toolsets']['cli'].remove('delegation')
        atomic_config_replace(homes[0] / 'config.yaml', raw)
        migrate_config(interactive=False, quiet=True)
        assert 'delegation' not in _get_platform_tools(read_user_config_raw(homes[0] / 'config.yaml'), 'cli')


def test_fresh_main_default_and_legacy_restricted_boundary(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.config_migrations import _migrate_to_50
    from sci_cli.tools_config import _get_platform_tools
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path))
    assert 'delegation' in _get_platform_tools({}, 'cli')
    raw = {'platform_toolsets': {'cli': ['skills']}, 'agent': {'disabled_toolsets': ['delegation']}}
    atomic_config_replace(tmp_path / 'config.yaml', raw)
    (tmp_path / 'science-profile.json').write_text('{}')
    _migrate_to_50({'config_added': []}, True)
    assert read_user_config_raw(tmp_path / 'config.yaml') == raw
