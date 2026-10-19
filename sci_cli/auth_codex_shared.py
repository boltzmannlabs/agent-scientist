"""Explicit Codex credential reuse, checked before success and shared by reference."""

from pathlib import Path
import json
import os
import tomllib


def codex_home():
    return Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").expanduser().resolve()


def read_external(home):
    """Read the selected file store without consuming its rotating refresh token."""
    from sci_cli.auth_constants import _codex_err

    home = Path(home)
    try:
        config = tomllib.loads((home / "config.toml").read_text(encoding="utf-8-sig")) if (home / "config.toml").exists() else {}
        mode = config.get("cli_auth_credentials_store", "file")
        if mode != "file":
            raise _codex_err(
                f"Codex uses {mode!r} credential storage. SCI cannot read that store safely. "
                "Choose a new SCI OAuth login, or explicitly configure Codex file storage and sign in there.",
                "codex_external_store_unsupported", relogin=True)
        value = json.loads((home / "auth.json").read_text(encoding="utf-8-sig"))
        tokens = value.get("tokens")
        if not isinstance(tokens, dict) or not tokens.get("access_token"):
            raise ValueError("missing OAuth token")
        return tokens
    except (OSError, ValueError, TypeError) as exc:
        raise _codex_err("Current Codex file credentials are unavailable. Sign in with Codex or choose a new SCI login.",
                         "codex_external_credentials_missing", relogin=True) from exc


def external_credentials(*, read_only=False):
    from sci_cli import auth
    from sci_cli.auth_codex import _codex_runtime_result, _codex_base_url

    state = auth._load_global_auth_store().get("providers", {}).get("openai-codex") or {}
    if not state.get("external_codex_home"):
        state = auth._load_provider_state(auth._load_auth_store(), "openai-codex") or {}
    home = state.get("external_codex_home")
    if not home:
        return None
    tokens = read_external(home)
    from agent.credential_pool import _codex_principal_identity
    expected = state.get("external_codex_identity")
    if expected and tuple(expected) != _codex_principal_identity(tokens["access_token"]):
        raise auth.AuthError("The Codex file now belongs to another account/workspace. Re-add Codex to review this login change.",
                             provider="openai-codex", code="codex_external_identity_changed", relogin_required=True)
    if auth._codex_access_token_is_expiring(tokens["access_token"], 0):
        raise auth.AuthError("Codex's shared token has expired. Open Codex to refresh its login, or sign SCI in again. "
                             "SCI does not rotate another client's refresh token.", provider="openai-codex",
                             code="codex_external_token_expired", relogin_required=True)
    return _codex_runtime_result(tokens["access_token"], source="codex-file-reference",
                                 last_refresh=None, base_url=_codex_base_url())


def validate(access_token, base_url):
    """A read-only authenticated usage request; never an inference or research request."""
    from sci_cli.auth_constants import _codex_err, httpx
    from sci_cli.auth_codex import _codex_http_client, _codex_usage_probe_url
    from agent.codex_headers import codex_account_headers, is_official_codex_base_url
    from sci_cli.auth_codex import _codex_access_token_is_expiring

    if not access_token or _codex_access_token_is_expiring(access_token, 0):
        raise _codex_err("Codex credentials are missing or expired. Renew the current Codex login or choose a new SCI sign-in.",
                         "codex_login_token_expired", relogin=True)

    if not is_official_codex_base_url(base_url):
        raise _codex_err("Cannot validate a Codex OAuth login against a custom endpoint. Use the official Codex route.",
                         "codex_login_validation_route", relogin=False)
    try:
        with _codex_http_client(timeout=httpx.Timeout(15.0)) as client:
            response = client.get(_codex_usage_probe_url(base_url), headers={
                "Authorization": f"Bearer {access_token}", "Accept": "application/json",
                **codex_account_headers(access_token)})
    except httpx.TransportError as exc:
        raise _codex_err("Codex credential validation could not reach OpenAI. No login success is confirmed; retry when connected.",
                         "codex_login_validation_unreachable", relogin=False) from exc
    if response.status_code != 200:
        raise _codex_err(f"Codex credential validation returned HTTP {response.status_code}. "
                         "No login success is confirmed. Choose current Codex credentials or a new SCI login.",
                         "codex_login_validation_failed", relogin=response.status_code in {401, 403})


def link_external(home, *, expected_token=None):
    from sci_cli import auth
    from sci_constants import get_sci_home, get_default_sci_root
    from sci_cli.shared_llm import _read_main_scope
    from agent.credential_pool import _codex_principal_identity
    from sci_cli.shared_provider_lifecycle import singleton_row

    tokens = read_external(home)
    if expected_token and tokens["access_token"] != expected_token:
        raise auth.AuthError("The Codex login changed during validation. Re-add it to review the current credential.",
                             provider="openai-codex", code="codex_login_changed", relogin_required=False)

    # Persist the path only. Codex remains the sole refresh owner for this grant.
    root = get_default_sci_root(home=get_sci_home())
    with _read_main_scope(root), auth._auth_store_lock():
        store = auth._load_auth_store()
        previous = store.get("providers", {}).get("openai-codex")
        if previous and previous.get("tokens"):
            row = singleton_row("openai-codex", previous, "Previous SCI login")
            if row:
                store.setdefault("credential_pool", {}).setdefault("openai-codex", []).append(row)
        auth._store_provider_state(store, "openai-codex", {
            "external_codex_home": str(home), "auth_mode": "chatgpt",
            "external_codex_identity": _codex_principal_identity(tokens["access_token"])}, set_active=False)
        auth._save_auth_store(store)


