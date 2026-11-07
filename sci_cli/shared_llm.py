"""Main's inference-provider catalog, shared without sharing project configuration.

This is a read-time view for model selection/resolution, never a config writer.
Profile-local provider definitions and credentials remain authoritative. Main's
model choice, research-service secrets, tools and execution settings are not inherited.
"""

from contextlib import contextmanager
from copy import deepcopy
from functools import wraps


def _main_home():
    from sci_constants import get_default_sci_root, get_sci_home

    home = get_sci_home()
    main = get_default_sci_root(home=home)
    return main if main.resolve() != home.resolve() else None


@contextmanager
def _read_main_scope(main):
    from sci_constants import set_sci_home_override, reset_sci_home_override
    from agent.secret_scope import build_profile_secret_scope, set_secret_scope, reset_secret_scope

    secrets = build_profile_secret_scope(main)
    home_token = set_sci_home_override(main)
    secret_token = set_secret_scope(secrets, profile_home=str(main))
    try:
        yield
    finally:
        reset_secret_scope(secret_token)
        reset_sci_home_override(home_token)


def provider_config(config, *, expand=True):
    """Add main's missing provider definitions, retaining the caller's model/settings.

    Expansion occurs in the owning home so a shared endpoint's key reference cannot
    accidentally resolve to an unrelated profile secret with the same variable name.
    Local overrides replace whole entries, never inherit credentials from another URL.
    """
    main = _main_home()
    if main is None:
        return config
    from sci_cli.config import read_user_config_raw, _expand_env_vars
    from sci_cli.providers import custom_provider_aliases

    with _read_main_scope(main):
        raw = read_user_config_raw(main / "config.yaml")
        shared = deepcopy({k: raw[k] for k in ("providers", "custom_providers") if k in raw})
        from providers import get_provider_profile
        shared["providers"] = {name: value for name, value in shared.get("providers", {}).items()
                               if not ((profile := get_provider_profile(name)) and profile.credential_scope == "profile")}
        if expand:
            shared = _expand_env_vars(shared)
        from agent.secret_scope import get_secret_str
        entries = list((shared.get("providers") or {}).values()) + list(shared.get("custom_providers") or [])
        for entry in entries:
            if expand and isinstance(entry, dict) and not entry.get("api_key"):
                key_env = entry.get("key_env") or entry.get("api_key_env")
                if key_env:
                    entry["api_key"] = get_secret_str(str(key_env), "")
    result = deepcopy(config)
    local = result.get("custom_providers") or []
    local_providers = result.get("providers") or {}
    names = set()
    for name, entry in [*local_providers.items(), *(("", e) for e in local)]:
        if isinstance(entry, dict):
            names.update(custom_provider_aliases(entry.get("name", ""), name))
    inherited_providers = {name: entry for name, entry in shared.get("providers", {}).items()
                           if not names.intersection(custom_provider_aliases(entry.get("name", ""), name))}
    # Endpoint/model identity recovery uses the first matching entry. Keep the
    # owning profile first even when main names the same route differently.
    result["providers"] = {**local_providers, **inherited_providers}
    inherited = [e for e in shared.get("custom_providers", [])
                 if isinstance(e, dict) and not names.intersection(custom_provider_aliases(e.get("name", "")))]
    result["custom_providers"] = local + inherited
    # Keep main's catalog policy while preserving any stricter local exclusions.
    excluded = (raw.get("model_catalog") or {}).get("excluded_providers") or []
    if excluded:
        catalog = result.setdefault("model_catalog", {})
        catalog["excluded_providers"] = list(dict.fromkeys([*excluded, *catalog.get("excluded_providers", [])]))
    return result


def with_shared_credentials(function):
    """Expose only registered inference-key variables during picker/runtime resolution.

    Never modify os.environ or the profile's persistent secret scope. Main's custom
    key_env references are resolved on their own entries by provider_config instead.
    """
    @wraps(function)
    def wrapped(*args, **kwargs):
        main = _main_home()
        if main is None:
            return function(*args, **kwargs)
        from agent.secret_scope import (
            build_profile_secret_scope, current_secret_scope, set_secret_scope, reset_secret_scope,
            is_multiplex_active, get_secret_str,
        )
        from sci_constants import get_sci_home
        from sci_cli.auth import PROVIDER_REGISTRY
        from sci_cli.config import read_user_config_raw

        home = get_sci_home()
        local = current_secret_scope()
        if local is None and is_multiplex_active():
            get_secret_str("OPENROUTER_API_KEY")  # retain the fail-closed unbound-scope guard
        secrets = dict(local if local is not None else build_profile_secret_scope(home))
        main_secrets = build_profile_secret_scope(main)
        local_providers = read_user_config_raw(home / "config.yaml").get("providers", {})
        # A local endpoint override must not acquire main's key for that provider.
        key_names = {slug: provider.api_key_env_vars or () for slug, provider in PROVIDER_REGISTRY.items()}
        # OpenRouter has a dedicated resolver rather than an auth-registry entry.
        key_names.setdefault("openrouter", ("OPENROUTER_API_KEY",))
        for slug, names in key_names.items():
            from providers import get_provider_profile
            profile = get_provider_profile(slug)
            if profile is not None and profile.credential_scope == "profile":
                continue
            if slug in local_providers:
                continue
            for name in names:
                if name not in secrets and main_secrets.get(name):
                    secrets[name] = main_secrets[name]
        token = set_secret_scope(secrets, profile_home=str(home))
        try:
            return function(*args, **kwargs)
        finally:
            reset_secret_scope(token)
    return wrapped


def custom_pool_candidates(base_url, provider_name=None):
    """Find inherited named-provider pools without borrowing a sibling endpoint's key."""
    from agent.credential_pool import custom_provider_pool_key_candidates

    from sci_cli.config import get_compatible_custom_providers, load_config
    from sci_cli.providers import custom_provider_aliases

    main = _main_home()
    if main is not None and provider_name:
        requested = str(provider_name).lower()
        local = get_compatible_custom_providers(load_config())
        if not any(requested in custom_provider_aliases(e.get("name", ""), e.get("provider_key", ""))
                   for e in local):
            with _read_main_scope(main):
                return custom_provider_pool_key_candidates(base_url, provider_name)
    return custom_provider_pool_key_candidates(base_url, provider_name)
