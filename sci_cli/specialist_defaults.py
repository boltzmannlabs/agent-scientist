"""Reviewed baseline for CLI file, Python and delegation capabilities."""
BASELINE_TOOLSETS = ('terminal', 'file', 'skills', 'code_execution', 'delegation')


def enable_baseline(config):
    """One-time migration/explicit repair; later opt-outs remain authoritative."""
    from sci_cli.toolset_validation import parse_platform_toolsets_value
    from agent.skill_utils import parse_config_string_list
    platforms = config.get('platform_toolsets') or {}
    raw = platforms.get('cli')
    changed = False
    if raw is not None:
        selected = parse_platform_toolsets_value(raw)
        if selected is None:
            raise ValueError('CLI toolsets must be a YAML list before applying specialist defaults.')
        if 'sci-cli' not in selected:
            missing = [name for name in BASELINE_TOOLSETS if name not in selected]
            if missing:
                config.setdefault('platform_toolsets', {})['cli'] = [*selected, *missing]
                changed = True
    agent = config.get('agent') or {}
    disabled = parse_config_string_list(agent.get('disabled_toolsets'))
    remaining = [name for name in disabled if name not in BASELINE_TOOLSETS]
    if remaining != disabled:
        config.setdefault('agent', {})['disabled_toolsets'] = remaining
        changed = True
    return changed
