"""Profile-local conversation picker and safe session handoff."""

from sci_cli.skill_add import WizardUI, Cancelled


def flush_before_switch(cli):
    """A failed flush must leave the user in their current conversation."""
    if getattr(cli, "_agent_running", False) or getattr(cli, "_science_running_worker", None):
        raise ValueError("Finish or explicitly cancel the running work before switching.")
    agent = getattr(cli, "agent", None)
    if agent and getattr(cli, "conversation_history", None):
        agent._flush_messages_to_session_db(cli.conversation_history,
                                            conversation_history=cli.conversation_history)


def pick_session(cli):
    from sci_cli.session_picker import choose_session
    ui = WizardUI(cli)
    if not getattr(cli, "_session_db", None):
        ui.show("Saved conversation store unavailable; current session unchanged.")
        return None
    try:
        selected = choose_session(cli)
    except (Cancelled, KeyboardInterrupt, EOFError):
        selected = None
    if selected is None:
        ui.show("Conversation selection cancelled; current session unchanged.")
    return selected
