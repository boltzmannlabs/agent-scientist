"""Observers see complete conversation permissions even when API schemas are deferred."""

import copy

from agent.api_request_hooks import ApiRequestHooksMixin
from agent.turn_api_request import _fire_pre_api_request_hook


def test_hook_scope_preserves_deferred_permissions_without_mutating_request_or_prompt(monkeypatch):
    class Agent(ApiRequestHooksMixin):
        session_id = "fixture-session"
        platform = "cli"
        model = "fixture-model"
        provider = "custom"
        base_url = "http://fixture.invalid"
        api_mode = "chat_completions"
        max_tokens = 100
        tools = [{"type": "function", "function": {"name": "tool_call"}}]
        valid_tool_names = {"tool_call", "skill_view"}

    messages = [{"role": "system", "content": "byte-stable cached prefix"},
                {"role": "user", "content": "Inspect my accepted job"}]
    request = {"messages": messages, "tools": [{"type": "function", "function": {"name": "tool_call"}}]}
    original = copy.deepcopy((messages, request, Agent.tools))
    events = []
    monkeypatch.setattr("sci_cli.lifecycle.has_hook", lambda name: True)
    monkeypatch.setattr("sci_cli.lifecycle.invoke_hook", lambda name, **kwargs: events.append((name, kwargs)))
    monkeypatch.setattr(
        "agent.tool_executor._tool_search_scoped_names",
        lambda agent: frozenset({"boltzmann_status", "boltzmann_download"}),
    )
    _fire_pre_api_request_hook(Agent(), request, messages, [], messages=messages,
                              original_user_message="Inspect my accepted job", approx_tokens=30,
                              total_chars=90, retry_count=0, api_call_count=1, api_request_id="attempt",
                              api_start_time=0, effective_task_id="task", turn_id="turn")
    assert len(events) == 1
    assert set(events[0][1]["available_tool_names"]) == {
        *Agent.valid_tool_names, "boltzmann_status", "boltzmann_download"
    }
    assert events[0][1]["request"]["body"]["tools"] == request["tools"]
    assert (messages, request, Agent.tools) == original
