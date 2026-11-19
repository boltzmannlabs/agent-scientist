"""Web onboarding reuses CLI authorization without leaking across profiles."""
from pathlib import Path


def test_login_and_account_are_profile_scoped(tmp_path, monkeypatch):
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.web_routers.boltzmann import login, account_status
    from sci_cli.plugins import get_plugin_manager
    from plugins.boltzmann.authentication import AuthenticationResult
    from plugins.boltzmann.auth import current_key

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    a, b = tmp_path / 'a', tmp_path / 'b'
    monkeypatch.setenv('SCI_HOME', str(a))
    for home in (a, b):
        home.mkdir()
        atomic_config_replace(home / 'config.yaml', {'plugins': {'enabled': []}, 'platform_toolsets': {'cli': ['skills']}})
    receipt = lambda key: AuthenticationResult(key == 'fixture-valid', 'Verified' if key == 'fixture-valid' else 'Invalid')
    monkeypatch.setattr('plugins.boltzmann.onboarding.authenticate_api_key', receipt)
    monkeypatch.setattr('plugins.boltzmann.nodeapi_helpers.authenticate_api_key', receipt)
    with profile_scope(a):
        manager = get_plugin_manager()
        original = manager._cli_ref
        assert not login('fixture-invalid')['ok']
        assert not current_key()
        result = login('fixture-valid')
        assert result['ok'], result
        assert 'fixture-valid' not in result['message']
        assert manager._cli_ref is original
        assert account_status(True)['verified']
        assert 'boltzmann' in read_user_config_raw()['plugins']['enabled']
        before = {p.name: p.read_bytes() for p in a.iterdir() if p.is_file()}
        with monkeypatch.context() as scoped:
            def unexpected_validation(*args):
                raise AssertionError('An authorized duplicate must not revalidate or rewrite')
            scoped.setattr('plugins.boltzmann.onboarding.authenticate_api_key', unexpected_validation)
            duplicate = login('  fixture-valid  ')
        assert duplicate['ok'] and duplicate['already_connected']
        assert 'fixture-valid' not in duplicate['message']
        assert before == {p.name: p.read_bytes() for p in a.iterdir() if p.is_file()}
    with profile_scope(b):
        assert not account_status(True)['authorized']
        assert not current_key()
    with profile_scope(a):
        assert account_status(True)['verified']


def test_router_is_mounted_and_catalog_uses_cli_source(tmp_path, monkeypatch):
    import asyncio
    from sci_cli.web_server import app
    from sci_cli.web_routers.boltzmann import tools
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.science_catalog_view import catalog_rows
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    home = tmp_path / '.sci'
    home.mkdir()
    monkeypatch.setenv('SCI_HOME', str(home))
    paths = {route.path for route in app.routes}
    assert {'/api/boltzmann/login', '/api/boltzmann/tools', '/api/boltzmann/status'} <= paths
    with profile_scope(home):
        result = asyncio.run(tools())
        assert [r['name'] for r in result['tools']] == [r['name'] for r in catalog_rows()]
        assert all('section' in row and row['description'].strip() and row['description'] != row['name'] for row in result['tools'])
