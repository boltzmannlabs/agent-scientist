"""Retired model URLs migrate across profiles without undoing routing safeguards."""

from pathlib import Path

import sci_yaml as yaml


def test_update_migrates_main_and_siblings_and_backup_keeps_public_route(tmp_path, monkeypatch):
    from sci_cli.backup import create_quick_snapshot, restore_config_model_settings_if_rewritten
    from sci_cli.config import DEFAULT_CONFIG, migrate_config, read_user_config_raw
    from sci_cli.config_migration_boltzmann import LEGACY_BASE_URL, PUBLIC_BASE_URL
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.update_cmd_config import _migrate_sibling_profile_configs
    from plugins.boltzmann.model_gateway import endpoint

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    main = tmp_path / ".sci"
    a, b = main / "profiles/a", main / "profiles/b"
    monkeypatch.setenv("SCI_HOME", str(main))
    homes = (main, a, b)
    snapshots = {}
    for index, home in enumerate(homes):
        home.mkdir(parents=True, exist_ok=True)
        url = LEGACY_BASE_URL if home != b else "https://custom.example.invalid/v1"
        config = {
            "_config_version": 51,
            "model": {"provider": "boltzmann_models", "default": "glm", "base_url": url},
            "providers": {"boltzmann_models": {"base_url": url}},
            "auxiliary": {"compression": {"provider": "boltzmann-models", "base_url": url}},
            "custom_prompt": "Preserve scientific instructions.",
        }
        (home / "config.yaml").write_text("# Keep my comment\n" + yaml.safe_dump(config), encoding="utf-8")
        (home / ".env").write_text(f"BOLTZMANN_API_KEY=fixture-{index}\n", encoding="utf-8")
        (home / "conversation.txt").write_text("Existing conversation", encoding="utf-8")
        snapshots[home] = create_quick_snapshot(sci_home=home)
        assert snapshots[home]

    with profile_scope(main):
        assert not migrate_config(interactive=False, quiet=True)["warnings"]
    assert {row[0] for row in _migrate_sibling_profile_configs()} == {"a", "b"}

    from agent.secret_scope import is_multiplex_active, set_multiplex_active
    previous = is_multiplex_active()
    set_multiplex_active(True)
    try:
        for home in (a, b, a, main):
            with profile_scope(home):
                expected = PUBLIC_BASE_URL if home != b else "https://custom.example.invalid/v1"
                assert restore_config_model_settings_if_rewritten(snapshots[home], home) is None
                raw = read_user_config_raw()
                assert raw["model"] == {"provider": "boltzmann_models", "default": "glm", "base_url": expected}
                assert raw["providers"]["boltzmann_models"]["base_url"] == expected
                assert raw["auxiliary"]["compression"]["base_url"] == expected
                assert raw["_config_version"] == DEFAULT_CONFIG["_config_version"]
                assert endpoint() == expected
                assert "# Keep my comment" in (home / "config.yaml").read_text()
                assert raw["custom_prompt"] == "Preserve scientific instructions."
                assert (home / ".env").read_text() == f"BOLTZMANN_API_KEY=fixture-{homes.index(home)}\n"
                assert (home / "conversation.txt").read_text() == "Existing conversation"
                before = (home / "config.yaml").read_bytes()
                migrate_config(interactive=False, quiet=True)
                assert (home / "config.yaml").read_bytes() == before

        # The exception cannot authorize an arbitrary endpoint or model rewrite.
        from sci_cli.config import atomic_config_write
        with profile_scope(a):
            raw = read_user_config_raw()
            raw["model"].update(default="unexpected", base_url="https://unexpected.example.invalid/v1")
            atomic_config_write(a / "config.yaml", raw)
            restored = restore_config_model_settings_if_rewritten(snapshots[a], a)
            assert {"model.default", "model.base_url"} <= set(restored["keys"])
    finally:
        set_multiplex_active(previous)


def test_unversioned_and_custom_routes_are_preserved_except_retired_boltzmann_url(tmp_path, monkeypatch):
    from sci_cli.config import migrate_config, read_user_config_raw
    from sci_cli.config_migration_boltzmann import LEGACY_BASE_URL, PUBLIC_BASE_URL
    from sci_cli.native_profile_creation import profile_scope

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path))
    for index, provider in enumerate(("boltzmann-models", "custom", {"malformed": True})):
        home = tmp_path / f"case-{index}"
        home.mkdir()
        config = {
            "model": {"provider": provider, "base_url": LEGACY_BASE_URL + "/"},
            "providers": {"boltzmann-models": {"base_url": LEGACY_BASE_URL},
                          "custom": {"base_url": LEGACY_BASE_URL},
                          "boltzmann_models": {"base_url": LEGACY_BASE_URL + "/custom"}},
            "auxiliary": {"title": {"provider": "custom", "base_url": LEGACY_BASE_URL}},
        }
        (home / "config.yaml").write_text(yaml.safe_dump(config), encoding="utf-8")
        with profile_scope(home):
            result = migrate_config(interactive=False, quiet=True)
            assert not result["warnings"]
            raw = read_user_config_raw()
            assert raw["model"]["base_url"] == (PUBLIC_BASE_URL if index == 0 else LEGACY_BASE_URL + "/")
            assert raw["providers"]["boltzmann-models"]["base_url"] == PUBLIC_BASE_URL
            assert raw["providers"]["custom"]["base_url"] == LEGACY_BASE_URL
            assert raw["providers"]["boltzmann_models"]["base_url"] == LEGACY_BASE_URL + "/custom"
            assert raw["auxiliary"]["title"]["base_url"] == LEGACY_BASE_URL
