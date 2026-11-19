"""Browser adapter for the CLI's native science-profile creation services.

The dashboard owns the presentation; profile validation and publication remain in
``native_profile_creation`` and ``native_profile_services``.
"""

from copy import deepcopy
from pathlib import Path
import fnmatch
import hashlib
import json
import secrets
import threading
import time

_DISCOVERIES: dict[str, dict] = {}
_DISCOVERIES_LOCK = threading.Lock()
_DISCOVERY_TTL = 600


def _home():
    from sci_cli.profiles import _get_default_sci_home
    return _get_default_sci_home()


def _fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode()).hexdigest()


def _source_config(home):
    from sci_cli.config import read_user_config_raw
    return read_user_config_raw(home / "config.yaml")


def _prune_discoveries():
    cutoff = time.monotonic() - _DISCOVERY_TTL
    with _DISCOVERIES_LOCK:
        for token in [key for key, value in _DISCOVERIES.items() if value["created"] < cutoff]:
            _DISCOVERIES.pop(token, None)


def _mcp_options(home, config, name, raw):
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.native_profile_services import mcp_credentials
    from sci_cli.science_profiles_catalog import cached_tools
    from urllib.parse import urlsplit
    from sci_cli.mcp_security import validate_mcp_server_entry

    reason = ""
    if validate_mcp_server_entry(name, raw):
        reason = "MCP security validation rejected this configuration."
    if raw.get("url"):
        parsed = urlsplit(raw["url"])
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            reason = "Remove embedded credentials, query parameters, or fragments before selecting this server."
    try:
        with profile_scope(home):
            mcp_credentials(object(), _ExistingCredentialUI(), home, name, deepcopy(raw))
    except ValueError as exc:
        reason = str(exc)
    if raw.get("auth") == "oauth":
        from sci_cli.mcp_config import _oauth_tokens_present
        with profile_scope(home):
            if not _oauth_tokens_present(name):
                reason = "Complete OAuth authentication on the MCP page before adding this connection to a profile."
    tools = cached_tools(name, raw)
    include = (raw.get("tools") or {}).get("include")
    exclude = (raw.get("tools") or {}).get("exclude", [])
    if isinstance(include, list):
        tools = {key: value for key, value in tools.items()
                 if any(fnmatch.fnmatchcase(key, pattern) for pattern in include)}
    if isinstance(exclude, list):
        tools = {key: value for key, value in tools.items()
                 if not any(fnmatch.fnmatchcase(key, pattern) for pattern in exclude)}
    return {
        "key": f"mcp:{name}", "name": name, "kind": "mcp",
        "description": "MCP tools are individually selectable; only selected tools are copied.",
        "tools": [{"name": key, "description": value} for key, value in sorted(tools.items())],
        "transport": "local" if raw.get("command") else "remote",
        "destination": raw.get("command") or raw.get("url") or "",
        "auth": raw.get("auth") or "none", "ready": not reason,
        "reason": reason, "config_fingerprint": _fingerprint(raw),
    }


def _plugin_options(home, name, manifest):
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.plugins import get_plugin_manager
    from tools.registry import registry
    from agent.secret_scope import build_profile_secret_scope

    reason = ""
    with profile_scope(home):
        loaded = get_plugin_manager()._plugins.get(name)
        registered = list(getattr(loaded, "tools_registered", ())) if loaded else []
        toolsets = sorted({entry.toolset for tool in registered if (entry := registry.get_entry(tool))})
        config = _source_config(home)
        entry = deepcopy(config.get("plugins", {}).get("entries", {}).get(name, {}))
        secrets_scope = build_profile_secret_scope(home)
    if not toolsets:
        reason = "Plugin is not loaded with known toolsets in the source profile. Set it up there first."
    required = [item if isinstance(item, str) else item.get("name", "") for item in manifest.requires_env]
    if required:
        reason = "This plugin requires credentials; configure it in the source profile first."
    if entry.get("settings"):
        reason = "This plugin has custom settings that the profile wizard cannot safely copy."
    if manifest.requires_plugins:
        reason = "This plugin depends on other plugins; configure the complete set in the source profile first."
    is_boltzmann = name == "boltzmann"
    credential_ready = bool(secrets_scope.get("BOLTZMANN_API_KEY")) if is_boltzmann else True
    if is_boltzmann:
        reason = ("A saved Boltzmann API key is available; approve read-only validation before saving."
                  if credential_ready else
                  "A profile-specific Boltzmann API key is required; enter one here or configure it in the source profile.")
    return {
        "key": f"plugin:{name}", "name": name, "kind": "plugin",
        "description": manifest.description,
        "tools": [{"name": tool, "description": "Plugin-provided tool"} for tool in manifest.provides_tools],
        "capabilities": list(manifest.capabilities), "ready": not reason or is_boltzmann,
        "credential_ready": credential_ready,
        "reason": reason, "plugin_path": str(manifest.path) if manifest.source == "user" else "",
        "config_fingerprint": _fingerprint(entry),
    }


