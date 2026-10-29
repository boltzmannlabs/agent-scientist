"""CLI entry point available even when the Boltzmann runtime plugin is disabled."""

import json


def run(cli, raw_args):
    from sci_constants import get_sci_home
    from sci_cli.plugins import PluginContext, PluginManifest, get_plugin_manager
    from sci_cli.science_profiles import MANIFEST, config_digest
    from sci_cli.science_profile_approval import approval_record, require_approval
    from sci_cli.config import read_user_config_raw
    from plugins.boltzmann.onboarding import add_boltzmann, enable_toolset

    words = raw_args.strip().split()
    if any(word not in {"--now", "--replace"} for word in words):
        return "Usage: /add_boltzmann [--now] [--replace]. Enter keys only in the masked prompt."
    if getattr(cli, "_agent_running", False):
        return "[add_boltzmann] Finish or cancel the current turn before configuring Boltzmann."
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
            return f"[add_boltzmann] Profile policy check failed: {exc}. Nothing was authorized."
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
    return add_boltzmann(ctx, raw_args, complete_setup=complete_setup)
