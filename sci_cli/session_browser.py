"""Profile-local conversation picker and safe session handoff."""

from sci_cli.skill_add import WizardUI, Cancelled


def require_empty_input_queue(cli):
    """Pending prompts belong to the current conversation until run or explicitly removed."""
    from queue import Queue
    pending = getattr(cli, "_pending_input", None)
    if isinstance(pending, Queue) and not pending.empty():
        raise ValueError("Queued messages belong to this conversation. Let them finish, or use "
                         "/queue list and /queue clear before switching conversations or profiles.")


def flush_before_switch(cli):
    """A failed flush must leave the user in their current conversation."""
    if getattr(cli, "_agent_running", False) or getattr(cli, "_science_running_worker", None):
        raise ValueError("Finish or explicitly cancel the running work before switching.")
    require_empty_input_queue(cli)
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
