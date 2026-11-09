"""An owned welcome widget: animation never writes over terminal scrollback."""

from io import StringIO
import time

from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.filters import Condition
from prompt_toolkit.layout import Window, FormattedTextControl, ConditionalContainer
from rich.console import Console

from sci_cli.banner_science import SCIENCE_LOGO_MIN_COLUMNS, science_welcome_panel
from sci_cli.logo_animation import logo_frames


class WelcomeAnimation:
    def __init__(self):
        self.params = None
        self.app = None
        self.timer = None
        self.started = None
        self.stopped = False
        self.dismissed = False
        self.frame = 0
        self.cache_key = None
        self.fragments = []
        self.widget = ConditionalContainer(
            Window(FormattedTextControl(self.render), wrap_lines=False, dont_extend_height=True),
            Condition(lambda: self.params is not None and not self.dismissed),
        )

    def capture(self, console, params):
        if self.params is not None or self.dismissed or not console.is_terminal or console.width < SCIENCE_LOGO_MIN_COLUMNS or console.height < 28:
            return False
        self.params = params
        return True

    def bind(self, app):
        if self.params is None:
            return
        self.app = app
        app.before_render += self.before_render
        app.key_processor.before_key_press += self.stop

    def before_render(self, app):
        if self.started is None and not self.stopped:
            self.started = time.monotonic()
            self.tick()
        if app.is_done:
            self.stop()

    def tick(self):
        self.timer = None
        if self.stopped or not self.app.is_running:
            return
        animation = logo_frames()
        self.frame = int((time.monotonic() - self.started) * 1000 / animation['frame_ms']) % len(animation['frames'])
        self.app.invalidate()
        self.timer = self.app.loop.call_later(animation['frame_ms'] / 1000, self.tick)

    def stop(self, *_):
        self.stopped = True
        self.frame = 0
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.app:
            self.app.invalidate()

    def render(self):
        if self.params is None or self.dismissed:
            return []
        size = self.app.output.get_size() if self.app else None
        width = size.columns if size else self.params['width']
        # Keep the composer visible when a formerly tall terminal is shrunk.
        if size and size.rows < 28:
            width = min(width, SCIENCE_LOGO_MIN_COLUMNS - 1)
        key = (width, self.frame)
        if key != self.cache_key:
            stream = StringIO()
            console = Console(file=stream, width=width, force_terminal=True, color_system='truecolor')
            console.print(science_welcome_panel(**{**self.params, 'width': width},
                          logo=logo_frames()['frames'][self.frame]))
            self.fragments = to_formatted_text(ANSI(stream.getvalue().rstrip('\n')))
            self.cache_key = key
        return self.fragments

    def dismiss(self, cli):
        if self.params is None or self.dismissed:
            return
        self.stop()
        self.dismissed = True
        # Preserve one still card in scrollback; animation frames are never chat messages.
        cli._console_print(science_welcome_panel(**{**self.params, 'width': cli.console.width}))
