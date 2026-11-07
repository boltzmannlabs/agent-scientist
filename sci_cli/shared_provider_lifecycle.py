"""Publish explicitly added LLM capabilities to the shared library in main.

Only the chosen provider's definitions and credentials move. Model selections,
service secrets and conversation state always stay with their owning profile.
"""

from contextlib import ExitStack
from copy import deepcopy
import re


class ProviderRemovedError(RuntimeError):
    code = "sci_provider_removed"

    def __init__(self, message):
        super().__init__(message)
        self.body = {"error": {"code": self.code, "message": message}}


def enforce_runtime_access(provider):
    """A revoked provider stops cached clients without changing their prompt or model."""
    from sci_cli.runtime_provider import _raise_if_provider_disabled
    try:
        _raise_if_provider_disabled(provider)
    except ValueError as exc:
        raise ProviderRemovedError(
            "This profile's access to the selected provider was removed. No model request was sent. "
            "Choose a provider with /model or re-add its login before continuing.") from exc


def singleton_row(provider, state, label):
    """Retain an independent singleton grant when consolidating provider storage."""
    from agent.credential_pool import PooledCredential
    from sci_cli.auth import PROVIDER_REGISTRY
    payload = deepcopy(state)
    payload.update(payload.pop("tokens", {}) or {})
    if not payload.get("access_token"):
        return None
    source = {"anthropic": "manual:sci_pkce", "minimax-oauth": "manual:oauth"}.get(provider, "manual:device_code")
    config = PROVIDER_REGISTRY.get(provider)
    payload.update(source=source, auth_type="oauth", label=payload.get("label") or label)
    if config:
        payload.setdefault("base_url", config.inference_base_url)
    return PooledCredential.from_dict(provider, payload).to_dict()


