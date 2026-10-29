"""Rename through the existing profile-scoped title service."""


def rename(cli, command):
    from sci_cli.skill_add import Cancelled, WizardUI

    ui = WizardUI(cli)
    parts = command.split(None, 1)
    title = parts[1].strip() if len(parts) > 1 else ""
    if not title:
        if getattr(cli, "_agent_running", False):
            ui.show('Use /rename <name> while the parent is running; no input prompt was opened.')
            return
        try:
            title = ui.ask("New conversation name (Cancel to keep the current name):")
        except Cancelled:
            ui.show("Rename cancelled. Conversation unchanged.")
            return
        if title.lower() == "cancel":
            ui.show("Rename cancelled. Conversation unchanged.")
            return
    if len(title) >= 2 and title[0] == title[-1] and title[0] in "\"'":
        title = title[1:-1]
    cli._cmd_title(f"/title {title}")
