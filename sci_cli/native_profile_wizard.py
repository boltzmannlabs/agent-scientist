"""Science-friendly native profile creation, with no separate prepare command."""

from pathlib import Path
import shlex
import threading

from sci_cli.skill_add import WizardUI, Cancelled
from sci_cli.native_profile_review import review_workspace
from sci_cli.science_profiles_ui import PERSONA
from sci_cli.science_profiles_catalog import science_skill_choices, select_science_items


def choose_sources(ui, initial=()):
    from sci_cli.science_profiles import Source, local_source
    from urllib.parse import urlsplit
    result = list(initial)
    while True:
        choices = ["Done", "Add file/folder", "Add URL"] + (["Remove a source"] if result else []) + ["Cancel"]
        choice = ui.choose(f"Optional sources: {len(result)} added", choices)
        if choice == "Done":
            return result
        if choice == "Remove a source":
            labels = {f"{i + 1}. {s['location']} [{s['access']}]": i for i, s in enumerate(result)}
            result.pop(labels[ui.choose("Remove reference/access (original files stay untouched)", [*labels, "Cancel"])])
            continue
        raw = ui.ask("Source path or public HTTPS URL:").strip().strip('"').strip("'")
        source = Source(raw)
        path = local_source(source)
        if path is None and (urlsplit(raw).query or urlsplit(raw).fragment):
            raise ValueError("Use a public reference URL without a query string or fragment; do not save signed/private links.")
        if choice == "Add URL" and path is not None:
            raise ValueError("Expected a public HTTPS URL.")
        if choice == "Add file/folder" and path is None:
            raise ValueError("Expected a local file or folder.")
        ui.show("Adding a source does not read, download, index or upload it. "
                "A read-local grant permits local processing only; model-visible content needs the third choice. "
                "These are agent instructions, not filesystem sandbox rules.")
        modes = {"Reference only": "reference", "Allow local reading/processing": "read-local",
                 "Allow relevant contents to selected model": "model"}
        mode = modes[ui.choose("Source access", [*modes, "Cancel"])]
        result.append({"location": str(path) if path else raw, "access": mode})


def create_wizard(cli, command, ui=None, source_home=None):
    from sci_cli.profiles import _get_default_sci_home, validate_profile_name, get_profile_dir
    from sci_cli.config import read_user_config_raw, is_managed
    from sci_cli.native_profile_creation import create_native, reviewed_model_seed
    from sci_cli.native_profile_environment import prepare_environment
    from sci_cli.native_profile_services import choose_services
    from sci_cli.native_profile_session import request_switch
    ui = ui or WizardUI(cli)
    saved = None
    cli._science_cancel = threading.Event()
    try:
        if is_managed():
            raise ValueError("Profile creation is administrator-managed in this installation.")
        args = shlex.split(command)[1:]
        if len(args) > 1:
            raise ValueError('Usage: /Create_profile ["profile-name"]')
        home = Path(source_home) if source_home else _get_default_sci_home()
        original = read_user_config_raw(home / "config.yaml")
        reviewed_model_seed(original, source_home=home)
        from sci_cli.science_profiles import MANIFEST, read_spec
        legacy = (home / MANIFEST).is_file()
        service_home = _get_default_sci_home() if legacy else home
        service_config = read_user_config_raw(service_home / "config.yaml")
        initial_sources = []
        if legacy:
            old = read_spec(home)
            initial_sources = [{"location": s.location, "access": "reference"} for s in old.sources]
            ui.show("Migration creates a NEW native profile. The old project's files, credentials, history and "
                    "isolation settings stay untouched. The replacement uses main's reviewed backend, starts new "
                    "history, and keeps old sources as references only. Review any change from Docker isolation carefully.")
            ui.choose("Approve reviewing this separate replacement?", ["Review replacement", "Cancel"])
        name = args[0] if args else ui.ask("Name your science profile:")
        validate_profile_name(name)
        if name in {"default", "main"}:
            raise ValueError("Choose a new name, not main/default.")
        while get_profile_dir(name).exists():
            ui.choose(f"{name} already exists; nothing will be overwritten.", ["Rename", "Cancel"])
            name = ui.ask("New profile name:")
            validate_profile_name(name)
            if name in {"default", "main"}:
                raise ValueError("Choose a new name, not main/default.")
        ui.show(f"Source profile: {home}. Only reviewed skills, services and approved credentials will be copied. "
                "LLM login uses the existing shared authentication mechanism.")
        labels, skill_sources = science_skill_choices(home)
        skills = select_science_items(ui, "Scientific skills", labels)
        with review_workspace(ui, prefix="sci-profile-review-") as scratch:
            services = choose_services(cli, ui, service_home, service_config, scratch)
            sources = choose_sources(ui, initial_sources)
            terminal = prepare_environment(service_config, get_profile_dir(name), ui, cli._science_cancel)
            ui.show(f"Create profile {name}?\nSkills: {', '.join(skills) or 'none'}\n"
                    "Tools: " + (", ".join(f"{s.name} ({len(s.tools)} tools; credentials: {s.credential_choice}, values hidden)"
                                         for s in services) or "none") +
                    f"\nEnvironment: {terminal['backend']}\nWorkspace: {get_profile_dir(name) / 'workspace'}\n"
                    f"Sources/access: {sources or 'none'}\n"
                    "Selected skill instructions will be available. Specialist scientific dependencies are not automatically installed. "
                    "Routing/collaboration remains opt-in; original profile settings and conversation stay unchanged.")
            ui.choose(f'Create profile “{name}”?', ["Create profile", "Cancel"])
            if cli._science_cancel.is_set():
                raise Cancelled()
            if read_user_config_raw(home / "config.yaml") != original:
                raise ValueError("Source configuration changed during review; retry with the current settings.")
            if read_user_config_raw(service_home / "config.yaml") != service_config:
                raise ValueError("Service configuration changed during review; retry with the current settings.")
            saved = create_native(name, home, skills, services, sources, terminal, PERSONA,
                                  skill_sources=skill_sources)
        ui.show(f"Created {name}: {saved}. Selected capabilities enabled; no --prepare command needed. "
                "Scientific software requirements still apply. No research jobs ran during setup.")
        if ui.choose("Activate the new profile now?", ["Stay in current profile", "Activate now", "Cancel"]) == "Activate now":
            request_switch(cli, name, ui)
    except (Cancelled, KeyboardInterrupt, EOFError):
        ui.show(f"Profile {saved.name} was created; activation cancelled." if saved else
                "Profile creation cancelled. No profile published. Approved downloads or remote OAuth grants may remain.")
    except Exception as exc:
        from sci_cli.mcp_config import redact_mcp_probe_text
        ui.show((f"Profile {saved.name} was saved, but activation failed: " if saved else "Profile creation failed: ") +
                redact_mcp_probe_text(str(exc)) + ". No automatic retries or unexplained background work. "
                "Approved downloads or remote OAuth grants may remain.")
    finally:
        cli._science_cancel = None
