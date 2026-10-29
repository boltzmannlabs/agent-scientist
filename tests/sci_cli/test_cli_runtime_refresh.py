"""Fresh conversations reload config; reviewed reconnects refresh real CLI owners."""

import os
from pathlib import Path
import select
import subprocess
import sys
import time

import pytest

from tests.sci_cli.test_background_chats import ROOT, Viewer, service, wait_for
from sci_cli.background_chats import find_worker, request


class Terminal:
    def __init__(self, home):
        import fcntl
        import struct
        import termios
        self.master, slave = os.openpty()
        fcntl.ioctl(self.master, termios.TIOCSWINSZ, struct.pack('HHHH', 36, 120, 0, 0))
        self.output = b''
        self.process = subprocess.Popen(
            [sys.executable, '-m', 'sci_cli.main', '--cli'], cwd=home.parent,
            env={**os.environ, 'SCI_HOME': str(home), 'HOME': str(home.parent),
                 'PYTHONPATH': str(ROOT), 'TERM': 'xterm-256color', 'SCI_STATE_DB_GUARD_BYPASS': '1'},
            stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        os.close(slave)

    def until(self, predicate):
        deadline = time.monotonic() + 45
        while time.monotonic() < deadline:
            if select.select([self.master], [], [], 0.1)[0]:
                try:
                    self.output += os.read(self.master, 65536)
                except OSError:
                    break
            if predicate():
                return
        raise AssertionError(self.output[-6000:].decode(errors='replace'))

    def send(self, text):
        self.output = b''
        os.write(self.master, text.encode())
        self.until(lambda: text.encode() in self.output)
        time.sleep(0.5)  # Terminal paste/Enter pacing, not a completion assertion.
        os.write(self.master, b'\r')

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        os.close(self.master)


def test_foreground_refresh_does_not_discard_owned_work(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from sci_cli.cli_runtime_refresh import fresh_conversation
    from sci_cli import skill_add, native_profile_session
    original_resume = native_profile_session.request_resume
    ui = SimpleNamespace(show=Mock())
    monkeypatch.setattr(skill_add, 'WizardUI', lambda cli: ui)
    navigate = Mock()
    monkeypatch.setattr(native_profile_session, 'request_resume', navigate)
    cli = SimpleNamespace(_background_managed=False, _background_tasks={'running': object()},
                          conversation_history=[{'role': 'user', 'content': 'keep this'}])
    fresh_conversation(cli)
    navigate.assert_not_called()
    assert cli.conversation_history == [{'role': 'user', 'content': 'keep this'}]
    assert 'No work was stopped' in ui.show.call_args.args[0]
    cli._background_tasks.clear()
    fresh_conversation(cli)
    assert navigate.call_args.kwargs == {'foreground': True}
    # A foreground CLI must not become a daemon-backed chat just to reload.
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path / '.sci'))
    cli.session_id = 'old'
    cli._app = SimpleNamespace(loop=SimpleNamespace(call_soon_threadsafe=Mock()), exit=Mock())
    original_resume(cli, None, ui, foreground=True)
    assert '--no-daemon' in cli._pending_relaunch
    cli._background_managed = True
    fresh_conversation(cli)
    assert navigate.call_args.kwargs == {'foreground': False}


