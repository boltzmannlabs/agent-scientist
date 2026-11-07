"""Resume selects the existing writer's view, including across real CLI viewers."""

from copy import deepcopy
from pathlib import Path
from queue import Queue
from threading import Event
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests.agent.test_side_conversation import parent_agent, provider as provider
from tests.sci_cli.test_background_chats import Viewer, service, wait_for


@pytest.mark.platforms('posix')
def test_legacy_side_owner_reconnects_without_restarting_or_replaying(tmp_path, monkeypatch, capsys):
    from sci_cli import background_chat_terminal as terminal, cli_runtime_refresh
    from sci_cli.background_chats import find_view_worker, find_worker, request
    from sci_cli.active_sessions import active_session_registry_snapshot
    from sci_cli.native_profile_session import request_resume
    from sci_state import SessionDB

    source = '''
import os, sys
from pathlib import Path
from sci_cli.active_sessions import try_acquire_active_session
from sci_cli.background_chats import request
from sci_state import SessionDB
home = Path(os.environ['SCI_HOME'])
db = SessionDB(home / 'state.db')
side = 'side-' + home.name
leases = []
for sid, surface in [('parent', 'cli'), (side, 'side')]:
    db.create_session(sid, 'cli', system_prompt='cached-' + sid)
    db.append_message(sid, 'user', 'saved question')
    db.append_message(sid, 'assistant', 'saved answer')
    lease, error = try_acquire_active_session(session_id=sid, surface=surface, config={})
    assert lease and not error
    leases.append(lease)
# Older workers have leases but publish only their main conversation ID.
request('worker', pid=os.getpid(), session_id='parent', state='idle', background_tasks=0)
print('LEGACY_READY', flush=True)
for line in sys.stdin:
    print('Unexpected input: ' + line, flush=True)
'''
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / 'A', tmp_path / 'B']
    daemons, workers = [], []
    monkeypatch.setattr(cli_runtime_refresh, 'refresh_attached_worker',
                        Mock(side_effect=AssertionError('must not reload the shared runtime')))

    def attach_once(chat_id, *, home, takeover, view_session):
        assert view_session is None  # Do not send an unsupported select-view request.
        viewer = Viewer(home, chat_id, takeover=takeover)
        try:
            assert viewer.reply['attached'] == chat_id
            viewer.until(b'LEGACY_READY')
            assert b'Unexpected input' not in viewer.output
        finally:
            viewer.close()
        return {}

    monkeypatch.setattr(terminal, '_attach_once', attach_once)
    try:
        for home in homes:
            monkeypatch.setenv('SCI_HOME', str(home))
            daemons.append(service(home, worker_source=source))
            key = request('start', home=home, cwd=str(tmp_path))['id']
            workers.append(wait_for(lambda: find_view_worker('side-' + home.name, home)))
            assert workers[-1]['id'] == key
        for index in (0, 1, 0):
            home, worker = homes[index], workers[index]
            monkeypatch.setenv('SCI_HOME', str(home))
            side = 'side-' + home.name
            leases = active_session_registry_snapshot(home, strict=True)
            assert worker['legacy_side_view'] and worker['view_session'] == side
            assert find_view_worker(side, homes[1-index]) is None
            assert find_view_worker('not-a-session', home) is None
            assert find_worker(side, home) is None  # Side IDs cannot stop parent workers.
            with SessionDB(home / 'state.db') as db:
                saved = [(db.get_session(s)['system_prompt'], db.get_messages(s)) for s in ('parent', side)]
                app = SimpleNamespace(loop=SimpleNamespace(call_soon_threadsafe=Mock()), exit=Mock())
                cli = SimpleNamespace(session_id='another-chat', _session_db=db, _app=app, _agent_running=False)
                ui = SimpleNamespace(show=Mock(), choose=Mock(return_value='Move viewer'))
                request_resume(cli, side, ui)
                assert cli._pending_relaunch[2:5] == ['background', 'attach', side]
                assert any('Ctrl+/' in call.args[0] for call in ui.show.call_args_list)
                terminal.attach(worker['id'], home=home, takeover=True, view_session=side)
                assert [(db.get_session(s)['system_prompt'], db.get_messages(s)) for s in ('parent', side)] == saved
            assert find_worker(worker['id'], home)['pid'] == worker['pid']
            assert active_session_registry_snapshot(home, strict=True) == leases
        assert 'cannot select a side view automatically' in capsys.readouterr().out
    finally:
        for daemon in daemons:
            daemon.terminate()
            daemon.communicate(timeout=20)


