"""Logo motion stays in owned UI, preserving the artwork and chat surface."""

import asyncio
from io import StringIO
from types import MethodType, SimpleNamespace
import time

import pytest
from prompt_toolkit.application import Application
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.layout import ConditionalContainer, FormattedTextControl, Window
from prompt_toolkit.filters import Condition
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.widgets import TextArea
from rich.console import Console

from sci_cli.banner_science import science_art
from sci_cli.logo_animation import logo_frames
from sci_cli.skin_engine import load_skin
from sci_cli.skin_defaults import DEFAULT_SKIN_NAME
from sci_cli.welcome_animation import WelcomeAnimation


def test_rotation_preserves_face_and_canvas_while_turning_edge_on():
    frames = logo_frames()['frames']
    face = science_art()['boltzmann']
    assert frames[0] == frames[-1] == face
    assert all(len(frame) == len(face) and list(map(len, frame)) == list(map(len, face)) for frame in frames)
    def occupied_width(frame):
        columns = [i for line in frame for i, char in enumerate(line) if char != '\u2800']
        return max(columns) - min(columns) + 1
    assert min(map(occupied_width, frames)) < occupied_width(face) / 3
    assert len({tuple(frame) for frame in frames}) > len(frames) / 2


@pytest.mark.asyncio
async def test_real_application_animates_stops_on_input_and_preserves_one_still_card(tmp_path):
    class Terminal(StringIO):
        def isatty(self):
            return True

    stream = Terminal()
    console = Console(file=stream, width=110, height=40, force_terminal=True)
    params = dict(skin=load_skin(DEFAULT_SKIN_NAME), profile='fixture', model='fixture-model',
                  provider='fixture', cwd=str(tmp_path), tool_count=2, skill_count=3, width=110)
    welcome = WelcomeAnimation()
    assert not welcome.capture(Console(file=StringIO(), width=110, height=40), params)
    assert not welcome.capture(Console(file=stream, width=60, height=40, force_terminal=True), params)
    assert welcome.capture(console, params)
    size = [Size(rows=40, columns=110)]
    output = Vt100_Output(stream, lambda: size[0], term='xterm', enable_cpr=False)
    async def until(predicate):
        async def poll():
            while not predicate():
                await asyncio.sleep(0.01)
        await asyncio.wait_for(poll(), 3)
    with create_pipe_input() as pipe:
        text = TextArea()
        app = Application(layout=Layout(HSplit([welcome.widget, text]), focused_element=text),
                          input=pipe, output=output)
        welcome.bind(app)
        task = asyncio.create_task(app.run_async())
        try:
            await until(lambda: welcome.started is not None)
            still = welcome.render()
            welcome.started = time.monotonic() - 3
            # A rotation's final frame is deliberately identical to its first.
            # Wait for visible motion rather than assuming every nonzero frame differs.
            await until(lambda: welcome.frame > 0 and welcome.render() != still)
            assert 'fixture-model' in ''.join(fragment[1] for fragment in welcome.render())
            pipe.send_text('x')
            await until(lambda: text.text == 'x' and welcome.stopped)
            assert welcome.frame == 0 and welcome.timer is None
            assert welcome.render() == still
            size[0] = Size(rows=20, columns=60)
            assert 'fixture-model' in ''.join(fragment[1] for fragment in welcome.render())
            assert 'BOLTZMANN LABS' not in ''.join(fragment[1] for fragment in welcome.render())
            printed = []
            cli = SimpleNamespace(console=console, _console_print=printed.append)
            welcome.dismiss(cli)
            welcome.dismiss(cli)
            assert welcome.render() == [] and len(printed) == 1
            assert not welcome.capture(console, params)  # A later /clear must print normally.
            assert text.text == 'x'
        finally:
            app.exit()
            await task
        assert welcome.timer is None


@pytest.mark.asyncio
async def test_model_overlay_releases_welcome_space_and_keeps_one_still_card(tmp_path):
    from cli import SciCLI

    class Terminal(StringIO):
        def isatty(self):
            return True

    stream = Terminal()
    console = Console(file=stream, width=132, height=40, force_terminal=True)
    welcome = WelcomeAnimation()
    assert welcome.capture(console, dict(
        skin=load_skin(DEFAULT_SKIN_NAME), profile='fixture', model='fixture-model',
        provider='fixture', cwd=str(tmp_path), tool_count=2, skill_count=3, width=132))
    printed = []
    text = TextArea(text='saved draft')
    cli = SimpleNamespace(console=console, _console_print=printed.append,
                          _welcome_animation=welcome, _model_picker_state=None,
                          _modal_input_snapshot=None, _modal_buffer=lambda: text.buffer)
    for name in ('_capture_modal_input_snapshot', '_restore_modal_input_snapshot',
                 '_render_scroll_list_panel', '_filter_model_picker_entries'):
        method = getattr(SciCLI, name)
        setattr(cli, name, method if name == '_filter_model_picker_entries' else MethodType(method, cli))
    picker = ConditionalContainer(Window(FormattedTextControl(
        lambda: SciCLI._get_model_picker_display_fragments(cli)), dont_extend_height=True),
        Condition(lambda: cli._model_picker_state is not None))
    output = Vt100_Output(stream, lambda: Size(rows=40, columns=132), term='xterm', enable_cpr=False)
    with create_pipe_input() as pipe:
        app = Application(layout=Layout(HSplit([welcome.widget, picker, text]), focused_element=text),
                          input=pipe, output=output)
        cli._app = app
        cli._invalidate = lambda **kwargs: app.invalidate()
        welcome.bind(app)
        task = asyncio.create_task(app.run_async())
        try:
            async with asyncio.timeout(5):
                while welcome.started is None:
                    await asyncio.sleep(0.01)
            SciCLI._open_model_picker(cli, [{'name': 'fixture', 'models': ['model']}], 'model', 'fixture')
            assert welcome.dismissed and welcome.timer is None
            assert welcome.render() == [] and len(printed) == 1
            # A model list taller than the old welcome card still leaves the composer available.
            cli._model_picker_state.update(stage='model', provider_data={'name': 'fixture'},
                                           model_list=[f'model-{i}' for i in range(40)])
            app.invalidate()
            await asyncio.sleep(0)
            rendered = ''.join(t[1] for t in SciCLI._get_model_picker_display_fragments(cli))
            assert 'fixture' in rendered and 'model-0' in rendered
            assert welcome.render() == []
            SciCLI._restore_modal_input_snapshot(cli)
            assert text.text == 'saved draft'
            SciCLI._capture_modal_input_snapshot(cli)
            assert len(printed) == 1
        finally:
            app.exit()
            await task