@pytest.mark.platforms('posix')
def test_new_reloads_real_tool_config_without_changing_departed_prompt(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_write, read_user_config_raw
    from sci_state import SessionDB
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    homes = [tmp_path / n / '.sci' for n in ('a', 'b')]
    monkeypatch.setenv('SCI_HOME', str(homes[0]))
    daemons, terminals = [], []
    with FakeLLMServer([Text('FIRST_DONE'), Text('SECOND_DONE')] * 3) as model:
        for home in homes:
            write_sci_home(home, model.base_url, extra_config=
                           'platform_toolsets:\n  cli: [file]\ntools:\n  tool_search:\n    enabled: "off"\n')
            daemons.append(service(home, real_cli=True))
        try:
            for iteration, home in enumerate((homes[0], homes[1], homes[0])):
                cfg = read_user_config_raw(home / 'config.yaml')
                cfg['platform_toolsets']['cli'] = ['file']
                atomic_config_write(home / 'config.yaml', cfg)
                terminal = Terminal(home); terminals.append(terminal)
                terminal.until(lambda: '❯ '.encode() in terminal.output)
                count = len(model.main_requests())
                terminal.send('Reply FIRST_DONE for this fixture.')
                terminal.until(lambda: len(model.main_requests()) == count + 1 and b'FIRST_DONE' in terminal.output)
                worker = wait_for(lambda: next((c for c in request('status', home=home)['chats']
                                               if c['attached'] and c['state'] == 'idle' and c['session_id']), None))
                with SessionDB(home / 'state.db', read_only=True) as db:
                    original = db.get_session(worker['session_id'])['system_prompt']
                before = model.main_requests()[-1]
                assert 'delegate_task' not in {t['function']['name'] for t in before['tools']}
                cfg['platform_toolsets']['cli'] = ['file', 'delegation']
                atomic_config_write(home / 'config.yaml', cfg)
                terminal.send(f'/new now Reloaded fixture {iteration}')
                terminal.until(lambda: any(c['attached'] and c['pid'] != worker['pid']
                                           for c in request('status', home=home)['chats']))
                terminal.until(lambda: b'Session:' in terminal.output and
                               '❯ '.encode() in terminal.output.split(b'Session:', 1)[1])
                terminal.send('Reply SECOND_DONE for this fixture.')
                terminal.until(lambda: len(model.main_requests()) == count + 2 and b'SECOND_DONE' in terminal.output)
                after = model.main_requests()[-1]
                assert 'delegate_task' in {t['function']['name'] for t in after['tools']}
                with SessionDB(home / 'state.db', read_only=True) as db:
                    assert db.get_session(worker['session_id'])['system_prompt'] == original
                    assert any(m['content'] == 'Reply FIRST_DONE for this fixture.'
                               for m in db.get_messages(worker['session_id']))
                terminal.close(); terminals.remove(terminal)
        finally:
            for terminal in terminals:
                terminal.close()
            for daemon in daemons:
                daemon.terminate(); daemon.communicate(timeout=20)


@pytest.mark.platforms('posix')
def test_refresh_requires_consent_then_resumes_saved_real_worker(tmp_path, monkeypatch):
    from sci_cli import cli_runtime_refresh as refresh
    from sci_cli.skill_add import Cancelled
    from sci_state import SessionDB
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    home = tmp_path / '.sci'
    monkeypatch.setenv('SCI_HOME', str(home))
    source = tmp_path / 'source'; source.mkdir()
    module = source / 'cli.py'; module.write_text('old = True\n')
    original_scan = refresh.newer_source
    monkeypatch.setattr(refresh, 'newer_source', lambda started: original_scan(started, source))
    daemon = service(home)
    viewer = None

    class UI:
        def __init__(self, answers):
            self.answers = iter(answers)
        def show(self, message):
            pass
        def choose(self, question, choices):
            answer = next(self.answers)
            assert answer in choices
            return answer

    try:
        key = request('start', home=home, cwd=str(tmp_path))['id']
        worker = wait_for(lambda: (w if (w := find_worker(key, home)) and w['state'] == 'idle' else None))
        assert refresh.refresh_attached_worker(worker, home=home, ui=UI([])) == worker
        viewer = Viewer(home, key)
        viewer.until(b'READY')
        viewer.type('work\n'); viewer.until(b'completed:work')
        viewer.close(); viewer = None
        with SessionDB(home / 'state.db', read_only=True) as db:
            prompt = db.get_session('fixture')['system_prompt']
            messages = db.get_messages('fixture')
        module.write_text('old = False\n')  # Uncommitted change; no git version bump.
        # Keep the edit outside the process-start timestamp precision window.
        import psutil
        edit_time = max(time.time(), psutil.Process(worker['pid']).create_time() + 3)
        os.utime(module, (edit_time, edit_time))
        with pytest.raises(Cancelled):
            refresh.refresh_attached_worker(worker, home=home, ui=UI(['Cancel']))
        assert refresh.refresh_attached_worker(worker, home=home, ui=UI(['Keep existing runtime'])) == worker
        assert find_worker(key, home)['pid'] == worker['pid']
        replacement = refresh.refresh_attached_worker(worker, home=home, ui=UI([
            'Reload saved conversation with updated code', 'Close previous window and resume here']))
        new_worker = wait_for(lambda: (w if (w := find_worker(replacement['id'], home)) and w['state'] == 'idle' else None))
        assert new_worker['pid'] != worker['pid']
        assert not find_worker(key, home)
        with SessionDB(home / 'state.db', read_only=True) as db:
            assert db.get_session('fixture')['system_prompt'] == prompt
            assert db.get_messages('fixture') == messages  # No request replay.
    finally:
        if viewer:
            viewer.close()
        daemon.terminate(); daemon.communicate(timeout=20)