def options():
    """Read-only inventory. Does not connect to MCP servers or import plugin code."""
    from sci_cli.native_profile_creation import reviewed_model_seed
    from sci_cli.native_profile_services import catalog
    from sci_cli.science_profiles_catalog import science_skill_choices
    from sci_cli.config import DEFAULT_CONFIG

    home = _home()
    config = _source_config(home)
    reviewed_model_seed(config, source_home=home)
    skills, paths = science_skill_choices(home)
    services = []
    for key, (kind, name, value) in catalog(home, config).items():
        if kind == "mcp":
            services.append(_mcp_options(home, config, name, value))
        else:
            services.append(_plugin_options(home, name, value))
    terminal = deepcopy(DEFAULT_CONFIG.get("terminal", {}))
    terminal.update(deepcopy(config.get("terminal", {})))
    return {
        "skills": [{"name": name, "description": desc, "origin": "installed science skill"}
                   for name, desc in sorted(skills.items())],
        "services": services,
        "environment": {"backend": terminal.get("backend", "local"),
                        "docker_image": terminal.get("docker_image", "")},
        "source_home": str(home),
        "config_fingerprint": _fingerprint(config),
        "shared_llm_login": True,
        "persona": "Scientific persona supplied automatically: cite evidence, distinguish findings from hypotheses, disclose uncertainty, and ask about missing parameters.",
    }


def discover(name: str, approve_network: bool, approve_local_execution: bool):
    """Approved MCP handshake/discovery, with a short-lived profile/config-bound receipt."""
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.mcp_config import _probe_single_server, _oauth_tokens_present
    from sci_cli.mcp_security import validate_mcp_server_entry
    from urllib.parse import urlsplit

    home = _home()
    config = _source_config(home)
    raw = deepcopy((config.get("mcp_servers") or {}).get(name))
    if not isinstance(raw, dict):
        raise ValueError("MCP server is no longer configured in the source profile. Refresh the service list.")
    issues = validate_mcp_server_entry(name, raw)
    if issues:
        raise ValueError("MCP security validation rejected this connection.")
    if raw.get("url"):
        parsed = urlsplit(raw["url"])
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Remove embedded credentials, query parameters, or fragments before connecting.")
    if not approve_network:
        raise ValueError("Approve the handshake and tool discovery before connecting to this service.")
    if raw.get("command") and not approve_local_execution:
        raise ValueError("Approve local MCP process execution before discovery.")
    if raw.get("auth") == "oauth":
        with profile_scope(home):
            if not _oauth_tokens_present(name):
                raise ValueError("Complete OAuth authentication on the MCP page before discovery.")
    try:
        with profile_scope(home):
            found = _probe_single_server(name, raw)
    except Exception as exc:
        from sci_cli.mcp_config import redact_mcp_probe_text
        raise ValueError(redact_mcp_probe_text(str(exc))) from None
    prior = raw.get("tools") or {}
    include, exclude = prior.get("include"), prior.get("exclude", [])
    found = {tool: description for tool, description in found
             if (include is None or any(fnmatch.fnmatchcase(tool, pattern) for pattern in include))
             and not any(fnmatch.fnmatchcase(tool, pattern) for pattern in exclude)}
    tools = {tool: description for tool, description in found
             if not any(char in tool for char in "*?[]")}
    if not tools:
        raise ValueError("The connection returned no safely selectable tools.")
    token = secrets.token_urlsafe(24)
    _prune_discoveries()
    with _DISCOVERIES_LOCK:
        _DISCOVERIES[token] = {"created": time.monotonic(), "home": str(home.resolve()),
                               "name": name, "fingerprint": _fingerprint(raw),
                               "tools": sorted(tools), "local_approved": bool(raw.get("command"))}
    return {"token": token, "tools": [{"name": tool, "description": tools[tool]}
                                       for tool in sorted(tools)],
            "message": "Connection verified by handshake and discovery. No business tool was called."}


