"""The Omics foundation is private state, not inherited scientific authority."""

import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def root(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    home = tmp_path / "science-root"
    home.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setattr("sci_cli.profiles._notify_multiplexer", lambda *_: None)
    monkeypatch.setattr("sci_cli.profiles._maybe_register_gateway_service", lambda *_: None)
    atomic_config_replace(home / "config.yaml", {
        "model": {"provider": "openai-codex", "default": "fixture"},
        "platform_toolsets": {"cli": ["terminal", "delegation", "boltzmann"]},
        "plugins": {"enabled": ["boltzmann"]},
        "mcp_servers": {"private": {"url": "https://invalid.example/mcp"}},
    })
    (home / ".env").write_text("BOLTZMANN_API_KEY=private-service-fixture\n")
    return home


def cli_fixture():
    return SimpleNamespace(
        agent=SimpleNamespace(_cached_system_prompt="frozen", tools=["original"],
                              _flush_messages_to_session_db=Mock()),
        conversation_history=[{"role": "user", "content": "private main history"}],
        _app=SimpleNamespace(is_running=True, loop=Mock(), exit=Mock()),
    )


def test_activation_shared_auth_fresh_turns_and_resume_isolation(root, monkeypatch):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.native_profile_session import profile_label
    from sci_cli.omics_starter import startup_notice
    from sci_cli.profiles import list_profile_names, create_profile
    from sci_cli.science_profile_commands import activate
    from sci_cli.auth import write_credential_pool
    from sci_cli.runtime_provider import resolve_runtime_provider
    from agent.credential_pool import PooledCredential
    from sci_state import SessionDB
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text

    with FakeLLMServer(default_text="Omics fixture reply", aux=lambda _: Text("Omics fixture reply")) as server:
        cfg = read_user_config_raw(root / "config.yaml")
        cfg["model"] = {"provider": "fixture-gateway", "default": "fake-model"}
        cfg["providers"] = {"fixture-gateway": {"base_url": server.base_url}}
        atomic_config_replace(root / "config.yaml", cfg)
        with profile_scope(root):
            credential = PooledCredential(provider="fixture-gateway", id="fixture", label="Shared test login",
                auth_type="api_key", priority=0, source="manual", access_token="shared-fixture-key",
                base_url=server.base_url)
            write_credential_pool("fixture-gateway", [credential.to_dict()])
        before = {p.name: p.read_bytes() for p in (root / "config.yaml", root / ".env", root / "auth.json")}
        ui = SimpleNamespace(show=Mock(), choose=Mock(side_effect=["omics — set up coordinator", "Create Omics"]))
        cli = cli_fixture()
        activate(cli, "/activate", ui)
        home = root / "profiles" / "omics"
        assert home.is_dir(), ui.show.call_args_list
        assert cli._pending_relaunch == ["--cli", "-p", "omics"]
        assert "omics" in list_profile_names()
        assert "foundation instruction skills present" in startup_notice(home)
        assert not (home / "auth.json").exists()
        assert "private-service-fixture" not in (home / ".env").read_text()
        child_cfg = read_user_config_raw(home / "config.yaml")
        assert child_cfg["plugins"]["enabled"] == [] and child_cfg["mcp_servers"] == {}
        assert (home / ".no-bundled-skills").exists()
        from sci_cli.omics_foundation import foundation
        expected = {item["name"] for item in foundation()["skills"]}
        assert {p.parent.name for p in (home / "skills").rglob("SKILL.md")} == expected
        assert cli.agent._cached_system_prompt == "frozen" and cli.agent.tools == ["original"]
        assert cli.conversation_history == [{"role": "user", "content": "private main history"}]

        # Real imports and resolved shared credentials across separate homes, not copied token mocks.
        other = create_profile("other", no_skills=True, no_alias=True)
        for target in (home, other, home):
            with profile_scope(target):
                assert profile_label() == target.name
                route = resolve_runtime_provider(requested="fixture-gateway", target_model="fake-model")
                assert route["api_key"] == "shared-fixture-key"
        env = {**os.environ, "SCI_HOME": str(home), "SCI_PROFILE": "omics", "SCI_PROFILE_NAME": "omics",
               "PYTHONPATH": str(Path(__file__).resolve().parents[2])}
        # Block outbound destinations, while exercising real CLI initialization, tool resolution,
        # model HTTP requests, prompt construction and conversation persistence in a fresh process.
        script = '''
import socket
connect = socket.socket.connect
def local_only(self, address):
    if isinstance(address, tuple) and address[0] not in ('127.0.0.1', '::1', 'localhost'):
        raise AssertionError('Unexpected external network access')
    return connect(self, address)
socket.socket.connect = local_only
import sci_bootstrap
from cli import SciCLI, CLI_CONFIG
from sci_cli.tools_config import _get_platform_tools
tools = sorted(_get_platform_tools(CLI_CONFIG, 'cli'))
assert tools == ['skills'], tools
from model_tools import _select_tool_names
assert _select_tool_names(tools, None, True) == {'skills_list', 'skill_view', 'skill_manage'}
from tools.skills_tool import skill_view
loaded = skill_view('omics-study-design')
assert 'confounded' in loaded, loaded
instance = SciCLI(toolsets=tools)
assert instance._init_agent()
for prompt in ('hello omics', 'continue omics'):
    result = instance.agent.run_conversation(prompt, conversation_history=instance.conversation_history,
                                             task_id=instance.session_id)
    assert not result.get('failed'), result
    assert result['final_response'] == 'Omics fixture reply', result
    instance.conversation_history = result['messages']
instance.agent.close()
print('OMICS_FRESH_PROCESS_OK')
'''
        result = subprocess.run([sys.executable, "-c", script], cwd=home / "workspace", env=env,
                                text=True, capture_output=True, timeout=90)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "OMICS_FRESH_PROCESS_OK" in result.stdout
        requests = [r["body"] for r in server.requests if any(
            m.get("role") == "system" and "You are the Omics coordinator" in str(m.get("content"))
            for m in r["body"].get("messages", []))]
        assert len(requests) >= 2
        assert all(r.get("tools") for r in requests)
        prefixes = [[m for m in r["messages"] if m["role"] == "system"] for r in requests]
        assert prefixes[0] == prefixes[1]
        assert "Omics coordinator" in str(prefixes[0])
        assert "private main history" not in str(requests)

        db = SessionDB(home / "state.db")
        try:
            sessions = db.search_sessions(source="cli", limit=1)
            assert sessions
            session_id = sessions[0]["id"]
        finally:
            db.close()
        # Repeat direct and picker activation: no setup questionnaire; resume the stored session.
        for source, command, expected in ((root, "/activate omics", "omics"),
                                           (home, "/activate main", "default"),
                                           (other, "/activate omics", "omics")):
            ui.choose.reset_mock(side_effect=True)
            with profile_scope(source):
                instance = cli_fixture()
                activate(instance, command, ui)
                assert instance._pending_relaunch[2] == expected
                if expected == "omics":
                    assert instance._pending_relaunch[-2:] == ["--resume", session_id]
                ui.choose.assert_not_called()
        assert before == {name: (root / name).read_bytes() for name in before}


@pytest.mark.parametrize("case", ["cancel", "busy", "noninteractive", "conflict", "write_failure", "missing_model"])
def test_setup_failures_do_not_publish_or_overwrite(root, monkeypatch, case):
    from sci_cli.config import atomic_config_replace
    from sci_cli.profiles import create_profile
    from sci_cli.science_profile_commands import activate
    from sci_cli.skill_add import Cancelled
    home = root / "profiles" / "omics"
    ui = SimpleNamespace(show=Mock(), choose=Mock(return_value="Create Omics"))
    cli = cli_fixture()
    setups = {
        "cancel": lambda: setattr(ui.choose, "side_effect", Cancelled()),
        "busy": lambda: setattr(cli, "_agent_running", True),
        "noninteractive": lambda: setattr(cli._app, "is_running", False),
        "conflict": lambda: create_profile("omics", no_skills=True, no_alias=True),
        "write_failure": lambda: monkeypatch.setattr("sci_cli.profile_distribution.write_manifest",
            Mock(side_effect=OSError("fixture write failure"))),
        "missing_model": lambda: atomic_config_replace(root / "config.yaml", {}),
    }
    setups[case]()
    existing = (home / "SOUL.md").read_bytes() if home.is_dir() else None
    before = (root / "config.yaml").read_bytes()
    activate(cli, '/ACTIVATE "Omics" profile', ui)
    if case == "conflict":
        assert (home / "SOUL.md").read_bytes() == existing
        assert not (home / "distribution.yaml").exists()
        assert "opened unchanged" in str(ui.show.call_args_list)
        ui.choose.assert_not_called()
    elif case == "missing_model":
        assert home.exists()
        assert "once model authentication is available" in str(ui.show.call_args_list)
        from sci_cli.omics_starter import startup_notice
        assert "/login" in startup_notice(home)
    else:
        assert not home.exists()
        assert not hasattr(cli, "_pending_relaunch")
        assert not list(home.parent.glob(".omics.staging-*"))
    assert (root / "config.yaml").read_bytes() == before
