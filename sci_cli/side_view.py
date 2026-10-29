"""A temporary alternate-screen transcript; the parent's scrollback stays intact."""

import asyncio

from prompt_toolkit.document import Document
from prompt_toolkit.filters import Condition
from prompt_toolkit.formatted_text import ANSI, to_formatted_text
from prompt_toolkit.layout import DynamicContainer, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.lexers import Lexer
from prompt_toolkit.keys import Keys
from sci_cli.side_scroll import SideScrollFrame, TranscriptWindow
from sci_cli.side_surface import create_surface, output_scope
from prompt_toolkit.widgets import TextArea


class _TranscriptLexer(Lexer):
    def __init__(self):
        self.lines = [[]]

    def lex_document(self, document):
        lines = self.lines
        return lambda row: lines[row] if row < len(lines) else []


class SideView:
    def __init__(self, cli, footer, composer):
        self.cli, self.footer, self.composer = cli, footer, composer
        self.visible = False
        self.pending_parent = []
        self.main_buffer = composer.buffer
        self.surface = create_surface(cli)
        self.bindings = self.surface._tui_build_key_bindings()
        for binding in self.bindings.bindings:
            binding.handler = self._key_handler(binding.handler)
        side_layout, _ = self.surface._tui_build_layout(self.bindings)
        self.side_composer = self.surface._input_area
        # Side drafts never enter the on-disk main input history.
        from prompt_toolkit.history import InMemoryHistory
        self.side_composer.buffer.history = InMemoryHistory()
        self.side_buffer = self.side_composer.buffer
        self.lexer = _TranscriptLexer()
        self.transcript = TextArea(read_only=True, focusable=False, scrollbar=True, wrap_lines=True, lexer=self.lexer)
        self.transcript.window = TranscriptWindow(self, self.transcript.control)
        self._ansi = ""
        self.follow = True
        self.container = SideScrollFrame(self, [
            Window(FormattedTextControl(self.heading), height=1, style="class:hint"),
            self.transcript,
            side_layout.container,
        ])

    def _key_handler(self, callback):
        def handle(event):
            controller = getattr(self.cli, "_side_controller", None)
            with output_scope(controller.emit if controller else None):
                return callback(event)
        return handle

    def heading(self):
        from sci_cli.side_commands import label
        return label(self.cli) + " · PgUp/PgDn or wheel: scroll"

    def dispatch(self, fn):
        app = self.cli._app
        # All layout/buffer changes belong to the UI loop, including worker replies.
        try:
            here = asyncio.get_running_loop()
        except RuntimeError:
            here = None
        if app.loop is not None and app.loop is not here:
            app.loop.call_soon_threadsafe(fn)
        else:
            fn()

    def append(self, text):
        def update():
            self._ansi += text + "\n"
            lines = [[]]
            for style, body, *_ in to_formatted_text(ANSI(self._ansi)):
                for index, part in enumerate(body.split("\n")):
                    if index:
                        lines.append([])
                    lines[-1].append((style, part))
            self.lexer.lines = lines
            content = "\n".join("".join(part for _, part in line) for line in lines)
            buf = self.transcript.buffer
            cursor = len(content) if self.follow else buf.cursor_position
            buf.set_document(Document(content, cursor), bypass_readonly=True)
            self.cli._app.invalidate()
        self.dispatch(update)

    def capture_parent(self, text):
        """Called on the paint loop, so a pending print cannot race a screen switch."""
        if not self.visible:
            return False
        self.pending_parent.append(text)
        return True

    def select(self, visible):
        def switch():
            if self.visible == visible:
                return
            from cli import _cprint
            from sci_cli.cli_render import _set_chrome_floor
            app = self.cli._app
            app.renderer.erase()
            self.visible = visible
            app.full_screen = app.renderer.full_screen = visible
            app.layout.focus(self.side_composer if visible else self.composer)
            # Main resize-replay geometry does not describe the alternate screen.
            _set_chrome_floor(None)
            if not visible:
                pending, self.pending_parent = self.pending_parent, []
                with output_scope(None):
                    for text in pending:
                        _cprint(text)
            app.invalidate()
        self.dispatch(switch)

    def clear(self):
        def reset():
            from prompt_toolkit.history import InMemoryHistory
            self._ansi = ""
            self.lexer.lines = [[]]
            self.side_buffer.history = InMemoryHistory()
            self.side_buffer.reset()
            self.surface._attached_images.clear()
            self.transcript.buffer.set_document(Document(""), bypass_readonly=True)
            self.follow = True
        self.dispatch(reset)

    def scroll(self, direction, *, amount=None):
        self.transcript.window.move(direction, amount)


def install(cli, layout, composer):
    view = SideView(cli, layout.container, composer)
    cli._side_view = view
    layout.container = DynamicContainer(lambda: view.container if view.visible else view.footer)


def bind_keys(cli, kb):
    from sci_cli.side_commands import toggle
    # pt_input_extras normalizes CSI-u/modifyOtherKeys onto legacy US (Ctrl+_).
    kb.add("c-_", eager=True)(lambda event: toggle(cli))
    owner = getattr(cli, "_side_owner", cli)
    visible = Condition(lambda: bool(getattr(owner, "_side_view", None) and owner._side_view.visible))
    kb.add("pageup", filter=visible)(lambda event: owner._side_view.scroll(-1))
    kb.add("pagedown", filter=visible)(lambda event: owner._side_view.scroll(1))
    kb.add(Keys.ScrollUp, filter=visible)(lambda event: owner._side_view.scroll(-1, amount=3))
    kb.add(Keys.ScrollDown, filter=visible)(lambda event: owner._side_view.scroll(1, amount=3))
    kb.add("c-home", filter=visible)(lambda event: owner._side_view.transcript.window.move(0, fraction=0))
    kb.add("c-end", filter=visible)(lambda event: owner._side_view.transcript.window.move(0, fraction=1))
