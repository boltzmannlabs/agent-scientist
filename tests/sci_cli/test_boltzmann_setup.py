"""Setup stays reachable without granting runtime tools before authorization."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY, Mock

import pytest


def test_command_is_available_without_plugin_and_routes_case_insensitively(monkeypatch):
    from sci_cli.commands import resolve_command, COMMANDS, COMMANDS_BY_CATEGORY, is_gateway_known_command
    from sci_cli.commands_completion import SlashCommandCompleter
    from prompt_toolkit.document import Document
    from prompt_toolkit.completion import CompleteEvent
    from cli import SciCLI
    run = Mock(return_value="setup fixture")
    monkeypatch.setattr("sci_cli.boltzmann_setup.run", run)
    cli = SciCLI.__new__(SciCLI)
    for text in ("/add_boltzmann", "/Add_boltzmann", "/ADD_BOLTZMANN", "/boltzmann_login", "/BOLTZMANN_LOGIN"):
        definition = resolve_command(text)
        assert definition is not None
        handler, with_arg = cli._slash_handler(definition.name)
        assert with_arg
        getattr(cli, handler)(text)
        run.assert_called_with(cli, "", report=ANY)
    getattr(cli, handler)("/add_boltzmann --replace --now")
    run.assert_called_with(cli, "--replace --now", report=ANY)
    assert "/add_boltzmann" in COMMANDS
    assert "/boltzmann_login" in COMMANDS
    assert "/boltzmann_login" in dict(COMMANDS_BY_CATEGORY["Tools & Skills"])
    assert not is_gateway_known_command("boltzmann_login")
    assert "/add_boltzmann" in dict(COMMANDS_BY_CATEGORY["Tools & Skills"])
    assert resolve_command("/add_boltz") is None
    assert not is_gateway_known_command("add_boltzmann")
    for prefix in ("/add_", "/Add_"):
        completions = list(SlashCommandCompleter().get_completions(Document(prefix), CompleteEvent()))
        completed = [prefix[:len(prefix) + c.start_position] + c.text for c in completions]
        assert "/add_boltzmann" in [text.lower() for text in completed]


@pytest.mark.parametrize("legacy", [False, True])
def test_unconfigured_profile_auth_is_explicit_deferred_and_isolated(tmp_path, monkeypatch, legacy, capsys):
    from sci_cli.config import atomic_config_replace, read_user_config_raw, save_env_value_secure
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.science_profiles import create, ProfileSpec
    from sci_cli.science_profiles_sandbox import validate_runtime
    from sci_cli.boltzmann_setup import run
    from sci_cli.plugins import get_plugin_manager, discover_plugins
    from sci_cli.callbacks import prompt_for_secret
    from plugins.boltzmann.auth import available
    from plugins.boltzmann.schemas import SCHEMAS
    from tools.registry import registry

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr("sci_cli.profiles._notify_multiplexer", lambda *_: None)
    monkeypatch.setattr("sci_cli.profiles._maybe_register_gateway_service", lambda *_: None)
    atomic_config_replace(home / "config.yaml", {"plugins": {"enabled": []}, "display": {"skin": "mono"},
                          "platform_toolsets": {"cli": ["skills"]}, "model": {"provider": "openai", "default": "fixture"}})
    if legacy:
        a = create(ProfileSpec("a", "Evidence review", "Cite sources", "", setup_pending=True), home)
    else:
        a = home
    b = tmp_path / "other-profile"
    b.mkdir()
    atomic_config_replace(b / "config.yaml", {"plugins": {"enabled": ["boltzmann"]}})
    from plugins.boltzmann.authentication import AuthenticationResult
    validator = Mock(side_effect=lambda key: AuthenticationResult(key == "fixture-valid", "fixture verification"))
    monkeypatch.setattr("plugins.boltzmann.onboarding.authenticate_api_key", validator)
    cli = SimpleNamespace(agent=SimpleNamespace(system_prompt="frozen", tools=["skills_list"]),
                          conversation_history=[{"role": "user", "content": "private"}])
    cli._secret_capture_callback = lambda name, prompt, **kw: prompt_for_secret(cli, name, prompt, **kw)
    names = {s["name"] for s in SCHEMAS}
    with profile_scope(a):
        manager = get_plugin_manager()
        before = read_user_config_raw(a / "config.yaml")
        try:
            discover_plugins()
            assert not available()
            assert not registry.get_definitions(names, quiet=True)
            validator.assert_not_called()
            for value, outcome in (("", "CANCELLED"), ("invalid", "FAILED")):
                monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", lambda _, v=value: v)
                assert outcome in run(cli, "")
                assert not available()
                assert read_user_config_raw(a / "config.yaml") == before
            monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", lambda _: "fixture-valid")
            assert "SAVED" in run(cli, "")
            assert available()
            assert cli.agent.system_prompt == "frozen" and cli.agent.tools == ["skills_list"]
            assert cli.conversation_history == [{"role": "user", "content": "private"}]
            after = read_user_config_raw(a / "config.yaml")
            assert after["plugins"]["enabled"] == ["boltzmann"]
            assert after["platform_toolsets"]["cli"] == ["skills", "boltzmann"]
            assert after["model"] == before["model"]
            assert after.get("terminal") == before.get("terminal")
            if legacy:
                from sci_cli.science_profile_cli_policy import prepare, install
                from sci_cli.middleware import run_tool_execution_middleware
                spec = validate_runtime(a)
                assert spec.boltzmann_enabled
                fresh_cli = SimpleNamespace(agent=None, system_prompt="", max_turns=30,
                                            _approval_callback=Mock(return_value="deny"))
                prepare(fresh_cli)
                assert fresh_cli.enabled_toolsets == ["skills", "boltzmann"]
                fresh_cli.agent = SimpleNamespace(tools=[{"function": {"name": n}} for n in
                                                       (*names, "terminal", "skill_view", "boltzmann_future")])
                install(fresh_cli, spec)
                try:
                    assert fresh_cli.agent.valid_tool_names == names | {"skill_view"}
                    execute = Mock(return_value="approved fixture")
                    assert "not approved" in run_tool_execution_middleware("boltzmann_status", {}, execute)
                    execute.assert_not_called()
                    fresh_cli._approval_callback.return_value = "once"
                    assert run_tool_execution_middleware("boltzmann_status", {}, execute) == "approved fixture"
                finally:
                    fresh_cli._legacy_science_gate.dispose()
            assert not registry.get_definitions(names, quiet=True)  # still no live discovery
            discover_plugins(force=True)  # next-session discovery
            assert {t["function"]["name"] for t in registry.get_definitions(names, quiet=True)} == names
            with profile_scope(b):
                save_env_value_secure("BOLTZMANN_API_KEY", "fixture-valid")
                other = get_plugin_manager()
                try:
                    discover_plugins()
                    assert not available()  # a copied key is not profile consent
                    assert not registry.get_definitions(names, quiet=True)
                finally:
                    other.unload()
            assert available()
            assert {t["function"]["name"] for t in registry.get_definitions(names, quiet=True)} == names
        finally:
            manager.unload()
    assert "fixture-valid" not in capsys.readouterr().out
