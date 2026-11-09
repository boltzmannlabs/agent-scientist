"""Native science profiles own state; activation never transplants a live agent."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from sci_cli.native_profile_creation import Service, create_native, profile_scope
from sci_cli.native_profile_environment import prepare_environment


@pytest.fixture
def root(tmp_path, monkeypatch):
    from sci_cli import profiles
    from sci_cli.config import atomic_config_replace
    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr(profiles, "_notify_multiplexer", lambda *_: None)
    monkeypatch.setattr(profiles, "_maybe_register_gateway_service", lambda *_: None)
    atomic_config_replace(home / "config.yaml", {"terminal": {"backend": "local"},
                          "model": {"provider": "openai-codex", "default": "fixture"}})
    (home / ".env").write_text("PRIVATE_SERVICE_TOKEN=not-for-profiles\n")
    skill = home / "skills" / "science" / "evidence"
    skill.mkdir(parents=True)
    (skill / "SKILL.md").write_text("---\nname: evidence\ndescription: Review scientific evidence\n---\nCite sources.\n")
    (skill / "reference.md").write_text("A supporting reference.")
    return home


def test_publish_real_profiles_and_switch_a_b_a_without_leaking_state(root, tmp_path, monkeypatch):
    import os
    from sci_cli.config import read_user_config_raw
    from sci_cli.profiles import get_profile_dir, list_profile_names
    from plugins.boltzmann.auth import available
    from sci_cli.science_profile_commands import activate
    from sci_cli.native_profile_session import list_profiles, profile_label
    from sci_cli.commands import resolve_command, COMMANDS
    before = (root / "config.yaml").read_bytes(), (root / ".env").read_bytes()
    env_before = dict(os.environ)
    ui = SimpleNamespace(show=Mock(), choose=Mock())
    homes = {}
    for name in ("a", "b"):
        terminal = prepare_environment({"terminal": {"backend": "local"}}, get_profile_dir(name), ui, None)
        services = ([Service("boltzmann", "plugin", secrets={"BOLTZMANN_API_KEY": "approved-fixture"},
                              tools=["boltzmann_submit"], verified=True)] if name == "a" else [])
        homes[name] = create_native(name, root, ["science/evidence"], services, [], terminal, "Scientist")
    assert set(list_profile_names()) >= {"default", "a", "b"}
    assert before == ((root / "config.yaml").read_bytes(), (root / ".env").read_bytes())
    assert os.environ.get("BOLTZMANN_API_KEY") == env_before.get("BOLTZMANN_API_KEY")
    for name in ("a", "b", "a"):
        with profile_scope(homes[name]):
            assert profile_label() == name
            assert available() == (name == "a")
            cfg = read_user_config_raw(homes[name] / "config.yaml")
            from sci_cli.tools_config import _get_platform_tools
            from model_tools import get_tool_definitions
            selected = _get_platform_tools(cfg, 'cli')
            assert 'delegation' in selected
            definitions = get_tool_definitions(sorted(selected), quiet_mode=True, skip_tool_search_assembly=True)
            assert 'delegate_task' in {t['function']['name'] for t in definitions}
            assert 'clarify' in {t['function']['name'] for t in definitions}
            assert cfg["terminal"]["cwd"] == str(homes[name] / "workspace")
            assert "PRIVATE_SERVICE_TOKEN" not in (homes[name] / ".env").read_text()
            assert (homes[name] / "skills/science/evidence/reference.md").read_text() == "A supporting reference."
            list_profiles(ui)
    agent = SimpleNamespace(_cached_system_prompt="frozen", tools=[{"original": True}],
                            _flush_messages_to_session_db=Mock())
    cli = SimpleNamespace(agent=agent, conversation_history=[{"role": "user", "content": "private-main"}],
                          _app=SimpleNamespace(is_running=True, loop=Mock(), exit=Mock()))
    ui.choose.return_value = "a"
    activate(cli, "/activate", ui)
    assert cli._pending_profile_home == str(homes["a"])
    assert cli._pending_relaunch == ["--cli", "-p", "a"]  # no --continue on an empty profile
    assert agent._cached_system_prompt == "frozen" and agent.tools == [{"original": True}]
    assert cli.conversation_history == [{"role": "user", "content": "private-main"}]
    assert resolve_command("/PROFILES_LIST").name == "profiles_list"
    assert "/profiles_list" in COMMANDS
    cli._agent_running = True
    cli._pending_profile_home = "unchanged"
    activate(cli, "/activate b", ui)
    assert cli._pending_profile_home == "unchanged"


def test_wizard_existing_new_keys_cancel_invalid_key_and_duplicate_are_transactional(root, monkeypatch):
    from sci_cli.native_profile_wizard import create_wizard
    from sci_cli.native_profile_services import setup_boltzmann, credential
    from sci_cli.skill_add import Cancelled
    from sci_cli.profiles import get_profile_dir
    from sci_cli.config import save_env_value_secure
    from plugins.boltzmann.auth import available
    import sci_cli.callbacks as callbacks
    import plugins.boltzmann.nodeapi_helpers as helpers

    cli = SimpleNamespace()
    manifest = SimpleNamespace(source="bundled", path="unused")
    with profile_scope(root):
        save_env_value_secure("BOLTZMANN_API_KEY", "existing-fixture")
    ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=["Use existing key from source profile", "Validate key"]))
    from plugins.boltzmann.authentication import AuthenticationResult
    validate = Mock(return_value=AuthenticationResult(True, "fixture verification"))
    monkeypatch.setattr(helpers, "authenticate_api_key", validate)
    service = setup_boltzmann(cli, ui, root, manifest)
    validate.assert_called_once_with("existing-fixture")
    assert service.verified and len(service.tools) == 5
    assert not available()  # main only has a key, not a receipt
    capture = Mock(return_value={"success": True, "value": "new-fixture"})
    monkeypatch.setattr(callbacks, "prompt_for_secret", capture)
    ui.choose = Mock(return_value="Enter new key for this profile")
    assert credential(cli, ui, "BOLTZMANN_API_KEY", "existing")[0] == "new-fixture"
    assert capture.call_args.kwargs["persist"] is False
    validate.reset_mock()
    ui.choose = Mock(side_effect=["Use existing key from source profile", Cancelled()])
    with pytest.raises(Cancelled):
        setup_boltzmann(cli, ui, root, manifest)
    validate.assert_not_called()
    validate.return_value = AuthenticationResult(False, "Rejected fixture")
    ui.choose = Mock(side_effect=["Use existing key from source profile", "Validate key", "Remove service"])
    assert setup_boltzmann(cli, ui, root, manifest) is None
    # A controlled terminal walkthrough: scientific skills, no services,
    # no sources, native local environment, review, save, stay.
    ui.choose = Mock(side_effect=["Done", "Done", "Done", "Done", "Create profile", "Stay in current profile"])
    create_wizard(cli, '/Create_profile "omics"', ui)
    saved = get_profile_dir("omics")
    assert saved.is_dir(), ui.show.call_args_list
    assert json.loads((saved / "science-project.json").read_text())["name"] == "omics"
    assert not (saved / "science-profile.json").exists()
    original = (saved / "config.yaml").read_bytes()
    ui.choose = Mock(side_effect=Cancelled())
    create_wizard(cli, '/Create_profile "omics"', ui)
    assert (saved / "config.yaml").read_bytes() == original
    create_wizard(cli, '/Create_profile "cancelled"', ui)
    assert not get_profile_dir("cancelled").exists()


@pytest.mark.parametrize("action", ["retry", "skip", "cancel"])
def test_empty_key_keeps_review_and_closes_only_staged_logs(root, monkeypatch, action):
    import shutil
    from sci_constants import get_sci_home, sci_home_key
    from sci_cli import native_profile_services as services, native_profile_wizard as wizard
    from sci_cli.profiles import get_profile_dir
    from sci_cli.skill_add import Cancelled
    from tools.mcp_tool_config import _get_mcp_stderr_log, _close_mcp_stderr_logs
    from plugins.boltzmann.authentication import AuthenticationResult

    manifest = SimpleNamespace(source="bundled", path="unused", description="Fixture")
    monkeypatch.setattr(services, "catalog", lambda *_: {
        "mcp:fixture": ("mcp", "fixture", {"url": "https://fixture.invalid/mcp"}),
        "plugin:boltzmann": ("plugin", "boltzmann", manifest),
    })
    monkeypatch.setattr("sci_cli.science_integrations.missing_defaults", lambda *_: {})
    monkeypatch.setattr(wizard, "select_science_items", lambda *_: [])
    monkeypatch.setattr(services, "select_science_items", lambda ui, title, items, **_: list(items))
    staged = []

    def probe(*args, **kwargs):
        staged.append((get_sci_home(), _get_mcp_stderr_log()))
        staged[-1][1].write("Controlled discovery, no external calls.\n")
        return [("inspect", "Fixture tool")]

    monkeypatch.setattr("sci_cli.mcp_config._probe_single_server", probe)
    capture = Mock(side_effect=[{"success": True, "skipped": True, "reason": "cancelled"},
                                {"success": True, "value": "new-fixture"}])
    monkeypatch.setattr("sci_cli.callbacks.prompt_for_secret", capture)
    authenticate = Mock(return_value=AuthenticationResult(True, "Fixture"))
    monkeypatch.setattr("plugins.boltzmann.nodeapi_helpers.authenticate_api_key", authenticate)
    choices = ["Check connection", "Enter new key for this profile"]
    choices += {"retry": ["Enter new key for this profile", "Validate key"],
                "skip": ["Remove service"], "cancel": [Cancelled()]}[action]
    if action != "cancel":
        choices += ["Done", "Create profile", "Stay in current profile"]
    ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=choices))
    before = (root / "config.yaml").read_bytes(), (root / ".env").read_bytes()
    with profile_scope(root):
        main_log = _get_mcp_stderr_log()
    remove = shutil.rmtree

    def checked_remove(path, *args, **kwargs):
        for home, handle in staged:
            if Path(path) == home:
                assert handle.closed  # Invariant needed by Windows, on every host.
                assert not main_log.closed
        return remove(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", checked_remove)
    try:
        wizard.create_wizard(SimpleNamespace(), '/Create_profile "recovered"', ui)
        assert staged and all(handle.closed and not home.exists() for home, handle in staged)
        with profile_scope(root):
            assert _get_mcp_stderr_log() is main_log and not main_log.closed
        assert before == ((root / "config.yaml").read_bytes(), (root / ".env").read_bytes())
        saved = get_profile_dir("recovered")
        assert saved.exists() is (action != "cancel")
        if action != "cancel":
            metadata = json.loads((saved / "science-project.json").read_text())
            assert "fixture" in {item["name"] for item in metadata["services"]}
            assert ("boltzmann" in {item["name"] for item in metadata["services"]}) is (action == "retry")
        assert authenticate.call_count == (1 if action == "retry" else 0)
        if action == "retry":
            authenticate.assert_called_once_with("new-fixture")
        displayed = "\n".join(str(c.args[0]) for c in ui.show.call_args_list)
        assert "No usable BOLTZMANN_API_KEY" in displayed
        assert "new-fixture" not in displayed and "Profile creation failed" not in displayed
    finally:
        _close_mcp_stderr_logs(scope=sci_home_key(root))


@pytest.mark.parametrize("cancelled,retry", [(False, True), (False, False), (True, True), (True, False)])
def test_review_cleanup_failure_preserves_outcome_and_requires_explicit_retry(tmp_path, monkeypatch, cancelled, retry):
    import shutil
    from sci_cli.native_profile_review import review_workspace
    from sci_cli.skill_add import Cancelled
    from tools.mcp_tool_config import _get_mcp_stderr_log

    remove = shutil.rmtree
    attempts = []
    handle = None

    def fail_once(path, *args, **kwargs):
        assert handle.closed
        attempts.append(path)
        if len(attempts) == 1:
            raise PermissionError("Fixture external file lock")
        return remove(path, *args, **kwargs)

    monkeypatch.setattr(shutil, "rmtree", fail_once)
    ui = SimpleNamespace(show=Mock(), choose=Mock(return_value="Retry cleanup" if retry else "Keep temporary files for now"))
    try:
        try:
            with review_workspace(ui, prefix=str(tmp_path / "review-")) as scratch:
                with profile_scope(scratch):
                    handle = _get_mcp_stderr_log()
                if cancelled:
                    raise Cancelled()
        except Cancelled:
            assert cancelled
        else:
            assert not cancelled
        assert len(attempts) == (2 if retry else 1)
        ui.choose.assert_called_once()
        assert scratch.exists() is not retry
        assert "does not undo a saved profile" in ui.show.call_args.args[0]
        assert str(scratch) in ui.show.call_args.args[0]
    finally:
        if scratch.exists():
            remove(scratch)
