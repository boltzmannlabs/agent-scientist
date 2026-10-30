"""Read-only transcript navigation for the classic CLI; no agent or tool execution."""

from sci_cli.resume_transcript import tool_summary


class TranscriptView:
    """Keep disclosure state separate from both saved messages and model context."""

    def __init__(self, entries, area):
        self.entries = entries
        self.area = area
        self.expanded = set()
        self.line_entries = []
        self.starts = []
        self.refresh()

    @property
    def selected(self):
        row = self.area.buffer.document.cursor_position_row
        return self.line_entries[min(row, len(self.line_entries) - 1)] if self.line_entries else None

    def refresh(self, selected=0):
        from prompt_toolkit.document import Document
        blocks, self.line_entries, self.starts = [], [], []
        position = 0
        labels = {"user": "● You", "assistant": "◆ Sci", "event": "◈ Event"}
        for index, (role, body) in enumerate(self.entries):
            if role == "tool":
                block = ("▾ " + body if index in self.expanded else "▸ " + tool_summary(body))
            else:
                block = labels[role] + ":\n" + body
            block += "\n\n"
            self.starts.append(position)
            position += len(block)
            self.line_entries.extend([index] * block.count("\n"))
            blocks.append(block)
        text = "".join(blocks) or "No retained conversation text is available."
        cursor = self.starts[selected] if self.starts and selected is not None else 0
        self.area.buffer.set_document(Document(text, cursor_position=cursor), bypass_readonly=True)

    def toggle(self):
        index = self.selected
        if index is not None and self.entries[index][0] == "tool":
            self.expanded.symmetric_difference_update({index})
            self.refresh(index)

    def toggle_all(self):
        tools = {i for i, entry in enumerate(self.entries) if entry[0] == "tool"}
        self.expanded = set() if self.expanded == tools else tools
        self.refresh(self.selected)

    def next_tool(self, direction):
        tools = [i for i, entry in enumerate(self.entries) if entry[0] == "tool"]
        if not tools:
            return
        current = self.selected if self.selected is not None else -1
        candidates = [i for i in tools if (i - current) * direction > 0]
        index = (candidates[0] if direction > 0 else candidates[-1]) if candidates else (
            tools[0] if direction > 0 else tools[-1])
        self.area.buffer.cursor_position = self.starts[index]


def build_transcript_application(entries, *, title="Conversation", **kwargs):
    from prompt_toolkit.application import Application
    from prompt_toolkit.filters import Condition
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.layout import HSplit, Layout, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.search import start_search, stop_search
    from prompt_toolkit.styles import Style
    from prompt_toolkit.widgets import SearchToolbar, TextArea
    from sci_cli.skin_engine import get_prompt_toolkit_style_overrides

    search = SearchToolbar()
    area = TextArea(read_only=True, scrollbar=True, wrap_lines=True, search_field=search)
    view = TranscriptView(entries, area)
    kb = KeyBindings()
    reading = Condition(lambda: app.layout.has_focus(area))

    @kb.add("enter", filter=reading)
    def toggle(event):
        view.toggle()

    @kb.add("c-e", filter=reading)
    def toggle_all(event):
        view.toggle_all()

    @kb.add("tab", filter=reading)
    def next_tool(event):
        view.next_tool(1)

    @kb.add("s-tab", filter=reading)
    def previous_tool(event):
        view.next_tool(-1)

    @kb.add("c-f", filter=reading)
    @kb.add("/", filter=reading)
    def find(event):
        start_search(area.control)

    @kb.add("escape", eager=True)
    def back(event):
        if app.layout.has_focus(search):
            stop_search()
        else:
            app.exit()

    @kb.add("q", filter=reading)
    @kb.add("c-o", filter=reading)
    @kb.add("f8", filter=reading)
    @kb.add("c-c")
    def close(event):
        app.exit()

    footer = ("↑↓ PgUp/PgDn: scroll · Ctrl+Home/End: first/last · Tab: next tool · Enter: expand/collapse\n"
              "Ctrl+E: all details · / or Ctrl+F: search visible text · Esc/q: back to chat · Read-only")
    layout = Layout(HSplit([
        Window(FormattedTextControl(title), height=1, style="class:subagent-dock.heading"),
        area, search, Window(FormattedTextControl(footer), dont_extend_height=True, wrap_lines=True),
    ]), focused_element=area)
    kwargs.setdefault("style", Style.from_dict(get_prompt_toolkit_style_overrides()))
    app = Application(layout=layout, key_bindings=kb, full_screen=True, **kwargs)
    return app, view


def _busy(cli):
    from sci_cli.cli_subagent_monitor import modal_prompt_active
    return modal_prompt_active(cli) or any(getattr(cli, flag, False) for flag in (
        "_connection_state", "_agent_running", "_command_running"))


def transcript_available(cli):
    return not (_busy(cli) or getattr(cli, "_transcript_open", False)
                or getattr(getattr(cli, "_side_view", None), "visible", False))


def load_transcript(cli):
    """Read the active session each time, never a previous profile's resume cache."""
    from cli import _strip_reasoning_tags
    from sci_cli.cli_agent_setup_mixin import _collect_resume_entries
    db = getattr(cli, "_session_db", None)
    rows = []
    if db is not None and getattr(cli, "session_id", None):
        _, rows = db.get_resume_conversations(cli.session_id)
    if not rows:
        rows = getattr(cli, "conversation_history", [])
    return _collect_resume_entries(rows, _strip_reasoning_tags)


def open_transcript(cli):
    import asyncio
    from prompt_toolkit.application import in_terminal
    from tools.ansi_strip import sanitize_display_text

    if not transcript_available(cli):
        return
    cli._transcript_open = True
    owner = (getattr(cli, "_session_db", None), getattr(cli, "session_id", None))

    def interrupted():
        return _busy(cli) or owner != (getattr(cli, "_session_db", None), getattr(cli, "session_id", None))

    def before_render(app):
        if interrupted() and not app.is_done:
            app.exit()

    async def run():
        try:
            async with in_terminal():
                if interrupted():
                    return
                entries = load_transcript(cli)
                title = "Conversation · " + sanitize_display_text(str(getattr(cli, "session_id", "")))
                app, _ = build_transcript_application(
                    entries, title=title, before_render=before_render, refresh_interval=0.2)
                await app.run_async()
        except Exception:
            from cli import logger
            logger.exception("Could not open saved transcript")
            cli._console_print("Could not open the saved transcript. Your conversation is unchanged.")
        finally:
            cli._transcript_open = False
            cli._invalidate()

    asyncio.get_running_loop().create_task(run())


def bind_transcript_keys(cli, kb):
    from prompt_toolkit.filters import Condition
    for key in ("c-o", "f8"):
        kb.add(key, filter=Condition(lambda: transcript_available(cli)))(
            lambda event: open_transcript(cli))
