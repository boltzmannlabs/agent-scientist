"""Upgrade old approvals without granting host access or rewriting live conversations."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sci_cli.config import atomic_config_replace, read_user_config_raw
from sci_cli.native_profile_creation import profile_scope
from sci_cli.native_profile_update import update_wizard
from sci_cli.science_profile_cli_policy import prepare
from sci_cli.science_profiles import MANIFEST, ProfileSpec, Source, create, read_spec
from sci_cli.science_profiles_sandbox import validate_runtime
from sci_cli.skill_add import Cancelled


@pytest.fixture
def homes(tmp_path, monkeypatch):
    root = tmp_path / '.sci'
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(root))
    monkeypatch.setattr('sci_cli.profiles._notify_multiplexer', lambda *a: None)
    monkeypatch.setattr('sci_cli.profiles._maybe_register_gateway_service', lambda *a: None)
    atomic_config_replace(root / 'config.yaml', {'model': {
        'provider': 'custom', 'default': 'fixture', 'base_url': 'http://127.0.0.1:1234/v1'}})
    source = tmp_path / 'reference.txt'
    source.write_text('Private fixture reference')
    targets = [create(ProfileSpec(n, 'Research', 'Cite sources', '', setup_pending=True,
                                 sources=[Source(str(source), 'copy')] if n == 'a' else [],
                                 allow_llm_sources=n == 'a'), root) for n in ('a', 'b')]
    for home in targets:
        (home / '.env').write_text('PRIVATE_KEY=fixture-private\n')
        (home / 'workspace' / 'result.txt').write_text(home.name)
        (home / 'sessions' / 'retained.json').write_text('{"retained": true}')
    return root, targets


def cli_state():
    return SimpleNamespace(agent=None, max_turns=30, run_budget_seconds=None,
                           system_prompt='cached input', conversation_history=[{'role': 'user', 'content': 'hello'}])


def test_benign_edits_preserve_approval_but_sensitive_edits_need_review_and_fresh_session(homes):
    root, (a, b) = homes
    cli = cli_state()
    with profile_scope(a):
        prepare(cli)
    cli.agent = SimpleNamespace(system_prompt=cli.system_prompt, tools=['skill_view'])
    prompt = cli.system_prompt
    config = read_user_config_raw(a / 'config.yaml')
    config['display'] = {'skin': 'mono', 'show_reasoning': False}
    config['_config_version'] = 999
    config['model_catalog'] = {'ttl_minutes': 123}
    atomic_config_replace(a / 'config.yaml', config)
    for home in (a, b, a):
        with profile_scope(home):
            assert prepare(cli if home == a else cli_state()).name == home.name
    assert cli.system_prompt == cli.agent.system_prompt == prompt
    assert cli.agent.tools == ['skill_view']

    for path, value in ((('model', 'base_url'), 'http://127.0.0.1:4567/v1'),
                        (('auxiliary', 'title'), {'provider': 'custom', 'base_url': 'https://example.invalid'}),
                        (('terminal', 'docker_network'), True),
                        (('skills', 'inline_shell'), True)):
        edited = read_user_config_raw(a / 'config.yaml')
        edited.setdefault(path[0], {})[path[1]] = value
        atomic_config_replace(a / 'config.yaml', edited)
        with pytest.raises(ValueError, match='Update_profile') as exc:
            validate_runtime(a)
        assert '.'.join(path) in str(exc.value)
        atomic_config_replace(a / 'config.yaml', config)

    config['model']['base_url'] = 'http://127.0.0.1:4567/v1'
    config['model']['api_key'] = 'fixture-secret-never-in-review'
    atomic_config_replace(a / 'config.yaml', config)
    ui = SimpleNamespace(show=Mock(), choose=Mock(return_value='Approve profile repair'))
    with profile_scope(a):
        update_wizard(cli, '/Update_profile a', ui)
        assert validate_runtime(a).name == 'a'
        with pytest.raises(ValueError, match='new conversation'):
            prepare(cli)
        assert prepare(cli_state()).name == 'a'
    messages = '\n'.join(c.args[0] for c in ui.show.call_args_list)
    assert 'Saved' in messages and 'model.base_url' in messages
    assert 'fixture-secret-never-in-review' not in messages
    assert 'fixture-secret-never-in-review' not in (a / MANIFEST).read_text()
    assert cli.system_prompt == cli.agent.system_prompt == prompt
    assert cli.conversation_history == [{'role': 'user', 'content': 'hello'}]


def test_legacy_review_cancel_conflict_and_rename_keep_profile_data_and_restrictions(homes, monkeypatch):
    root, (a, b) = homes
    old = json.loads((a / MANIFEST).read_text())
    old.pop('config_review', None)
    (a / MANIFEST).write_text(json.dumps(old))
    renamed = a.with_name('renamed')
    a.rename(renamed)
    original = {p: (renamed / p).read_bytes() for p in
                (MANIFEST, 'config.yaml', '.env', 'SOUL.md', 'sessions/retained.json',
                 'workspace/result.txt', 'sources/0/reference.txt')}
    other = (b / 'config.yaml').read_bytes()
    cli = cli_state()
    ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=Cancelled()))
    update_wizard(cli, '/Update_profile renamed', ui)
    assert all((renamed / p).read_bytes() == data for p, data in original.items())

    def concurrent_change(*args):
        cfg = read_user_config_raw(renamed / 'config.yaml')
        cfg['display'] = {'skin': 'mono'}
        atomic_config_replace(renamed / 'config.yaml', cfg)
        return 'Approve profile repair'

    ui.choose = concurrent_change
    update_wizard(cli, '/Update_profile renamed', ui)
    assert (renamed / MANIFEST).read_bytes() == original[MANIFEST]
    assert 'changed during review' in ui.show.call_args.args[0]

    cfg = read_user_config_raw(renamed / 'config.yaml')
    cfg['terminal']['docker_network'] = True
    atomic_config_replace(renamed / 'config.yaml', cfg)
    ui.choose = Mock(return_value='Approve profile repair')
    update_wizard(cli, '/Update_profile renamed', ui)
    ui.choose.assert_not_called()
    assert (renamed / MANIFEST).read_bytes() == original[MANIFEST]
    cfg['terminal']['docker_network'] = False
    atomic_config_replace(renamed / 'config.yaml', cfg)
    with monkeypatch.context() as failed_write:
        failed_write.setattr('utils.atomic_json_write', Mock(side_effect=OSError('fixture disk failure')))
        update_wizard(cli, '/Update_profile renamed', ui)
        assert 'No new approval' in ui.show.call_args.args[0]
        assert (renamed / MANIFEST).read_bytes() == original[MANIFEST]
        assert read_user_config_raw(renamed / 'config.yaml') == cfg
    update_wizard(cli, '/Update_profile renamed', ui)
    for home in (renamed, b, renamed):
        with profile_scope(home):
            instance = cli_state()
            assert prepare(instance).name == home.name
            assert instance.enabled_toolsets == ['skills']
    saved = read_user_config_raw(renamed / 'config.yaml')
    assert saved['terminal']['docker_volumes'] == [f'{renamed / "workspace"}:/workspace:rw',
                                                  f'{renamed / "sources/0/reference.txt"}:/sources/0:ro']
    assert read_spec(renamed).sources[0].location == str(renamed / 'sources/0/reference.txt')
    assert saved['display']['skin'] == 'mono'
    for p in ('.env', 'SOUL.md', 'sessions/retained.json', 'workspace/result.txt', 'sources/0/reference.txt'):
        assert (renamed / p).read_bytes() == original[p]
    assert (b / 'config.yaml').read_bytes() == other
    assert list((renamed / 'backups').glob('profile-compatibility-*/science-profile.json'))

    # Existing prepared profiles keep their image requirement. Cancelling must not
    # even inspect Docker; failure to find the image must not approve a new receipt.
    image = 'sha256:' + 'a' * 64
    prepared = create(ProfileSpec('prepared', 'Research', 'Cite sources', image), root)
    receipt = (prepared / MANIFEST).read_bytes()
    inspect = Mock(side_effect=ValueError('Approved Docker image is unavailable'))
    monkeypatch.setattr('sci_cli.science_profiles_sandbox.resolve_image', inspect)
    ui.choose = Mock(side_effect=Cancelled())
    update_wizard(cli, '/Update_profile prepared', ui)
    inspect.assert_not_called()
    ui.choose = Mock(return_value='Approve profile repair')
    update_wizard(cli, '/Update_profile prepared', ui)
    inspect.assert_called_once_with(image)
    assert 'unavailable' in ui.show.call_args.args[0]
    assert (prepared / MANIFEST).read_bytes() == receipt