def reuse_current_login():
    """Explicit model setup prefers the current Codex file over stale SCI copies.

    Discovery/status never call this writer. An existing link still enforces its
    approved account/workspace; a rejected source never triggers a new OAuth flow.
    """
    from sci_cli.auth_codex import _codex_base_url
    from sci_cli.shared_provider_lifecycle import publish

    linked = external_credentials(read_only=True)
    if linked:
        print("Checking the linked Codex login; no new browser sign-in is required.")
        validate(linked["api_key"], linked["base_url"])
        publish("openai-codex", preferred_token=linked["api_key"])
        print("Codex authentication verified. Using the existing shared login.")
        return linked
    home = codex_home()
    if not (home / "auth.json").exists() and not (home / "config.toml").exists():
        return None
    print(f"Using the current Codex login from {home}; no new browser sign-in is required.")
    tokens = read_external(home)
    validate(tokens["access_token"], _codex_base_url())
    link_external(home, expected_token=tokens["access_token"])
    publish("openai-codex", preferred_token=tokens["access_token"])
    print("Codex authentication verified. Shared login available in main and all profiles. Selected models unchanged.")
    return external_credentials(read_only=True)


def choose_credentials(args, *, force_new=False):
    """Return (kind, credentials); kinds are external, saved, fresh. Never report success here."""
    from sci_cli import auth
    from sci_cli.auth_codex import _codex_base_url
    from sci_cli.auth_codex_browser import codex_oauth_login

    if not force_new:
        home = codex_home()
        if (home / "auth.json").exists() or (home / "config.toml").exists():
            print(f"Current Codex login source: {home} (file or configured credential store).")
            if auth._prompt_yes_no("Use the current Codex login? SCI will follow its file; Codex owns refresh. [Y/n]: ", default="y", cancel_raises=True):
                tokens = read_external(home)
                validate(tokens["access_token"], _codex_base_url())
                return "external", {"home": home, "api_key": tokens["access_token"]}
        try:
            existing = auth.resolve_codex_runtime_credentials()
        except auth.AuthError:
            existing = None
        if existing and auth._prompt_yes_no("Reuse SCI's saved Codex login (separate from the current Codex login)? [y/N]: ", default="n", cancel_raises=True):
            validate(existing["api_key"], existing["base_url"])
            return "saved", existing
    creds = codex_oauth_login(args)
    validate(creds["tokens"]["access_token"], creds.get("base_url") or _codex_base_url())
    return "fresh", creds


def add_credential(args, pool):
    """Pool-add entry point; reusing a login does not append another rotating-token copy."""
    from sci_cli import auth
    from sci_cli.shared_provider_lifecycle import publish

    kind, creds = choose_credentials(args, force_new=bool(getattr(args, "browser", False)))
    if kind == "external":
        link_external(creds["home"], expected_token=creds["api_key"])
    elif kind == "fresh":
        from sci_cli.auth_commands import _codex_pool_source, _warn_same_codex_account
        from agent.credential_pool import PooledCredential, label_from_token
        import uuid
        token = creds["tokens"]["access_token"]
        entry = PooledCredential(provider="openai-codex", id=uuid.uuid4().hex[:6],
            label=getattr(args, "label", None) or label_from_token(token, "Codex"),
            auth_type="oauth", priority=0, source=_codex_pool_source(creds), access_token=token,
            refresh_token=creds["tokens"].get("refresh_token"), base_url=creds.get("base_url"),
            last_refresh=creds.get("last_refresh"))
        existing = pool.entries()
        pool.add_entry(entry)
        _warn_same_codex_account(token, existing)
        # Explicit fresh login supersedes a file reference, but retains independent
        # pool accounts. No singleton copy of this rotating pair is created.
        from sci_constants import get_sci_home, get_default_sci_root
        from sci_cli.shared_llm import _read_main_scope
        with _read_main_scope(get_default_sci_root(home=get_sci_home())), auth._auth_store_lock():
            store = auth._load_auth_store()
            previous = store.get("providers", {}).get("openai-codex", {})
            if previous.get("external_codex_home"):
                store["providers"].pop("openai-codex")
                auth._save_auth_store(store)
    publish("openai-codex", preferred_token=creds.get("api_key") or creds.get("tokens", {}).get("access_token", ""))
    from sci_constants import get_sci_home, get_default_sci_root
    from sci_cli.shared_llm import _read_main_scope
    with _read_main_scope(get_default_sci_root(home=get_sci_home())):
        auth.mark_provider_active_if_unset("openai-codex")
    if getattr(args, "priority", None) is not None:
        from agent.credential_pool import load_pool
        central = load_pool("openai-codex")
        if kind == "fresh":
            central.move_entry(entry.id, int(args.priority))
        else:
            print("Priority is unchanged when reusing an existing login.")
    print("Codex authentication verified. Shared login available in main and all profiles. Selected models unchanged.")
    return True
