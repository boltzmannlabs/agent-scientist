"""Resume keeps row identities/profile scope and Escape never accepts a selection."""

import asyncio
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput


@pytest.mark.asyncio
async def test_resume_order_identity_search_and_escape_across_profile_homes(tmp_path, monkeypatch):
    from sci_state import SessionDB
    from sci_cli.session_picker import SessionPicker
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for home in (tmp_path / 'a', tmp_path / 'b', tmp_path / 'a'):
        monkeypatch.setenv('SCI_HOME', str(home))
        with SessionDB(home / 'state.db') as db:
            if not db.get_session('old'):
                for name in ('old', 'new'):
                    db.create_session(name, source='cli', system_prompt='unchanged prefix')
                    db.append_message(name, 'user', 'retained message')
                with sqlite3.connect(home / 'state.db') as sql:
                    sql.execute("UPDATE messages SET timestamp=100")
                    sql.execute("UPDATE sessions SET started_at=100, last_activity_at=300 WHERE id='old'")
                    sql.execute("UPDATE sessions SET started_at=200, last_activity_at=250 WHERE id='new'")
            cli = SimpleNamespace(_session_db=db, session_id='current')
            picker = SessionPicker(cli)
            assert [r['id'] for r in picker.rows] == ['old', 'new']
            labels = ''.join(text for _, text in picker.fragments())
            assert labels.count('Untitled') == 2
            assert 'messages' not in labels and 'old' not in labels and 'new' not in labels
            picker.move(1)
            with create_pipe_input() as pipe:
                app = picker.application(input=pipe, output=DummyOutput())
                pipe.send_text('\r')
                assert await asyncio.wait_for(app.run_async(), 5) == 'new'
            picker.search.text = 'old'
            assert [r['id'] for r in picker.rows] == ['old']
            with create_pipe_input() as pipe:
                app = picker.application(input=pipe, output=DummyOutput())
                pipe.send_text('\x1b')
                assert await asyncio.wait_for(app.run_async(), 5) is None
            assert db.get_session('old')['system_prompt'] == 'unchanged prefix'
            assert cli.session_id == 'current'


@pytest.mark.asyncio
async def test_escape_releases_wizard_and_approval_without_accepting_or_interrupting(monkeypatch):
    from queue import Queue
    from prompt_toolkit.application import Application, set_app
    from prompt_toolkit.key_binding.key_processor import KeyPress
    from prompt_toolkit.keys import Keys
    from cli import SciCLI
    monkeypatch.setenv('SCI_DEFER_AGENT_STARTUP', '1')
    cli = SciCLI(model='fixture', provider='openai-compat', api_key='fixture', base_url='http://127.0.0.1:1/v1')
    cli._tui_init_run_state()
    cli._paint_now = Mock()
    cli.agent = Mock()
    bindings = cli._tui_build_key_bindings()
    layout, _ = cli._tui_build_layout(bindings)
    with create_pipe_input() as pipe:
        app = Application(layout=layout, key_bindings=bindings, input=pipe, output=DummyOutput())
        cli._app = app
        with set_app(app):
            for attribute, expected in (('_clarify_state', None), ('_approval_state', 'deny')):
                answers = Queue()
                setattr(cli, attribute, {'response_queue': answers})
                app.key_processor.feed(KeyPress(Keys.Escape, '\x1b'))
                app.key_processor.process_keys()
                assert answers.get_nowait() == expected
                assert getattr(cli, attribute) is None
            cli._model_picker_state = {'stage': 'model', 'filter': 'filtered'}
            def close_picker():
                cli._model_picker_state = None
                app.current_buffer.text = 'restored draft'
            cli._close_model_picker = Mock(side_effect=close_picker)
            app.key_processor.feed(KeyPress(Keys.Escape, '\x1b'))
            app.key_processor.process_keys()
            cli._close_model_picker.assert_called_once()
            assert app.current_buffer.text == 'restored draft'
            cli.agent.interrupt.assert_not_called()

    # A real TTY without curses uses the numbered prompt and still accepts Escape.
    from prompt_toolkit.application import create_app_session
    from sci_cli.curses_ui import _read_numbered_input, _NumberedNavigation
    import sys
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    with create_pipe_input() as pipe, create_app_session(input=pipe, output=DummyOutput()):
        pipe.send_text('\x1b')
        assert await asyncio.wait_for(asyncio.to_thread(_read_numbered_input, 'Choice: '), 5) is _NumberedNavigation.CANCEL