class _WebSetupUI:
    def __init__(self, *, approve_image_download: bool, approve_plugin_scope: bool = False):
        self.approve_image_download = approve_image_download
        self.approve_plugin_scope = approve_plugin_scope

    def show(self, _message: str):
        return None

    def choose(self, _question: str, choices):
        if "Approve image download" in choices:
            if self.approve_image_download:
                return "Approve image download"
            raise ValueError("Docker image download was not approved. Nothing was created.")
        if "Approve plugin" in choices and self.approve_plugin_scope:
            return "Approve plugin"
        raise ValueError("This setup action must be completed in its dedicated dashboard flow first.")


class _ExistingCredentialUI:
    def show(self, _message: str):
        return None

    def choose(self, question: str, choices):
        existing = next((choice for choice in choices if choice.startswith("Use existing key")), None)
        if existing:
            return existing
        raise ValueError(f"{question}: credential is not saved in the source profile; configure it first.")


def _make_mcp_service(home, selection, discovery):
    from sci_cli.native_profile_creation import Service, profile_scope
    from sci_cli.native_profile_services import mcp_credentials
    from sci_cli.config import read_user_config_raw
    from sci_cli.mcp_security import validate_mcp_server_entry
    from agent.secret_scope import build_profile_secret_scope

    name = selection["name"]
    source = read_user_config_raw(home / "config.yaml")
    raw = deepcopy((source.get("mcp_servers") or {}).get(name))
    if not isinstance(raw, dict) or validate_mcp_server_entry(name, raw):
        raise ValueError(f"MCP connection {name} changed or is no longer valid.")
    if raw.get("url"):
        from urllib.parse import urlsplit
        parsed = urlsplit(raw["url"])
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(f"{name}: remove embedded credentials, query parameters, or fragments first.")
    if discovery["fingerprint"] != _fingerprint(raw):
        raise ValueError(f"MCP connection {name} changed after discovery. Discover it again before saving.")
    selected = list(dict.fromkeys(selection.get("tools") or []))
    if not selected or not set(selected).issubset(discovery["tools"]):
        raise ValueError(f"{name}: choose one or more tools from the completed discovery.")
    config = deepcopy(raw)
    with profile_scope(home):
        captured = mcp_credentials(object(), _ExistingCredentialUI(), home, name, config)
    if captured is None:
        raise ValueError(f"{name}: credentials were not available; nothing was copied.")
    secrets_map, decision = captured
    config.update(enabled=True, sampling={"enabled": False}, elicitation={"enabled": False})
    config["tools"] = {"include": selected, "resources": False, "prompts": False}
    return Service(name, "mcp", config, secrets_map, selected, decision, verified=True,
                   oauth_home=str(home) if raw.get("auth") == "oauth" else "")


def _make_plugin_service(home, selection, *, approve_scope, boltzmann_key="", approve_boltzmann_validation=False):
    from sci_cli.native_profile_creation import Service, profile_scope
    from sci_cli.native_profile_services import catalog
    from sci_cli.config import read_user_config_raw
    from agent.secret_scope import build_profile_secret_scope
    from sci_cli.science_profiles_catalog import BOLTZMANN_WORKFLOW_TOOLS

    if not approve_scope:
        raise ValueError(f"Approve the complete permission scope for plugin {selection['name']} before saving.")
    name = selection["name"]
    config = read_user_config_raw(home / "config.yaml")
    manifest = catalog(home, config).get(f"plugin:{name}")
    if not manifest or manifest[0] != "plugin":
        raise ValueError(f"Plugin {name} is no longer installed. Refresh the available services.")
    manifest = manifest[2]
    if name == "boltzmann":
        key = boltzmann_key.strip() or build_profile_secret_scope(home).get("BOLTZMANN_API_KEY", "")
        if not key:
            raise ValueError("Add a Boltzmann API key before selecting this service.")
        if not approve_boltzmann_validation:
            raise ValueError("Approve read-only Boltzmann API-key validation before saving.")
        from plugins.boltzmann.nodeapi_helpers import authenticate_api_key
        try:
            verification = authenticate_api_key(key)
        except Exception:
            raise ValueError("Boltzmann API-key validation failed or could not complete. No profile was created.") from None
        if not verification.authenticated:
            raise ValueError("Boltzmann API-key validation failed. No profile was created.")
        from sci_cli.plugins import get_plugin_manager
        from tools.registry import registry
        with profile_scope(home):
            loaded = get_plugin_manager()._plugins.get(name)
            tools = list(getattr(loaded, "tools_registered", ())) if loaded else []
            toolsets = sorted({entry.toolset for tool in tools if (entry := registry.get_entry(tool))})
        if not toolsets:
            raise ValueError("Boltzmann plugin tools are not loaded in the source profile.")
        return Service(name, "plugin", {}, {"BOLTZMANN_API_KEY": key},
                       list(BOLTZMANN_WORKFLOW_TOOLS), "new or existing key", verified=True,
                       plugin_path=str(manifest.path) if manifest.source == "user" else "",
                       toolsets=toolsets)
    from sci_cli.native_profile_services import setup_plugin
    return setup_plugin(None, _WebSetupUI(approve_image_download=False, approve_plugin_scope=True),
                        home, name, manifest, config)


