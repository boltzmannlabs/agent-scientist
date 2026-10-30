"""Existing isolated profiles switch directly without setup or relaxed permissions."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def saved_profiles(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    from sci_cli.science_profiles import ProfileSpec, create
    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr("sci_cli.profiles._notify_multiplexer", lambda *_: None)
    monkeypatch.setattr("sci_cli.profiles._maybe_register_gateway_service", lambda *_: None)
    atomic_config_replace(home / "config.yaml", {"model": {"provider": "openai", "default": "fixture"}})
    profiles = {"main": home}
    for name in ("a", "b"):
        profiles[name] = create(ProfileSpec(name, f"{name} research", "Cite evidence", "", setup_pending=True), home)
        (profiles[name] / "MEMORY.md").write_text(f"Private {name} memory")
    return profiles


def test_picker_switches_saved_profiles_and_resumes_without_reconfiguration(saved_profiles):
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.native_profile_session import profile_label
    from sci_cli.science_profile_commands import activate
    from sci_cli.skill_add import Cancelled
    from sci_state import SessionDB

    for name, home in saved_profiles.items():
        with profile_scope(home):
            db = SessionDB(home / "state.db")
            db.create_session(f"{name}-conversation", source="cli", system_prompt=f"{name} cached prompt")
            db.close()
    before = {p: p.read_bytes() for h in saved_profiles.values() for p in h.iterdir() if p.is_file()}
    for source, target in (("main", "a"), ("a", "b"), ("b", "a"), ("a", "main")):
        with profile_scope(saved_profiles[source]):
            assert profile_label() == source
            cli = SimpleNamespace(agent=SimpleNamespace(_flush_messages_to_session_db=Mock()),
                                  conversation_history=[{"role": "user", "content": source}],
                                  _app=SimpleNamespace(is_running=True, loop=Mock(), exit=Mock()))
            agent, history = cli.agent, list(cli.conversation_history)
            ui = SimpleNamespace(show=Mock(), choose=Mock(return_value=target))
            activate(cli, "/activate", ui)
            agent._flush_messages_to_session_db.assert_called_once()
            ui.choose.assert_called_once()
            assert f"{source} — currently active" in ui.choose.call_args.args[1]
            assert cli._pending_profile_home == str(saved_profiles[target])
            assert cli._pending_relaunch == ["--cli", "-p", "default" if target == "main" else target,
                                            "--resume", f"{target}-conversation"]
            cli._app.loop.call_soon_threadsafe.assert_called_once_with(cli._app.exit)
            assert cli.agent is agent and cli.conversation_history == history
    with profile_scope(saved_profiles["a"]):
        cli = SimpleNamespace()
        ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=Cancelled()))
        activate(cli, "/activate", ui)
        assert "cancelled" in ui.show.call_args.args[0]
        activate(cli, "/activate a", ui)
        assert "Already in a" in ui.show.call_args.args[0]
        assert not hasattr(cli, "_pending_relaunch")
    assert all(p.read_bytes() == contents for p, contents in before.items())


def test_legacy_cli_retains_policy_and_rejects_changed_config_before_cached_turn(saved_profiles):
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.science_profile_cli_policy import prepare, install
    from sci_cli.middleware import run_tool_execution_middleware
    from sci_cli.config import read_user_config_raw, atomic_config_replace
    from sci_cli.cli_agent_setup_mixin import CLIAgentSetupMixin

    with profile_scope(saved_profiles["a"]):
        cli = SimpleNamespace(agent=None, system_prompt="", max_turns=90, run_budget_seconds=None,
                              enabled_toolsets=["terminal", "file", "skills"], _approval_callback=Mock(return_value="once"))
        spec = prepare(cli)
        assert cli.enabled_toolsets == ["skills"] and cli.ignore_rules
        prompt = cli.system_prompt
        cli.agent = SimpleNamespace(tools=[{"function": {"name": n}} for n in
                                           ("skill_view", "terminal", "delegate_task", "mcp_fixture_read")])
        install(cli, spec)
        try:
            assert cli.agent.valid_tool_names == {"skill_view", "mcp_fixture_read"}
            execute = Mock(return_value="fixture")
            assert "permissions" in run_tool_execution_middleware("terminal", {}, execute)
            execute.assert_not_called()
            assert run_tool_execution_middleware("mcp_fixture_read", {}, execute) == "fixture"
            assert cli._approval_callback.call_args.kwargs == {"allow_permanent": False, "allow_session": False}
            cli._approval_callback.side_effect = EOFError()
            execute.reset_mock()
            assert "blocked" in run_tool_execution_middleware("mcp_fixture_read", {}, execute)
            execute.assert_not_called()
            assert CLIAgentSetupMixin._init_agent(cli)
            assert cli.system_prompt == prompt
            path = saved_profiles["a"] / "config.yaml"
            cfg = read_user_config_raw(path)
            cfg["terminal"]["backend"] = "local"
            atomic_config_replace(path, cfg)
            assert not CLIAgentSetupMixin._init_agent(cli)
            assert cli.system_prompt == prompt
        finally:
            cli._legacy_science_gate.dispose()


def test_activation_picker_has_no_number_prefixes_in_main_or_named_profiles(saved_profiles, monkeypatch):
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.science_profile_commands import activate
    from sci_cli.cli_modal_mixin import CLIModalMixin
    from sci_cli.cli_tui_mixin import CLITuiMixin
    from sci_cli.skill_add import WizardUI

    # More than ten entries exercises both the old numeric and blank-prefix rows.
    root = saved_profiles['a'].parent
    for letter in 'cdefghijklm':
        profile = root / f'project-{letter}'
        profile.mkdir()
        (profile / 'config.yaml').write_text('{}\n')
    notices = []
    monkeypatch.setattr(WizardUI, 'show', lambda self, text: notices.append(text))
    for source in ('main', 'a', 'b', 'a'):
        with profile_scope(saved_profiles[source]):
            cli = SimpleNamespace(_app=SimpleNamespace(is_running=True))
            def clarify(batch):
                entry = batch[0]
                assert entry['numbered_choices'] is False
                assert len(entry['choices']) > 10
                assert f'{source} — currently active' in entry['choices']
                cli._clarify_state = {'questions': batch, 'answers': {}, 'answer_meta': {}}
                CLIModalMixin._clarify_batch_set_active(cli, cli._clarify_state, 0)
                for index, choice in enumerate(entry['choices']):
                    cli._clarify_state['selected'] = index
                    text = ''.join(fragment[1] for fragment in CLITuiMixin._get_clarify_display_fragments(cli))
                    row = next(line for line in text.splitlines() if line.rstrip('│ ').endswith(choice))
                    prefix = row.rsplit(choice, 1)[0]
                    assert not any(ch.isdigit() for ch in prefix) and '.' not in prefix
                return {'outcome': 'cancelled', 'answers': {}}
            cli._clarify_callback = clarify
            activate(cli, '/activate')
            assert notices[-1] == 'Activation cancelled. Current selection unchanged.'
            assert hasattr(cli, '_clarify_state')
            assert not hasattr(cli, '_pending_relaunch')
