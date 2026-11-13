"""Fit summary requests for small helpers without changing large-window cadence."""
from agent.model_metadata import estimate_tokens_rough


def fit_summary_prompt(compressor, prompt, content, summary_budget, rebuild):
    window = getattr(compressor, "_summary_context_length", None) or compressor.context_length
    if window >= compressor._MIN_TRIGGER_TOKENS:
        return prompt
    # Reserve the requested summary, lean-mode session log, and framing/estimator
    # headroom. Do not impose a wire max_tokens cap that could truncate a summary.
    from agent.context_compressor import _LEAN_SESSION_LOG_BUDGET_TOKENS
    output = summary_budget + (_LEAN_SESSION_LOG_BUDGET_TOKENS if compressor.tail_mode == "lean" else 0)
    budget = window - max(window // 4, output) - 1024
    if budget <= 0 or estimate_tokens_rough(rebuild("")) > budget:
        raise ValueError("Compression instructions and retained summary exceed the helper's input budget; choose a larger compression model.")
    for _ in range(8):
        size = estimate_tokens_rough(prompt)
        if size <= budget:
            return prompt
        # Only summarize a bounded excerpt of the turn data. The prompt's
        # instructions, previous summary, focus and memory stay intact.
        target = max(0, int(len(content) * budget / max(size, 1) * 0.8))
        content = compressor._bound_oversized_record(content, target) if target else ""
        prompt = rebuild(content)
    raise ValueError("Compression input could not fit the helper's context window; no summary request was sent.")
