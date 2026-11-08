"""Native ConPTY viewers detach from a live profile owner without restarting inference."""

import json
import os
from pathlib import Path
import sys
import threading
import time

import psutil
import pytest

from sci_cli.background_chats import find_worker, read_server, request
from sci_cli.win_pty_bridge import WinPtyBridge
from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home

ROOT = Path(__file__).resolve().parents[2]


def wait_for(predicate, seconds=40):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result = predicate()
        if result:
            return result
        time.sleep(.05)
    raise AssertionError('Timed out waiting for the Windows background fixture')


def finish_service(home):
    record = read_server(home)
    if record:
        for row in request('status', home=home)['chats']:
            if row['alive']:
                request('stop', home=home, id=row['id'], force=True)
        request('shutdown', home=home)
        wait_for(lambda: read_server(home) is None)


@pytest.mark.platforms('windows')
@pytest.mark.live_system_guard_bypass  # Only the recorded daemon and ConPTYs under this temp home.
@pytest.mark.parametrize('action', ['background', 'cancel_task', 'exit', 'close'])
@pytest.mark.asyncio
async def test_windows_ctrl_c_detach_and_resume_keep_the_same_task(tmp_path, action):
    home = tmp_path / '.sci'
    viewers = []
    release = threading.Event()

    def respond(_request):
        release.wait(180)
        # ConPTY may encode spaces as cursor moves; a single-word marker
        # tests retained answer visibility without freezing its paint bytes.
        return Text('BACKGROUNDREPLY42', chunk_chars=128)

    with FakeLLMServer(respond) as model:
        write_sci_home(home, model.base_url)
        env = {**os.environ, 'SCI_HOME': str(home), 'USERPROFILE': str(tmp_path),
               'HOME': str(tmp_path), 'PYTHONPATH': str(ROOT), 'TERM': 'xterm-256color',
               'SCI_DISABLE_LAZY_INSTALLS': '1', 'SCI_STATE_DB_GUARD_BYPASS': '1'}
        output = bytearray()

        def until(bridge, predicate, seconds=40):
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                if data := bridge.read(.05):
                    output.extend(data)
                result = predicate()
                if result:
                    return result
            logs = []
            for path in (home / 'runtime/background-chats/service.log', home / 'logs/agent.log', home / 'logs/errors.log'):
                if path.exists():
                    logs.append(path.name + ':\n' + path.read_text(encoding='utf-8-sig', errors='replace')[-12000:])
            raise AssertionError(f'Windows viewer did not reach expected state: {output[-4000:]!r}\n' + '\n'.join(logs))

        def launch(args):
            bridge = WinPtyBridge.spawn([sys.executable, '-m', 'sci_cli.main', '--cli', *args],
                                        cwd=str(ROOT), env=env, cols=110, rows=36)
            viewers.append(bridge)
            return bridge

        try:
            viewer = launch([])
            until(viewer, lambda: '❯'.encode() in output, seconds=180)
            await viewer.write(b'hello Windows fixture')
            until(viewer, lambda: b'hello Windows fixture' in output)
            # Match a typed Enter after the CLI's paste-detection window.
            time.sleep(.2)
            await viewer.write(b'\r')
            until(viewer, lambda: model.main_requests())
            worker = until(viewer, lambda: next((r for r in request('status', home=home)['chats']
                                                 if r['session_id'] and r['state'] == 'running'), None))
            if action == 'close':
                viewer.close()
            else:
                await viewer.write(b'\x03')
                until(viewer, lambda: b'Task is still running' in output)
                await viewer.write({'cancel_task': b'1', 'background': b'2', 'exit': b'3'}[action])
            if action == 'cancel_task':
                release.set()
                until(viewer, lambda: find_worker(worker['id'], home)['state'] == 'idle')
                assert viewer.is_alive()
            elif action == 'exit':
                release.set()
                until(viewer, lambda: not viewer.is_alive())
                wait_for(lambda: find_worker(worker['id'], home) is None)
            else:
                until(viewer, lambda: not viewer.is_alive())
                release.set()
                wait_for(lambda: find_worker(worker['id'], home)['state'] == 'idle')
                assert find_worker(worker['id'], home)['pid'] == worker['pid']
                output.clear()
                resumed = launch(['--resume', worker['session_id']])
                # Backend attachment precedes the viewer entering console raw
                # mode. Wait for the replayed prompt before sending shortcuts.
                until(resumed, lambda: '❯'.encode() in output and find_worker(worker['id'], home)['attached'], seconds=180)
                # A replayed prompt predates input readiness. Prove a fresh
                # keyboard round trip before exercising a one-shot shortcut.
                await resumed.write(b'RECONNECTED42')
                until(resumed, lambda: b'RECONNECTED42' in output)
                await resumed.write(b'\x15')
                # ConPTY redraws its current viewport rather than emitting
                # every historical frame. Browse the saved transcript too.
                await resumed.write(b'\x1b[19~' if action == 'background' else b'\x0f')
                until(resumed, lambda: b'BACKGROUNDREPLY42' in output)
                assert find_worker(worker['id'], home)['pid'] == worker['pid']
                await resumed.write(b'q')
                await resumed.write(b'\x1d')
                until(resumed, lambda: not resumed.is_alive())
            assert len(model.main_requests()) == 1
        finally:
            release.set()
            for viewer in viewers:
                viewer.close()
            finish_service(home)


@pytest.mark.platforms('windows')
@pytest.mark.live_system_guard_bypass  # Services are created solely in these temporary profile homes.
def test_windows_service_profile_scope_and_private_auth_record(tmp_path):
    import win32security
    from sci_cli.background_chats import connect, ensure_server, locations, send

    homes = [tmp_path / 'a', tmp_path / 'b']
    try:
        for home in homes:
            ensure_server(home)
        owners = []
        for home in (homes[0], homes[1], homes[0]):
            status = request('status', home=home)
            assert status['profile_home'] == str(home.resolve())
            owners.append(status['pid'])
        assert owners[0] == owners[2] != owners[1]
        path = locations(homes[0])[1] / 'server.json'
        descriptor = win32security.GetFileSecurity(str(path), win32security.DACL_SECURITY_INFORMATION | win32security.OWNER_SECURITY_INFORMATION)
        owner = win32security.ConvertSidToStringSid(descriptor.GetSecurityDescriptorOwner())
        acl = descriptor.GetSecurityDescriptorDacl()
        assert acl is not None
        assert all(win32security.ConvertSidToStringSid(acl.GetAce(i)[-1]) in {owner, 'S-1-5-18'} for i in range(acl.GetAceCount()))
        # Authenticated profile A must still reject a request scoped to B.
        record = read_server(homes[0])
        import socket
        with socket.create_connection(tuple(record['endpoint']), timeout=5) as sock:
            send(sock, {'token': record['token'], 'home': str(homes[1].resolve())})
            with sock.makefile('rb') as stream:
                assert 'authentication failed' in json.loads(stream.readline())['error']
        with connect(homes[0]) as sock:
            send(sock, {'action': 'status'})
            with sock.makefile('rb') as stream:
                assert json.loads(stream.readline())['pid'] == owners[0]
    finally:
        for home in homes:
            finish_service(home)
