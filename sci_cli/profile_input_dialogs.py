"""Input dialogs belong to the interactive CLI, not a profile's science services."""


def interactive_toolsets(enabled, disabled):
    """Prepare a fresh conversation without rewriting saved profile permissions.

    Call only where a user can answer the CLI's clarify callback. Headless runs
    and delegated workers retain their own tool selection and delivery policy.
    """
    selected = None if enabled is None else list(dict.fromkeys([*enabled, "clarify"]))
    excluded = [name for name in (disabled or []) if name != "clarify"]
    return selected, excluded
