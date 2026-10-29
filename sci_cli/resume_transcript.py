"""Display-only replay of a saved transcript. Never stages a message or executes a tool."""

from rich.text import Text
from rich.console import Group

import json


def tool_summary(body):
    """A factual preview, never a claim that a saved tool ran successfully."""
    heading, _, payload = body.partition("\n")
    try:
        data = json.loads(payload)
    except (ValueError, TypeError):
        data = None
    preview = ""
    if isinstance(data, dict):
        if heading.startswith("Call "):
            from agent.display import build_tool_preview
            preview = build_tool_preview(heading.removeprefix("Call "), data, max_len=90) or ""
        elif data.get("error"):
            preview = "error: " + str(data["error"])
    preview = " ".join(preview.split())
    if len(preview) > 90:
        preview = preview[:89] + "…"
    return heading + (" · " + preview if preview else "") + f" · {len(payload):,} chars saved"


def render_transcript(cli, entries):
    from cli import _record_output_history_entry, _suspend_output_history
    from sci_cli.cli_render import assistant_message_panel
    from sci_cli.cli_status_bar_mixin import CLIStatusBarMixin
    from cli import _accent_hex
    # Keep detailed activity in the read-only viewer, never rerun it during replay.
    entries = [(role, body) for role, body in entries if role in ("user", "assistant")]

    def render(role, body):
        if role == "assistant":
            return assistant_message_panel(
                body, mode=getattr(cli, "final_response_markdown", "render"),
                width=CLIStatusBarMixin._scrollback_box_width())
        message = Text(style="bold")
        message.append("● ", style=_accent_hex())
        message.append(body)
        return Group(Text("─" * 40, style=_accent_hex()), message)

    if not entries:
        cli._console_print(Text("No retained conversation text is available for this session."))
        return
    for role, body in entries:
        # One resize-aware entry per message, not one bounded/giant recap. Terminal
        # scrollback contains every emitted message even when the repaint cache rolls over.
        _record_output_history_entry(
            lambda role=role, body=body: cli._render_resume_history_panel_lines(render(role, body)))
        with _suspend_output_history():
            cli._console_print(render(role, body))
    cli._console_print(Text("Conversation restored. Ctrl+O / F8: browse transcript and expand tool details. "
                            "Scroll up to review; continue below. Nothing was rerun.", style="dim"))
