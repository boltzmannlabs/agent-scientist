"""CLI entry point available even when the Boltzmann runtime plugin is disabled."""

import json


def result_display(message):
    """Style the printable setup receipt without interpreting account text as markup."""
    from rich.text import Text
    from sci_cli.skin_engine import get_active_skin

    skin = get_active_skin()
    text = Text(message, style=skin.get_color("banner_text"))
    background = skin.get_color("account_bg")
    surface = f" on {background}" if background else ""
    account = False
    offset = 0
    for line in message.splitlines(keepends=True):
        if "✓ Boltzmann account" in line and line.startswith("╭"):
            account = True
        if account:
            end = offset + len(line.rstrip("\n"))
            outline = skin.get_color("account_border", skin.get_color("ui_ok")) + surface
            text.stylize(skin.get_color("banner_text") + surface, offset, end)
            if line.startswith(("╭", "╰")):
                text.stylize(outline, offset, end)
            elif line.startswith("│"):
                text.stylize(outline, offset, offset + 1)
                text.stylize(outline, end - 1, end)
            if "✓ Boltzmann account" in line or "Successfully authenticated" in line:
                text.stylize(f"bold {skin.get_color('ui_ok')}" + surface, offset, end)
            for label in ("Email:", "Credits:", "Frozen credits:"):
                position = line.find(label)
                if position >= 0:
                    text.stylize(skin.get_color("hint_text", skin.get_color("banner_dim")), offset + position, offset + position + len(label))
                    value_color = skin.get_color("banner_text" if label == "Email:" else "banner_title")
                    text.stylize(f"bold {value_color}", offset + position + len(label), end - 1)
            if line.startswith("╰"):
                account = False
        offset += len(line)
    return text


def _saved(message):
    return any(line.startswith("[add_boltzmann] SAVED.") for line in message.splitlines())


def run(cli, raw_args, *, ui=None, report=None):
    def finish(message):
        if report is not None:
            report(message)
        return message

    from sci_constants import get_sci_home
    from sci_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
    from sci_cli.science_profiles import MANIFEST, config_digest
    from sci_cli.science_profile_approval import approval_record, require_approval
    from sci_cli.config import read_user_config_raw
    from plugins.boltzmann.onboarding import add_boltzmann, enable_toolset

    words = raw_args.strip().split()
    if any(word not in {"--now", "--replace"} for word in words):
        return finish("Usage: /add_boltzmann [--now] [--replace]. Enter keys only in the masked prompt.")
    if getattr(cli, "_agent_running", False):
        return finish("[add_boltzmann] Finish or cancel the current turn before configuring Boltzmann.")
    if ui is None and getattr(getattr(cli, "_app", None), "is_running", False):
        from sci_cli.skill_add import WizardUI
        ui = WizardUI(cli)
    home = get_sci_home()
    manifest = home / MANIFEST
    legacy = manifest.is_file()
    complete_setup = None
    if legacy:
        from sci_cli.science_profiles_sandbox import validate_runtime
        try:
            spec = validate_runtime(home)
            original = read_user_config_raw(home / "config.yaml")
            reviewed = manifest.read_bytes()
            require_approval(home, spec, original)
            if json.loads(reviewed).get("config_digest") != spec.config_digest:
                raise ValueError("Profile configuration changed during review; retry")
        except (OSError, ValueError) as exc:
            return finish(f"[add_boltzmann] Profile policy check failed: {exc}. Nothing was authorized.")
        from cli import _cprint
        _cprint("[add_boltzmann] This adds only the five authenticated Boltzmann operations to this isolated profile. "
                "Its local execution restrictions stay unchanged. External operations still require approval. "
                "Activation is next session only, including when --now is supplied.")
        raw_args = " ".join(word for word in words if word != "--now")

        def complete_setup():
            # Never approve pre-existing edits or concurrent configuration changes
            # as a side effect of adding one service.
            if manifest.read_bytes() != reviewed:
                raise ValueError("Profile permissions changed during authorization; retry.")

            def record(updated):
                from utils import atomic_json_write
                if manifest.read_bytes() != reviewed:
                    raise ValueError("Profile permissions changed while saving; execution remains blocked.")
                payload = json.loads(reviewed)
                payload.update(boltzmann_enabled=True, config_digest=config_digest(updated),
                               config_review=approval_record(updated))
                atomic_json_write(manifest, payload)

            enable_toolset(expected_config=original, after_save=record)

    manager = get_plugin_manager()
    manager._cli_ref = cli
    ctx = PluginContext(PluginManifest(name="boltzmann"), manager)
    from plugins.boltzmann.auth import current_key
    from sci_cli.skill_add import Cancelled
    reuse = False
    try:
        if current_key() and "--replace" not in words and ui is not None:
            choice = ui.choose("A Boltzmann key is saved for this profile (value hidden).", [
                "Verify existing key", "Enter a replacement key", "Cancel"])
            if choice == "Cancel":
                return finish("[add_boltzmann] CANCELLED. Existing key and authorization are unchanged.")
            reuse = choice == "Verify existing key"
    except (Cancelled, KeyboardInterrupt, EOFError):
        return finish("[add_boltzmann] CANCELLED. Existing key and authorization are unchanged.")
    # Publish account details before another modal opens or /new closes this
    # runtime. The slash adapter supplies the terminal-safe renderer once.
    message = finish(add_boltzmann(ctx, raw_args, complete_setup=complete_setup, reuse_saved=reuse))
    if _saved(message) and "--now" not in words and ui is not None and getattr(getattr(cli, "_app", None), "is_running", False):
        try:
            choice = ui.choose("Boltzmann is saved. When should the tools become available?", [
                "Start a new conversation now", "Keep the current conversation"])
        except (Cancelled, KeyboardInterrupt, EOFError):
            return message
        if choice == "Start a new conversation now":
            cli._cmd_new("/new --yes")
    return message


