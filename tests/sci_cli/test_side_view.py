"""View changes preserve drafts/reading position and never paint parent text in side."""

import asyncio
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from prompt_toolkit.application import Application, set_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.key_binding.key_processor import KeyPress
from prompt_toolkit.keys import Keys
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType
from prompt_toolkit.output import DummyOutput


@pytest.mark.asyncio
@pytest.mark.parametrize('running,copy_fails', [(False, False), (True, False), (True, True)])
async def test_ctrl_c_copies_selected_side_text_before_any_cancel_or_exit(monkeypatch, running, copy_fails):
    import cli as cli_module
    from sci_cli import clipboard
    from sci_constants import sci_home_key

    monkeypatch.setenv('SCI_DEFER_AGENT_STARTUP', '1')
    native = Mock(side_effect=PermissionError('fixture clipboard denied') if copy_fails else None,
                  return_value=True)
    monkeypatch.setattr(clipboard, 'is_remote_shell_session', lambda: False)
    monkeypatch.setattr(clipboard, 'write_clipboard_text', native)
    owner = cli_module.SciCLI(model='fixture', provider='openai-compat', api_key='fixture',
                              base_url='http://127.0.0.1:1/v1')
    owner._tui_init_run_state()
    kb = owner._tui_build_key_bindings()
    layout, _ = owner._tui_build_layout(kb)
    view = owner._side_view
    owner.agent = SimpleNamespace(interrupt=Mock())
    owner._agent_running = running
    controller = SimpleNamespace(owner=(sci_home_key(), owner.session_id), active=True,
                                 ui=view.surface, outcome='ready',
                                 running=running, conversation=SimpleNamespace(closed=Event()), close=Mock())
    owner._side_controller = controller
    with create_pipe_input() as pipe:
        app = Application(layout=layout, key_bindings=kb, input=pipe, output=DummyOutput())
        owner._app = view.surface._app = app
        app._sci_side_view = view
        with set_app(app):
            owner._input_area.buffer.text = 'main draft'
            view.select(True)
            view.side_buffer.text = 'side draft'
            view.append('copy this response')
            view.transcript.control.create_content(80, 10)
            for kind, column in ((MouseEventType.MOUSE_DOWN, 0), (MouseEventType.MOUSE_UP, 8)):
                view.transcript.control.mouse_handler(MouseEvent(
                    Point(column, 0), kind, MouseButton.LEFT, frozenset()))
            native.reset_mock()
            for _ in range(2):
                app.key_processor.feed(KeyPress(Keys.ControlC, '\x03'))
                app.key_processor.process_keys()
            assert native.call_count == 2
            native.assert_called_with('copy this')
            assert view.visible and not controller.conversation.closed.is_set()
            controller.close.assert_not_called()
            owner.agent.interrupt.assert_not_called()
            assert owner._input_area.buffer.text == 'main draft'
            assert view.side_buffer.text == 'side draft'
            if copy_fails:
                assert view.copy_status.startswith('Copy failed')
            # With selection cleared, the ordinary Ctrl+C close path still works.
            view.transcript.buffer.exit_selection()
            app.key_processor.feed(KeyPress(Keys.ControlC, '\x03'))
            app.key_processor.process_keys()
            controller.close.assert_called_once()
            owner.agent.interrupt.assert_not_called()


@pytest.mark.parametrize('remote,native_ok', [(False, True), (False, False), (True, True)])
def test_side_copy_uses_local_clipboard_or_user_terminal(monkeypatch, remote, native_ok):
    from sci_cli import clipboard
    from sci_cli.side_view import SideView

    native = Mock(return_value=native_ok)
    monkeypatch.setattr(clipboard, 'is_remote_shell_session', lambda: remote)
    monkeypatch.setattr(clipboard, 'write_clipboard_text', native)
    view = SideView.__new__(SideView)
    view.cli = SimpleNamespace(_write_osc52_clipboard=Mock())
    view.copy_text('selected side text')
    if remote or not native_ok:
        view.cli._write_osc52_clipboard.assert_called_once_with('selected side text')
        assert view.copy_status == 'Copy sent to terminal'
    else:
        view.cli._write_osc52_clipboard.assert_not_called()
        assert view.copy_status == 'Copied'
    if remote:
        native.assert_not_called()
    else:
        native.assert_called_once_with('selected side text')


