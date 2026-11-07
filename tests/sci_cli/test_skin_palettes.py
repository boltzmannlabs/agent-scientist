"""Built-in skin palette audit: completeness + WCAG contrast, per polarity.

Every built-in skin must be a complete, coherent palette with no accidental
fallbacks (a partial skin inherits the default palette, which is how
"slate feels all over the place" happened), and every palette must be a
hand-tuned foreground values passing the palette-audit floors (strong >= 3.9,
soft >= 2.8), with quieter frames and metadata >= 2.0. The TUI may additionally
lift these quiet roles for the actual host background. Mirrors the desktop
app's paired colors/darkColors contract.
"""

import pytest

from sci_cli.skin_engine import _BUILTIN_SKINS
from sci_cli.skin_defaults import SURFACE_COLOR_KEYS

# Union of the color keys consumed by the TUI (fromSkin) and the classic CLI
# (banner.py / display.py / prompt_toolkit overrides). completion_menu_meta_*
# intentionally excluded: they default to the base menu keys.
REQUIRED_KEYS = frozenset(
    {
        "banner_border",
        "banner_title",
        "banner_accent",
        "banner_dim",
        "banner_text",
        "ui_accent",
        "ui_label",
        "ui_ok",
        "ui_error",
        "ui_warn",
        "prompt",
        "input_rule",
        "response_border",
        "status_bar_bg",
        "status_bar_text",
        "status_bar_strong",
        "status_bar_dim",
        "status_bar_good",
        "status_bar_warn",
        "status_bar_bad",
        "status_bar_critical",
        "session_label",
        "session_border",
        "completion_menu_bg",
        "completion_menu_current_bg",
        "selection_bg",
        "shell_dollar",
        "voice_status_bg",
    }
)

# Foreground roles and their minimum contrast against the palette's pole.
# Matches ui-tui/src/theme.ts STRONG/SOFT tiers.
STRONG_FG = (
    "banner_title",
    "banner_accent",
    "banner_text",
    "ui_accent",
    "ui_label",
    "ui_ok",
    "ui_error",
    "prompt",
    "status_bar_strong",
    "status_bar_good",
    "status_bar_bad",
    "status_bar_critical",
    "shell_dollar",
)
SOFT_FG = (
    "banner_dim",
    "ui_warn",
    "input_rule",
    "response_border",
    "status_bar_dim",
    "status_bar_warn",
    "session_label",
)
# Frames and secondary session metadata intentionally sit below body-text contrast.
# Preserve the approved local palette rather than brighten its quiet outlines.
QUIET_FG = ("banner_border", "session_border")
# status_bar_text renders on status_bar_bg, not the terminal background.
ON_STATUS_BAR = ("status_bar_text", "status_bar_strong", "status_bar_dim")

FILLS = (
    "status_bar_bg",
    "completion_menu_bg",
    "completion_menu_current_bg",
    "selection_bg",
    "voice_status_bg",
)

STRONG_MIN = 3.9
SOFT_MIN = 2.8
QUIET_MIN = 2.0
# Assumed terminal poles, matching ui-tui/src/theme.ts referenceBackground().
DARK_POLE = "#101014"
LIGHT_POLE = "#ffffff"


def _rgb(hex_color: str):
    h = hex_color.lstrip("#")
    assert len(h) == 6, f"not a 6-digit hex: {hex_color!r}"
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _channel(v: float) -> float:
    c = v / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_color: str) -> float:
    r, g, b = _rgb(hex_color)
    return 0.2126 * _channel(r) + 0.7152 * _channel(g) + 0.0722 * _channel(b)


def contrast(a: str, b: str) -> float:
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# Native CLI/TUI rendering has one dark palette. Shared light overlays may
# remain in skin assets for non-terminal clients, but are never selected here.
LIGHT_AUTHORED = frozenset()


# A `light_colors`/`dark_colors` block is an OVERLAY on `colors`, not a full
# replacement — a skin may ship a fills-only light overlay (flip the dark navy
# menu/status fills to light) while its vivid foregrounds keep coming from
# `colors` and render raw. So only the base `colors` block is held to the
# completeness + full foreground-contrast contract; overlays are audited for
# valid keys and fill polarity only.
def _base_palettes():
    """Yield (skin, palette, is_light) for every built-in's base `colors`."""
    for name, skin in _BUILTIN_SKINS.items():
        yield name, skin.get("colors", {}), name in LIGHT_AUTHORED


