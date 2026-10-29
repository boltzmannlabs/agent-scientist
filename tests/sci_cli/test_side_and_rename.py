"""Interactive command boundaries, persisted titles and temporary side input ownership."""

from copy import deepcopy
from pathlib import Path
from queue import Queue
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from sci_cli.rename_command import rename
from sci_cli.side_commands import cancel_from_keyboard, handle_side, route_input


def test_rename_updates_only_profile_metadata_and_survives_reopen(tmp_path, monkeypatch):
    from sci_cli.commands import COMMANDS, resolve_command
    from sci_cli.cli_loops_mixin import CLILoopsMixin
    from sci_cli.skill_add import Cancelled, WizardUI
    from sci_state import SessionDB

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    for name in ('A', 'B', 'A'):
        home = tmp_path / name
        home.mkdir(exist_ok=True)
        monkeypatch.setenv('SCI_HOME', str(home))
        db = SessionDB(home / 'state.db')
        if not db.get_session('chat'):
            db.create_session('chat', 'cli', system_prompt='fixed prompt')
            db.append_message('chat', 'user', 'original conversation')
        before = db.get_messages_as_conversation('chat')
        cli = SimpleNamespace(_session_db=db, session_id='chat', _pending_title=None, _agent_running=False)
        cli._cmd_title = lambda text: CLILoopsMixin._cmd_title(cli, text)
        rename(cli, f'/rename "{name} named chat"')
        assert db.get_session_title('chat') == f'{name} named chat'
        monkeypatch.setattr(WizardUI, 'ask', Mock(side_effect=Cancelled))
        rename(cli, '/rename')
        assert db.get_session_title('chat') == f'{name} named chat'
        assert db.set_auto_title('chat', 'automatic overwrite', source=db.TITLE_SOURCE_LLM) is False
        assert db.get_messages_as_conversation('chat') == before
        assert db.get_session('chat')['system_prompt'] == 'fixed prompt'
        db.close()
        reopened = SessionDB(home / 'state.db')
        assert reopened.get_session_title('chat') == f'{name} named chat'
        reopened.close()
    assert resolve_command('/ReNaMe').name == 'rename'
    assert '/rename' in COMMANDS and '/side' in COMMANDS
    assert resolve_command('btw') is None and '/btw' not in COMMANDS


def test_side_routes_followups_back_close_and_profile_change_without_parent_interruption(monkeypatch, tmp_path):
    from sci_cli import side_commands
    from sci_cli.cli_tui_mixin import CLITuiMixin

    monkeypatch.setenv('SCI_HOME', str(tmp_path))
    started, release = Event(), Event()
    prompts = []

    class Discussion:
        def __init__(self, parent, history, **kwargs):
            self.parent = parent
            self.closed = Event()
            self.transcript = []
            self.history = deepcopy(history)

        def answer(self, text):
            prompts.append(text)
            started.set()
            assert release.wait(10)
            self.transcript.extend([{'role': 'user', 'content': text}, {'role': 'assistant', 'content': 'reply'}])
            return 'reply'

        def close(self):
            self.closed.set()
            release.set()

    monkeypatch.setattr(side_commands, 'SideConversation', Discussion)
    output = []
    monkeypatch.setattr(side_commands, '_show', lambda cli, text: output.append(text))
    parent = SimpleNamespace(interrupt=Mock())
    cli = SimpleNamespace(agent=parent, session_id='parent', conversation_history=[{'role': 'assistant', 'content': 'prior'}],
                          _agent_running=True, _pending_input=Queue(), _app=Mock())
    event = SimpleNamespace(app=SimpleNamespace(current_buffer=SimpleNamespace(text='', reset=Mock()), invalidate=Mock()))
    # A parent clarification must not swallow the command or a side follow-up.
    cli._clarify_state = {'question': 'parent approval'}
    event.app.current_buffer.text = '/SIDE\twhy?'
    assert CLITuiMixin._tui_enter_overlay(cli, event) is False
    event.app.current_buffer.text = ''
    # Exercise the actual pre-queue Enter path while parent chat() is blocked.
    assert CLITuiMixin._tui_enter_inline_command(cli, event, '/side why?', False)
    controller = cli._side_controller
    assert started.wait(5)
    resets = event.app.current_buffer.reset.call_count
    assert CLITuiMixin._tui_enter_inline_command(cli, event, 'unsent while busy', False)
    assert event.app.current_buffer.reset.call_count == resets
    assert CLITuiMixin._tui_enter_overlay(cli, event) is False
    assert cli._clarify_state == {'question': 'parent approval'}
    assert route_input(cli, '/rename must not rename parent')
    assert route_input(cli, '!touch forbidden')
    side_commands.toggle(cli)
    assert not route_input(cli, 'parent followup')
    handle_side(cli, '/side')
    release.set()
    controller.worker.join(5)
    assert route_input(cli, 'side followup')
    controller.worker.join(5)
    assert prompts == ['why?', 'side followup']
    assert cli._pending_input.empty()
    cli._session_db = SimpleNamespace(resolve_resume_session_id=lambda _: 'compacted-parent')
    cli.session_id = 'compacted-parent'
    assert side_commands.current(cli) is controller
    assert not controller.conversation.closed.is_set()
    assert cancel_from_keyboard(cli, event)
    parent.interrupt.assert_not_called()
    assert not controller.active and controller.conversation.closed.is_set()
    assert cli.conversation_history == [{'role': 'assistant', 'content': 'prior'}]
    handle_side(cli, '/side')
    new = cli._side_controller
    monkeypatch.setenv('SCI_HOME', str(tmp_path / 'other'))
    assert not route_input(cli, 'other profile text')
    assert new.conversation.closed.is_set()
    assert not any('Tools and scientific execution are disabled' in line for line in output)
