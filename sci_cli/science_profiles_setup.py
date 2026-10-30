"""Optional, explicitly approved setup for an already saved science project."""

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
import threading

from sci_cli.science_profiles import MANIFEST, config_digest, read_spec, reviewed_remote_config
from sci_cli.science_profiles_catalog import select_service_tools, service_required_tools


def prepare_profile(cli, home, ui):
    from sci_cli.config import atomic_config_replace, read_user_config_raw
    from sci_cli.science_profiles_sandbox import validate_runtime
    from utils import atomic_json_write
    spec = validate_runtime(home)
    initial_spec = asdict(spec)
    original = read_user_config_raw(home / "config.yaml")
    config = deepcopy(original)
    cli._science_cancel = threading.Event()
    try:
        choices = ["Done"]
        if spec.setup_pending:
            choices.append("Prepare local execution")
        choices.extend(f"Connect {server}" for server in spec.pending_tools)
        action = ui.choose("Optional setup for your saved project. Done keeps it as-is.", (*choices, "Cancel"))
        if action == "Done":
            return False
        if action == "Prepare local execution":
            from sci_cli.science_profiles_environment import choose_environment
            image = choose_environment(home, spec.skills, spec.mcp_tools, ui, cli._science_cancel)
            spec.image, spec.setup_pending = image, False
            config["terminal"]["docker_image"] = image
            config["platform_toolsets"]["cli"] = ["terminal", "file", "skills", *spec.mcp_tools]
            if spec.sources and not spec.allow_llm_sources:
                allow = ui.choose("Allow this profile to read your saved local sources and send their contents to its LLM? URLs remain references, not automatic downloads.",
                                  ("Keep references only", "Allow source processing", "Cancel"))
                if allow == "Allow source processing":
                    from sci_cli.science_profiles import regular_files
                    for source in spec.sources:
                        if not source.location.startswith("https://"):
                            path = Path(source.location)
                            if path.is_symlink() or str(path.resolve(strict=True)) != source.location:
                                raise ValueError("A source moved or became a symlink. Source access was not enabled.")
                            regular_files(path)
                    spec.allow_llm_sources = True
                    config["terminal"]["docker_volumes"] += [f"{s.location}:/sources/{i}:ro"
                        for i, s in enumerate(spec.sources) if not s.location.startswith("https://")]
        else:
            server = action.removeprefix("Connect ")
            source = Path(spec.capability_source_home)
            cfg = read_user_config_raw(source / "config.yaml").get("mcp_servers", {}).get(server)
            try:
                safe = reviewed_remote_config(server, cfg)
            except ValueError as exc:
                ui.show(f"{server}: Setup required — {exc}\nYour profile and tool selections are saved. "
                        "This wizard cannot yet isolate host/stdio services or transfer service credentials. "
                        "Prepare a supported HTTPS connection through /Add_mcp in the source profile, then try setup again. "
                        "No host process was launched and no service permissions were granted.")
                return False
            ui.show(f"Connect {server} at {safe['url']}. This performs handshake and tool discovery only, not scientific work.")
            ui.choose("Approve this service connection check?", ("Check connection", "Cancel"))
            from sci_cli.mcp_config import _probe_single_server
            discovered = dict(_probe_single_server(server, safe))
            wanted = spec.pending_tools[server]
            if wanted:
                missing = set(wanted) - set(discovered) - set(service_required_tools(server))
                if missing:
                    ui.show(f"Previously selected tools are unavailable: {', '.join(sorted(missing))}. Review a new explicit selection.")
                    wanted = []
            names = select_service_tools(ui, server, discovered, selected=wanted or None, verified=True)
            if not names:
                ui.show("No tools selected. Project unchanged; service remains Setup required.")
                return False
            ui.show(f"Explicit allowed tools: {', '.join(names)}. Future server tools are not automatically granted.")
            spec.mcp_tools[server] = names
            spec.pending_tools.pop(server)
            config.setdefault("mcp_servers", {})[server] = {**safe, "tools": {"include": names, "resources": False, "prompts": False}}
            config["platform_toolsets"]["cli"].append(server)
        ui.choose("Save this setup? The next project turn starts a NEW project conversation; the main conversation is unchanged.",
                  ("Save setup", "Cancel"))
        if cli._science_cancel.is_set():
            from sci_cli.skill_add import Cancelled
            raise Cancelled()
        if read_user_config_raw(home / "config.yaml") != original or asdict(read_spec(home)) != initial_spec:
            raise ValueError("Profile settings changed during setup. Nothing was overwritten; retry to review them.")
        # Close only this CLI's affected worker, never change an active cached prefix.
        for key, worker in list(getattr(cli, "_science_workers", {}).items()):
            if worker.home == home:
                worker.close()
                del cli._science_workers[key]
        spec.config_digest = config_digest(config)
        from sci_cli.science_profile_approval import approval_record
        spec.config_review = approval_record(config)
        atomic_config_replace(home / "config.yaml", config)
        try:
            atomic_json_write(home / MANIFEST, asdict(spec))
        except Exception as exc:
            raise RuntimeError("Configuration saved but the setup receipt failed. Execution is blocked by the integrity check; the profile was not reported ready.") from exc
        ui.show("Setup saved. Selected service calls still require approval; local software checks are not scientific validation.")
        return True
    finally:
        cli._science_cancel = None