def test_view_preserves_composers_scroll_and_defers_parent_output(monkeypatch):
    from sci_cli.cli_render import _cprint
    import cli as cli_module

    monkeypatch.setenv("SCI_DEFER_AGENT_STARTUP", "1")

    async def exercise():
        owner = cli_module.SciCLI(model="fixture", provider="openai-compat", api_key="fixture",
                                  base_url="http://127.0.0.1:1/v1")
        owner._tui_init_run_state()
        kb = owner._tui_build_key_bindings()
        layout, _ = owner._tui_build_layout(kb)
        view = owner._side_view
        composer = owner._input_area
        main = composer.buffer
        owner._attached_images = ['main-image']
        with create_pipe_input() as pipe:
            app = Application(layout=layout, input=pipe, output=DummyOutput())
            owner._app = app
            app._sci_side_view = view
            view.surface._app = app
            with set_app(app):
                main.text = 'main draft'
                main.cursor_position = 3
                view.select(True)
                view.side_buffer.text = 'side draft'
                view.side_buffer.cursor_position = 4
                owner._side_controller = SimpleNamespace(
                    active=True, ui=view.surface, outcome='ready',
                    conversation=SimpleNamespace(closed=Event()))
                before_heading = view.heading()
                owner._agent_running = owner._command_running = True
                owner._spinner_text = 'MAIN_ONLY_TOOL'
                owner._command_status = 'MAIN_ONLY_COMMAND'
                assert view.heading() == before_heading and 'ready' in before_heading
                assert not view.surface._agent_running and not view.surface._command_running
                assert not view.surface._render_spinner_text()
                assert 'MAIN_ONLY' not in view.surface._tui_placeholder_text()
                owner._agent_running = owner._command_running = False
                owner._side_controller = None
                assert view.surface._attached_images == []
                owner._capture_modal_input_snapshot()
                assert view.side_buffer.text == 'side draft'
                owner._restore_modal_input_snapshot()
                view.append('\n'.join(f'row {n}' for n in range(100)))
                view.scroll(-1)
                position = view.transcript.buffer.cursor_position
                assert position < len(view.transcript.text)
                _cprint('parent finished while side visible')
                assert view.pending_parent == ['parent finished while side visible']
                assert 'parent finished' not in view.transcript.text
                view.append('side response received while reading earlier text')
                assert view.transcript.buffer.cursor_position == position
                flushed = []
                monkeypatch.setattr(cli_module, '_cprint', flushed.append)
                view.select(False)
                assert composer.buffer is main and main.text == 'main draft'
                assert main.cursor_position == 3
                assert owner._attached_images == ['main-image']
                assert flushed == ['parent finished while side visible']
                assert view.pending_parent == []
                view.select(True)
                assert app.current_buffer.text == 'side draft'
                assert app.current_buffer.cursor_position == 4
                assert view.transcript.buffer.cursor_position == position
                view.select(False)
                view.side_buffer.history.append_string('temporary side question')
                view.surface._attached_images = ['temporary image']
                view.clear()
                assert main.text == 'main draft'
                assert view.transcript.text == ''
                assert view.side_buffer.history.get_strings() == []
                assert view.surface._attached_images == []

                # Messages queued in main retain ownership when a view switch
                # happens before the process loop consumes them.
                from sci_constants import sci_home_key
                from sci_cli import science_profile_router
                owner._side_controller = SimpleNamespace(
                    owner=(sci_home_key(), owner.session_id), active=True,
                    conversation=SimpleNamespace(closed=Event()), submit=Mock(), emit=view.append)
                view.select(True)
                monkeypatch.setattr(science_profile_router, 'route_input', lambda *a, **k: False)
                owner.chat = Mock()
                owner._turn_summary_begin = Mock()
                owner._tui_after_turn = Mock()
                owner._tui_process_one_input('queued in main before the switch')
                owner.chat.assert_called_once_with('queued in main before the switch', images=None, voice_input=False)
                owner._side_controller.submit.assert_not_called()

                from sci_cli.side_commands import route_input
                view.surface._attached_images = ['side-image']
                assert route_input(view.surface, 'inspect the attachment', has_images=True)
                owner._side_controller.submit.assert_called_once_with('inspect the attachment', ['side-image'])
                assert not view.surface._attached_images and owner._attached_images == ['main-image']

                # Keypress-generated summaries belong to side, like worker output.
                monkeypatch.setattr(cli_module, '_cprint', _cprint)
                view._key_handler(lambda event: _cprint('SIDE_KEY_SUMMARY'))(None)
                assert 'SIDE_KEY_SUMMARY' in view.transcript.text
                assert not any('SIDE_KEY_SUMMARY' in line for line in view.pending_parent)

    asyncio.run(exercise())


def test_connection_updates_keep_both_modal_owners_until_each_finishes(monkeypatch):
    from sci_cli.cli_modal_mixin import CLIModalMixin
    from tools.connectors.operation import ConnectionOperation

    main, side = CLIModalMixin(), CLIModalMixin()
    main._side_view = SimpleNamespace(surface=side)
    side._side_owner = main
    for ui, name in ((main, 'main'), (side, 'side')):
        ui._connection_state = {'payload': {'op_id': name}, 'target': {'name': name}}
        ui._restore_modal_input_snapshot = Mock()
        ui._paint_now = Mock()
    monkeypatch.setattr(ConnectionOperation, 'on_change', None)
    assert side._connection_install_hook()
    assert not main._connection_install_hook()
    hook = ConnectionOperation.on_change
    hook(SimpleNamespace(op_id='side'), None, {'settled_at': 1})
    assert side._connection_state is None
    assert main._connection_state is not None
    assert ConnectionOperation.on_change == hook
    hook(SimpleNamespace(op_id='main'), None, {'settled_at': 1})
    assert main._connection_state is None and ConnectionOperation.on_change is None
