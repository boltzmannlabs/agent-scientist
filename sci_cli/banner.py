"""Welcome banner, ASCII art, skills summary, and update check for the CLI."""
import json
import logging
import os
import re
import shutil
import sys
import threading
from pathlib import Path
from sci_cli import source_check
# Historical updater import (tests/compat/old_updater_surface.json). In-tree callers use the owner.
from sci_cli.source_check import _github_compare_behind  # noqa: F401
from sci_constants import get_sci_home
from typing import TYPE_CHECKING, Any, Dict, List, Optional

# rich and prompt_toolkit are imported lazily: this module sits on the TUI gateway's critical
# startup path purely for the lightweight update-check helpers, and eager rich/prompt_toolkit
# imports cost ~50ms before ``gateway.ready`` could fire.
if TYPE_CHECKING:
    from rich.console import Console

logger = logging.getLogger(__name__)

# ANSI building blocks for conversation display (``_DIM``/``_RST`` are imported by callbacks.py).
_DIM = "\033[2m"
_RST = "\033[0m"


def _check_via_pypi() -> Optional[int]:
    # Shim to stop the old updater doing work until relaunch. no registry query.
    return None


def check_via_pypi() -> Optional[int]:
    # Shim to stop the old updater doing work until relaunch. status is unknown.
    return None


def _quiet(fn, default=None):
    """``fn()``, or ``default`` on any exception — for best-effort display inputs."""
    try:
        return fn()
    except Exception:
        return default


def cprint(text: str):
    """Print ANSI-colored text through prompt_toolkit's renderer."""
    from prompt_toolkit import print_formatted_text as _pt_print
    from prompt_toolkit.formatted_text import ANSI as _PT_ANSI
    # prompt_toolkit needs a real console: on Windows a redirected/absent stdout raises
    # NoConsoleScreenBufferError, and display helpers must never crash the caller over that.
    if _quiet(lambda: _pt_print(_PT_ANSI(text)) or True) is None:
        print(text)


def _active_skin():
    """The active skin object (raises when the skin engine is unavailable)."""
    from sci_cli.skin_engine import get_active_skin
    return get_active_skin()


def _skin_color(key: str, fallback: str) -> str:
    """Get a color from the active skin, or return fallback."""
    return _quiet(lambda: _active_skin().get_color(key, fallback), fallback)


# === ASCII Art & Branding ===

from sci_cli import __release_date__ as RELEASE_DATE
from sci_cli.version_info import get_version_info

SCI_AGENT_LOGO = """[bold #FFD700]██╗  ██╗███████╗██████╗ ███╗   ███╗███████╗███████╗       █████╗  ██████╗ ███████╗███╗   ██╗████████╗[/]
[bold #FFD700]██║  ██║██╔════╝██╔══██╗████╗ ████║██╔════╝██╔════╝      ██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝[/]
[#FFBF00]███████║█████╗  ██████╔╝██╔████╔██║█████╗  ███████╗█████╗███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║[/]
[#FFBF00]██╔══██║██╔══╝  ██╔══██╗██║╚██╔╝██║██╔══╝  ╚════██║╚════╝██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║[/]
[#CD7F32]██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗███████║      ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║[/]
[#CD7F32]╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝╚══════╝      ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝[/]"""

# Compact ANSI Shadow lettering: native blocks and double-line shadows, not
# resampled pixels. Keep the complete title within the original banner footprint.
_AGENTIC_GLYPHS = {
    "A": (" ████╗ ", "██╔═██╗", "██████║", "██╔═██║", "██║ ██║", "╚═╝ ╚═╝"),
    "G": (" ████╗ ", "██╔══╝ ", "██║███╗", "██║ ██║", "╚████╔╝", " ╚═══╝ "),
    "E": ("█████╗", "██╔══╝", "████╗ ", "██╔═╝ ", "█████╗", "╚════╝"),
    "N": ("███╗ ██╗", "████╗██║", "██╔████║", "██║╚███║", "██║ ╚██║", "╚═╝  ╚═╝"),
    "T": ("██████╗", "╚═██╔═╝", "  ██║  ", "  ██║  ", "  ██║  ", "  ╚═╝  "),
    "I": ("██╗", "██║", "██║", "██║", "██║", "╚═╝"),
    "C": (" ███╗", "██╔═╝", "██║  ", "██║  ", "╚███╗", " ╚══╝"),
    "S": ("█████╗", "██╔══╝", "█████╗", "╚══██║", "█████║", "╚════╝"),
    "-": ("     ", "     ", "████╗", "╚═══╝", "     ", "     "),
}
_AGENTIC_GRADIENT = ("#F04FCB", "#B45BFF", "#557BFF", "#28C8F5", "#20D6A5")


