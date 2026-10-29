"""Profile activation and explicit routing consent; parent conversations stay intact."""

import shlex

from sci_cli.skill_add import WizardUI, Cancelled


def activate(cli, command, ui=None):
    from sci_cli.profiles import list_profile_names
    from sci_cli.native_profile_session import request_switch, profile_label
    ui = ui or WizardUI(cli, numbered_choices=False)
    try:
        args = shlex.split(command)[1:]
        if len(args) == 2 and args[1].lower() == "profile":
            args.pop()
        if not args:
            choices = {}
            for item in list_profile_names():
                label = "main" if item == "default" else item
                choices[label + (" — currently active" if label == profile_label() else "")] = item
            if "omics" not in choices and "omics — currently active" not in choices:
                choices["omics — set up coordinator"] = "omics"
            name = choices[ui.choose("Choose a profile", [*choices, "Cancel"])]
        elif len(args) == 1 and not args[0].startswith("--"):
            name = args[0]
        else:
            raise ValueError('Usage: /activate ["profile-name"] [profile]. New profiles need no --prepare.')
        # Setup must not create state while a turn is running or outside the REPL.
        if name.strip().lower() == "omics":
            name = "omics"
            if getattr(cli, "_agent_running", False) or getattr(cli, "_science_running_worker", None):
                raise ValueError("Finish or cancel the current turn before switching profiles.")
            if not getattr(getattr(cli, "_app", None), "is_running", False):
                raise ValueError("Profile activation requires the interactive CLI.")
            from sci_cli.omics_starter import ensure_omics
            ensure_omics(ui)
        request_switch(cli, name, ui)
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show("Activation cancelled. Current selection unchanged.")
    except Exception as exc:
        ui.show(f"Activation failed: {exc}. Current selection unchanged.")


def routing(cli, command, ui=None):
    """Session-local opt-in: no surprise routing just because a profile exists."""
    from sci_constants import sci_home_key
    from sci_cli.science_profiles import available_profiles
    ui = ui or WizardUI(cli)
    try:
        args = shlex.split(command)[1:]
        if args == ["off"]:
            cli._science_routing = None
            cli._science_routing_names = None
            ui.show("Automatic profile routing is off for this CLI.")
            return
        if args not in ([], ["on"]):
            raise ValueError("Usage: /profile_routing [on|off]")
        from sci_cli.science_profiles_catalog import select_science_items
        profiles = available_profiles()
        if not profiles:
            raise ValueError("Create a research profile with /Create_profile first.")
        names = select_science_items(ui, "Profiles allowed to route automatically in this CLI",
                                     {n: s.purpose for n, s in profiles.items()})
        if not names:
            ui.show("No profiles selected. Routing settings unchanged.")
            return
        opted = {n: profiles[n].purpose for n in names}
        from sci_cli.skill_add_draft import prepare_route
        route = prepare_route(cli)
        try:
            identity = (route.provider, route.model, route.endpoint)
        finally:
            route.close()
        ui.show(f"Router model: {identity[0]} / {identity[1]} at {identity[2]}. New user requests and opted-in profile purposes go to this model, without your earlier conversation or files.\nEligible profiles: {opted}\nMatching profiles can collaborate within approved sharing permissions; additional or sensitive data transfers require confirmation. Provider charges apply.")
        ui.choose("Enable automatic routing in this CLI?", ("Enable routing", "Cancel"))
        cli._science_routing = (sci_home_key(), cli.provider, cli.model, getattr(cli, "base_url", None))
        cli._science_router_identity = identity
        cli._science_routing_names = (sci_home_key(), tuple(names))
        ui.show("Automatic routing enabled. Manual activation takes priority. /profile_routing off disables routing.")
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show("Routing setup cancelled.")
    except Exception as exc:
        ui.show(f"Routing setup failed: {exc}")
