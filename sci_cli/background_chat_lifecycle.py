"""Interactive task ownership: interrupt, disconnect, and stop are distinct actions."""

import os
import time


def show_running_exit_choices(cli):
    """Reuse the existing nonblocking selection modal on the UI thread."""
    if not getattr(cli, "_background_managed", False):
        return False
    cli._capture_modal_input_snapshot()
    cli._slash_confirm_state = {
        "title": "Task is still running",
        "detail": "Choose what happens to the current task. Esc keeps it running here.",
        "choices": [
            ("cancel_task", "Cancel task", "Stop the current task and stay in SCI"),
            ("background", "Run in background", "Disconnect this terminal; the task continues"),
            ("exit", "Exit", "Stop the current task and exit SCI"),
        ],
        "selected": 0,
        "on_choice": lambda choice: finish_exit_choice(cli, choice),
    }
    cli._slash_confirm_deadline = time.monotonic() + 3600
    cli._invalidate()
    return True


def finish_exit_choice(cli, choice):
    from agent.interrupt_compat import request_hard_interrupt
    from sci_cli.background_chats import detach_cli
    cli._restore_modal_input_snapshot()
    if choice == "background":
        detach_cli(cli)
    elif choice in ("cancel_task", "exit"):
        if getattr(cli, "agent", None) and getattr(cli, "_agent_running", False):
            request_hard_interrupt(cli.agent)
        if choice == "exit":
            cli._should_exit = True
            cli._app.exit()


def navigate(cli):
    """Move only the attached viewer; keep the departing worker and prompt intact."""
    from sci_cli.background_chats import request
    args, home = cli._pending_relaunch, cli._pending_profile_home
    cli._pending_relaunch = None
    cli._pending_profile_home = None
    request("navigate", pid=os.getpid(), args=args, target_home=home)
