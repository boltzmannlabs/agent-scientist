"""Release theme defaults work without copying the developer's private SCI home."""

from pathlib import Path

import pytest

import sci_yaml as yaml
from sci_constants import reset_sci_home_override, set_sci_home_override
from sci_cli import skin_engine
from sci_cli.cli_config_load import _cli_config_defaults
from sci_cli.config import load_config_readonly, seed_config_file
from sci_cli.config_defaults import DEFAULT_CONFIG


@pytest.fixture
def released_palette():
    source = Path(__file__).resolve().parents[2] / "assets/skins/neon-theme.yaml"
    return yaml.safe_load(source.read_text(encoding="utf-8"))


@pytest.mark.parametrize("use_template", [True, False])
def test_fresh_install_and_missing_theme_use_released_palette(tmp_path, monkeypatch, released_palette, use_template):
    home = tmp_path / "fresh"
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    template = None if use_template else tmp_path / "missing-template.yaml"
    seed_config_file(home / "config.yaml", template)
    config = load_config_readonly()
    expected_name = released_palette["name"]
    assert DEFAULT_CONFIG["display"]["skin"] == expected_name
    assert _cli_config_defaults()["display"]["skin"] == expected_name
    assert config["display"]["skin"] == expected_name
    assert "color_mode" not in DEFAULT_CONFIG["display"]
    assert "color_mode" not in _cli_config_defaults()["display"]
    assert "color_mode" not in config["display"]
    assert not (home / "skins").exists()
    skin_engine.init_skin_from_config(config)
    assert skin_engine.get_active_skin().colors == released_palette["colors"]
    assert skin_engine.get_active_skin().light_colors == released_palette["light_colors"]
    for name in ("default", "missing-theme"):
        assert skin_engine.load_skin(name).colors == released_palette["colors"]
    choices = {skin["name"] for skin in skin_engine.list_skins()}
    assert expected_name in choices
    assert "default" not in choices  # The old gold theme is not a selectable built-in.


def test_profile_theme_isolation_and_existing_choices_are_preserved(tmp_path, monkeypatch, released_palette):
    first, second = tmp_path / "A", tmp_path / "B"
    monkeypatch.setenv("SCI_HOME", str(first))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    seed_config_file(first / "config.yaml")
    second.mkdir()
    config_file = second / "config.yaml"
    config_file.write_text("# User choices\ndisplay:\n  skin: my-theme\nagent:\n  max_turns: 17\n", encoding="utf-8")
    skins = second / "skins"
    skins.mkdir()
    custom_file = skins / "my-theme.yaml"
    custom_file.write_text("name: my-theme\ncolors:\n  banner_title: '#123456'\n", encoding="utf-8")
    before_config, before_skin = config_file.read_bytes(), custom_file.read_bytes()
    monkeypatch.setattr(skin_engine, "_active_skin_by_home", {})

    for home in (first, second, first):
        token = set_sci_home_override(home)
        try:
            config = load_config_readonly()
            skin = skin_engine.get_active_skin()  # Real cold-profile startup path.
            if home == first:
                assert skin.name == released_palette["name"]
                assert skin.colors == released_palette["colors"]
            else:
                assert skin.name == "my-theme"
                assert skin.get_color("banner_title") == "#123456"
                assert skin.get_color("banner_accent") == released_palette["colors"]["banner_accent"]
                assert config["agent"]["max_turns"] == 17
                seed_config_file(config_file)  # Installer reruns must not reset user settings.
        finally:
            reset_sci_home_override(token)
    assert config_file.read_bytes() == before_config
    assert custom_file.read_bytes() == before_skin
