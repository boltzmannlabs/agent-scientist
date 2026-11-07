"""Catalog navigation uses terminal modals and the owning profile's installed metadata."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sci_cli.native_profile_creation import profile_scope
from sci_cli.science_catalog_view import registry_path, run_catalog
from sci_cli.skill_add import WizardUI


@pytest.fixture
def catalogs(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace, load_config_readonly

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / ".sci"
    monkeypatch.setenv("SCI_HOME", str(root))
    homes = [root / "profiles/a", root / "profiles/b"]
    for home in homes:
        home.mkdir(parents=True)
        atomic_config_replace(home / "config.yaml", {"plugins": {"enabled": []}})
        (home / ".env").write_text("PRIVATE_TEST_KEY=fixture-private\n")
        plugin = home / "plugins/boltzmann"
        refs = plugin / "skills/boltzmann-tools/references"
        refs.mkdir(parents=True)
        (plugin / "plugin.yaml").write_text('name: boltzmann\nversion: "1.0.0"\ndescription: Fixture\n')
        (plugin / "__init__.py").write_text('raise AssertionError("Catalog browsing must not import plugin code")\n')
        modules = [
            ("protein", "Protein Engineering", "Antibody Generation"),
            ("molecule", "Small Molecule Design", "Screening"),
            ("synthetic", "Synthetic Chemistry", "Retrosynthesis"),
            ("rna", "RNA Design", "RNA Generation"),
            ("quantum", "Density Functional Theory", "Quantum Chemistry"),
            ("mds", "Molecular Dynamics", "Molecular Dynamics"),
        ]
        tools = [{"display_name": f"{home.name}-protein-{i:02}", "module_id": "protein", "status": "active",
                  "aliases": [f"synonym-{home.name}"] if i == 0 else []} for i in range(40)]
        tools.extend({"display_name": f"{home.name}-{key}", "module_id": key, "status": "active",
                      "aliases": [f"synonym-{home.name}"]} for key in ("molecule", "synthetic", "rna", "quantum", "mds"))
        tools.extend({"display_name": "Duplicate display name", "module_id": "molecule", "status": "active"}
                     for _ in range(2))
        tools.append({"display_name": "Removed fixture", "module_id": "protein", "status": "removed"})
        data = {"status": "canonical", "modules": [{"id": key, "domain": domain, "title": title}
                for key, domain, title in modules], "tools": tools,
                "unavailable_entries": [{"display_name": f"{home.name}-legacy", "module_id": None,
                                         "status": "unavailable", "aliases": [f"legacy-{home.name}"]}]}
        (refs / "tool-contracts.v1.json").write_text(json.dumps(data))
        # Slash commands run after the CLI has initialized its config and persona.
        with profile_scope(home):
            load_config_readonly()
    def forbidden(*args, **kwargs):
        raise AssertionError("Catalog browsing must not read stdin or open a network connection")
    monkeypatch.setattr("builtins.input", forbidden)
    monkeypatch.setattr("socket.socket.connect", forbidden)
    return homes


def _pick(fragment):
    def choose(question, choices):
        matches = [choice for choice in choices if fragment in choice]
        assert len(matches) == 1, (fragment, choices)
        return matches[0]
    return choose


def _terminal(steps):
    pending = list(steps)
    seen = []

    def clarify(questions):
        row = questions[0]
        question, choices = row["question"], row["choices"]
        seen.append((question, choices))
        step = pending.pop(0)
        if step is None:
            return {"outcome": "cancelled", "answers": {}}
        answer = step(question, choices) if callable(step) else step
        assert not choices or answer in choices, (answer, choices)
        return {"outcome": "submitted", "answers": {"skill_add": answer}}

    cli = SimpleNamespace(_app=SimpleNamespace(is_running=True), _clarify_callback=clarify,
                          agent=SimpleNamespace(_cached_system_prompt="frozen-prefix", tools=[{"name": "fixture"}]),
                          conversation_history=[{"role": "user", "content": "Keep this conversation"}])
    ui = WizardUI(cli)
    ui.show = Mock()
    return cli, ui, pending, seen


def _files(home):
    return {str(path.relative_to(home)): path.read_bytes() for path in home.rglob("*") if path.is_file()}


def _unchanged(home, before):
    after = _files(home)
    assert after.keys() == before.keys(), ("Created files", after.keys() - before.keys(), "Removed files", before.keys() - after.keys())
    assert not [name for name in before if before[name] != after[name]], "Profile files changed"


def test_module_search_pagination_details_and_back_are_visible_in_terminal_pickers(catalogs):
    home = catalogs[0]
    before = _files(home)
    cli, ui, pending, seen = _terminal([
        "Protein Engineering", "Search", "synonym-a", _pick("a-protein-00"), "Back", "Clear search",
        "Next page", "Previous page", "Back", "Simulation tools", "Back",
        "Small Molecule Design", _pick("Duplicate display name (entry 1)"), "Back", "Back",
        "All", "Search", "legacy-a", _pick("a-legacy [unavailable]"), "Back", "Clear search",
        "Search", "no such tool fixture", "Back", "Done",
    ])
    with profile_scope(home):
        run_catalog(cli, "/boltzmann_tools", ui)
    assert not pending
    assert seen[0][1] == ["Protein Engineering", "Small Molecule Design", "Synthetic Chemistry", "RNA Design",
                          "Simulation tools", "All", "Search", "Done"]
    filtered = next(choices for question, choices in seen if "search: synonym-a" in question)
    assert any("a-protein-00" in choice for choice in filtered)
    assert not any("a-molecule" in choice or "a-rna" in choice for choice in filtered)
    simulation = next(choices for question, choices in seen if question.startswith("Simulation tools —"))
    assert any("a-quantum" in choice for choice in simulation) and any("a-mds" in choice for choice in simulation)
    assert not any("a-protein" in choice for choice in simulation)
    all_choices = next(choices for question, choices in seen if question.startswith("All —") and "search:" not in question)
    assert any("Protein Engineering → Antibody Generation → a-protein" in choice for choice in all_choices)
    assert any("Catalog status: unavailable" in question for question, _ in seen)
    assert any("No matching tools" in question for question, _ in seen)
    assert "Removed fixture" not in str(seen)
    _unchanged(home, before)
    assert cli.agent._cached_system_prompt == "frozen-prefix" and cli.agent.tools == [{"name": "fixture"}]
    assert cli.conversation_history == [{"role": "user", "content": "Keep this conversation"}]


def test_direct_commands_cancellation_and_profile_alternation_preserve_installed_sources(catalogs):
    a, b = catalogs
    before = {home: _files(home) for home in catalogs}
    for home, command, title, expected in (
        (a, "/boltzmann_tools search synonym-a", "All —", "a-protein-00"),
        (b, "/boltzmann_tools protein-engineering", "Protein Engineering —", "b-protein-00"),
        (a, "/boltzmann_tools simulation tools", "Simulation tools —", "a-quantum"),
        (a, '/boltzmann_tools "Quantum Chemistry"', "All —", "a-quantum"),
    ):
        cli, ui, pending, seen = _terminal(["Done"])
        with profile_scope(home):
            assert registry_path().is_relative_to(home / "plugins/boltzmann")
            run_catalog(cli, command, ui)
        assert not pending and seen[0][0].startswith(title)
        assert any(expected in choice for choice in seen[0][1])
        other = "b-" if home == a else "a-"
        assert not any(other in choice for choice in seen[0][1])
    for command, steps in (("/boltzmann_tools", [None]), ('/boltzmann_tools "unfinished', [])):
        cli, ui, pending, seen = _terminal(steps)
        with profile_scope(a):
            run_catalog(cli, command, ui)
        assert not pending
        assert "closed" in str(ui.show.call_args_list) or "could not be read" in str(ui.show.call_args_list)
    for home in catalogs:
        _unchanged(home, before[home])