def create_profile(body):
    """Validate the browser review and publish through the same native transaction as CLI."""
    from sci_cli.native_profile_creation import create_native, reviewed_model_seed
    from sci_cli.native_profile_environment import prepare_environment
    from sci_cli.profiles import get_profile_dir, validate_profile_name
    from sci_cli.config import read_user_config_raw
    from sci_cli.science_profiles_catalog import science_skill_choices
    from sci_cli.science_profiles import Source, local_source
    from sci_cli.science_profiles_ui import PERSONA

    home = _home()
    original = read_user_config_raw(home / "config.yaml")
    if body.config_fingerprint != _fingerprint(original):
        raise ValueError("The source profile configuration changed during review. Refresh the choices and review again.")
    reviewed_model_seed(original, source_home=home)
    validate_profile_name(body.name)
    if body.name in {"default", "main"}:
        raise ValueError("Choose a new named profile, not default/main.")
    destination = get_profile_dir(body.name)
    if destination.exists():
        raise FileExistsError(f"Profile {body.name} already exists; nothing was overwritten.")
    labels, skill_sources = science_skill_choices(home)
    if len(set(body.skills)) != len(body.skills) or not set(body.skills).issubset(labels):
        raise ValueError("Select installed science skills from the available list.")
    sources = []
    source_locations = set()
    for item in body.sources:
        location = item.location.strip()
        if not location or item.access not in {"reference", "read-local", "model"}:
            raise ValueError("Each source needs a path/URL and an explicit access choice.")
        from urllib.parse import urlsplit
        path = local_source(Source(location))
        if path is None:
            parsed = urlsplit(location)
            if parsed.query or parsed.fragment:
                raise ValueError("Use a public reference URL without a query string or fragment; signed/private links are not accepted.")
            if item.access != "reference":
                raise ValueError("Web URLs are saved as references only. Download and add a local file to grant local or model access.")
        else:
            location = str(path)
        if location in source_locations:
            raise ValueError("Each project source can only be added once.")
        source_locations.add(location)
        sources.append({"location": location, "access": item.access})
    services = []
    used_names = set()
    _prune_discoveries()
    for selection in body.services:
        name = selection.name
        if name in used_names:
            raise ValueError(f"Service {name} was selected more than once.")
        used_names.add(name)
        if selection.kind == "mcp":
            with _DISCOVERIES_LOCK:
                discovery = deepcopy(_DISCOVERIES.get(selection.discovery_token or ""))
            if not discovery or discovery["home"] != str(home.resolve()) or discovery["name"] != name:
                raise ValueError(f"{name}: discovery receipt expired. Approve a fresh handshake and discovery.")
            if discovery["created"] < time.monotonic() - _DISCOVERY_TTL:
                raise ValueError(f"{name}: discovery receipt expired. Discover tools again before saving.")
            services.append(_make_mcp_service(home, selection.model_dump(), discovery))
        elif selection.kind == "plugin":
            services.append(_make_plugin_service(
                home, selection.model_dump(), approve_scope=selection.approve_scope,
                boltzmann_key=body.boltzmann_api_key.get_secret_value(),
                approve_boltzmann_validation=body.approve_boltzmann_validation))
        else:
            raise ValueError(f"Unsupported service type: {selection.kind}")
    terminal = prepare_environment(original, destination,
                                   _WebSetupUI(approve_image_download=body.approve_image_download),
                                   threading.Event())
    if read_user_config_raw(home / "config.yaml") != original:
        raise ValueError("The source profile configuration changed during review; refresh choices and try again.")
    path = create_native(body.name, home, body.skills, services, sources, terminal,
                         PERSONA, skill_sources=skill_sources)
    with _DISCOVERIES_LOCK:
        for selection in body.services:
            if selection.discovery_token:
                _DISCOVERIES.pop(selection.discovery_token, None)
    return {"ok": True, "name": body.name, "path": str(path), "skills": body.skills,
            "services": [{"name": service.name, "kind": service.kind, "tools": service.tools}
                         for service in services], "sources": sources,
            "environment": terminal.get("backend", "local")}
