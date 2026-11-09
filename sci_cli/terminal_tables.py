"""Shared presentation for grouped terminal details; values remain literal text."""

from rich import box
from rich.cells import cell_len
from rich.table import Table
from rich.text import Text


def key_value_table(rows, *, skin, title=None, expand=False) -> Table:
    rows = list(rows)
    table = Table(
        title=Text(title, style=skin.get_color("banner_title")) if title else None,
        box=box.ROUNDED, border_style=skin.get_color("session_border"),
        show_header=False, padding=(0, 1), expand=expand,
    )
    label_width = min(12, max((cell_len(str(label)) for label, _ in rows), default=1))
    table.add_column(style=skin.get_color("banner_dim"), overflow="fold", min_width=label_width, max_width=24)
    table.add_column(style=skin.get_color("banner_text"), overflow="fold", ratio=1)
    for label, value in rows:
        table.add_row(Text(str(label)), value if isinstance(value, Text) else Text(str(value)))
    return table
