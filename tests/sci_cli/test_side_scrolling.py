"""Transcript scrolling counts screen rows and preserves the independent composer."""

from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from prompt_toolkit.application import Application, set_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.layout import Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.layout.mouse_handlers import MouseHandlers
from prompt_toolkit.layout.screen import Screen, WritePosition
from prompt_toolkit.mouse_events import MouseButton, MouseEvent, MouseEventType
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.widgets import TextArea

from sci_cli.side_scroll import SideScrollFrame, TranscriptControl, TranscriptWindow


def build_view(text):
    view = SimpleNamespace(follow=True, transcript=TextArea(text=text, read_only=True, focusable=False))
    view.transcript.control = TranscriptControl(view, view.transcript.buffer, view.transcript.lexer)
    view.copy_text = Mock()
    view.transcript.window = TranscriptWindow(view, view.transcript.control)
    view.scroll = lambda direction, amount=None: view.transcript.window.move(direction, amount)
    composer = TextArea(text='keep my draft', height=1)
    frame = SideScrollFrame(view, [Window(FormattedTextControl('Side'), height=1), view.transcript, composer])
    app = Application(layout=Layout(frame, focused_element=composer), output=DummyOutput())
    view.cli = SimpleNamespace(_app=app)
    app.invalidate = Mock()
    return view, composer, app, frame


def render(frame, width=24, height=12):
    screen, mouse = Screen(), MouseHandlers()
    frame.write_to_screen(screen, mouse, WritePosition(0, 0, width, height), '', True, None)
    return '\n'.join(''.join(screen.data_buffer[y][x].char for x in range(width)) for y in range(height)), mouse


@pytest.mark.asyncio
async def test_wrapped_rows_scroll_and_keep_reading_position_when_more_text_arrives():
    view, composer, app, frame = build_view('START ' + 'long世界paragraph ' * 90 + ' END')
    with set_app(app):
        bottom, _ = render(frame)
        window = view.transcript.window
        assert 'END' in bottom and window.maximum > 20
        top_before = window.top
        view.scroll(-1)
        earlier, _ = render(frame)
        assert earlier != bottom and window.top < top_before and not view.follow
        anchor = (window.vertical_scroll, window.vertical_scroll_2)
        view.transcript.text += '\nnew output\n' * 20
        render(frame)
        assert (window.vertical_scroll, window.vertical_scroll_2) == anchor
        window.move(0, fraction=0)
        first, _ = render(frame)
        assert 'START' in first
        window.move(0, fraction=1)
        last, _ = render(frame)
        assert 'new output' in last and view.follow
        render(frame, width=16)
        assert window.top == window.maximum
        assert composer.text == 'keep my draft' and app.layout.current_buffer is composer.buffer


@pytest.mark.asyncio
async def test_wheel_over_composer_and_scrollbar_drag_do_not_edit_or_focus_transcript():
    view, composer, app, frame = build_view('\n'.join(f'entry {i}' for i in range(80)))
    with set_app(app):
        _, mouse = render(frame)
        window = view.transcript.window
        bottom = window.top
        wheel = MouseEvent(Point(3, 11), MouseEventType.SCROLL_UP, MouseButton.NONE, frozenset())
        mouse.mouse_handlers[11][3](wheel)
        render(frame)
        assert window.top == bottom - 3
        # Click and drag the right-hand scrollbar to the top then bottom.
        _, mouse = render(frame)
        for kind, row in ((MouseEventType.MOUSE_DOWN, 3), (MouseEventType.MOUSE_MOVE, 2), (MouseEventType.MOUSE_UP, 2)):
            mouse.mouse_handlers[row][23](MouseEvent(Point(23, row), kind, MouseButton.LEFT, frozenset()))
        first, _ = render(frame)
        assert 'entry 0' in first and not view.follow
        window.move(0, fraction=1)
        last, _ = render(frame)
        assert 'entry 79' in last and view.follow
        assert composer.text == 'keep my draft' and app.layout.current_buffer is composer.buffer


@pytest.mark.asyncio
@pytest.mark.parametrize('reverse', [False, True])
async def test_drag_copies_wrapped_unicode_output_without_changing_composer(reverse):
    text = '0123456789世界ABCDEFGHIJ\nsecond line'
    view, composer, app, frame = build_view(text)
    with set_app(app):
        app.layout.update_parents_relations()
        _, mouse = render(frame, width=12)
        start, end = Point(2, 1), Point(6, 2)
        if reverse:
            start, end = end, start
        for kind, point in ((MouseEventType.MOUSE_DOWN, start),
                            (MouseEventType.MOUSE_MOVE, end),
                            (MouseEventType.MOUSE_UP, end)):
            mouse.mouse_handlers[point.y][point.x](MouseEvent(point, kind, MouseButton.LEFT, frozenset()))
        view.copy_text.assert_called_once_with('23456789世界ABC')
        from sci_cli.side_view import SideView
        assert SideView.selected_text(view) == '23456789世界ABC'
        assert view.transcript.buffer.selection_state is not None
        assert not view.follow
        assert composer.text == 'keep my draft' and app.layout.current_buffer is composer.buffer
        assert view.transcript.text == text
        view.scroll(-1)
        mouse.mouse_handlers[end.y][end.x](MouseEvent(end, MouseEventType.MOUSE_UP, MouseButton.LEFT, frozenset()))
        assert view.copy_text.call_count == 1