def publish(provider, *, base_url="", preferred_token=""):
    from providers import get_provider_profile
    profile = get_provider_profile(provider)
    if profile is not None and profile.credential_scope == "profile":
        return  # A service account is authorized independently by each owning profile.
    from sci_constants import get_sci_home, get_default_sci_root
    from sci_cli.provider_removal import _homes, _read, _definitions, _aliases, _url
    from sci_cli.providers import custom_provider_aliases, ALIASES
    from sci_cli.config import atomic_config_replace, is_managed, load_env, save_env_value, require_env_writable
    from sci_cli.shared_llm import _read_main_scope
    from sci_cli import auth

    home = get_sci_home()
    root = get_default_sci_root(home=home)
    if is_managed():
        raise ValueError("Shared provider changes are managed by your administrator.")
    owners = _homes(home)
    snapshots = {h: (h / "config.yaml").read_bytes() if (h / "config.yaml").exists() else None for h in owners}
    configs = {h: _read(h) for h in owners}
    aliases = set(custom_provider_aliases(provider)) | {provider.lower()}
    aliases.update(alias for alias, canonical in ALIASES.items() if canonical == provider)
    from sci_cli.provider_removal import _check_managed, Target
    _check_managed(Target(provider, provider, aliases))
    definitions = []
    for key, entry in _definitions(configs[home]):
        if aliases.intersection(_aliases(key, entry)) or (provider == "custom" and base_url and _url(entry) == base_url.rstrip("/")):
            definitions.append((key, deepcopy(entry)))
            aliases.update(_aliases(key, entry))
    was_removed = any(
        aliases.intersection(str(v).lower() for v in (cfg.get("model_catalog") or {}).get("excluded_providers", [])) or
        any(isinstance(entry, dict) and entry.get("enabled") is False and aliases.intersection(_aliases(key, entry))
            for key, entry in (cfg.get("providers") or {}).items())
        for cfg in configs.values())
    # Never replace a different endpoint just because its display name matches.
    for key, entry in definitions:
        for existing_key, existing in _definitions(configs[root]):
            if aliases.intersection(_aliases(existing_key, existing)) and _url(existing) and _url(entry) != _url(existing):
                raise ValueError("A shared provider with this name uses another endpoint. Rename the new provider before sharing it.")
    desired = deepcopy(configs)
    for owner, config in desired.items():
        catalog = config.get("model_catalog") or {}
        if "excluded_providers" in catalog:
            catalog["excluded_providers"] = [v for v in catalog["excluded_providers"] if str(v).lower() not in aliases]
        for key, entry in (config.get("providers") or {}).copy().items():
            if isinstance(entry, dict) and aliases.intersection(_aliases(key, entry)):
                if entry == {"enabled": False}:
                    del config["providers"][key]
                else:
                    if entry.get("enabled") is False:
                        entry.pop("enabled")
        if owner == home and home != root:
            for key, entry in definitions:
                if key:
                    config.get("providers", {}).pop(key, None)
                else:
                    config["custom_providers"] = [e for e in config.get("custom_providers", []) if e != entry]
    for key, entry in definitions:
        if entry.get("enabled") is False:
            entry.pop("enabled")
        if key:
            desired[root].setdefault("providers", {})[key] = entry
        else:
            entries = desired[root].setdefault("custom_providers", [])
            entries[:] = [e for e in entries if not isinstance(e, dict) or not aliases.intersection(_aliases("", e))]
            entries.append(entry)

    env_names = set()
    pconfig = auth.PROVIDER_REGISTRY.get(provider)
    if pconfig:
        env_names.update(pconfig.api_key_env_vars or ())
    if provider == "openrouter":
        env_names.add("OPENROUTER_API_KEY")
    for _, entry in definitions:
        env_names.update(str(entry[k]) for k in ("key_env", "api_key_env") if entry.get(k))
        env_names.update(re.findall(r"\$\{(?:env:)?([A-Za-z_][A-Za-z_0-9]*)\}", str(entry.get("api_key", ""))))
    local_env = load_env()
    keys = {name: local_env[name] for name in env_names if local_env.get(name)}
    saved = []
    try:
        # Consistent profile -> root lock order, matching rotating-grant transactions.
        with ExitStack() as stack:
            for owner in [h for h in owners if h != root] + [root]:
                stack.enter_context(auth._auth_store_lock(target_path=owner / "auth.json"))
            stores = {h: auth._load_auth_store(h / "auth.json") for h in owners}
            previous_states = {h: deepcopy(s.get("providers", {}).get(provider)) for h, s in stores.items()}
            central = stores[root]
            shared_state = central.get("providers", {}).get(provider) or {}
            local_state = stores[home].get("providers", {}).get(provider) or {}
            fresh_local = preferred_token and (local_state.get("tokens") or {}).get("access_token") == preferred_token
            chosen = local_state if fresh_local else (shared_state if shared_state.get("external_codex_home") else local_state or shared_state)
            if chosen:
                central.setdefault("providers", {})[provider] = deepcopy(chosen)
                preferred_token = preferred_token or (chosen.get("tokens") or {}).get("access_token", "")
            rows = []
            for owner in [home, root, *owners]:
                for row in stores[owner].get("credential_pool", {}).get(provider, []):
                    if isinstance(row, dict) and row not in rows:
                        rows.append(deepcopy(row))
            for owner, state in previous_states.items():
                if state and state != chosen:
                    row = singleton_row(provider, state, "Existing login: " + ("main" if owner == root else owner.name))
                    if row:
                        rows.append(row)
            if (provider == "openai-codex" and preferred_token and chosen and chosen.get("tokens") and
                    chosen["tokens"].get("access_token") != preferred_token):
                rows.append(singleton_row(provider, chosen, "Previous SCI login"))
                central.get("providers", {}).pop(provider, None)
            # A confirmed re-login replaces stale copies of that Codex identity,
            # while independent accounts and API-key credentials are retained.
            if provider == "openai-codex" and preferred_token and (was_removed or chosen.get("external_codex_home")):
                from agent.credential_pool import _codex_principal_identity
                identity = _codex_principal_identity(preferred_token)
                if identity:
                    rows = [r for r in rows if r.get("auth_type") != "oauth" or
                            _codex_principal_identity(r.get("access_token")) != identity or
                            (not chosen.get("external_codex_home") and r.get("access_token") == preferred_token)]
            unique = {}
            for row in rows:
                fingerprint = (row.get("access_token"), row.get("refresh_token")) if row.get("access_token") else (row.get("id"), row.get("source"))
                unique.setdefault(fingerprint, row)
            if rows:
                ordered = sorted(unique.values(), key=lambda row: row.get("priority", 0))
                if preferred_token and was_removed:
                    ordered.sort(key=lambda row: row.get("access_token") != preferred_token)
                for priority, row in enumerate(ordered):
                    row["priority"] = priority
                central.setdefault("credential_pool", {})[provider] = ordered
            else:
                central.get("credential_pool", {}).pop(provider, None)
            for owner in owners:
                store = stores[owner]
                store.get("suppressed_sources", {}).pop(provider, None)
                if owner != root:
                    store.get("providers", {}).pop(provider, None)
                    store.get("credential_pool", {}).pop(provider, None)
                if store != auth._load_auth_store(owner / "auth.json"):
                    auth._save_auth_store(store, target_path=owner / "auth.json")
                    saved.append(str(owner / "auth.json"))
            with _read_main_scope(root):
                for name, value in keys.items():
                    require_env_writable(name, "set")
                    save_env_value(name, value)
                    saved.append(str(root / ".env"))
            for owner, config in desired.items():
                path = owner / "config.yaml"
                current = path.read_bytes() if path.exists() else None
                if current != snapshots[owner]:
                    raise ValueError("Configuration changed during provider sharing; review and retry.")
                if config != configs[owner]:
                    atomic_config_replace(path, config)
                    saved.append(str(path))
    except Exception as exc:
        raise ValueError(f"Shared provider setup stopped ({type(exc).__name__}). Saved files: " +
                         (", ".join(saved) or "none") + ". Credentials already saved are retained; retry setup.") from exc
