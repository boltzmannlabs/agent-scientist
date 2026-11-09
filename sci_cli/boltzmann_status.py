"""Read-only account verification using the active profile's Boltzmann login."""

from rich.panel import Panel
from rich.text import Text


def status_panel():
    from plugins.boltzmann.auth import available, current_key
    from plugins.boltzmann.nodeapi_helpers import authenticate_api_key
    from sci_constants import get_sci_home, profile_name_for_home
    from sci_cli.skin_engine import get_active_skin

    skin = get_active_skin()
    home = get_sci_home()
    name = profile_name_for_home(home)
    label = "main (default)" if name == "default" else name or "custom SCI_HOME"
    body = Text(style=skin.get_color("banner_text"))

    def field(name, value):
        body.append(name + ": ", style=f"bold {skin.get_color('banner_title')}")
        body.append(str(value) + "\n")

    field("Profile", label)
    key = current_key()
    if not key:
        field("Status", "Not logged in — no Boltzmann key saved for this profile.")
        body.append("Run /boltzmann_login to sign in.")
    elif not available():
        field("Status", "Not logged in — a key is saved, but profile authorization is missing or invalid.")
        body.append("Run /boltzmann_login and verify the existing key.")
    else:
        verification = authenticate_api_key(key)
        # Do not display the old account if another command rotated/revoked
        # the credential while its verification request was in flight.
        if current_key() != key or not available():
            field("Status", "Login changed during verification. Run /boltzmann_status again.")
        elif not verification.authenticated:
            field("Status", "Verification failed — current login could not be confirmed.")
            body.append(verification.message)
        else:
            field("Status", "Logged in — verified with Boltzmann.")
            field("Email", verification.email or "Not provided by the service")
            for label, value in (("Available credits", verification.credits),
                                 ("Frozen credits", verification.frozen_credits)):
                field(label, f"{value:,.2f}" if value is not None else "Not provided by the service")
    return Panel(body, title=Text("Boltzmann status", style=f"bold {skin.get_color('banner_title')}"),
                 border_style=skin.get_color("banner_border"),
                 style=f"{skin.get_color('banner_text')} on {skin.get_color('terminal_elevated')}",
                 expand=False)


def run(cli, command):
    if len(command.split()) != 1:
        cli._console_print(Text("Usage: /boltzmann_status (checks the active profile)."))
        return
    cli._console_print(Text("Checking Boltzmann status for the active profile…"))
    try:
        panel = status_panel()
    except (OSError, RuntimeError, ValueError):
        cli._console_print(Text("Could not read Boltzmann status for this profile. No login settings were changed."))
        return
    cli._console_print(panel)
