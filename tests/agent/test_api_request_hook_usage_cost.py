"""Behavior contract for provider-reported lifecycle usage cost."""

from types import SimpleNamespace

from agent.api_request_hooks import ApiRequestHooksMixin


class _HookHarness(ApiRequestHooksMixin):
    provider = "custom"
    api_mode = "chat_completions"


def test_usage_hook_exposes_only_numeric_provider_reported_cost():
    response = SimpleNamespace(
        usage={
            "prompt_tokens": 11,
            "completion_tokens": 7,
            "total_tokens": 18,
            "cost": 0.000123,
            "provider_private_metadata": {"should_not": "escape"},
        }
    )

    summary = _HookHarness()._usage_summary_for_api_request_hook(response)

    assert summary["provider_cost_usd"] == 0.000123
    assert "provider_private_metadata" not in summary
