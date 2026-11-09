"""Branded science welcome panel; consumes the inventory already collected at startup."""

from functools import lru_cache
from importlib.resources import files
import json

from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sci_cli.terminal_tables import key_value_table

# The unchanged 34-column logo fits beside the details in a standard 80-column terminal.
SCIENCE_LOGO_MIN_COLUMNS = 70


@lru_cache(maxsize=1)
def science_art():
    return json.loads(files("sci_cli").joinpath("data/science-terminal-art.json").read_text(encoding="utf-8"))


def science_welcome_panel(*, skin, profile, model, provider, cwd, tool_count,
                          skill_count, context_length=None, context_pinned=False,
                          yolo=False, width=80, logo=None, compact=False):
    text = skin.get_color("banner_text")
    dim = skin.get_color("banner_dim")
    surface = skin.get_color("terminal_elevated")
    title = Text("Agent Scientist", style=f"bold {skin.get_color('banner_title')}")
    configured = bool(model and model.strip().lower() != "unknown")
    model_label = f"{model} · {provider}" if configured and provider else model
    rows = [
        ("Profile", "main" if profile in (None, "default", "main") else profile),
        ("Model", model_label if configured else "no model configured — /model to connect"),
        ("Workspace", cwd),
        ("Capabilities", f"{tool_count} tools · {skill_count} skills · /capabilities for details"),
    ]
    if context_length:
        rows.append(("Context", f"{context_length:,} tokens" + (" (pinned)" if context_pinned else "")))
    fields = key_value_table(rows, skin=skin, expand=True)
    if width >= SCIENCE_LOGO_MIN_COLUMNS:
        brand = Text("\n".join(logo if logo is not None else science_art()["boltzmann"]), style=skin.get_color("banner_title"), no_wrap=True)
        brand.append("\n       BOLTZMANN LABS", style=f"bold {dim}")
        columns = Table.grid(padding=(0, 1 if compact else 3), expand=True)
        columns.add_column(width=34)
        columns.add_column(ratio=1)
        details = [title, Text("Your scientific workspace", style=dim), fields]
        if not compact:
            details = [Text(), title, Text("Your scientific workspace", style=dim), Text(), fields]
        columns.add_row(brand, Group(*details))
        content = [columns]
    else:
        content = [title, Text("Built by Boltzmann Labs", style=dim)]
        if not compact:
            content.append(Text())
        content.append(fields)
    if yolo:
        if not compact:
            content.append(Text())
        content.append(Text("⚠ YOLO mode — all approval prompts bypassed", style=skin.get_color("ui_warn")))
    return Panel(
        Group(*content), box=box.ROUNDED, padding=(0, 1) if compact else (1, 2),
        border_style=skin.get_color("banner_border"),
        style=f"{text} on {surface}" if surface else text,
        subtitle=Text("agent-sci", style=dim), subtitle_align="right",
    )
