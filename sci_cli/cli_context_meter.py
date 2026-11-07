"""Single-row context occupancy; only the boundary brightness is animated."""

from math import cos, tau
from time import monotonic
from prompt_toolkit.utils import get_cwidth

def context_meter(percent: float | None, width: int = 16) -> list:
    """Fill left-to-right from usage, never elapsed time; width includes all cells.

    Existing UI redraws drive a subtle boundary-only pulse. No animation state,
    timer, or interpolation may advance the occupied count beyond actual usage.
    """
    from sci_cli.skin_engine import get_active_skin
    skin = get_active_skin()
    foreground = skin.get_color("meter_foreground", "#FFFFFF")
    background = skin.get_color("meter_background", "#000000")
    style = f"fg:{foreground} bg:{background}"
    percent = max(0, min(100, percent or 0))
    full = int(percent * width / 100)
    fragments = [(style, "▰" * full)]
    if full < width:
        brightness = .75 + .25 * (1 + cos(tau * monotonic() / 1.2)) / 2
        boundary = "#" + "".join(f"{round(int(foreground[i:i + 2], 16) * brightness):02X}" for i in (1, 3, 5))
        fragments.append((f"fg:{boundary} bg:{background}", "▱"))
        fragments.append((style + " dim", "·" * (width - full - 1)))
    return fragments


def frame_status(fragments: list, width: int) -> list:
    """Keep the inline meter and surrounding status within the terminal width."""
    used = 0
    middle = []
    for style, text in fragments:
        visible = []
        for char in text:
            cells = get_cwidth(char)
            if used + cells > width:
                break
            visible.append(char)
            used += cells
        middle.append((style, "".join(visible)))
    return middle
