"""Turn summaries report only usage returned by the provider."""

from types import SimpleNamespace


def test_turn_usage_report_sums_provider_counts_and_cached_subsets():
    from agent.turn_usage import capture_usage_counters, format_turn_usage, usage_since

    agent = SimpleNamespace(
        session_prompt_tokens=0,
        session_input_tokens=0,
        session_output_tokens=0,
        session_cache_read_tokens=0,
        session_cache_write_tokens=0,
        session_reasoning_tokens=0,
        session_api_calls=0,
        session_usage_reported_calls=0,
    )
    before = capture_usage_counters(agent)
    agent.session_prompt_tokens += 120
    agent.session_input_tokens += 70
    agent.session_cache_read_tokens += 40
    agent.session_cache_write_tokens += 10
    agent.session_output_tokens += 18
    agent.session_reasoning_tokens += 6
    agent.session_api_calls += 2
    agent.session_usage_reported_calls += 2

    report = usage_since(agent, before)
    assert report == {
        "status": "reported",
        "input_tokens": 120,
        "uncached_input_tokens": 70,
        "output_tokens": 18,
        "cache_read_tokens": 40,
        "cache_write_tokens": 10,
        "reasoning_tokens": 6,
        "total_tokens": 138,
        "api_calls": 2,
        "reported_calls": 2,
    }
    assert format_turn_usage(report) == (
        "Token usage (provider-reported): input 120 · output 18 · total 138 · "
        "cached input read 40 / write 10"
    )


def test_turn_usage_report_marks_missing_provider_usage_instead_of_estimating():
    from agent.turn_usage import capture_usage_counters, format_turn_usage, usage_since

    agent = SimpleNamespace(
        session_prompt_tokens=0,
        session_input_tokens=0,
        session_output_tokens=0,
        session_cache_read_tokens=0,
        session_cache_write_tokens=0,
        session_reasoning_tokens=0,
        session_api_calls=0,
        session_usage_reported_calls=0,
    )
    before = capture_usage_counters(agent)
    agent.session_api_calls = 2
    agent.session_usage_reported_calls = 1
    agent.session_prompt_tokens = 120
    agent.session_input_tokens = 100
    agent.session_cache_read_tokens = 20
    agent.session_output_tokens = 18

    report = usage_since(agent, before)

    assert report["status"] == "partial"
    assert report["api_calls"] == 2
    assert report["reported_calls"] == 1
    assert report["input_tokens"] == 120
    assert report["output_tokens"] == 18
    assert format_turn_usage(report) == (
        "Token usage (partial; counts returned for 1/2 model calls): input 120 · output 18 · "
        "total 138 · cached input read 20 / write 0 · calls without usage data are excluded"
    )


def test_turn_usage_report_says_unavailable_when_provider_omits_counts():
    from agent.turn_usage import format_turn_usage

    assert format_turn_usage({"status": "unavailable"}) == (
        "Token usage unavailable: the provider returned no token counts."
    )
