"""Explicit service selection and credential consent for native science profiles."""

from copy import deepcopy
from contextlib import contextmanager
import fnmatch
import hashlib
import json
import re
import threading
import time
from urllib.parse import urlsplit

from sci_cli.native_profile_creation import Service, profile_scope
from sci_cli.skill_add import Cancelled
from sci_cli.science_profiles_catalog import select_science_items, BOLTZMANN_WORKFLOW_TOOLS

ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


@contextmanager
def progress(ui, stage):
    from agent.memory_provider import spawn_context_thread
    stopped = threading.Event()
    start = time.monotonic()
    ui.show(f"[{stage}] Started. Waiting for the service; its timeout applies.")

    def report():
        while not stopped.wait(10):
            ui.show(f"[{stage}] {time.monotonic() - start:.0f}s elapsed. No research job has been submitted.")

    thread = spawn_context_thread(report, name="profile-setup-progress", daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join()
        ui.show(f"[{stage}] Attempt ended after {time.monotonic() - start:.1f}s.")


def catalog(home, config):
    from sci_cli.plugins_discovery import collect_directory_manifests, resolve_manifest_winners
    with profile_scope(home):
        manifests = resolve_manifest_winners(collect_directory_manifests())
    options = {"mcp:" + name: ("mcp", name, value) for name, value in config.get("mcp_servers", {}).items()
               if isinstance(value, dict) and "boltzmann" not in name.lower().replace("-", "").replace("_", "")}
    for key, manifest in manifests.items():
        if manifest.kind == "standalone" and manifest.provides_tools:
            options["plugin:" + key] = ("plugin", key, manifest)
    priority = {"tooluniverse": 0, "boltzmann": 1}
    return dict(sorted(options.items(), key=lambda item: (
        priority.get(re.sub(r"[^a-z0-9]", "", item[1][1].lower()), 2), item[0].lower())))


def credential(cli, ui, name, existing):
    from sci_cli.callbacks import prompt_for_secret
    while True:
        cancel = getattr(cli, "_science_cancel", None)
        if cancel is not None and cancel.is_set():
            raise Cancelled()
        choices = (["Use existing key from source profile"] if existing else []) + [
            "Enter new key for this profile", "Remove service", "Cancel"]
        choice = ui.choose(f"Credential {name} (values hidden; an approved copy is independent of the source)", choices)
        if choice == "Remove service":
            return None, "removed"
        if choice.startswith("Use existing"):
            return existing, "existing copy"
        snapshot = getattr(cli, "_capture_modal_input_snapshot", None)
        restore = getattr(cli, "_restore_modal_input_snapshot", None)
        if snapshot:
            snapshot()
        try:
            result = prompt_for_secret(cli, name, f"New {name} for this profile", persist=False)
        finally:
            if restore:
                restore()
        value = result.get("value")
        if not result.get("success") or not isinstance(value, str) or not value.strip():
            ui.show(f"No usable {name} was entered. Nothing saved. "
                    "Choose an existing key, enter a key again, or remove this service to continue without it.")
            continue
        return value, "new"


def setup_boltzmann(cli, ui, home, manifest):
    from agent.secret_scope import build_profile_secret_scope
    from plugins.boltzmann.nodeapi_helpers import authenticate_api_key
    from plugins.boltzmann.authentication import AUTHENTICATE_URL, PLATFORM_URL
    existing = build_profile_secret_scope(home).get("BOLTZMANN_API_KEY", "")
    while True:
        key, choice = credential(cli, ui, "BOLTZMANN_API_KEY", existing)
        if key is None:
            return None
        ui.show(f"Get a Boltzmann API key by logging in at {PLATFORM_URL}. "
                f"Verification sends the selected key only to {AUTHENTICATE_URL} "
                "using GET with a JSON body. Read-only, 15-second limit; no scientific job.")
        ui.choose("Approve Boltzmann credential validation?", ["Validate key", "Cancel"])
        with progress(ui, "Boltzmann authentication"):
            verification = authenticate_api_key(key)
        if verification.authenticated:
            ui.show(verification.account_summary())
            ui.show("Authentication succeeded. All five helper operations are included. "
                    "This selection is plugin-wide; it does not restrict individual scientific workflows.")
            return Service("boltzmann", "plugin", secrets={"BOLTZMANN_API_KEY": key},
                           tools=list(BOLTZMANN_WORKFLOW_TOOLS), credential_choice=choice,
                           plugin_path=str(manifest.path) if manifest.source == "user" else "", verified=True)
        action = ui.choose("Key rejected or service unreachable. Nothing saved.", [
            "Choose another credential", "Remove service", "Cancel"])
        if action == "Remove service":
            return None


def mcp_credentials(cli, ui, home, name, config):
    from agent.secret_scope import build_profile_secret_scope
    existing = build_profile_secret_scope(home)
    secrets, decisions = {}, []
    # Credential headers and inline environment values never stay in config.
    for field in ("headers", "env"):
        for label, value in list((config.get(field) or {}).items()):
            if not isinstance(value, str):
                raise ValueError("MCP headers/environment values must be strings.")
            if field == "env" and not re.search(r"(?i)(key|token|secret|password|credential)", label):
                continue
            if not ENV_REF.search(value):
                key = "MCP_" + re.sub(r"[^A-Z0-9_]", "_", (name + "_" + label).upper())
                scheme = re.fullmatch(r"(Bearer|Basic)\s+(.+)", value, re.IGNORECASE) if field == "headers" else None
                existing[key] = scheme[2] if scheme else value
                config[field][label] = (scheme[1] + " " if scheme else "") + "${" + key + "}"
    for key in sorted(set(ENV_REF.findall(json.dumps(config)))):
        value, decision = credential(cli, ui, key, existing.get(key, ""))
        if value is None:
            return None
        secrets[key] = value
        decisions.append(decision)
    # Different connections may use the same conventional API_KEY variable but
    # different values. Bind each reference to a service-specific stored slot.
    prefix = "MCP_" + re.sub(r"[^A-Z0-9_]", "_", name.upper()) + "_" + hashlib.sha256(name.encode()).hexdigest()[:12].upper() + "_"
    replacements = {key: prefix + key for key in secrets}

    def rewrite(value):
        if isinstance(value, str):
            return ENV_REF.sub(lambda m: "${" + replacements.get(m[1], m[1]) + "}", value)
        if isinstance(value, dict):
            return {k: rewrite(v) for k, v in value.items()}
        if isinstance(value, list):
            return [rewrite(v) for v in value]
        return value

    updated = rewrite(config)
    config.clear()
    config.update(updated)
    secrets = {replacements[k]: v for k, v in secrets.items()}
    return secrets, ", ".join(sorted(set(decisions))) or "none"


def setup_mcp(cli, ui, home, name, raw, scratch, *, selected=None):
    from sci_cli.mcp_security import validate_mcp_server_entry
    from sci_cli.mcp_config import _probe_single_server, redact_mcp_probe_text
    config = deepcopy(raw)
    prior_filter = config.get("tools") or {}
    if not isinstance(prior_filter, dict) or any(
        not isinstance(prior_filter[k], list) or any(not isinstance(v, str) for v in prior_filter[k])
        for k in ("include", "exclude") if k in prior_filter
    ):
        raise ValueError("MCP tool filters must contain lists of tool-name patterns.")
    issues = validate_mcp_server_entry(name, config)
    if issues:
        raise ValueError("MCP security validation rejected this configuration.")
    if config.get("url"):
        url = urlsplit(config["url"])
        if url.username or url.password or url.query or url.fragment:
            raise ValueError("Use a credential-free MCP URL and header/env credential references.")
    supplied = mcp_credentials(cli, ui, home, name, config)
    if supplied is None:
        return None
    secrets, decision = supplied
    config.update(enabled=True, sampling={"enabled": False}, elicitation={"enabled": False})
    prior_filter = deepcopy(prior_filter)
    config["tools"] = {"resources": False, "prompts": False}
    preview = deepcopy(config)
    preview["headers"] = {k: "[hidden]" for k in config.get("headers", {})}
    preview["env"] = {k: "[hidden]" for k in config.get("env", {})}
    ui.show(f"Connection {name}: " + redact_mcp_probe_text(json.dumps(preview, indent=2)))
    if config.get("command"):
        ui.show("This starts local MCP code with host access. Package runners may download software. "
                "No scientific/business tool will be called during the check.")
        ui.choose("Approve local server execution and any package-runner download shown above?", ["Approve execution", "Cancel"])
    if config.get("auth") == "oauth" or config.get("oauth"):
        ui.show("OAuth uses a new profile-owned sign-in. Existing tokens are not copied. "
                "Review the service's destination and requested scopes above and in the consent screen. "
                "Cancelling later deletes local staged tokens, but may leave an authorization grant at the service.")
        ui.choose("Approve this service's OAuth sign-in?", ["Approve sign-in", "Cancel"])
    ui.choose("Approve handshake and tool discovery? No business tools or research data.", ["Check connection", "Cancel"])
    ui.show(f"[Connection] Testing {name}; the configured connection/OAuth timeout applies.")
    from tools.mcp_oauth import force_interactive_oauth, login_connect_timeout
    timeout = login_connect_timeout(config) if config.get("auth") == "oauth" or config.get("oauth") else None
    with profile_scope(scratch, secrets), force_interactive_oauth(), progress(ui, name + " discovery"):
        found = dict(_probe_single_server(name, config, connect_timeout=timeout,
                                         cancel_event=getattr(cli, "_science_cancel", None)))
    include, exclude = prior_filter.get("include"), prior_filter.get("exclude", [])
    found = {k: v for k, v in found.items()
             if (include is None or any(fnmatch.fnmatchcase(k, p) for p in include))
             and not any(fnmatch.fnmatchcase(k, p) for p in exclude)}
    if any(any(char in name for char in "*?[]") for name in found):
        raise ValueError("Server returned tool names containing wildcard characters. An exact allowlist cannot safely represent them; nothing enabled.")
    selected = select_science_items(ui, f"{name}: allowed tools (individually selectable; explicit allowlist)", found,
                                    selected=[n for n in (selected or []) if n in found])
    if not selected:
        ui.show(f"{name}: no tools selected; connection omitted.")
        return None
    config["tools"] = {"include": selected, "resources": False, "prompts": False}
    return Service(name, "mcp", config, secrets, selected, decision, verified=True, oauth_home=str(scratch))


def setup_plugin(cli, ui, home, name, manifest, config):
    if name == "boltzmann":
        return setup_boltzmann(cli, ui, home, manifest)
    from sci_cli.plugins import get_plugin_manager
    from tools.registry import registry
    with profile_scope(home):
        loaded = get_plugin_manager()._plugins.get(name)
        registered = list(getattr(loaded, "tools_registered", ()))
        toolsets = sorted({entry.toolset for tool in registered if (entry := registry.get_entry(tool))})
    if not toolsets:
        raise ValueError("This plugin is not loaded with known toolsets in the source profile. Set it up there first; no code was imported by this wizard.")
    entry = deepcopy(config.get("plugins", {}).get("entries", {}).get(name, {}))
    required = [item if isinstance(item, str) else item.get("name", "") for item in manifest.requires_env]
    if required:
        raise ValueError("This credentialed plugin has no supported authentication checker in the profile wizard. "
                         "Use its native setup inside the target profile, or select its MCP connector. "
                         "No credentials were copied or access granted.")
    # Do not silently clone settings containing undocumented credentials.
    if entry.get("settings"):
        raise ValueError("This plugin has custom settings; a reviewed profile-copy adapter is needed. Use its native setup in the target profile.")
    ui.show(f"Plugin {name}: {manifest.description}\nTools: {', '.join(manifest.provides_tools)}\n"
            f"Complete plugin permission scope: {', '.join(manifest.capabilities) or 'standard plugin execution'}. "
            "Plugin code has host access. No per-tool isolation is promised. Installed code is reused; "
            "removing or changing that installation affects this profile. Authentication/execution is not tested here.")
    if manifest.requires_plugins:
        raise ValueError("This plugin declares other plugin dependencies requiring joint permission review. Use its native setup in the target profile.")
    ui.choose("Enable this installed plugin with its complete permission scope?", ["Approve plugin", "Cancel"])
    entry["granted_capabilities"] = list(manifest.capabilities)
    return Service(name, "plugin", entry, {}, list(manifest.provides_tools),
                   "none", str(manifest.path) if manifest.source == "user" else "", True,
                   toolsets=toolsets)


def choose_services(cli, ui, home, config, scratch, *, existing=None, additional_home=None):
    from sci_cli.science_integrations import missing_defaults, prepare_default
    from sci_cli.config import read_user_config_raw
    existing = existing or {}
    options = catalog(home, config)
    origins = {key: (home, config) for key in options}
    if additional_home is not None and additional_home != home:
        extra_config = read_user_config_raw(additional_home / "config.yaml")
        for key, value in catalog(additional_home, extra_config).items():
            if key not in options:
                options[key] = value
                origins[key] = (additional_home, extra_config)
    defaults = missing_defaults({"mcp_servers": {v[1]: v[2] for v in options.values() if v[0] == "mcp"}})
    for name, value in defaults.items():
        options["mcp:" + name] = ("mcp", name, value)
        origins["mcp:" + name] = (home, config)
    for key, service in existing.items():
        if key not in options:
            options[key] = (service.kind, service.name, None)
            origins[key] = (home, config)
    labels = {key: ("MCP: explicit tool selection after approved discovery" if kind == "mcp" else
                   f"Plugin-wide access: {value.description if value else 'preserved custom integration'}")
              + (" [profile-local]" if key in existing else " [default setup]" if name in defaults else " [source available]")
              for key, (kind, name, value) in options.items()}
    chosen = []
    for kind, title in (("mcp", "MCP connections"), ("plugin", "Plugins (plugin-wide permissions)")):
        section = {key: text for key, text in labels.items() if options[key][0] == kind}
        chosen.extend(select_science_items(ui, title, section, selected=[k for k in existing if k in section]))
    result = []
    for key in chosen:
        kind, name, value = options[key]
        source_home, source_config = origins[key]
        if key in existing:
            prior = existing[key]
            action = ui.choose(f"{name}: keep existing credentials/access or review changes?",
                               ["Keep existing access", "Review connection/credentials", "Cancel"])
            if action == "Keep existing access":
                result.append(prior)
                continue
            if value is None:
                raise ValueError(f"{name}: custom integration has no discoverable manifest; keep existing access or use its native setup.")
        while True:
            try:
                if name in defaults and kind == "mcp":
                    value = prepare_default(name, ui)
                initial = existing[key].tools if key in existing else None
                service = (setup_mcp(cli, ui, source_home, name, value, scratch, selected=initial) if kind == "mcp" else
                           setup_plugin(cli, ui, source_home, name, value, source_config))
                if getattr(cli, "_science_cancel", None) is not None and cli._science_cancel.is_set():
                    raise Cancelled()
                if service:
                    result.append(service)
                break
            except (Cancelled, KeyboardInterrupt, EOFError):
                raise
            except Exception as exc:
                if getattr(cli, "_science_cancel", None) is not None and cli._science_cancel.is_set():
                    if not isinstance(exc, InterruptedError):
                        ui.show("Cancellation requested, but connection/probe cleanup could not be verified. "
                                "Review the service's process state before retrying.")
                    raise Cancelled() from None
                # Provider exceptions may contain keys/headers. No raw exception
                # or config enters conversation/terminal logs.
                from sci_cli.mcp_config import redact_mcp_probe_text
                if isinstance(exc, ValueError):
                    ui.show(redact_mcp_probe_text(str(exc)))
                action = ui.choose(f"{name}: setup failed or is unsupported. No access granted. "
                                   "Retry credential/setup review, remove this service, or cancel.",
                                   ["Retry", "Remove service", "Cancel"])
                if action == "Remove service":
                    break
    return result
