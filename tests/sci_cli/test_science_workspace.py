"""Science inventories, selectors and native updates use real isolated profile homes."""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def multiplex():
    from agent.secret_scope import is_multiplex_active, set_multiplex_active
    previous = is_multiplex_active()
    set_multiplex_active(True)
    try:
        yield
    finally:
        set_multiplex_active(previous)


@pytest.fixture
def homes(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / ".sci"
    monkeypatch.setenv("SCI_HOME", str(root))
    monkeypatch.setenv("SCI_BUNDLED_SKILLS", str(tmp_path / "bundled-skills"))
    result = [root, root / "profiles/a", root / "profiles/b"]
    for home in result:
        home.mkdir(parents=True)
        atomic_config_replace(home / "config.yaml", {"display": {"skin": "mono"}, "terminal": {"backend": "local"},
            "plugins": {"enabled": []}, "platform_toolsets": {"cli": ["file", "skills"]}})
    return result


def test_reviewed_save_defers_watcher_but_reports_other_edits(homes, capsys):
    from sci_cli.config import read_user_config_raw, atomic_config_replace
    from sci_cli.native_profile_creation import Service, profile_scope
    from sci_cli.native_profile_update import save_update
    from cli import SciCLI
    home = homes[1]
    cli = SimpleNamespace(_last_config_check=0, _config_sig=None, _config_mcp_servers={},
                          _reload_mcp=Mock(side_effect=AssertionError("No live reload")))
    service = Service("fixture", "mcp", {"url": "https://example.org/mcp", "enabled": True,
                      "tools": {"include": ["lookup"]}}, verified=True)
    with profile_scope(home):
        save_update(home, read_user_config_raw(), services=[service], cli=cli)
        SciCLI._check_config_mcp_changes(cli)
        assert cli._config_mcp_servers["fixture"]["tools"]["include"] == ["lookup"]
        cfg = read_user_config_raw()
        cfg["mcp_servers"]["separate-edit"] = {"url": "https://example.org/other"}
        atomic_config_replace(home / "config.yaml", cfg)
        cli._last_config_check = 0
        SciCLI._check_config_mcp_changes(cli)
        assert "separate-edit" in capsys.readouterr().out
        cli._reload_mcp.assert_not_called()
        # Updating another profile does not mark this CLI's watcher.
        other_cli = SimpleNamespace()
        save_update(homes[2], read_user_config_raw(homes[2] / "config.yaml"), services=[service], cli=other_cli)
        assert not hasattr(other_cli, "_science_deferred_mcp")


def test_bundled_skills_can_be_copied_and_runtime_names_are_disabled(homes, monkeypatch, tmp_path):
    from sci_cli.science_profiles_catalog import science_skill_choices
    from sci_cli.native_profile_update import save_update
    from sci_cli.config import read_user_config_raw
    from sci_cli.native_profile_creation import profile_scope
    from tools.skills_tool import _find_all_skills
    bundled = tmp_path / "packaged"
    source = bundled / "science/example-folder"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: evidence-review\ndescription: Scientific evidence\n---\nReview evidence.")
    (source / "reference.md").write_text("Supporting source")
    monkeypatch.setenv("SCI_BUNDLED_SKILLS", str(bundled))
    home = homes[1]
    with profile_scope(home):
        labels, paths = science_skill_choices(homes[0], home)
        name = "science/example-folder"
        assert "bundled default" in labels[name]
        save_update(home, read_user_config_raw(), skills=[name], skill_sources=paths)
        assert (home / "skills" / name / "reference.md").read_text() == "Supporting source"
        save_update(home, read_user_config_raw(), skills=[], skill_sources=paths)
        assert "evidence-review" in read_user_config_raw()["skills"]["disabled"]
        assert all(s["name"] != "evidence-review" for s in _find_all_skills())


def test_select_all_covers_entire_section_and_remains_individually_reversible():
    from sci_cli.science_profiles_catalog import select_science_items
    options = {f"tool-{n}": "example" for n in range(13)}
    steps = iter(["Search", "Select all", "Clear search", "toggle", "Done"])
    def choose(question, choices):
        assert "entire section" in question
        value = next(steps)
        return next(c for c in choices if c.startswith("[selected] tool-0")) if value == "toggle" else value
    ui = SimpleNamespace(show=Mock(), ask=lambda _: "tool-12", choose=choose)
    assert set(select_science_items(ui, "Tools", options)) == set(options) - {"tool-0"}
    ui.choose = Mock(side_effect=["Clear selection", "Done"])
    assert select_science_items(ui, "Skills", options, selected=list(options)) == []


def test_catalog_grouping_filters_and_search_follow_installed_registry(tmp_path):
    from sci_cli.science_catalog_view import catalog_rows
    path = tmp_path / "registry.json"
    data = {"modules": [{"id": "a", "domain": "Domain A", "title": "Module A"}], "tools": [
        {"display_name": "Example " + status, "module_id": "a", "status": status, "aliases": ["synonym"]}
        for status in ("active", "on_hold", "removed", "ignored")]}
    path.write_text(json.dumps(data), encoding="utf-8-sig")
    rows = catalog_rows(path)
    assert {r["name"] for r in rows} == {"Example active", "Example on_hold"}
    assert all(r["module"] == "Module A" and r["domain"] == "Domain A" for r in rows)
    assert catalog_rows(path, query="synonym") == rows
    assert catalog_rows(path, domain="other") == []


def test_update_preserves_isolation_and_conflicts_fail_before_writes(homes, multiplex):
    from sci_cli.config import read_user_config_raw, atomic_config_replace
    from sci_cli.native_profile_creation import profile_scope, Service
    from sci_cli.native_profile_update import save_update
    root, a, b = homes
    for home in homes:
        (home / ".env").write_text("PRIVATE_TOKEN=fixture-" + home.name + "\n")
        (home / "SOUL.md").write_text("Private persona " + home.name)
    original = {h: ((h / "config.yaml").read_bytes(), (h / ".env").read_bytes(), (h / "SOUL.md").read_bytes()) for h in homes}
    for home in (a, b, a):
        with profile_scope(home):
            cfg = read_user_config_raw()
            service = Service("fixture", "mcp", {"url": "https://example.org/mcp", "enabled": True,
                 "tools": {"include": ["search"]}}, tools=["search"], credential_choice="unchanged", verified=True)
            save_update(home, cfg, services=[service])
            now = read_user_config_raw()
            assert now["mcp_servers"]["fixture"]["tools"]["include"] == ["search"]
            assert now["display"] == cfg["display"] and now["terminal"] == cfg["terminal"]
    assert (root / "config.yaml").read_bytes() == original[root][0]
    for home in homes:
        assert (home / ".env").read_bytes() == original[home][1]
        assert (home / "SOUL.md").read_bytes() == original[home][2]
    cfg = read_user_config_raw(a / "config.yaml")
    changed = deepcopy(cfg)
    changed["display"]["skin"] = "other"
    atomic_config_replace(a / "config.yaml", changed)
    with pytest.raises(ValueError, match="changed during review"):
        save_update(a, cfg, services=[service])
    assert read_user_config_raw(a / "config.yaml") == changed
    save_update(a, changed, represented=["mcp:fixture"])
    assert read_user_config_raw(a / "config.yaml")["mcp_servers"]["fixture"]["enabled"] is False
    assert read_user_config_raw(b / "config.yaml")["mcp_servers"]["fixture"]["enabled"] is True


def test_defaults_respect_custom_disabled_entries_and_cancel_before_install(homes, monkeypatch):
    from sci_cli.science_integrations import missing_defaults, prepare_default
    from sci_cli.skill_add import Cancelled
    cfg = {"mcp_servers": {"pubmed": {"enabled": False, "tools": {"exclude": ["private"]}}}}
    before = deepcopy(cfg)
    assert "pubmed" not in missing_defaults(cfg)
    assert cfg == before
    install = Mock()
    monkeypatch.setattr("pm.ensure_python_tool", install)
    ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=Cancelled))
    with pytest.raises(Cancelled):
        prepare_default("tooluniverse", ui)
    install.assert_not_called()


