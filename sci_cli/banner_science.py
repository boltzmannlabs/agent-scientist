"""Branded science welcome panel; consumes the inventory already collected at startup."""

from functools import lru_cache
from importlib.resources import files
import json

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@lru_cache(maxsize=1)
def science_art():
    return json.loads(files("sci_cli").joinpath("data/science-terminal-art.json").read_text(encoding="utf-8"))


def science_welcome_panel(*, skin, profile, model, provider, cwd, tool_count,
                          skill_count, context_length=None, context_pinned=False,
                          yolo=False, width=80, logo=None):
    text = skin.get_color("banner_text")
    dim = skin.get_color("banner_dim")
    surface = skin.get_color("terminal_elevated")
    title = Text("Agent Scientist", style=f"bold {skin.get_color('banner_title')}")
    fields = Table.grid(padding=(0, 2), expand=True)
    stacked = width < 55
    fields.add_column(style=text, overflow="fold", ratio=1)
    if not stacked:
        fields.add_column(style=text, overflow="fold", ratio=3)

    def row(name, value):
        label = Text(name, style=dim)
        value = Text(str(value), style=text)
        if stacked:
            fields.add_row(label)
            fields.add_row(value)
        else:
            fields.add_row(label, value)
    configured = bool(model and model.strip().lower() != "unknown")
    model_label = f"{model} · {provider}" if configured and provider else model
    for name, value in (
        ("Profile", "main" if profile in (None, "default", "main") else profile),
        ("Model", model_label if configured else "no model configured — /model to connect"),
        ("Workspace", cwd),
        ("Capabilities", f"{tool_count} tools · {skill_count} skills · /capabilities for details"),
    ):
        row(name, value)
    if context_length:
        row("Context", f"{context_length:,} tokens" + (" (pinned)" if context_pinned else ""))
    if width >= 85:
        brand = Text("\n".join(logo if logo is not None else science_art()["boltzmann"]), style=skin.get_color("banner_title"), no_wrap=True)
        brand.append("\n       BOLTZMANN LABS", style=f"bold {dim}")
        columns = Table.grid(padding=(0, 3), expand=True)
        columns.add_column(width=34)
        columns.add_column(ratio=1)
        columns.add_row(brand, Group(Text(), title, Text("Your scientific workspace", style=dim), Text(), fields))
        content = [columns]
    else:
        content = [title, Text("Built by Boltzmann Labs", style=dim), Text(), fields]
    if yolo:
        content.extend([Text(), Text("⚠ YOLO mode — all approval prompts bypassed", style=skin.get_color("ui_warn"))])
    return Panel(
        Group(*content), box=box.ROUNDED, padding=(1, 2),
        border_style=skin.get_color("banner_border"),
        style=f"{text} on {surface}" if surface else text,
        subtitle=Text("agent-sci", style=dim), subtitle_align="right",
    )