def test_local_resume_preserves_both_writers_drafts_queue_and_cached_context(provider, tmp_path, monkeypatch):
    from sci_cli.native_profile_session import request_resume
    from sci_cli.side_commands import SideController
    from sci_cli.active_sessions import active_session_registry_snapshot, try_acquire_active_session
    from sci_state import SessionDB

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    url, requests, _, _ = provider
    clients = {}
    try:
        for name in ('A', 'B', 'A'):
            home = tmp_path / name
            home.mkdir(exist_ok=True)
            monkeypatch.setenv('SCI_HOME', str(home))
            if name not in clients:
                parent = parent_agent(url)
                db = parent._session_db = SessionDB(home / 'state.db')
                db.create_session(parent.session_id, 'cli', system_prompt=parent._cached_system_prompt)
                db.append_message(parent.session_id, 'user', name + ' context')
                db.append_message(parent.session_id, 'assistant', 'original answer')
                lease, error = try_acquire_active_session(session_id=parent.session_id, surface='cli', config={})
                assert lease and not error
                view = SimpleNamespace(surface=None, select=Mock(), clear=Mock(), draft='side draft')
                cli = SimpleNamespace(agent=parent, session_id=parent.session_id, _session_db=db,
                                      conversation_history=db.get_messages_as_conversation(parent.session_id),
                                      _side_view=view, _agent_running=True, _pending_input=Queue(), draft='main draft')
                cli._pending_input.put('queued main request')
                cli._side_controller = SideController(cli)
                assert cli._side_controller.conversation.answer('side ' + name) == 'Fixture side answer.'
                clients[name] = cli, lease
            cli, lease = clients[name]
            side = cli._side_controller
            prompt = side.conversation._agent._cached_system_prompt
            history = deepcopy(cli.conversation_history)
            rows = cli._session_db.get_messages(side.conversation.id)
            owners = active_session_registry_snapshot(home, strict=True)
            requests_before = len(requests)
            ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=AssertionError('must not recover owner')))
            side.select(False)
            request_resume(cli, side.conversation.id, ui)
            assert side.active
            cli._side_view.select.assert_called_with(True)
            request_resume(cli, cli.session_id, ui)
            assert not side.active
            cli._side_view.select.assert_called_with(False)
            assert active_session_registry_snapshot(home, strict=True) == owners
            assert cli._session_db.get_messages(side.conversation.id) == rows
            assert cli.conversation_history == history
            assert cli.agent._cached_system_prompt == 'Stable parent prompt.\n'
            assert side.conversation._agent._cached_system_prompt == prompt
            assert len(requests) == requests_before
            assert cli.draft == 'main draft' and cli._side_view.draft == 'side draft'
            assert list(cli._pending_input.queue) == ['queued main request']
            assert not hasattr(cli, '_pending_relaunch')
    finally:
        for cli, lease in clients.values():
            cli._side_controller.close()
            lease.release()
            cli.agent.close()