def test_new_commands_are_routed_and_inventory_does_not_probe(homes, monkeypatch, multiplex):
    from sci_cli.commands import resolve_command, COMMANDS
    from cli import SciCLI
    from sci_cli.capability_overview import inventory
    from sci_cli.native_profile_creation import profile_scope
    from tools.registry import registry
    probe = Mock(side_effect=AssertionError("Inventory must not probe"))
    monkeypatch.setattr("sci_cli.mcp_config._probe_single_server", probe)
    for command in ("capabilities", "boltzmann_tools", "Update_profile"):
        cmd = resolve_command("/" + command.upper())
        assert cmd and cmd.cli_only
        assert hasattr(SciCLI, "_handle_" + cmd.name + "_command")
        assert "/" + command in COMMANDS or "/" + command.lower() in COMMANDS
    for home in (homes[1], homes[2], homes[1]):
        with profile_scope(home):
            registry.register(name="fixture_no_probe", toolset="fixture", schema={"parameters": {}},
                              handler=lambda _: "{}", check_fn=probe, scope=str(home.resolve()))
            rows = inventory(SimpleNamespace(agent=None))
            assert any(r.name == "fixture_no_probe" for r in rows)
            assert any(r.kind == "default MCP" and r.name == "pubmed" for r in rows)
    probe.assert_not_called()


