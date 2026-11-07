"""Native CLI appearance is fixed to the dark palette."""

from __future__ import annotations


def test_native_cli_ignores_legacy_light_settings_and_terminal_hints(monkeypatch, tmp_path):
    import cli
    from sci_cli.config import atomic_config_replace
    from sci_constants import get_sci_home

    monkeypatch.setenv("SCI_HOME", str(tmp_path / ".sci"))
    atomic_config_replace(get_sci_home() / "config.yaml", {"display": {"color_mode": "light"}})
    for key, value in {
        "SCI_LIGHT": "1",
        "SCI_TUI_LIGHT": "1",
        "SCI_TUI_THEME": "light",
        "SCI_TUI_BACKGROUND": "#ffffff",
        "COLORFGBG": "0;15",
        "TERM_PROGRAM": "Apple_Terminal",
    }.items():
        monkeypatch.setenv(key, value)

    assert cli._detect_light_mode() is False
    assert cli._maybe_remap_for_light_mode("#FFF8DC") == "#FFF8DC"


def test_native_skin_reads_ignore_light_palette(monkeypatch):
    from sci_cli.skin_engine import SkinConfig

    skin = SkinConfig(
        "fixture",
        colors={"banner_title": "#FF7AA7"},
        light_colors={"banner_title": "#000000"},
    )
    monkeypatch.setenv("SCI_LIGHT", "1")
    monkeypatch.setenv("SCI_TUI_THEME", "light")

    assert skin.get_color("banner_title") == "#FF7AA7"
