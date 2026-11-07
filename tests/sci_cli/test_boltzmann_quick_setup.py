"""Quick setup and slash login share secure profile-local admission, before model setup."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from plugins.boltzmann.authentication import AuthenticationResult
from sci_cli import setup
from sci_cli.boltzmann_setup import quick_setup_step, run
from sci_cli.config import atomic_config_replace, read_user_config_raw, save_env_value_secure, load_env
from sci_cli.native_profile_creation import profile_scope


def test_quick_setup_first_step_then_model_preserves_account_and_profile_scope(tmp_path, monkeypatch, capsys):
    from sci_cli.setup_quick import _run_first_time_quick_setup
    from plugins.boltzmann.auth import available
    from sci_cli.plugins import get_plugin_manager

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    home, other = tmp_path / ".sci", tmp_path / "other"
    home.mkdir(); other.mkdir()
    monkeypatch.setenv("SCI_HOME", str(home))
    atomic_config_replace(home / "config.yaml", {"display": {"skin": "mono"}, "mcp_servers": {"custom": {"url": "https://example.invalid/mcp"}}})
    (home / ".env").write_text("UNRELATED_FIXTURE_SECRET=keep\n")
    seen = []
    login_instructions = []

    def capture_key(prompt):
        login_instructions.append(capsys.readouterr().out)
        assert "authenticate" not in seen
        return "fixture-valid"

    def verify(key):
        assert "BOLTZMANN_API_KEY" not in load_env()
        seen.append("authenticate")
        assert key == "fixture-valid"
        return AuthenticationResult(True, "Authentication successful", "fixture@example.invalid", 2259, 335)

    monkeypatch.setattr("plugins.boltzmann.onboarding.authenticate_api_key", verify)
    monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", capture_key)
    monkeypatch.setattr(setup, "prompt_choice", lambda q, c, *a, **k: 1 if q.startswith("Connect a messaging") else 0)

    def model(config, **kwargs):
        seen.append("model")
        assert available()
        assert "boltzmann" in config["platform_toolsets"]["cli"]
        config["model"] = {"default": "fixture-model", "provider": "custom"}

    monkeypatch.setattr(setup, "setup_model_provider", model)
    monkeypatch.setattr(setup, "setup_terminal_backend", lambda config: seen.append("terminal"))
    monkeypatch.setattr(setup, "_print_setup_summary", lambda *a: None)
    monkeypatch.setattr("sci_cli.gateway.ensure_gateway_service", lambda **k: None)
    with profile_scope(home):
        original_cli = get_plugin_manager()._cli_ref
        config = setup.load_config()
        _run_first_time_quick_setup(config, home, False)
        assert get_plugin_manager()._cli_ref is original_cli
        assert seen == ["authenticate", "model", "terminal"]
        raw = read_user_config_raw()
        assert raw["plugins"]["enabled"] == ["boltzmann"]
        assert raw["model"]["default"] == "fixture-model"
        assert raw["display"]["skin"] == "mono" and "custom" in raw["mcp_servers"]
        assert load_env()["UNRELATED_FIXTURE_SECRET"] == "keep"
        assert load_env()["BOLTZMANN_API_KEY"] == "fixture-valid"
        with profile_scope(other):
            assert not available() and "BOLTZMANN_API_KEY" not in load_env()
        assert available()
    output = capsys.readouterr().out
    assert "fixture-valid" not in output
    assert "fixture@example.invalid" in output and "2,259" in output and "335" in output
    assert "https://app.boltzmann.co/user-profile" in "".join(login_instructions)
    assert "Get your Boltzmann API key" not in output
    assert "https://app.boltzmann.co/" not in output


def test_existing_key_reuse_replacement_failure_cancel_and_explicit_new_boundary(tmp_path, monkeypatch, capsys):
    from sci_cli.callbacks import prompt_for_secret
    from plugins.boltzmann.auth import available
    from sci_cli.skill_add import Cancelled
    from sci_cli.plugins_state import PluginState

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setenv("SCI_HOME", str(home))
    atomic_config_replace(home / "config.yaml", {"platform_toolsets": {"cli": ["skills"]}})
    save_env_value_secure("BOLTZMANN_API_KEY", "existing-fixture")
    snapshots = (home / ".env").read_bytes(), (home / "config.yaml").read_bytes()
    verify = Mock(side_effect=lambda key: AuthenticationResult(key == "existing-fixture", "Rejected fixture"))
    monkeypatch.setattr("plugins.boltzmann.onboarding.authenticate_api_key", verify)
    monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", lambda _: "invalid-fixture")
    cli = SimpleNamespace(agent=SimpleNamespace(tools=["original"], system_prompt="frozen"),
                          conversation_history=[{"role": "user", "content": "private"}], _cmd_new=Mock())
    cli._secret_capture_callback = lambda name, prompt, **kw: prompt_for_secret(SimpleNamespace(), name, prompt, **kw)
    ui = SimpleNamespace(choose=Mock(side_effect=Cancelled()))
    assert "CANCELLED" in run(cli, "", ui=ui)
    verify.assert_not_called()
    ui.choose = Mock(return_value="Enter a replacement key")
    assert "FAILED" in run(cli, "--replace", ui=ui)
    assert snapshots == ((home / ".env").read_bytes(), (home / "config.yaml").read_bytes())
    assert not available()
    cli._app = SimpleNamespace(is_running=True)
    ui.choose = Mock(side_effect=["Verify existing key", "Keep the current conversation"])
    assert "SAVED" in run(cli, "", ui=ui)
    assert available() and PluginState("boltzmann").get("authorization")
    cli._cmd_new.assert_not_called()
    assert cli.agent.tools == ["original"] and cli.agent.system_prompt == "frozen"
    assert cli.conversation_history == [{"role": "user", "content": "private"}]
    ui.choose = Mock(side_effect=["Verify existing key", "Start a new conversation now"])
    assert "SAVED" in run(cli, "", ui=ui)
    cli._cmd_new.assert_called_once_with("/new --yes")
    assert "existing-fixture" not in capsys.readouterr().out


@pytest.mark.parametrize("choice,aborts", [(1, False), (2, True)])
def test_quick_setup_skip_or_cancel_never_requests_or_saves_credentials(tmp_path, monkeypatch, choice, aborts):
    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    verify = Mock(side_effect=AssertionError("No authentication without login selection"))
    monkeypatch.setattr("plugins.boltzmann.onboarding.authenticate_api_key", verify)
    monkeypatch.setattr(setup, "prompt_choice", lambda *a, **k: choice)
    if aborts:
        with pytest.raises(KeyboardInterrupt):
            quick_setup_step({}, home)
    else:
        quick_setup_step({}, home)
    verify.assert_not_called()
    assert not (home / ".env").exists()


@pytest.mark.parametrize("failure", ["save", "enable", "rotation"])
def test_failed_save_enable_or_concurrent_key_rotation_reports_actual_state(tmp_path, monkeypatch, failure):
    from plugins.boltzmann import onboarding
    from plugins.boltzmann.auth import available, authorize_saved_key
    from sci_cli.callbacks import prompt_for_secret

    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    atomic_config_replace(home / "config.yaml", {"platform_toolsets": {"cli": ["skills"]}})
    save_env_value_secure("BOLTZMANN_API_KEY", "previous-fixture")
    authorize_saved_key()
    before = (home / ".env").read_bytes(), (home / "config.yaml").read_bytes()
    monkeypatch.setattr(onboarding, "authenticate_api_key", lambda _: AuthenticationResult(True, "Authentication successful"))
    monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", lambda _: "new-fixture")
    cli = SimpleNamespace(agent=None)
    cli._secret_capture_callback = lambda name, prompt, **kw: prompt_for_secret(cli, name, prompt, **kw)

    def fail(*args, **kwargs):
        raise PermissionError("Fixture write denied")

    if failure == "save":
        monkeypatch.setattr("sci_cli.callbacks.save_env_value_secure", fail)
    elif failure == "enable":
        monkeypatch.setattr(onboarding, "enable_toolset", fail)
    else:
        enable = onboarding.enable_toolset

        def rotate():
            enable()
            save_env_value_secure("BOLTZMANN_API_KEY", "concurrent-fixture")

        monkeypatch.setattr(onboarding, "enable_toolset", rotate)
    message = run(cli, "--replace")
    assert "FAILED" in message and "SAVED." not in message
    if failure == "save":
        assert available()
        assert before == ((home / ".env").read_bytes(), (home / "config.yaml").read_bytes())
    else:
        assert not available()  # A different or unreceipted key is never authorized.
        assert "partially updated" in message
        assert load_env()["BOLTZMANN_API_KEY"] == ("new-fixture" if failure == "enable" else "concurrent-fixture")


def test_quick_setup_retry_is_explicit_and_missing_items_mode_still_offers_login(tmp_path, monkeypatch):
    from sci_cli.setup_quick import _run_quick_setup

    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    atomic_config_replace(home / "config.yaml", {"model": {"provider": "custom", "default": "fixture"}})
    keys = iter(["invalid-fixture", "valid-fixture"])
    seen, choices = [], []
    monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", lambda _: next(keys))

    def verify(key):
        seen.append(key)
        assert "BOLTZMANN_API_KEY" not in load_env()
        return AuthenticationResult(key == "valid-fixture", "Fixture verification")

    def choose(question, items, *args, **kwargs):
        choices.append(question)
        return 0

    monkeypatch.setattr("plugins.boltzmann.onboarding.authenticate_api_key", verify)
    monkeypatch.setattr(setup, "prompt_choice", choose)
    config = setup.load_config()
    quick_setup_step(config, home)
    assert seen == ["invalid-fixture", "valid-fixture"]
    assert any("did not complete" in question for question in choices)
    assert "boltzmann" in config["plugins"]["enabled"]
    choices.clear()
    monkeypatch.setattr(setup, "prompt_choice", lambda q, *a, **k: choices.append(q) or 1)
    monkeypatch.setattr("sci_cli.config.get_missing_env_vars", lambda **k: [])
    monkeypatch.setattr("sci_cli.config.get_missing_config_fields", lambda: [])
    monkeypatch.setattr("sci_cli.config.check_config_version", lambda: (1, 1))
    _run_quick_setup(config, home)
    assert choices == ["Boltzmann login — first setup step"]
    assert seen == ["invalid-fixture", "valid-fixture"]  # Skip does not revalidate.


@pytest.mark.parametrize("refresh", [False, RuntimeError, KeyboardInterrupt])
def test_explicit_refresh_failure_does_not_hide_successful_save(tmp_path, monkeypatch, refresh):
    from plugins.boltzmann import onboarding
    from plugins.boltzmann.auth import available
    from sci_cli.callbacks import _secret_result

    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr(onboarding, "authenticate_api_key", lambda _: AuthenticationResult(True, "Authenticated"))
    monkeypatch.setattr(onboarding, "register_skills", lambda _: None)
    monkeypatch.setattr("sci_cli.plugins.discover_plugins", lambda **k: None)

    def attempt(**kwargs):
        if refresh:
            raise refresh()
        return False

    ctx = SimpleNamespace(prompt_secret=lambda name, prompt, **kw: _secret_result(name, "fixture-key", **kw),
                          refresh_tools=attempt)
    message = onboarding.add_boltzmann(ctx, "--now")
    assert "[add_boltzmann] SAVED." in message and "not confirmed" in message
    assert available() and load_env()["BOLTZMANN_API_KEY"] == "fixture-key"
    assert "current conversation is unchanged" not in message.lower()


@pytest.mark.parametrize("command", ["/boltzmann_login", "/add_boltzmann"])
@pytest.mark.parametrize("choice", ["Keep the current conversation", "Start a new conversation now"])
def test_slash_account_details_are_visible_before_activation_picker_or_relaunch(tmp_path, monkeypatch, command, choice):
    from cli import SciCLI
    from sci_cli.callbacks import prompt_for_secret
    from rich.text import Text

    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    atomic_config_replace(home / "config.yaml", {"platform_toolsets": {"cli": ["skills"]}})
    verifier = Mock(return_value=AuthenticationResult(True, "Authenticated", "account@example.invalid", 2259, 335))
    monkeypatch.setattr("plugins.boltzmann.onboarding.authenticate_api_key", verifier)
    monkeypatch.setattr("sci_cli.callbacks.masked_secret_prompt", lambda _: "fixture-key")
    displayed = []
    monkeypatch.setattr("cli._cprint", lambda line: displayed.append(Text.from_ansi(line).plain))
    cli = SciCLI.__new__(SciCLI)
    cli._app = SimpleNamespace(is_running=True)
    cli.agent = SimpleNamespace(system_prompt="frozen", tools=["original"])
    cli.conversation_history = [{"role": "user", "content": "keep"}]
    cli._secret_capture_callback = lambda name, prompt, **kw: prompt_for_secret(SimpleNamespace(), name, prompt, **kw)

    def visible():
        text = "\n".join(displayed)
        assert "Email: account@example.invalid" in text
        assert "Credits: 2,259" in text and "Frozen credits: 335" in text

    def pick(question, choices):
        visible()  # The account must be shown while this follow-up dialog is open.
        assert "Start a new conversation now" in choices
        return choice

    def navigate(command):
        visible()  # A fresh process can close this terminal surface immediately.
        assert command == "/new --yes"

    cli._cmd_new = Mock(side_effect=navigate)
    ui = SimpleNamespace(choose=pick)
    monkeypatch.setattr("sci_cli.skill_add.WizardUI", lambda _: ui)
    from sci_cli.commands import resolve_command
    definition = resolve_command(command)
    handler, _ = cli._slash_handler(definition.name)
    getattr(cli, handler)(command)
    visible()
    assert "\n".join(displayed).count("Email: account@example.invalid") == 1
    assert "fixture-key" not in "\n".join(displayed)
    assert cli._cmd_new.call_count == (choice == "Start a new conversation now")
    assert cli.agent.system_prompt == "frozen" and cli.agent.tools == ["original"]
    verifier.assert_called_once_with("fixture-key")