def test_duplicate_disable_is_recoverable_and_requires_native_authorization(homes):
    from sci_cli.science_integrations import disable_duplicate
    from sci_cli.config import atomic_config_replace, read_user_config_raw, save_env_value_secure
    from sci_cli.native_profile_creation import profile_scope
    from plugins.boltzmann.auth import authorize_saved_key
    root, a, _ = homes
    entry = {"command": "python", "args": ["/fixture/boltzmann_mcp_server.py"], "enabled": True,
             "tools": {"include": ["fixture"]}}
    cfg = read_user_config_raw(a / "config.yaml")
    cfg.update(mcp_servers={"boltzmann": entry}, plugins={"enabled": ["boltzmann"]})
    atomic_config_replace(a / "config.yaml", cfg)
    with pytest.raises(ValueError, match="not authorized"):
        disable_duplicate(a)
    with profile_scope(a):
        save_env_value_secure("BOLTZMANN_API_KEY", "fixture")
        authorize_saved_key()
    backup = Path(disable_duplicate(a))
    assert json.loads(backup.read_text()) == entry
    assert backup.stat().st_mode & 0o077 == 0
    assert read_user_config_raw(a / "config.yaml")["mcp_servers"]["boltzmann"]["enabled"] is False
    assert disable_duplicate(a) is None
    assert "mcp_servers" not in read_user_config_raw(root / "config.yaml")


def test_update_modal_walkthrough_preserves_persona_and_supporting_skill_files(homes, monkeypatch):
    from sci_cli.native_profile_update import update_wizard
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.config import read_user_config_raw
    from sci_cli.skill_add import WizardUI
    root, a, _ = homes
    skill = root / "skills/science/evidence"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: evidence\ndescription: Scientific evidence review\n---\nCite evidence.")
    (skill / "support.md").write_text("Supporting notes")
    (a / "SOUL.md").write_text("Original scientist persona")
    (a / ".env").write_text("PRIVATE_KEY=fixture-private\n")
    step = iter(["Select all", "Done", "Done", "Done", "Done", "Save and enable for the next session", "Keep current conversation"])
    questions = []
    def clarify(rows):
        value = next(step)
        questions.append(rows[0]["question"])
        assert value in rows[0]["choices"]
        return {"outcome": "submitted", "answers": {"skill_add": value}}
    cli = SimpleNamespace(_app=SimpleNamespace(is_running=True), _clarify_callback=clarify,
                          agent=SimpleNamespace(_cached_system_prompt="frozen", tools=[{"old": "tool"}]))
    ui = WizardUI(cli)
    ui.show = Mock()
    with profile_scope(a):
        update_wizard(cli, '/Update_profile "a"', ui)
    assert (a / "skills/science/evidence/support.md").read_text() == "Supporting notes"
    assert (a / "SOUL.md").read_text() == "Original scientist persona"
    assert (a / ".env").read_text() == "PRIVATE_KEY=fixture-private\n"
    assert cli.agent._cached_system_prompt == "frozen" and cli.agent.tools == [{"old": "tool"}]
    assert read_user_config_raw(a / "config.yaml")["skills"]["disabled"] == []
    assert any("MCP connections" in q for q in questions) and any("Plugins" in q for q in questions)
    assert "fixture-private" not in str(ui.show.call_args_list)
