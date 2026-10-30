"""Searchable resume view; identities stay separate from display labels."""

import asyncio
from contextlib import closing

from prompt_toolkit.application import Application, in_terminal, set_app
from prompt_toolkit.data_structures import Point
from prompt_toolkit.input import create_input
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import HSplit, Layout, Window
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea

from sci_cli.timefmt import relative_time
from sci_cli.session_listing import query_session_listing
from sci_state_sessions import INTERNAL_LISTING_SOURCES
from tools.ansi_strip import sanitize_display_text


class SessionPicker:
    def __init__(self, cli):
        self.cli = cli
        self.limit = 50
        self.selected = 0
        self.rows = []
        self.search = TextArea(height=1, multiline=False, prompt="Search: ")
        self.search.buffer.on_text_changed += self._search_changed
        self.control = FormattedTextControl(self.fragments, get_cursor_position=lambda: Point(0, self.selected))
        self.window = Window(self.control, height=12, wrap_lines=False, always_hide_cursor=True)
        self.refresh()

    def refresh(self):
        self.rows = query_session_listing(
            self.cli._session_db, source="cli", include_all_sources=False,
            current_session_id=self.cli.session_id, include_current_session=True,
            include_unnamed=True, search_query=self.search.text, limit=self.limit + 1,
            exclude_sources=list(INTERNAL_LISTING_SOURCES), order_by_last_active=True)
        self.more = len(self.rows) > self.limit
        self.rows = self.rows[:self.limit]
        self.selected = min(self.selected, max(0, len(self.rows) - 1))

    def _search_changed(self, _):
        self.selected, self.limit = 0, 50
        self.refresh()

    def move(self, delta):
        target = max(0, self.selected + delta)
        if target >= len(self.rows) and self.more:
            self.limit += 50
            self.refresh()
        self.selected = min(target, max(0, len(self.rows) - 1))

    def fragments(self):
        if not self.rows:
            return [("class:hint", "  No conversations found")]
        parts = []
        for index, row in enumerate(self.rows):
            age = relative_time(row.get("last_active"), session_id=row["id"])
            title = " ".join(sanitize_display_text(str(row.get("title") or "Untitled")).split())
            style = "class:menu.completions.completion.current" if index == self.selected else ""
            parts.append((style, f"{'›' if index == self.selected else ' '} {age:<12}  {title}\n"))
        return parts

    def application(self, *, input=None, output=None, style=None, before_render=None):
        kb = KeyBindings()
        for key, delta in (("up", -1), ("down", 1), ("pageup", -10), ("pagedown", 10)):
            kb.add(key)(lambda event, step=delta: self.move(step))

        @kb.add("enter")
        def choose(event):
            if self.rows:
                event.app.exit(result=self.rows[self.selected]["id"])

        @kb.add("escape", eager=True)
        @kb.add("c-c")
        def cancel(event):
            event.app.exit(result=None)

        from sci_cli.native_profile_session import profile_label
        layout = HSplit([
            Window(FormattedTextControl(f"Resume conversation · {profile_label()}"), height=1),
            self.search,
            Window(FormattedTextControl("  Updated       Conversation"), height=1),
            self.window,
            Window(FormattedTextControl("↑/↓ navigate · type to search · Enter resume · Esc cancel"), height=1),
        ])
        return Application(layout=Layout(layout, focused_element=self.search), key_bindings=kb,
                           full_screen=False, erase_when_done=True, input=input, output=output,
                           style=style, before_render=before_render, refresh_interval=0.25)


def choose_session(cli):
    """Borrow the existing terminal on its event loop; the caller is the command worker."""
    parent = cli._app

    async def run():
        with set_app(parent):
            return await show()

    async def show():
        async with in_terminal():
            picker = SessionPicker(cli)
            def before_render(app):
                if not parent.is_running and not app.is_done:
                    app.exit(result=None)
            # The parent may still have an Escape-flush timer pending. A fresh
            # parser prevents that timer from consuming this picker's keystrokes.
            with closing(create_input()) as terminal_input:
                app = picker.application(input=terminal_input, output=parent.output,
                                         style=parent.style, before_render=before_render)
                return await app.run_async()

    # Slash commands execute in the CLI worker, never block the UI loop on itself.
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is parent.loop:
        raise RuntimeError("Resume selection must run in the CLI command worker.")
    return asyncio.run_coroutine_threadsafe(run(), parent.loop).result()
