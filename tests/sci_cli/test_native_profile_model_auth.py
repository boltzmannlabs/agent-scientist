"""Science profiles reuse shared model credentials without copying secrets."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def model_homes(tmp_path, monkeypatch):
    from agent.secret_scope import set_multiplex_active

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    main = tmp_path / 'science-root'
    main.mkdir()
    monkeypatch.setenv('SCI_HOME', str(main))
    monkeypatch.setattr('sci_cli.profiles._get_profiles_root', lambda: main / 'profiles')
    monkeypatch.setattr('sci_cli.profiles._get_default_sci_home', lambda: main)
    monkeypatch.setattr('sci_cli.profiles._notify_multiplexer', lambda *_: None)
    monkeypatch.setattr('sci_cli.profiles._maybe_register_gateway_service', lambda *_: None)
    set_multiplex_active(True)
    try:
        yield main, main / 'profiles' / 'a', main / 'profiles' / 'b'
    finally:
        set_multiplex_active(False)


def test_inline_model_rejected_before_wizard_selections(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    from sci_cli.native_profile_wizard import create_wizard

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    home = tmp_path / '.sci'
    home.mkdir()
    monkeypatch.setenv('SCI_HOME', str(home))
    atomic_config_replace(home / 'config.yaml', {'model': {
        'provider': 'custom', 'api_key': 'fixture-secret', 'default': 'fixture'}})
    ui = SimpleNamespace(show=Mock(), ask=Mock(), choose=Mock())
    create_wizard(SimpleNamespace(), '/create_profile example', ui=ui, source_home=home)
    ui.ask.assert_not_called()
    ui.choose.assert_not_called()
    assert 'inline API key' in str(ui.show.call_args_list)
    assert 'fixture-secret' not in str(ui.show.call_args_list)


def test_created_profile_resolves_shared_model_without_secret_copy(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.native_profile_creation import create_native, profile_scope
    from sci_cli.auth import write_credential_pool
    from sci_cli.runtime_provider import resolve_runtime_provider
    from agent.credential_pool import PooledCredential

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    main = tmp_path / 'science-root'
    main.mkdir()
    monkeypatch.setenv('SCI_HOME', str(main))
    monkeypatch.setattr('sci_constants.get_default_sci_root', lambda **_: main)
    monkeypatch.setattr('sci_cli.profiles._get_profiles_root', lambda: main / 'profiles')
    monkeypatch.setattr('sci_cli.profiles._get_default_sci_home', lambda: main)
    monkeypatch.setattr('sci_cli.profiles._notify_multiplexer', lambda *_: None)
    monkeypatch.setattr('sci_cli.profiles._maybe_register_gateway_service', lambda *_: None)
    provider = 'fixture-gateway'
    url = 'http://127.0.0.1:54321/v1'
    atomic_config_replace(main / 'config.yaml', {
        'model': {'provider': provider, 'default': 'fixture'},
        'providers': {provider: {'base_url': url}}})
    with profile_scope(main):
        entry = PooledCredential(provider=provider, id='fixture', label='Fixture',
            auth_type='api_key', priority=0, source='manual',
            access_token='fixture-secret', base_url=url)
        write_credential_pool(provider, [entry.to_dict()])
        create_native('study', main, [], [], [], {'backend': 'local'}, 'Scientist')
    child = main / 'profiles' / 'study'
    assert child.is_dir()
    assert 'fixture-secret' not in str(read_user_config_raw(child / 'config.yaml'))
    for home in (main, child, main):
        with profile_scope(home):
            runtime = resolve_runtime_provider(requested=provider, target_model='fixture')
            assert runtime['api_key'] == 'fixture-secret'
            assert runtime['base_url'].rstrip('/') == url
    if (child / 'auth.json').exists():
        assert 'fixture-secret' not in (child / 'auth.json').read_text()


@pytest.mark.parametrize('catalog,credential,model_key', [
    ('custom_providers', 'key_env', '${SCI_FIXTURE_LLM_KEY}'),
    ('custom_providers', 'api_key_env', '${env:SCI_FIXTURE_LLM_KEY}'),
    ('custom_providers', 'api_key', '${SCI_FIXTURE_LLM_KEY}'),
    ('providers', 'key_env', '${SCI_FIXTURE_LLM_KEY}'),
    ('providers', 'api_key_env', '${env:SCI_FIXTURE_LLM_KEY}'),
    ('providers', 'api_key', '${env:SCI_FIXTURE_LLM_KEY}'),
    ('providers', 'api_key', None),
    ('providers', 'key_env', None),
])
def test_reference_credential_creates_profiles_with_shared_auth(model_homes, catalog, credential, model_key):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.native_profile_creation import create_native, profile_scope
    from sci_cli.runtime_provider import resolve_runtime_provider
    from agent.secret_scope import get_secret_str

    main, a, b = model_homes
    url = 'http://127.0.0.1:54321/v1'
    provider = 'lab' if catalog == 'providers' else 'custom:lab'
    entry = {'name': 'lab', 'base_url': url,
             credential: '${SCI_FIXTURE_LLM_KEY}' if credential == 'api_key' else 'SCI_FIXTURE_LLM_KEY'}
    model = {'provider': provider, 'default': 'fixture', 'base_url': url, 'context_length': 8192}
    if model_key:
        model['api_key'] = model_key
    original = {'model': model, catalog: {'lab': entry} if catalog == 'providers' else [entry]}
    atomic_config_replace(main / 'config.yaml', original)
    (main / '.env').write_text('SCI_FIXTURE_LLM_KEY=main-fixture-secret\nBOLTZMANN_API_KEY=private-research\n')
    before = {p: p.read_bytes() for p in (main / 'config.yaml', main / '.env')}
    for home in (a, b):
        # Source-home ownership must win even when a different profile is bound.
        with profile_scope(b, {}):
            create_native(home.name, main, [], [], [], {'backend': 'local'}, 'Scientist')
        config = read_user_config_raw(home / 'config.yaml')
        assert config['model'] == {k: v for k, v in model.items() if k != 'api_key'}
        assert not config.get('providers') and not config.get('custom_providers')
        for path in (home / 'config.yaml', home / '.env', home / 'auth.json'):
            if path.exists():
                assert 'main-fixture-secret' not in path.read_text()
                assert 'private-research' not in path.read_text()
    # A profile-local provider remains authoritative, with no cross-profile key leak.
    config = read_user_config_raw(b / 'config.yaml')
    config['providers'] = {'lab': {'name': 'lab', 'base_url': url, 'key_env': 'SCI_FIXTURE_LLM_KEY'}}
    atomic_config_replace(b / 'config.yaml', config)
    (b / '.env').write_text('SCI_FIXTURE_LLM_KEY=profile-b-secret\n')
    for home, expected in ((a, 'main-fixture-secret'), (b, 'profile-b-secret'), (a, 'main-fixture-secret')):
        with profile_scope(home):
            runtime = resolve_runtime_provider(requested=provider, target_model='fixture')
            assert runtime['api_key'] == expected
            assert runtime['base_url'].rstrip('/') == url
            assert not get_secret_str('BOLTZMANN_API_KEY', '')
            assert get_secret_str('SCI_FIXTURE_LLM_KEY', '') == ('profile-b-secret' if home == b else '')
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize('problem', ['missing-key', 'different-key', 'different-endpoint',
                                     'missing-provider', 'credential-command', 'local-override',
                                     'disabled-override', 'keyed-provider-precedence'])
def test_unshareable_reference_stops_before_profile_review(model_homes, problem):
    from sci_cli.config import atomic_config_replace
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.native_profile_wizard import create_wizard

    main, a, b = model_homes
    entry = {'name': 'lab', 'base_url': 'http://127.0.0.1:54321/v1', 'key_env': 'SCI_FIXTURE_LLM_KEY'}
    model = {'provider': 'custom:lab', 'default': 'fixture', 'base_url': entry['base_url'],
             'api_key': '${SCI_FIXTURE_LLM_KEY}'}
    if problem == 'different-key':
        model['api_key'] = '${OTHER_FIXTURE_KEY}'
    if problem == 'different-endpoint':
        model['base_url'] = 'http://127.0.0.1:54322/v1'
    if problem == 'credential-command':
        entry['key_cmd'] = 'must-not-run'
    original = {'model': model, 'custom_providers': [] if problem == 'missing-provider' else [entry]}
    if problem == 'keyed-provider-precedence':
        original['providers'] = {'lab': {**entry, 'key_env': 'OTHER_FIXTURE_KEY'}}
    atomic_config_replace(main / 'config.yaml', original)
    if problem != 'missing-key':
        (main / '.env').write_text('SCI_FIXTURE_LLM_KEY=main-fixture-secret\nOTHER_FIXTURE_KEY=different-secret\n')
    source = main
    if problem in {'local-override', 'disabled-override'}:
        b.mkdir(parents=True)
        original['custom_providers'][0]['extra_headers'] = {'X-Profile': 'private-override'}
        if problem == 'disabled-override':
            original['providers'] = {'lab': {'enabled': False}}
        atomic_config_replace(b / 'config.yaml', original)
        source = b
    ui = SimpleNamespace(show=Mock(), ask=Mock(), choose=Mock())
    with profile_scope(source):
        create_wizard(SimpleNamespace(), '/create_profile a', ui=ui, source_home=source)
    ui.ask.assert_not_called()
    ui.choose.assert_not_called()
    output = str(ui.show.call_args_list)
    assert 'Profile creation failed' in output
    assert 'inline API key' not in output
    assert 'main-fixture-secret' not in output and 'different-secret' not in output
    assert not a.exists()


@pytest.mark.parametrize('catalog', ['providers', 'custom_providers'])
@pytest.mark.parametrize('credential', ['key_env', 'api_key_env', 'api_key'])
def test_bare_custom_creates_profiles_using_the_exact_shared_route(model_homes, catalog, credential):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.native_profile_creation import create_native, profile_scope
    from sci_cli.runtime_provider import resolve_runtime_provider

    main, a, b = model_homes
    url = 'http://127.0.0.1:54321/v1'
    entry = {'name': 'Lab display name', 'base_url': url,
             credential: '${SCI_FIXTURE_LLM_KEY}' if credential == 'api_key' else 'SCI_FIXTURE_LLM_KEY'}
    other = {'name': 'other', 'base_url': 'http://127.0.0.1:54322/v1', 'key_env': 'OTHER_FIXTURE_KEY'}
    provider = 'custom:lab' if catalog == 'providers' else 'custom:lab-display-name'
    model = {'provider': 'custom', 'default': 'fixture', 'base_url': url + '/',
             'api_key': '${env:SCI_FIXTURE_LLM_KEY}', 'context_length': 8192}
    original = {'model': model, catalog: {'other': other, 'lab': entry} if catalog == 'providers' else [other, entry]}
    atomic_config_replace(main / 'config.yaml', original)
    (main / '.env').write_text('SCI_FIXTURE_LLM_KEY=main-fixture-secret\nOTHER_FIXTURE_KEY=other-secret\n')
    before = {p: p.read_bytes() for p in (main / 'config.yaml', main / '.env')}
    for home in (a, b):
        with profile_scope(b, {}):
            create_native(home.name, main, [], [], [], {'backend': 'local'}, 'Scientist')
        config = read_user_config_raw(home / 'config.yaml')
        assert config['model'] == {**{k: v for k, v in model.items() if k != 'api_key'}, 'provider': provider}
        assert not config.get('providers') and not config.get('custom_providers')
        for name in ('config.yaml', '.env', 'auth.json'):
            path = home / name
            if path.exists():
                assert 'main-fixture-secret' not in path.read_text()
    for home in (a, b, a):
        with profile_scope(home):
            runtime = resolve_runtime_provider(requested=provider, target_model='fixture')
            assert runtime['api_key'] == 'main-fixture-secret'
            assert runtime['base_url'].rstrip('/') == url
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize('problem', ['ambiguous', 'missing-route', 'wrong-route', 'wrong-key',
                                     'disabled', 'disabled-legacy', 'disabled-keyed-override', 'local-override'])
def test_bare_custom_never_guesses_or_bypasses_access_checks(model_homes, problem):
    from copy import deepcopy
    from sci_cli.config import atomic_config_replace
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.native_profile_wizard import create_wizard

    main, a, b = model_homes
    url = 'http://127.0.0.1:54321/v1'
    entry = {'name': 'lab', 'base_url': url, 'key_env': 'SCI_FIXTURE_LLM_KEY'}
    model = {'provider': 'custom', 'default': 'fixture', 'base_url': url, 'api_key': '${SCI_FIXTURE_LLM_KEY}'}
    changes = {
        'ambiguous': {'custom_providers': [entry, {**entry, 'name': 'other'}]},
        'missing-route': {'model': {k: v for k, v in model.items() if k != 'base_url'}},
        'wrong-route': {'model': {**model, 'base_url': 'http://127.0.0.1:54322/v1'}},
        'wrong-key': {'model': {**model, 'api_key': '${OTHER_FIXTURE_KEY}'}},
        'disabled': {'custom_providers': [], 'providers': {'lab': {**entry, 'enabled': False}}},
        'disabled-legacy': {'custom_providers': [{**entry, 'enabled': False}]},
        'disabled-keyed-override': {'providers': {'lab': {'enabled': False}}},
    }
    original = {'model': model, 'custom_providers': [entry], **changes.get(problem, {})}
    atomic_config_replace(main / 'config.yaml', original)
    (main / '.env').write_text('SCI_FIXTURE_LLM_KEY=main-fixture-secret\nOTHER_FIXTURE_KEY=other-secret\n')
    source = main
    if problem == 'local-override':
        b.mkdir(parents=True)
        local = deepcopy(original)
        local['custom_providers'][0]['key_env'] = 'OTHER_FIXTURE_KEY'
        atomic_config_replace(b / 'config.yaml', local)
        source = b
    before = (main / 'config.yaml').read_bytes()
    ui = SimpleNamespace(show=Mock(), ask=Mock(), choose=Mock())
    with profile_scope(source):
        create_wizard(SimpleNamespace(), '/create_profile a', ui=ui, source_home=source)
    ui.ask.assert_not_called()
    ui.choose.assert_not_called()
    assert 'Profile creation failed' in str(ui.show.call_args_list)
    assert 'main-fixture-secret' not in str(ui.show.call_args_list)
    assert not a.exists()
    assert (main / 'config.yaml').read_bytes() == before