def _agentic_sciences_logo(columns: Optional[int] = None):
    """Draw ANSI Shadow type over terminal-native scientific linework.

    Startup artwork lives in scrollback, so a bounded, left-aligned footprint
    survives narrowing a wide pane to the original banner's 95-column minimum.
    Braille supplies detail around the type without resampling the lettering.
    """
    from math import cos, pi, sin
    from rich.style import Style
    from rich.text import Text

    columns = max(1, columns or shutil.get_terminal_size((80, 24)).columns)
    if columns < 95:
        return Text()
    width, art_rows = 94, 15
    title_lines = [
        "".join(_AGENTIC_GLYPHS[char][row] for char in "AGENT-SCIENTIST")
        for row in range(6)
    ]
    title_top = 4
    title_left = (width - len(title_lines[0])) // 2
    pixel_width, pixel_height = width * 2, art_rows * 4
    ink = [bytearray(pixel_width) for _ in range(pixel_height)]
    ribbon = [bytearray(pixel_width) for _ in range(pixel_height)]
    sx, sy = (pixel_width - 1) / 1000, (pixel_height - 1) / 270

    def point(x, y, value=180, solid=False):
        px, py = round(x * sx), round(y * sy)
        if 0 <= px < pixel_width and 0 <= py < pixel_height:
            ink[py][px] = max(ink[py][px], value)
            if solid:
                ribbon[py][px] = 1

    def path(points, value=160, solid=False):
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            steps = max(1, round(max(abs(x1 - x0) * sx, abs(y1 - y0) * sy)))
            for step in range(steps + 1):
                t = step / steps
                point(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, value, solid=solid)

    def node(x, y, radius=4):
        path([(x + radius * cos(i * pi / 8), y + radius * sin(i * pi / 8))
              for i in range(17)], 240)

    # Signed, phase-opposed strands cross repeatedly along the horizontal axis.
    # Extend past the first/last crossing so the ends never close into a frame.
    def strand_y(x, sign):
        phase = (x - 156) / 688
        amplitude = 52 + 62 * abs(cos(pi * phase)) ** 1.5
        axis = 143
        if abs(x - 500) < 64:
            axis -= 16 * (1 + cos(pi * (x - 500) / 64))
        return axis + sign * amplitude * sin(4 * pi * phase)

    for x in range(114, 889, 16):
        first, second = strand_y(x, 1), strand_y(x, -1)
        path(((x, first), (x, second)), 150)
        if x % 48 == 18:
            node(x, first, 2)
    for px in range(round(112 * sx), round(888 * sx) + 1):
        x = px / sx
        for sign in (1, -1):
            y = strand_y(x, sign)
            toward_axis = 1 if y < 143 else -1
            for offset in (-1.5, 0, 1.5):
                point(x, y + offset, 250, solid=True)
            for offset in (4, 7, 10):
                if (px * 13 + offset * 7) % 11 < 6:
                    point(x, y + toward_axis * offset, 170)

    # Molecular branches and angular instrument panels share the helix rails.
    branches = (
        ((37, 81), (48, 63), (72, 68), (80, 86), (70, 103), (44, 101), (37, 81)),
        ((72, 68), (87, 44), (109, 51), (112, 75), (91, 74)),
        ((87, 44), (81, 32)),
        ((109, 51), (119, 36)),
        ((80, 86), (105, 92), (140, 94)),
        ((72, 211), (87, 200), (108, 211), (111, 232), (93, 244),
         (73, 233), (72, 211)),
        ((87, 200), (80, 188)),
        ((111, 232), (129, 239), (140, 229)),
        ((93, 244), (94, 257)),
        ((88, 104), (28, 104), (15, 113), (15, 173), (30, 187), (53, 190)),
        ((30, 116), (73, 116)),
        ((30, 176), (78, 176)),
        ((108, 211), (143, 200), (182, 200)),
        ((110, 89), (184, 89)),
        ((109, 51), (124, 45), (137, 54), (133, 70), (116, 71), (109, 51)),
        ((124, 45), (128, 28), (143, 23)),
        ((137, 54), (154, 52)),
        ((111, 232), (119, 216), (135, 212), (143, 227), (129, 239)),
        ((48, 69), (43, 82), (48, 95)),
        ((78, 230), (93, 238), (106, 229)),
    )
    for mirror in (False, True):
        for branch in branches:
            path([(1000 - x if mirror else x, y) for x, y in branch], 220)
        for x, y in ((48, 63), (72, 68), (87, 44), (81, 32), (112, 75),
                     (28, 104), (73, 233), (94, 257), (129, 239),
                     (124, 45), (143, 23), (154, 52), (135, 212)):
            node(1000 - x if mirror else x, y)
        for x, y in ((115, 31), (152, 67), (137, 193), (62, 217)):
            mx = 1000 - x if mirror else x
            path(((mx - 3, y), (mx + 3, y)), 180)
            path(((mx, y - 3), (mx, y + 3)), 180)
        for x in range(24, 164, 7):
            for y in (39, 57, 78, 211, 229, 249):
                if (x * 11 + y * 7) % 19 < 4:
                    point(1000 - x if mirror else x, y, 145)
    # Flask at left, sprouting leaves at right, as in the supplied composition.
    path(((46, 24), (59, 24), (57, 24), (57, 36), (70, 64),
          (36, 64), (48, 36), (48, 24)), 240)
    path(((43, 53), (63, 53)), 50)
    for x, y in ((51, 42), (56, 50), (47, 59), (60, 59)):
        point(x, y, 220)
    path(((950, 65), (950, 50)), 235)
    path(((950, 50), (937, 46), (930, 33), (929, 21),
          (942, 26), (948, 38), (950, 50)), 235)
    path(((950, 50), (952, 36), (964, 25), (974, 22),
          (971, 35), (962, 45), (950, 50)), 235)
    for direction in (-1, 1):
        for step in range(36):
            t = step / 35
            x, y = 950 + direction * 23 * t, 50 - 29 * t
            half_width = 6 * sin(pi * t)
            path(((x - half_width, y), (x + half_width, y)), 240, solid=True)
    path(((950, 50), (935, 29)), 145)
    path(((950, 50), (967, 28)), 145)
    for x, y in ((356, 55), (640, 55), (356, 239), (640, 239)):
        node(x, y, 4)
        path(((x + 6, y), (x + 58, y)), 115)
    for x in range(475, 532, 9):
        node(x, 80, 1.4)
        node(x, 219, 1.4)

    # Short measurement strokes stay open; no perimeter around the wordmark.
    for left, right in ((76, 465), (532, 927)):
        path(((left + 28, 87), (left + 102, 87)), 180)
        path(((right - 109, 208), (right - 22, 208)), 180)
        node(left + 28, 87, 2.5)
        node(right - 22, 208, 2.5)

    stops = [tuple(int(color[index:index + 2], 16) for index in (1, 3, 5))
             for color in _AGENTIC_GRADIENT]

    def color_at(column, brightness=1):
        position = (column / max(width - 1, 1) - .077) / .848
        progress = min(1, max(0, position)) * (len(stops) - 1)
        left = min(int(progress), len(stops) - 2)
        fraction = progress - left
        rgb = (max(0, min(255, round((a + (b - a) * fraction) * brightness)))
               for a, b in zip(stops[left], stops[left + 1]))
        return "#" + "".join(f"{channel:02X}" for channel in rgb)

    # Quadrant order: upper-left, upper-right, lower-left, lower-right.
    quadrants = " ▘▝▀▖▌▞▛▗▚▐▜▄▙▟█"
    dots = ((1, 8), (2, 16), (4, 32), (64, 128))
    logo = Text(no_wrap=True, overflow="crop")
    for row in range(art_rows):
        cells = []
        for column in range(width):
            title_row, title_column = row - title_top, column - title_left
            if 0 <= title_row < len(title_lines) and 0 <= title_column < len(title_lines[0]):
                char = title_lines[title_row][title_column]
                brightness = 1.06 - title_row * .025
                if char not in ("█", " "):
                    brightness *= .76
            else:
                px, py = column * 2, row * 4
                ribbon_mask = 0
                for q, (dx, dy) in enumerate(((0, 0), (1, 0), (0, 2), (1, 2))):
                    if ribbon[py + dy][px + dx] and ribbon[py + dy + 1][px + dx]:
                        ribbon_mask |= 1 << q
                if ribbon_mask:
                    char, brightness = quadrants[ribbon_mask], 1.03
                else:
                    bits, strength = 0, 0
                    for dy in range(4):
                        for dx in range(2):
                            value = ink[py + dy][px + dx]
                            if value:
                                bits |= dots[dy][dx]
                                strength = max(strength, value)
                    char = chr(0x2800 + bits) if bits else " "
                    brightness = .45 + strength / 255 * .5
            cells.append((char, brightness))
        # Styled trailing spaces also reflow in terminal scrollback.
        while cells and cells[-1][0] == " ":
            cells.pop()
        if row:
            logo.append("\n")
        for column, (char, brightness) in enumerate(cells):
            logo.append(char, Style(color=color_at(column, brightness), bgcolor="#000000"))

    subtitle = "AUTONOMOUS SCIENTIFIC AGENTS FOR LIFE SCIENCES"
    if len(subtitle) + 12 <= width:
        rule = "─" * min(7, (width - len(subtitle) - 8) // 2)
        subtitle = f"○{rule}  {subtitle}  {rule}○"
    if len(subtitle) <= width:
        logo.append("\n\n")
        for column, char in enumerate(subtitle.center(width).rstrip()):
            logo.append(char, Style(color=color_at(column), bgcolor="#000000"))
    return logo


# Braille preserves the reference's dotted silhouette within the original 30x15 hero slot.
SCI_B_LOGO = """[#FFE3ED]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢀⣠⣴⣿⣿⣦⣄⡀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣶⣤⡀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠀⠀⣀⣴⣾⡇⠀⠀⢸⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣷⣤⣀⠀⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⢰⣿⣿⣿⣿⡇⠀⠀⢸⣿⠿⠿⠿⠿⣿⣿⣿⣿⣿⣿⣿⣿⣷⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⢸⣿⣿⣿⣿⡇⠀⠀⠈⠀⠀⠀⠀⠀⠀⠉⠻⣿⣿⣿⣿⣿⣿⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⢸⣿⣿⣿⣿⡇⠀⠀⠀⢀⣠⣤⣤⣄⡀⠀⠀⠘⣿⣿⣿⣿⣿⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⢸⣿⣿⣿⣿⡇⠀⠀⢠⣿⣿⠿⣻⣿⣿⡀⠀⠀⢹⣿⣿⣿⣿⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⢸⣿⣿⣿⣿⣧⠀⠀⠘⣿⢳⠁⠀⠀⣿⠃⠀⠀⣼⣿⣿⣿⣿⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⢸⣿⣿⣿⣿⣿⣆⠀⠀⠈⠚⠂⠠⠂⠁⠀⠀⣰⣿⣿⣿⣿⣿⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠸⢿⣿⣿⣿⣿⣿⣷⣄⡀⠀⠀⠀⠀⢀⣠⣾⣿⣿⣿⣿⣿⡿⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠀⠀⠉⠻⢿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⣿⡿⠛⠁⠀⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠀⠀⠀⠀⠀⠉⠛⢿⣿⣿⣿⣿⣿⣿⣿⣿⠿⠛⠁⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠛⢿⣿⣿⠿⠋⠁⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]
[#FFE3ED]⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠈⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀⠀[/]"""

# === Skills scanning ===

# Per-process caches: ``None`` until computed, then a 1-tuple ``(value,)`` so a computed ``None``
# is distinguishable from "not yet computed". Reset by assigning ``None`` (tests, ``sci skills``).
_available_skills_cache: Optional[tuple] = None
_git_banner_state_cache: Optional[tuple] = None
_latest_release_cache: Optional[tuple] = None

_UNCACHED = object()  # compute() result that must not be memoized


def _memo(cache_name: str, compute):
    """Return the cached value under module global ``cache_name``, computing (and storing) it once.

    Not consulted under a routed profile (SCI_HOME override): every memo here is derived from the
    launch home (its skills tree, its checkout), and the TUI gateway calls these per profile."""
    from sci_constants import get_sci_home_override
    if get_sci_home_override() is not None:
        return compute()
    cached = globals()[cache_name]
    if cached is not None:
        return cached[0]
    value = compute()
    if value is not _UNCACHED:
        globals()[cache_name] = (value,)
    return value


def get_available_skills() -> Dict[str, List[str]]:
    """Return skills grouped by category, filtered by platform and disabled state.

    Cached per-process (the skills-tree walk costs ~100ms and feeds only the startup banner);
    ``prefetch_banner_data()`` pays it off-thread. A failed scan yields ``{}`` and is not cached.
    """
    def _scan():
        from tools.skills_tool import _find_all_skills
        return _find_all_skills()  # already filtered

    def _compute():
        all_skills = _quiet(_scan)
        if all_skills is None:
            return _UNCACHED
        skills_by_category: Dict[str, List[str]] = {}
        for skill in all_skills:
            skills_by_category.setdefault(skill.get("category") or "general", []).append(skill["name"])
        return skills_by_category
    result = _memo("_available_skills_cache", _compute)
    return {} if result is _UNCACHED else result


def _resolve_repo_dir() -> Optional[Path]:
    """The active Sci git checkout, or None if this isn't a git install.

    Prefers the running code's location: ``$SCI_HOME/sci-agent/`` may be a stale copy
    carried over by ``--clone-all``.
    """
    repo_dir = Path(__file__).parent.parent.resolve()
    if not (repo_dir / ".git").exists():
        repo_dir = get_sci_home() / "sci-agent"
    return repo_dir if (repo_dir / ".git").exists() else None


def get_git_banner_state(repo_dir: Optional[Path] = None) -> Optional[dict]:
    """Return upstream/local git hashes for the startup banner.

    Cached per-process (default ``repo_dir`` only): 2-3 git subprocesses (~100ms) whose result
    cannot change under a running CLI. The cache lets ``prefetch_banner_data()`` pay it off-thread.
    """
    if repo_dir is not None:
        return _compute_git_banner_state(repo_dir)
    return _memo("_git_banner_state_cache", _compute_git_banner_state)


def _baked_banner_state() -> Optional[dict]:
    """Banner state from the baked build SHA (Docker image path), or None."""
    def _baked():
        from sci_cli.version_info import get_code_identity
        return get_code_identity().get("short_sha")
    baked = _quiet(_baked)
    return {"upstream": baked, "local": baked, "ahead": 0} if baked else None


def _compute_git_banner_state(repo_dir: Optional[Path] = None) -> Optional[dict]:
    repo_dir = repo_dir or _resolve_repo_dir()
    if repo_dir is None:
        return _baked_banner_state()
    upstream, local = (source_check._git_stdout(["rev-parse", "--short=8", rev], cwd=repo_dir) for rev in ("origin/main", "HEAD"))
    if not upstream or not local:
        # Live-git lookup failed (e.g. shallow clone without origin/main).
        return _baked_banner_state()
    ahead = source_check._git_count(["rev-list", "--count", "origin/main..HEAD"], cwd=repo_dir) or 0
    return {"upstream": upstream, "local": local, "ahead": max(ahead, 0)}


_RELEASE_URL_BASE = ""


def get_latest_release_tag(repo_dir: Optional[Path] = None) -> Optional[tuple]:
    """Return ``(tag, release_url)`` for the latest local git tag, or None (a miss is cached too).

    An unpublished distribution has no release link, including for inherited Git tags.
    """
    def _compute():
        if not _RELEASE_URL_BASE:
            return None
        rd = repo_dir or _resolve_repo_dir()
        tag = source_check._git_stdout(["describe", "--tags", "--abbrev=0"], cwd=rd, timeout=3) if rd else None
        return (tag, f"{_RELEASE_URL_BASE}/{tag}") if tag else None
    return _memo("_latest_release_cache", _compute)


def format_banner_version_label() -> str:
    """Return the version label shown in the startup banner title."""
    from sci_cli.config import get_project_root
    from sci_cli.steward import read_install_stamp
    from sci_cli.update_channel import is_canary_tag

    stamp = read_install_stamp(get_project_root())
    if stamp.get("distribution") == "desktop-app":
        label = f"Sci Agent v{get_version_info().derived_version}"
        if stamp.get("source") == "commit-build":
            return f"{label} · commit-build · {str(stamp.get('commit') or '')[:12]}"
        if stamp.get("tag"):
            channel = "canary" if is_canary_tag(stamp["tag"]) else "stable"
            return f"{label} · {channel}"
        if stamp.get("payload") == "bootstrap":
            # The old installer shell's CLI backend: the shell never updates
            # itself (`self`), the managed checkout under it does. Name the
            # shell so it doesn't read as a plain packaged build.
            return f"{label} · installer"
        return label

    base = f"Sci Agent v{get_version_info().derived_version} ({RELEASE_DATE})"
    from sci_cli.config import load_config
    from sci_cli.update_channel import resolve_update_channel

    channel = resolve_update_channel(_quiet(load_config), get_project_root())
    if channel != "main":
        head = source_check._git_stdout(["rev-parse", "HEAD"], cwd=get_project_root())
        return f"{base} · {channel}" + (f" · local {head[:12]}" if head else "")
    state = get_git_banner_state()
    if not state:
        return base
    upstream, local = state["upstream"], state["local"]
    ahead = int(state.get("ahead") or 0)
    if ahead <= 0 or upstream == local:
        return f"{base} · upstream {upstream}"
    return f"{base} · upstream {upstream} · local {local} (+{ahead} carried {_plural(ahead, 'commit')})"


# === Non-blocking update check ===

_update_result: Optional[int] = None
_update_check_done = threading.Event()


def _daemon(name: Optional[str], target) -> None:
    """Start a daemon thread running ``target`` with any exception swallowed."""
    threading.Thread(target=lambda: _quiet(target), name=name, daemon=True).start()


def _skip_background_prefetch() -> bool:
    """True when the banner's background prefetch threads must not start.

    Under pytest the prefetch daemon threads shell out to git (``rev-parse``,
    ``remote get-url``, the banner's git state) at an arbitrary point after
    import, and any test that patches the process-wide ``subprocess`` singleton
    (``patch("subprocess.run")`` / ``patch("subprocess.Popen")``) can record
    that stray spawn in place of the call it meant to pin.  Importing
    ``tui_gateway.server`` starts this prefetch, which is what flaked
    tests/tui_gateway/test_bot_relay_methods.py.
    Nothing under pytest needs a live update check; tests that exercise the
    prefetch itself monkeypatch this predicate to False.

    ``PYTEST_CURRENT_TEST`` is only set while a test runs, not during
    collection-time imports, hence the ``sys.modules`` check as well.
    """
    return "PYTEST_CURRENT_TEST" in os.environ or "pytest" in sys.modules


def prefetch_update_check():
    """Kick off update check in a background daemon thread.

    No-op under pytest — see ``_skip_background_prefetch``.
    """
    if _skip_background_prefetch():
        _update_check_done.set()
        return

    def _run():
        global _update_result
        _update_result = source_check.check_for_updates(passive=True).get("behind")
        _update_check_done.set()
    _daemon(None, _run)


_banner_data_prefetch_started = False


def prefetch_banner_data():
    """Warm the banner's subprocess/I/O-heavy inputs in a daemon thread.

    Git state (~130ms) and the skills index (~110ms) are cached per-process by their own modules,
    so warming them while the main thread pays the CPU-bound imports overlaps GIL-releasing I/O
    with import work. Idempotent; failures don't matter because the banner recomputes anything missing.
    """
    global _banner_data_prefetch_started
    if _banner_data_prefetch_started:
        return
    if _skip_background_prefetch():
        # Same stray-git-spawn cross-talk class as prefetch_update_check:
        # get_git_banner_state() shells out via the shared subprocess
        # singleton from a daemon thread, poisoning process-wide subprocess
        # mocks in unrelated tests.
        _banner_data_prefetch_started = True
        return
    _banner_data_prefetch_started = True
    _daemon("banner-data-prefetch", lambda: [_quiet(warm) for warm in (
        get_git_banner_state, get_latest_release_tag, get_available_skills)])


def get_update_result(timeout: float = 0.5) -> Optional[int]:
    """Get result of prefetched check. Returns None if not ready."""
    _update_check_done.wait(timeout=timeout)
    return _update_result


def _format_update_notice(behind: int) -> str:
    """Render the update warning line for a non-zero ``behind`` result."""
    from sci_cli.config import recommended_update_command
    if behind > 0:
        return (
            f"[bold yellow]⚠ {behind} {_plural(behind, 'commit')} behind[/]"
            f"[dim yellow] — run [bold]{recommended_update_command()}[/bold] to update[/]")
    # Shallow/source checkouts can lack the count too; still show their actual
    # update action rather than making a generic notice a dead end.
    command = recommended_update_command()
    suffix = f"[dim yellow] — run [bold]{command}[/bold][/]" if command else ""
    return f"[bold yellow]⚠ update available[/]{suffix}"


_deferred_update_notice_started = False


def _render_markup_to_ansi(markup: str) -> str:
    """Rich markup → ANSI string, for output that must go through prompt_toolkit's renderer.

    Under ``patch_stdout`` (the interactive CLI), a plain ``Console.print`` writes ESC bytes into
    the StdoutProxy, which sanitizes them into visible ``?[1;33m…`` artifacts (#83969).
    """
    from io import StringIO
    from rich.console import Console as _Console
    buf = StringIO()
    _Console(file=buf, force_terminal=True, color_system="truecolor", highlight=False).print(markup)
    return buf.getvalue().rstrip("\n")


def _defer_update_notice(max_wait: float = 30.0) -> None:
    """Print the update warning once the prefetched check completes (at most once per process).

    Used when the banner rendered before the update prefetch finished so startup never blocks on
    git/network. The notice lands after prompt_toolkit owns the terminal, so it is routed through
    ``cprint`` (prompt_toolkit's renderer prints above a running application from any thread).
    """
    global _deferred_update_notice_started
    if _deferred_update_notice_started:
        return
    _deferred_update_notice_started = True

    def _wait_and_print() -> None:
        if _update_check_done.wait(timeout=max_wait) and _update_result:
            cprint(_render_markup_to_ansi(_format_update_notice(_update_result)))
    _daemon("update-notice", _wait_and_print)  # never break the session over an update notice


# === Welcome banner ===

def _plural(n: int, word: str) -> str:
    return word if n == 1 else f"{word}s"


def _format_context_length(tokens: int) -> str:
    """Format a token count for display (e.g. 128000 → '128K', 1048576 → '1M')."""
    for unit, div in (("M", 1_000_000), ("K", 1_000)):
        if tokens >= div:
            val = tokens / div
            rounded = round(val)
            return f"{rounded}{unit}" if abs(val - rounded) < 0.05 else f"{val:.1f}{unit}"
    return str(tokens)


def _display_toolset_name(toolset_name: str) -> str:
    """Normalize internal/legacy toolset identifiers for banner display."""
    return toolset_name.removesuffix("_tools") if toolset_name else "unknown"


def _short_label(name: str) -> str:
    """Truncate a model/preset slug to fit the banner's left column."""
    return name[:25] + "..." if len(name) > 28 else name


# === Banner snapshot — warm-launch fast path ===
# The tool panel needs the full tool registry (~0.5-0.9s cold, the largest chunk of time-to-
# banner). The list is a pure function of (config.yaml, .env, code checkout, enabled toolsets),
# so the rendered inputs are snapshotted to disk and replayed when the fingerprint matches. The
# agent's REAL tool list is still computed fresh at first message; the snapshot only feeds the
# cosmetic panel, and a background refresh (cli.show_banner) re-verifies it right after render.

_BANNER_SNAPSHOT_VERSION = 1


def _banner_snapshot_path() -> Path:
    return get_sci_home() / "cache" / "banner_snapshot.json"


def banner_snapshot_fingerprint() -> Optional[str]:
    """Fingerprint the inputs the banner tool panel depends on."""
    import hashlib
    def _inputs():
        from sci_cli.config import get_config_path
        return (get_config_path(), get_sci_home() / ".env")
    paths = _quiet(_inputs)
    if paths is None:
        return None
    parts = [f"v{_BANNER_SNAPSHOT_VERSION}"]
    for p in paths:
        st = _quiet(p.stat)
        parts.append(f"{p.name}:{st.st_mtime_ns}:{st.st_size}" if st else f"{p.name}:absent")
    # Code checkout: commit when known, otherwise its derived version.
    version_info = get_version_info()
    parts.append(version_info.commit or version_info.derived_version)
    state = get_git_banner_state()
    if state:
        parts.append(str(state.get("local", "")))
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def load_banner_snapshot(enabled_toolsets: List[str] = None) -> Optional[Dict[str, Any]]:
    """Return the stored banner snapshot when its fingerprint is current."""
    blob = _quiet(lambda: json.loads(_banner_snapshot_path().read_text(encoding="utf-8-sig")))
    if not isinstance(blob, dict):
        return None
    fp = banner_snapshot_fingerprint()
    if (not fp or blob.get("fingerprint") != fp
            or blob.get("enabled_toolsets") != sorted(enabled_toolsets or [])
            or not isinstance(blob.get("tools"), list)
            or not all(isinstance(blob.get(k), dict)
                       for k in ("toolset_map", "availability", "skills_by_category"))):
        return None
    return blob


def save_banner_snapshot(tools: List[dict], enabled_toolsets: List[str], availability: Dict[str, Any],
                         toolset_map: Dict[str, str]) -> None:
    """Persist the banner tool panel inputs for next launch (best-effort)."""
    fp = banner_snapshot_fingerprint()
    if not fp:
        return
    payload = {
        "fingerprint": fp,
        "enabled_toolsets": sorted(enabled_toolsets or []),
        "tools": [{"function": {"name": t["function"]["name"]}}
                  for t in tools if isinstance(t, dict) and t.get("function", {}).get("name")],
        "toolset_map": toolset_map,
        "availability": {
            "unavailable_toolsets": availability.get("unavailable_toolsets", []),
            **{k: list(availability.get(k, [])) for k in ("lazy_tools", "disabled_tools")}},
        "skills_by_category": get_available_skills(),
    }

    def _write():
        from utils import atomic_json_write
        atomic_json_write(_banner_snapshot_path(), payload, indent=None, mode=0o600)
    _quiet(_write)


def compute_toolset_availability(enabled_toolsets: List[str] = None) -> Dict[str, Any]:
    """Compute ``{"unavailable_toolsets", "lazy_tools", "disabled_tools"}`` for the banner.

    Split out so the result can be snapshotted and replayed without importing ``model_tools``.
    """
    from model_tools import check_tool_availability, TOOLSET_REQUIREMENTS
    enabled_toolsets = enabled_toolsets or []
    _, unavailable_toolsets = check_tool_availability(quiet=True)
    # The availability check walks the GLOBAL registry, so it includes toolsets outside this
    # agent's platform set (e.g. `discord` on a CLI session) which must never surface in
    # "Available Tools". Restrict to enabled toolsets; an enabled toolset with unmet deps
    # legitimately shows as disabled/lazy below.
    _enabled_ts = {str(t) for t in enabled_toolsets}
    if _enabled_ts:
        unavailable_toolsets = [
            item for item in unavailable_toolsets if str(item.get("id", item.get("name", ""))) in _enabled_ts]
    # Toolsets with a check_fn are lazy-initialized (e.g. honcho): unavailable at banner time
    # because the check hasn't run yet, but not misconfigured.
    lazy_tools, disabled_tools = set(), set()
    for item in unavailable_toolsets:
        is_lazy = TOOLSET_REQUIREMENTS.get(item.get("name", ""), {}).get("check_fn")
        (lazy_tools if is_lazy else disabled_tools).update(item.get("tools", []))
    return {"unavailable_toolsets": unavailable_toolsets, "lazy_tools": sorted(lazy_tools),
            "disabled_tools": sorted(disabled_tools)}


def _mcp_server_line(srv: dict, *, dim: str, text: str) -> str:
    """One banner line for an MCP server status entry."""
    name, transport = srv["name"], srv["transport"]
    if srv["connected"]:
        return f"[dim {dim}]{name}[/] [{text}]({transport})[/] [dim {dim}]—[/] [{text}]{srv['tools']} tool(s)[/]"
    # Needs srv['tools'], so it cannot live in the suffix dict below. A registered but unspawned
    # server has callable tools; falling through to the red "failed" line misreports a working setup.
    if srv.get("status") == "lazy":
        return (f"[dim {dim}]{name}[/] [{text}]({transport})[/] [dim {dim}]—[/] "
                f"[{text}]{srv['tools']} tool(s)[/] [dim {dim}](lazy, starts on first use)[/]")
    status = "disabled" if srv.get("disabled") else srv.get("status")
    suffix = {"disabled": f"[dim {dim}]— disabled[/]", "connecting": "[yellow]— connecting[/]",
              "configured": f"[dim {dim}]— configured[/]"}.get(status)
    if suffix is not None:
        return f"[dim {dim}]{name}[/] [dim]({transport})[/] {suffix}"
    return _mcp_failed_line(name, transport, srv.get("error"))


def _mcp_failed_line(name: str, transport: str, error: Optional[str]) -> str:
    """Failed MCP connect: the short reason (already humanised by ``_format_connect_error``) and the
    exact next command, so 'failed' is never the whole story."""
    from rich.markup import escape
    reason = escape(" ".join(str(error or "").split())[:120]) or "no details recorded"
    next_cmd = (f"sci mcp login {name}" if re.search(r"\b401\b|unauthori[sz]ed", reason, re.I)
                else f"sci mcp test {name}")
    return (f"[red]{name}[/] [dim]({transport})[/] [red]— could not connect:[/] {reason} "
            f"[dim]— run `{next_cmd}`[/]")


def _truncate_tool_names(tool_names: List[str]) -> List[Optional[str]]:
    """Cut a toolset's tool list to ~42 columns; ``None`` marks the elided tail."""
    if len(", ".join(tool_names)) <= 45:
        return list(tool_names)
    short_names: List[Optional[str]] = []
    length = 0
    for name in tool_names:
        if length + len(name) + 2 > 42:
            short_names.append(None)
            break
        short_names.append(name)
        length += len(name) + 2
    return short_names


def _pack_skill_names(skill_names: List[str], avail: int) -> str:
    """Join skill names into ``avail`` columns, ending with ``+N more`` when they don't all fit."""
    parts: List[str] = []
    length = 0
    for i, name in enumerate(skill_names):
        needed = (2 if parts else 0) + len(name)
        after = len(skill_names) - (i + 1)  # indicator size IF we add this skill then stop
        ind_len = len(f", +{after} more") if after > 0 else 0
        if parts and length + needed + ind_len > avail:
            parts.append(f"+{len(skill_names) - len(parts)} more")
            break
        parts.append(name)
        length += needed
    return ", ".join(parts)


def _moa_aggregator_label(preset_name: str) -> str:
    """Short aggregator-model label for a MoA preset ("" when the preset has none)."""
    from sci_cli.config import load_config
    from sci_cli.moa_config import normalize_moa_config
    preset = normalize_moa_config(load_config().get("moa") or {}).get("presets", {}).get(preset_name)
    model = str(((preset or {}).get("aggregator") or {}).get("model") or "")
    return model.split("/")[-1]


def _mcp_configured() -> bool:
    """Cheap probe: does config.yaml or the persisted plugin key cache name any MCP server?

    The full ``get_mcp_status()`` path resolves portable plugin MCP servers, which JOINS the in-flight
    background plugin discovery (~100ms on the startup path), so skip it when nothing is configured.
    When either probe can't tell, take the full path.
    """
    def _native():
        from sci_cli.config import load_config
        return bool((load_config() or {}).get("mcp_servers"))

    def _portable():
        from sci_cli.plugins import get_portable_mcp_server_names_nowait
        return bool(get_portable_mcp_server_names_nowait())
    return _quiet(_native, True) or _quiet(_portable, True)


def _probe_mcp_status() -> list:
    from tools.mcp_tool_discovery import get_mcp_status
    return get_mcp_status()


def _codex_runtime_active() -> bool:
    """True when the codex_app_server runtime is active (tool counts then live inside codex)."""
    from sci_cli.codex_runtime_switch import get_current_runtime
    from sci_cli.config import load_config
    return get_current_runtime(load_config()) == "codex_app_server"


def _active_profile_name() -> Optional[str]:
    from sci_cli.profiles import get_active_profile_name
    return get_active_profile_name()


def _route_model_for_banner(provider: Any) -> str:
    """The model the resolved route will actually serve when config names none: today only the Nous
    free tier (welcome host -> ``nous/welcome``). Read from the boot record and local auth state;
    no network. Empty when nothing resolves, so the caller keeps its "no model configured" line."""
    if (provider or "auto").strip().lower() not in ("auto", "nous"):
        return ""
    from sci_cli.anon_auth import GUEST_MODEL, free_tier_route
    return GUEST_MODEL if free_tier_route() else ""


def _banner_left_lines(model: str, cwd: str, session_id, context_length, provider, *, accent: str, dim: str,
                       context_pinned: bool = False) -> list:
    """Model / cwd / session lines under the hero art. ``context_pinned`` marks a
    ``model.context_length`` pin so the user can tell it apart from provider metadata (#66168)."""
    def _dim_sep(label: str) -> str:
        return f" [dim {dim}]·[/] [dim {dim}]{label}[/]"
    lines = []
    pin = " (pinned)" if context_pinned else ""
    ctx_str = _dim_sep(f"{_format_context_length(context_length)} context{pin}") if context_length else ""
    nous_str = _dim_sep("Boltzmann Labs")
    if not (model or "").strip():
        # Credentials resolve lazily on the first message; the banner prints first. Ask the route
        # the same question so a fresh free-tier install shows its model, not a red "unconfigured".
        model = _quiet(lambda: _route_model_for_banner(provider), "") or model
    if (provider or "").strip().lower() == "moa":
        # MoA virtual provider: ``model`` is a preset name; show it with its aggregator.
        agg_label = _quiet(lambda: _moa_aggregator_label(model), "")
        agg_str = _dim_sep(f"agg {agg_label}") if agg_label else ""
        lines.append(f"[{accent}]MoA: {_short_label(model)}[/]{agg_str}{ctx_str}{nous_str}")
    elif not (model or "").strip() or (model or "").strip().lower() == "unknown":
        # Unconfigured install: the clearest place to say what is wrong and how to fix it.
        lines.append(f"[bold red]no model configured[/] [dim {dim}]— run /model or sci setup[/]")
    else:
        model_short = model.split("/")[-1].removesuffix(".gguf")
        lines.append(f"[{accent}]{_short_label(model_short)}[/]{ctx_str}{nous_str}")
    if os.getenv("SCI_YOLO_MODE"):
        lines.append(f"[bold red]⚠ YOLO mode[/] [dim {dim}]— all approval prompts bypassed[/]")
    lines.append(f"[dim {dim}]{cwd}[/]")
    if session_id:
        lines.append(f"[dim {_skin_color('session_border', '#8B8682')}]Session: {session_id}[/]")
    return lines


def _banner_tool_lines(
    tools: list, unavailable_toolsets: list, get_toolset_for_tool, *,
    lazy_tools: set, disabled_tools: set, accent: str, dim: str, text: str) -> list:
    """"Available Tools" section: up to 8 toolsets, each truncated to ~42 columns."""
    lines = [f"[bold {accent}]Available Tools[/]"]
    toolsets_dict: Dict[str, list] = {}
    for tool in tools:
        tool_name = tool["function"]["name"]
        toolset = _display_toolset_name(get_toolset_for_tool(tool_name) or "other")
        toolsets_dict.setdefault(toolset, []).append(tool_name)
    for item in unavailable_toolsets:
        names = toolsets_dict.setdefault(_display_toolset_name(item.get("id", item.get("name", "unknown"))), [])
        for tool_name in item.get("tools", []):
            if tool_name not in names:
                names.append(tool_name)

    def _color_tool(name: Optional[str]) -> str:
        if name is None:  # truncation marker
            return "[dim]...[/]"
        color = "red" if name in disabled_tools else "yellow" if name in lazy_tools else text
        return f"[{color}]{name}[/]"
    sorted_toolsets = sorted(toolsets_dict.keys())
    for toolset in sorted_toolsets[:8]:
        tool_names = _truncate_tool_names(sorted(toolsets_dict[toolset]))
        lines.append(f"[dim {dim}]{toolset}:[/] {', '.join(_color_tool(n) for n in tool_names)}")
    if len(sorted_toolsets) > 8:
        lines.append(f"[dim {dim}](and {len(sorted_toolsets) - 8} more toolsets...)[/]")
    return lines


def _banner_skill_lines(skills_by_category: Dict[str, List[str]], skills_enabled: bool, *, dim: str, text: str) -> list:
    """"Available Skills" body, sized to ~60% of the terminal width (the right grid column)."""
    if not skills_enabled:
        return [f"[dim {dim}]Skills toolset disabled[/]"]
    if not skills_by_category:
        return [f"[dim {dim}]No skills installed[/]"]
    right_col_width = max(int(shutil.get_terminal_size().columns * 0.6) - 10, 30)
    lines = []
    for category in sorted(skills_by_category.keys()):
        # Account for the "category: " prefix.
        skills_str = _pack_skill_names(sorted(skills_by_category[category]), max(right_col_width - len(category) - 2, 20))
        lines.append(f"[dim {dim}]{category}:[/] [{text}]{skills_str}[/]")
    return lines


def build_welcome_banner(
    console: "Console", model: str, cwd: str, tools: List[dict] = None, enabled_toolsets: List[str] = None,
    session_id: str = None, get_toolset_for_tool=None, context_length: int = None, provider: str = None,
    availability: Dict[str, Any] = None, skills_by_category: Dict[str, List[str]] = None,
    context_pinned: bool = False, welcome_handler=None,
):
    """Build and print a welcome banner with caduceus on left and info on right.

    When ``provider == "moa"``, ``model`` is a MoA preset name and the aggregator is rendered.
    Passing a precomputed ``availability`` together with ``get_toolset_for_tool`` avoids any
    ``model_tools`` import (banner snapshot replay).
    """
    from rich.panel import Panel
    from rich.table import Table
    if get_toolset_for_tool is None:
        from model_tools import get_toolset_for_tool
    tools = tools or []
    enabled_toolsets = enabled_toolsets or []
    if availability is None:
        availability = compute_toolset_availability(enabled_toolsets)
    _enabled_ts = {str(t) for t in enabled_toolsets}
    # Resolve skin colors once for the entire banner
    accent = _skin_color("banner_accent", "#FF356F")
    dim = _skin_color("banner_dim", "#AF426B")
    text = _skin_color("banner_text", "#FFE3ED")
    # Use skin's custom caduceus art if provided
    _bskin = _quiet(_active_skin)
    from sci_cli.skin_defaults import DEFAULT_SKIN_NAME
    if (getattr(_bskin, "name", None) == DEFAULT_SKIN_NAME
            and not (_bskin.banner_logo or _bskin.banner_hero)):
        from sci_cli.banner_science import science_welcome_panel

        skills_enabled = not _enabled_ts or "skills" in _enabled_ts
        skills = (skills_by_category if skills_by_category is not None else get_available_skills()) if skills_enabled else {}
        display_model = model or _quiet(lambda: _route_model_for_banner(provider), "")
        if console.width >= 95:
            console.print(_agentic_sciences_logo(console.width))
            console.print()
        welcome_params = dict(
            skin=_bskin, profile=_quiet(_active_profile_name), model=display_model,
            provider=provider, cwd=cwd, tool_count=len(tools),
            skill_count=sum(len(names) for names in skills.values()),
            context_length=context_length, context_pinned=context_pinned,
            yolo=bool(os.getenv("SCI_YOLO_MODE")),
            width=console.width,
        )
        if welcome_handler is None or not welcome_handler(console, welcome_params):
            console.print(science_welcome_panel(**welcome_params))
        behind = _quiet(lambda: get_update_result(timeout=0.05))
        if behind:
            console.print(_format_update_notice(behind))
        elif behind is None and not _update_check_done.is_set():
            _defer_update_notice()
        return
    left_lines = ["", getattr(_bskin, "banner_hero", None) or SCI_B_LOGO, ""]
    left_lines += _banner_left_lines(model, cwd, session_id, context_length, provider, accent=accent, dim=dim,
                                     context_pinned=context_pinned)
    right_lines = _banner_tool_lines(
        tools, availability.get("unavailable_toolsets", []), get_toolset_for_tool,
        lazy_tools=set(availability.get("lazy_tools", [])), disabled_tools=set(availability.get("disabled_tools", [])),
        accent=accent, dim=dim, text=text)
    # MCP Servers section (only if configured) — see ``_mcp_configured`` for why the cheap probe.
    mcp_status = _quiet(_probe_mcp_status, []) if _mcp_configured() else []
    if mcp_status:
        right_lines += ["", f"[bold {accent}]MCP Servers[/]"]
        right_lines.extend(_mcp_server_line(srv, dim=dim, text=text) for srv in mcp_status)
    right_lines += ["", f"[bold {accent}]Available Skills[/]"]
    # The skills catalog is only reachable when the `skills` toolset is enabled (skill_view /
    # skill_manage). When disabled (Blank Slate) the agent cannot load any skill, so advertising
    # the on-disk catalog would be misleading — reflect the real state.
    _skills_enabled = (not _enabled_ts) or ("skills" in _enabled_ts)
    if not _skills_enabled:
        skills_by_category = {}
    elif skills_by_category is None:
        skills_by_category = get_available_skills()
    total_skills = sum(len(s) for s in skills_by_category.values())
    right_lines += _banner_skill_lines(skills_by_category, _skills_enabled, dim=dim, text=text)
    right_lines.append("")
    mcp_connected = sum(1 for s in mcp_status if s["connected"])
    summary_parts = [f"{len(tools)} tools", f"{total_skills} skills"]
    if mcp_connected:
        summary_parts.append(f"{mcp_connected} MCP servers")
    summary_parts.append("/help for commands")
    # Flag the codex_app_server runtime so users understand why tool counts may not match what's
    # reachable (codex builds its own tool list inside the spawned subprocess).
    if _quiet(_codex_runtime_active, False):
        right_lines.append(f"[bold {accent}]Runtime:[/] [{text}]codex app-server[/] "
                           f"[dim {dim}](terminal/file ops/MCP run inside codex)[/]")
    # Show active profile name when not 'default'. Never break the banner over a profiles.py bug.
    _profile_name = _quiet(_active_profile_name)
    if _profile_name and _profile_name != "default":
        right_lines.append(f"[bold {accent}]Profile:[/] [{text}]{_profile_name}[/]")
    right_lines.append(f"[dim {dim}]{' · '.join(summary_parts)}[/]")
    # Update check — NEVER block the banner on it: the prefetch does git/network work that rarely
    # finishes before render, so a blocking wait adds its full timeout to every startup. If not
    # ready, a daemon thread prints the same notice above the prompt when it lands.
    def _update_line():
        behind = get_update_result(timeout=0.05)
        if behind is None and not _update_check_done.is_set():
            _defer_update_notice()
        elif behind is not None and behind != 0:
            right_lines.append(_format_update_notice(behind))
    _quiet(_update_line)  # Never break the banner over an update check
    layout_table = Table.grid(padding=(0, 2))
    layout_table.add_column("left", justify="left")
    layout_table.add_column("right", justify="left")
    layout_table.add_row("\n".join(left_lines), "\n".join(right_lines))
    version_label = format_banner_version_label()
    release_info = get_latest_release_tag()
    if release_info:
        version_label = f"[link={release_info[1]}]{version_label}[/link]"
    surface = _skin_color("terminal_elevated", "")
    outer_panel = Panel(
        layout_table, title=f"[bold {_skin_color('banner_title', '#FF7AA7')}]{version_label}[/]",
        border_style=_skin_color("banner_border", "#8D123B"), padding=(1, 2),
        style=f"on {surface}" if surface else "")
    console.print()
    banner_width = min(console.width, shutil.get_terminal_size().columns)
    if banner_width >= 95:
        title_logo = getattr(_bskin, "banner_logo", None)
        if not title_logo:
            from rich.padding import Padding

            # Paint blank rows and unused columns too, so the terminal's default
            # background cannot show through as bands around the artwork.
            title_logo = Padding(_agentic_sciences_logo(banner_width), 0, style="on #000000")
        console.print(title_logo, width=banner_width)
        console.print()
    console.print(outer_panel)
