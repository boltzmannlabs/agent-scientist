"""View changes preserve drafts/reading position and never paint parent text in side."""

import asyncio
from threading import Event
from types import SimpleNamespace
from unittest.mock import Mock

from prompt_toolkit.application import Application, set_app
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput


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