@pytest.mark.platforms('posix')
def test_real_cli_resume_moves_side_view_without_replay_or_profile_crossover(tmp_path, monkeypatch):
    from sci_cli.background_chats import connect, find_view_worker, find_worker, request, send
    from sci_cli import cli_runtime_refresh as refresh
    from sci_cli.active_sessions import active_session_registry_snapshot
    from sci_state import SessionDB
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home
    import json

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / name / '.sci' for name in ('a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    daemons, viewers, owners = [], [], []

    def type_command(viewer, text):
        viewer.output = b''
        viewer.type(text)
        viewer.until(text.split()[-1].encode())
        time.sleep(0.5)  # PTY paste/Enter pacing, not a completion assertion.
        viewer.type('\r')

    def attach_view(home, key, session, takeover=False):
        viewer = Viewer.__new__(Viewer)
        viewer.sock = connect(home)
        viewer.sock.settimeout(20)
        send(viewer.sock, {'action': 'attach', 'id': key, 'view_session': session, 'takeover': takeover})
        viewer.stream = viewer.sock.makefile('rb')
        viewer.output = b''
        viewer.reply = json.loads(viewer.stream.readline())
        viewers.append(viewer)
        return viewer

    entered, release = Event(), Event()

    def respond(record):
        message = record['body']['messages'][-1]['content']
        if message == 'hold side request':
            entered.set()
            assert release.wait(60)
            return Text('SIDE_WORK_COMPLETED')
        return Text('MAIN_READY' if message == 'hello' else 'SIDE_READY')

    with FakeLLMServer(respond) as model:
        try:
            for home in homes:
                write_sci_home(home, model.base_url)
                daemons.append(service(home, real_cli=True))
                key = request('start', home=home, cwd=str(tmp_path))['id']
                viewer = Viewer(home, key); viewers.append(viewer)
                viewer.until('❯ '.encode())
                type_command(viewer, 'hello')
                viewer.until(b'MAIN_READY')
                type_command(viewer, '/btw explain the previous answer')
                viewer.until(b'SIDE_READY')
                owner = wait_for(lambda: (row if (row := find_worker(key, home))
                                         and len(row.get('view_sessions', [])) == 2 and row['state'] == 'idle' else None))
                side_id = next(s for s in owner['view_sessions'] if s != owner['session_id'])
                # Return to main, then use the real /resume dispatcher in this same CLI.
                viewer.type('\x1f')  # Ctrl+/
                type_command(viewer, '/resume ' + side_id)
                viewer.until(b'\x1b[?1049h')  # Existing side's alternate-screen view.
                viewer.until(b'SIDE_READY')
                viewer.type('side draft kept')
                viewer.until(b'side draft kept')
                owners.append((owner, side_id, viewer))

            owner, _, viewer = owners[0]
            viewer.type('\x15')  # Clear only the unsent side draft.
            type_command(viewer, 'hold side request')
            assert entered.wait(10)
            viewer.type('side draft kept')
            viewer.until(b'side draft kept')
            wait_for(lambda: find_worker(owner['id'], homes[0])['state'] == 'running')
            requests_before = len(model.main_requests())
            for index in (0, 1, 0):
                home = homes[index]
                owner, side_id, previous = owners[index]
                assert find_view_worker(side_id, homes[1-index]) is None
                selected = find_view_worker(side_id, home)
                assert selected['view_session'] == side_id and selected['id'] == owner['id']
                assert find_worker(side_id, home) is None  # A view ID cannot stop its parent process.
                with SessionDB(home / 'state.db', read_only=True) as db:
                    before = [(db.get_session(s)['system_prompt'], db.get_messages(s))
                              for s in (owner['session_id'], side_id)]
                leases = active_session_registry_snapshot(home, strict=True)
                denied = attach_view(home, owner['id'], side_id)
                assert 'Another terminal' in denied.reply['error']
                # Code changes must not turn a reconnect into a whole-process shutdown.
                monkeypatch.setattr(refresh, 'newer_source', lambda started: Path('edited.py'))
                ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=AssertionError('must not offer shared-runtime kill')))
                assert refresh.refresh_attached_worker(owner, home=home, ui=ui) == owner
                viewer = attach_view(home, owner['id'], side_id, takeover=True)
                assert viewer.reply['attached'] == owner['id'], viewer.reply
                viewer.until(b'side draft kept')
                # Superseded input cannot reach either conversation.
                try:
                    previous.type('WRONG_VIEW_INPUT\r')
                except OSError:
                    pass
                assert find_worker(owner['id'], home)['pid'] == owner['pid']
                assert active_session_registry_snapshot(home, strict=True) == leases
                with SessionDB(home / 'state.db', read_only=True) as db:
                    assert [(db.get_session(s)['system_prompt'], db.get_messages(s))
                            for s in (owner['session_id'], side_id)] == before
                owners[index] = owner, side_id, viewer
            assert len(model.main_requests()) == requests_before
            release.set()
            owners[0][2].until(b'SIDE_WORK_COMPLETED')
            # Closing only the side releases its lease, while main remains resumable.
            owner, side_id, viewer = owners[0]
            viewer.type('\x11')  # Ctrl+Q inside side.
            wait_for(lambda: find_view_worker(side_id, homes[0]) is None)
            assert find_worker(owner['id'], homes[0])['pid'] == owner['pid']
            assert not any(e['session_id'] == side_id for e in active_session_registry_snapshot(homes[0], strict=True))
            with SessionDB(homes[0] / 'state.db', read_only=True) as db:
                assert db.get_session(side_id) and db.get_messages(side_id)
        finally:
            release.set()
            for viewer in viewers:
                viewer.close()
            for daemon in daemons:
                daemon.terminate()
                daemon.communicate(timeout=20)