def quick_setup_step(config, sci_home):
    """First quick-setup step; reload its writes before later setup savers run."""
    from types import SimpleNamespace
    from sci_cli import setup
    from sci_cli.callbacks import prompt_for_secret
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.plugins import get_plugin_manager
    from rich.console import Console

    class SetupUI:
        def choose(self, question, choices):
            return choices[setup.prompt_choice(question, list(choices), 0)]

    ui = SetupUI()
    choice = ui.choose("Boltzmann login — first setup step", [
        "Log in to Boltzmann", "Continue without Boltzmann", "Cancel setup"])
    if choice == "Cancel setup":
        raise KeyboardInterrupt()
    if choice == "Continue without Boltzmann":
        setup.print_info("Boltzmann skipped. You can connect later with /boltzmann_login or /add_boltzmann.")
        return
    cli = SimpleNamespace(agent=None)

    def capture_key(name, prompt, **kwargs):
        from plugins.boltzmann.authentication import PLATFORM_URL
        # Interactive CLI/TUI render this inside their transient secret panel.
        # Quick setup has no panel, so show it immediately before masked entry.
        print(f"\nGet your Boltzmann API key by logging in here:\n  {PLATFORM_URL}\n", flush=True)
        return prompt_for_secret(cli, name, prompt, **kwargs)

    cli._secret_capture_callback = capture_key
    with profile_scope(sci_home):
        manager = get_plugin_manager()
        previous_cli = manager._cli_ref
        try:
            while True:
                message = run(cli, "", ui=ui)
                Console(highlight=False).print(result_display(message))
                # This also preserves any reported partial writes after a failure.
                config.clear()
                config.update(setup.load_config())
                if _saved(message):
                    # Model/terminal setup holds this dict and saves it later.
                    # Reload so it cannot undo plugin enablement or exclusions.
                    return
                action = ui.choose("Boltzmann login did not complete.", [
                    "Retry login", "Continue without Boltzmann", "Cancel setup"])
                if action == "Cancel setup":
                    raise KeyboardInterrupt()
                if action == "Continue without Boltzmann":
                    return
        finally:
            manager._cli_ref = previous_cli
