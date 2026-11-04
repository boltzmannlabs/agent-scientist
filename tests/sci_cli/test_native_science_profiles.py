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
    validate = Mock(return_value=True)
    monkeypatch.setattr(helpers, "validate_api_key", validate)
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
    validate.return_value = False
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
