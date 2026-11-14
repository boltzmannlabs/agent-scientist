"""Generic chat outputs reuse authenticated managed files and their owning execution backend."""
import base64
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from sci_cli import web_server
from sci_cli.config import atomic_config_replace
from sci_state import SessionDB


@pytest.fixture
def homes(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    main = tmp_path / '.sci'
    monkeypatch.setenv('SCI_HOME', str(main))
    monkeypatch.delenv('SCI_DASHBOARD_FILES_ROOT', raising=False)
    monkeypatch.setattr(web_server.app.state, 'auth_required', False, raising=False)
    result = {}
    for name in ('default', 'lab'):
        home = main if name == 'default' else main / 'profiles' / name
        workspace = home / 'workspace'
        workspace.mkdir(parents=True)
        atomic_config_replace(home / 'config.yaml', {'terminal': {'backend': 'local'}})
        db = SessionDB(db_path=home / 'state.db')
        db.create_session(name + '-session', source='gui', cwd=str(workspace))
        db.close()
        result[name] = (home, workspace)
    with TestClient(web_server.app) as client:
        client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
        yield client, result


@pytest.mark.parametrize('name', ['paired sequences.csv', 'sequence.fasta', 'weights.unknown', 'README'])
def test_chat_downloads_preserve_bytes_owner_auth_and_read_limits(homes, name, monkeypatch):
    client, profiles = homes
    for profile in ('default', 'lab', 'default'):
        home, workspace = profiles[profile]
        content = (profile + '\nverified output').encode()
        target = workspace / name
        target.write_bytes(content)
        params = {'path': './' + name, 'profile': profile, 'session_id': profile + '-session'}
        listing = client.get('/api/files', params={**params, 'path': '.'})
        assert listing.status_code == 200 and name in [row['name'] for row in listing.json()['entries']]
        read = client.get('/api/files/read', params=params)
        assert read.status_code == 200, read.text
        assert base64.b64decode(read.json()['data_url'].split(',', 1)[1]) == content
        assert client.get('/api/files/read', params={**params, 'max_bytes': 1}).status_code == 413
        assert client.head('/api/files/download', params=params).status_code == 200
        response = client.get('/api/files/download', params=params)
        assert response.status_code == 200 and response.content == content
        assert 'attachment' in response.headers['content-disposition']
        assert client.get('/api/files/download', params={**params, 'session_id': 'missing'}).status_code == 404
        other = 'lab' if profile == 'default' else 'default'
        assert client.get('/api/files/download', params={**params, 'session_id': other + '-session'}).status_code == 404
        assert client.get('/api/files/download', params={**params, 'path': str(workspace / 'missing.csv')}).status_code == 404
        (workspace / '.env').write_text('PRIVATE_FIXTURE=value')
        assert client.get('/api/files/download', params={**params, 'path': str(workspace / '.env')}).status_code == 403
    params = {'path': str(target), 'profile': 'default', 'session_id': 'default-session'}
    client.headers.clear()
    assert client.head('/api/files/download', params=params).status_code == 401
    assert client.get('/api/files/download', params={**params, 'token': web_server._SESSION_TOKEN}).status_code == 200
    client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
    monkeypatch.setenv('SCI_DASHBOARD_FILES_ROOT', str(profiles['default'][1]))
    assert client.get('/api/files/download', params={**params, 'path': str(profiles['lab'][1] / name)}).status_code == 403


def test_remote_outputs_use_owned_backend_and_never_fall_back_to_host_files(homes, monkeypatch):
    from sci_cli import ssh_workspace_fs
    client, profiles = homes
    home, _ = profiles['lab']
    atomic_config_replace(home / 'config.yaml', {'terminal': {'backend': 'ssh', 'ssh_host': 'fixture'}})
    calls = []

    class Backend:
        cwd = '/remote/outputs'

        def list_dir(self, path, hidden):
            calls.append(('list', path))
            return {'entries': [{'name': 'output.any', 'path': path + '/output.any', 'isDirectory': False}]}

        def inspect_file(self, path):
            calls.append(('inspect', path))
            return ('/remote/.env' if path.endswith('secret-link') else path), (200 * 1024 * 1024 if path.endswith('huge') else 6)

        def read_bytes(self, path, *, max_bytes):
            calls.append(('read', path))
            return b'remote', 6, path

        def stream_file(self, path):
            calls.append(('stream', path))
            yield b'remote'

    def backend(profile, terminal):
        return Backend() if terminal.get('backend') == 'ssh' else None

    monkeypatch.setattr(ssh_workspace_fs, 'get_ssh_workspace_fs', backend)
    params = {'path': '/remote/outputs/output.any', 'profile': 'lab', 'session_id': 'lab-session'}
    plugin_output = profiles['lab'][1] / 'plugin-output.any'
    plugin_output.write_bytes(b'local plugin output')
    local_params = {**params, 'path': str(plugin_output)}
    assert client.get('/api/files/download', params=local_params).content == b'local plugin output'
    assert calls == []  # a plugin artifact under SCI storage is not a terminal-backend file
    listing = client.get('/api/files', params={**params, 'path': '/remote/outputs'})
    assert listing.status_code == 200 and listing.json()['read_only']
    assert client.head('/api/files/download', params=params).status_code == 200
    assert not any(call[0] == 'stream' for call in calls)
    assert client.get('/api/files/download', params=params).content == b'remote'
    read = client.get('/api/files/read', params=params)
    assert read.status_code == 200 and base64.b64decode(read.json()['data_url'].split(',')[1]) == b'remote'
    assert client.get('/api/files/read', params={**params, 'max_bytes': 2}).status_code == 413
    calls.clear()
    assert client.get('/api/files/download', params={**params, 'session_id': 'default-session'}).status_code == 404
    assert calls == []  # ownership check precedes backend I/O
    assert client.get('/api/files/download', params={**params, 'path': '/remote/secret-link'}).status_code == 403
    assert not any(call[0] == 'stream' for call in calls)
    assert client.head('/api/files/download', params={**params, 'path': '/remote/huge'}).status_code == 413
    atomic_config_replace(home / 'config.yaml', {'terminal': {'backend': 'docker'}})
    assert client.get('/api/files/download', params=local_params).content == b'local plugin output'
    target = profiles['default'][1] / 'host.any'
    target.write_bytes(b'wrong host file')
    assert client.get('/api/files/download', params={**params, 'path': str(target)}).status_code == 409
