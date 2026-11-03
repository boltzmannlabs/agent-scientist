"""Desktop launches preserve profile, file-access and process-lifetime boundaries."""
import asyncio
import json
import os
from pathlib import Path
import sys

import psutil
import pytest
from fastapi import HTTPException
from starlette.testclient import TestClient

from sci_cli import web_pymol, web_server
from sci_platform.resolver.desktop_session import DesktopSession


def test_desktop_routes_guard_files_and_keep_profile_scopes_separate(tmp_path, monkeypatch):
    home = tmp_path / '.sci'
    home.mkdir()
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(home))
    monkeypatch.setenv('SCI_DASHBOARD_FILES_ROOT', str(tmp_path / 'files'))
    files = tmp_path / 'files'
    files.mkdir()
    source = files / 'structure.pdb'
    source.write_text('HEADER fixture\nEND\n')
    (files / 'commands.pml').write_text('quit')
    (files / '.env').write_text('SECRET=fixture')
    outside = tmp_path / 'outside.pdb'
    outside.write_text('END\n')
    for name in ('a', 'b'):
        profile = home / 'profiles' / name
        profile.mkdir(parents=True)
        (profile / 'config.yaml').write_text('{}\n')
    monkeypatch.setattr(web_server.app.state, 'auth_required', False, raising=False)
    monkeypatch.setattr(web_server.app.state, 'bound_host', None, raising=False)
    monkeypatch.setattr(web_pymol, 'desktop_sessions', lambda: [DesktopSession('fixture', 'Fixture desktop', {})])
    selected_roots = []
    async def launch(request, root, content, suffix, name, desktop_id):
        selected_roots.append(root)
        assert content == source.read_bytes()
        return {'pid': 123, 'atoms': 1, 'version': 'fixture', 'desktop': 'Fixture desktop'}
    monkeypatch.setattr(web_pymol, 'launch_desktop', launch)
    def no_install(*args, **kwargs):
        pytest.fail('Inspection/launch must not install dependencies')
    monkeypatch.setattr(web_pymol.pm, 'ensure_environment', no_install)
    with TestClient(web_server.app) as client:
        payload = {'path': str(source), 'desktop_id': 'fixture'}
        assert client.post('/api/structures/pymol/launch', json=payload).status_code == 401
        client.headers[web_server._SESSION_HEADER_NAME] = web_server._SESSION_TOKEN
        for name in ('a', 'b', 'a'):
            info = client.get('/api/structures/pymol', params={'profile': name})
            assert info.status_code == 200
            assert info.json()['installed'] is False
            assert client.post('/api/structures/pymol/launch', params={'profile': name}, json=payload).status_code == 200
        assert selected_roots == [home / 'profiles' / name / 'environments' / 'pymol-desktop' for name in ('a', 'b', 'a')]
        for path, status in [(outside, 403), (files / '.env', 403), (files / 'commands.pml', 415)]:
            assert client.post('/api/structures/pymol/launch', json={**payload, 'path': str(path)}).status_code == status
        assert client.post('/api/structures/pymol/launch', json={**payload, 'command': 'untrusted'}).status_code == 422
        assert len(selected_roots) == 3


@pytest.mark.parametrize('outcome', ['ready', 'cancelled', 'timeout'])
def test_launch_waits_for_readiness_and_reaps_failed_startups(tmp_path, monkeypatch, outcome):
    worker = tmp_path / 'worker.py'
    worker.write_text('''import json, os, time
from pathlib import Path
Path('pid').write_text(str(os.getpid()))
assert os.environ.get('SCI_FIXTURE_PRIVATE_KEY') is None
assert Path('structure.pdb').read_bytes() == b'fixture structure'
Path('ready.tmp').write_text(json.dumps({'atoms': 7, 'version': 'fixture'}))
Path('ready.tmp').replace('ready.json')
time.sleep(30)
''')
    monkeypatch.setenv('SCI_FIXTURE_PRIVATE_KEY', 'must-not-reach-child')
    monkeypatch.setattr(web_pymol, 'WORKER', worker)
    monkeypatch.setattr(web_pymol.pm, 'environment_python', lambda *args, **kwargs: Path(sys.executable))
    monkeypatch.setattr(web_pymol, 'desktop_sessions', lambda: [DesktopSession('fixture', 'Fixture desktop', {})])
    work = tmp_path / 'sci-pymol-fixture'
    work.mkdir()
    monkeypatch.setattr(web_pymol.tempfile, 'mkdtemp', lambda **kwargs: str(work))
    if outcome == 'timeout':
        monkeypatch.setattr(web_pymol, 'START_TIMEOUT', 0)
    class Request:
        async def is_disconnected(self):
            return outcome == 'cancelled'
    before = {p.pid for p in psutil.Process().children()}
    try:
        call = web_pymol.launch_desktop(Request(), tmp_path, b'fixture structure', '.pdb', 'test.pdb', 'fixture')
        if outcome == 'ready':
            result = asyncio.run(call)
            assert result['atoms'] == 7
            assert psutil.pid_exists(result['pid'])
            assert work.exists()
        else:
            with pytest.raises(HTTPException) as exc:
                asyncio.run(call)
            assert exc.value.status_code == (499 if outcome == 'cancelled' else 504)
            assert not work.exists()
            assert not ({p.pid for p in psutil.Process().children()} - before)
    finally:
        for child in psutil.Process().children():
            if child.pid not in before:
                child.kill()
                child.wait(timeout=5)
