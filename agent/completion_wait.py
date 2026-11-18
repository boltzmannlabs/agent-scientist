"""Wait policy for adapters that synthesize chunks from a complete JSON response."""


def waits_for_complete_response(agent):
    # Read the adapter's declared capability, not an inferred provider/model name.
    return getattr(type(getattr(agent, 'client', None)), 'completion_response_mode', None) == 'complete'


def complete_response_stale_timeout(agent, *, streaming=True):
    import os
    from sci_cli.timeouts import get_provider_stale_timeout
    from agent.chat_completion_helpers import cap_to_run_budget, _stream_env_stale_base

    explicit = get_provider_stale_timeout(agent.provider, agent.model)
    if explicit is not None:
        return explicit
    if not streaming and 'SCI_API_CALL_STALE_TIMEOUT' in os.environ:
        value = float(os.environ['SCI_API_CALL_STALE_TIMEOUT'])
        return value if value > 0 else float('inf')
    base, explicit_env = _stream_env_stale_base()
    return base if explicit_env else cap_to_run_budget(agent, float('inf'))
