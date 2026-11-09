"""Interactive dialogs are built in; science permissions and cached turns stay scoped."""

from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.fixture
def homes(tmp_path, monkeypatch):
    from sci_cli.config import atomic_config_replace
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    root = tmp_path / ".sci"
    monkeypatch.setenv("SCI_HOME", str(root))
    result = [root, root / "profiles/a", root / "profiles/b"]
    for home in result:
        home.mkdir(parents=True)
        atomic_config_replace(home / "config.yaml", {
            "platform_toolsets": {"cli": ["file", "skills", "no_mcp"], "webhook": []},
            "agent": {"disabled_toolsets": ["clarify", "terminal"]},
            "mcp_servers": {"unselected": {"url": "https://example.invalid/mcp", "enabled": True}},
            "terminal": {"backend": "docker"}, "display": {"skin": "mono"}})
        for name, content in {".env": "FIXTURE_KEY=private\n", "SOUL.md": "Private persona",
                              "history.json": '[{"role":"user","content":"private"}]'}.items():
            (home / name).write_text(content)
    return result


def test_interactive_cli_boots_existing_profiles_with_dialogs_without_changing_permissions(homes, monkeypatch):
    import cli as cli_mod
    from model_tools import get_tool_definitions
    from sci_cli.config import read_user_config_raw
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.tools_config import _get_platform_tools
    from agent.secret_scope import is_multiplex_active, set_multiplex_active

    before = {p: p.read_bytes() for home in homes for p in home.iterdir() if p.is_file()}
    monkeypatch.setattr(cli_mod, "_prepare_deferred_agent_startup", lambda: None)
    monkeypatch.setattr("sci_cli.mcp_startup.ensure_mcp_discovery_before_agent_build", lambda **_: None)
    builds = []
    def construct(**kwargs):
        # Exercise real schema resolution, including tool-search assembly. No provider call.
        tools = get_tool_definitions(kwargs['enabled_toolsets'], kwargs['disabled_toolsets'], quiet_mode=True)
        agent = SimpleNamespace(tools=tools, _cached_system_prompt="frozen", kwargs=kwargs)
        builds.append(agent)
        return agent
    monkeypatch.setattr("run_agent.AIAgent", construct)
    previous = is_multiplex_active()
    set_multiplex_active(True)
    try:
        for home in (homes[0], homes[1], homes[2], homes[1]):
            with profile_scope(home):
                cfg = read_user_config_raw(home / 'config.yaml')
                cli = cli_mod.SciCLI(compact=True, toolsets=sorted(_get_platform_tools(cfg, 'cli')))
                cli.disabled_toolsets = list(cfg['agent']['disabled_toolsets'])
                selected, excluded = deepcopy(cli.enabled_toolsets), list(cli.disabled_toolsets)
                cli._session_db = object()
                cli._resumed = False
                cli.conversation_history = [{"role": "user", "content": home.name}]
                cli.finalize_preloaded_skills = lambda: None
                cli._install_tool_callbacks = lambda: None
                cli._ensure_tirith_security = lambda: None
                cli._ensure_runtime_credentials = lambda: True
                assert cli._init_agent()
                agent = cli.agent
                names = {t['function']['name'] for t in agent.tools}
                assert 'clarify' in names
                assert 'terminal' not in names
                assert not any(n.startswith(('boltzmann_', 'mcp_')) for n in names)
                assert agent.kwargs['clarify_callback'] == cli._clarify_callback
                assert 'unselected' not in agent.kwargs['enabled_toolsets']
                assert cli.enabled_toolsets == selected and cli.disabled_toolsets == excluded
                frozen = deepcopy(agent.tools), agent._cached_system_prompt, list(cli.conversation_history)
                count = len(builds)
                assert cli._init_agent()
                assert len(builds) == count and cli.agent is agent
                assert frozen == (agent.tools, agent._cached_system_prompt, cli.conversation_history)

                # Automation uses the saved selection and never gains an unanswerable modal.
                cli.agent = None
                cli._single_query_mode = True
                assert cli._init_agent()
                assert 'clarify' not in {t['function']['name'] for t in cli.agent.tools}
                assert cli.agent.kwargs['clarify_callback']([])['outcome'] == 'undelivered'
    finally:
        set_multiplex_active(previous)
    assert all(p.read_bytes() == data for p, data in before.items())


def test_restricted_profile_can_ask_without_gaining_execution(homes):
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.science_profile_permissions import install_gate
    from sci_cli.middleware import run_tool_execution_middleware
    from sci_cli.profile_input_dialogs import interactive_toolsets
    from model_tools import get_tool_definitions

    with profile_scope(homes[1]):
        enabled, disabled = interactive_toolsets(['skills'], ['clarify'])
        agent = SimpleNamespace(tools=get_tool_definitions(enabled, disabled, quiet_mode=True,
                                                          skip_tool_search_assembly=True))
        ask = Mock(side_effect=AssertionError('A question is not an external transfer'))
        gate = install_gate(agent, ask, allow_local=False)
        try:
            assert 'clarify' in agent.valid_tool_names
            execute = Mock(return_value='answered')
            assert run_tool_execution_middleware('clarify', {'questions': []}, execute) == 'answered'
            execute.assert_called_once()
            execute.reset_mock()
            assert 'permissions' in run_tool_execution_middleware('terminal', {}, execute)
            execute.assert_not_called()
            ask.assert_not_called()
        finally:
            gate.dispose()