def _overlays():
    """Yield (skin, block, palette, is_light) for every partial overlay block."""
    for name, skin in _BUILTIN_SKINS.items():
        if skin.get("light_colors"):
            yield name, "light_colors", skin["light_colors"], True
        if skin.get("dark_colors"):
            yield name, "dark_colors", skin["dark_colors"], False


BASE_PALETTES = list(_base_palettes())
BASE_IDS = [f"{skin}:colors" for skin, _, _ in BASE_PALETTES]
OVERLAYS = list(_overlays())
OVERLAY_IDS = [f"{skin}:{block}" for skin, block, _, _ in OVERLAYS]


@pytest.mark.parametrize(("skin", "palette", "is_light"), BASE_PALETTES, ids=BASE_IDS)
def test_base_palette_is_complete(skin, palette, is_light):
    missing = REQUIRED_KEYS - palette.keys()
    assert not missing, f"{skin}.colors missing keys: {sorted(missing)}"


@pytest.mark.parametrize(("skin", "palette", "is_light"), BASE_PALETTES, ids=BASE_IDS)
def test_base_palette_contrast_and_polarity(skin, palette, is_light):
    pole = LIGHT_POLE if is_light else DARK_POLE
    problems = []

    # Light-authored bases render on a light pole where the classic look is the
    # vivid palette rendered RAW (transparent terminals apply no lift), so the
    # firm STRONG/SOFT floors only apply to dark-authored bases on a dark pole.
    if not is_light:
        for key in STRONG_FG:
            ratio = contrast(palette[key], pole)
            if ratio < STRONG_MIN:
                problems.append(f"{key}={palette[key]} contrast {ratio:.2f} < {STRONG_MIN} vs {pole}")

        for key in SOFT_FG:
            ratio = contrast(palette[key], pole)
            if ratio < SOFT_MIN:
                problems.append(f"{key}={palette[key]} contrast {ratio:.2f} < {SOFT_MIN} vs {pole}")

        for key in QUIET_FG:
            ratio = contrast(palette[key], pole)
            if ratio < QUIET_MIN:
                problems.append(f"{key}={palette[key]} contrast {ratio:.2f} < {QUIET_MIN} vs {pole}")

    status_bg = palette["status_bar_bg"]
    for key in ON_STATUS_BAR:
        floor = STRONG_MIN if key == "status_bar_strong" else SOFT_MIN
        ratio = contrast(palette[key], status_bg)
        if ratio < floor:
            problems.append(f"{key}={palette[key]} contrast {ratio:.2f} < {floor} vs status_bar_bg {status_bg}")

    _check_fills(palette, is_light, FILLS, problems)
    _check_chip(palette, problems)

    assert not problems, f"{skin}.colors:\n  " + "\n  ".join(problems)


@pytest.mark.parametrize(("skin", "block", "palette", "is_light"), OVERLAYS, ids=OVERLAY_IDS)
def test_overlay_keys_and_fill_polarity(skin, block, palette, is_light):
    unknown = palette.keys() - (REQUIRED_KEYS | SURFACE_COLOR_KEYS | {"completion_menu_meta_bg", "completion_menu_meta_current_bg"})
    assert not unknown, f"{skin}.{block} has unknown keys: {sorted(unknown)}"

    problems = []
    _check_fills(palette, is_light, [k for k in FILLS if k in palette], problems)
    if "completion_menu_current_bg" in palette and "completion_menu_bg" in palette:
        _check_chip(palette, problems)

    assert not problems, f"{skin}.{block}:\n  " + "\n  ".join(problems)


def _check_fills(palette, is_light, keys, problems):
    for key in keys:
        lum = luminance(palette[key])
        if is_light and lum < 0.4:
            problems.append(f"{key}={palette[key]} is a dark fill (lum {lum:.2f}) in a light palette")
        if not is_light and lum > 0.35:
            problems.append(f"{key}={palette[key]} is a light fill (lum {lum:.2f}) in a dark palette")


def _check_chip(palette, problems):
    # The selection chip must remain distinguishable from the menu surface.
    chip = contrast(palette["completion_menu_current_bg"], palette["completion_menu_bg"])
    if chip < 1.15:
        problems.append(
            f"completion_menu_current_bg={palette['completion_menu_current_bg']} "
            f"indistinguishable from completion_menu_bg (contrast {chip:.2f})"
        )
