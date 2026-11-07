"""Model admission and account reporting reuse the scientific service's login."""

from contextlib import contextmanager
from pathlib import Path

from sci_constants import get_sci_home

PROVIDER = "boltzmann_models"
MODELS = ("qwen", "discoveryrsi", "glm", "codex")
DEFAULT_BASE_URL = "http://100.87.197.84:8010/v1"
LOGIN_REQUIRED = "You are not authorized to use Boltzmann models in this profile. Run /boltzmann_login to connect your account."


def owner_home():
    from agent.specialist_policy import current_policy

    home = get_sci_home().resolve()
    policy = current_policy()
    if (
        policy is not None
        and policy.execution_home
        and Path(policy.execution_home).resolve() == home
    ):
        return Path(policy.home).resolve()
    return home


@contextmanager
def owner_scope(expected=None):
    home = owner_home()
    if expected is not None and home != Path(expected).resolve():
        raise PermissionError(
            "This Boltzmann model client belongs to another profile. " + LOGIN_REQUIRED
        )
    from sci_cli.native_profile_creation import profile_scope

    with profile_scope(home):
        yield home


def endpoint():
    from sci_cli.config import read_user_config_raw
    from urllib.parse import urlsplit

    config = read_user_config_raw()
    value = config.get("providers", {}).get(PROVIDER, {}).get("base_url", "")
    model = config.get("model", {})
    if (
        not value
        and isinstance(model, dict)
        and model.get("provider") in {PROVIDER, "boltzmann-models"}
    ):
        value = model.get("base_url", "")
    value = (value or DEFAULT_BASE_URL).strip().rstrip("/")
    parsed = urlsplit(value)
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Boltzmann model base URL must be an HTTP(S) endpoint without credentials, query or fragment."
        )
    return value


def credentials(*, strict=False):
    from .auth import available, current_key

    with owner_scope():
        authorized = available()
        if strict and not authorized:
            raise PermissionError(LOGIN_REQUIRED)
        return {
            "provider": PROVIDER,
            "api_key": current_key() if authorized else "",
            "base_url": endpoint(),
            "source": "profile Boltzmann authorization",
        }


def setup_model(current_model=""):
    from .auth import require_authorized
    from sci_cli.model_setup_flows_common import _pick_model_or_prompt, _finish_model

    try:
        with owner_scope():
            key = require_authorized()
            base = endpoint()
    except PermissionError:
        print(LOGIN_REQUIRED)
        return
    print(
        f"Boltzmann model gateway: {base}\nThis sends model messages using this profile's Boltzmann account."
    )
    chosen = _pick_model_or_prompt(
        list(MODELS),
        "Model name: ",
        current_model=current_model,
        confirm_provider=PROVIDER,
        confirm_base_url=base,
        confirm_api_key=key,
        notes={
            "codex": "Gateway output limits are server-managed; max_tokens is ignored."
        },
    )
    if chosen and chosen not in MODELS:
        print("Choose qwen, discoveryrsi, glm or codex. Nothing changed.")
        return
    _finish_model(
        chosen,
        PROVIDER,
        f"Default model set to {chosen} via boltzmann_models",
        base_url=base,
        api_mode="chat_completions",
    )


def account_usage():
    from datetime import datetime, timezone
    from agent.account_usage import AccountUsageSnapshot
    from .auth import available, current_key
    from .authentication import AUTHENTICATE_URL
    from .nodeapi_helpers import authenticate_api_key
    from .model_response import latest_response

    with owner_scope() as home:
        authorized = available()
        key = current_key() if authorized else ""
        snapshot = latest_response(home, endpoint(), key) if authorized else None
        if snapshot is not None:
            return snapshot
        result = authenticate_api_key(key) if authorized else None
    details = ()
    if result is not None and result.authenticated:
        details = tuple(
            line
            for line in (
                f"Email: {result.email}" if result.email else "",
                f"Available credits: {result.credits:,.2f}"
                if result.credits is not None
                else "Available credits: not provided",
                f"Frozen credits: {result.frozen_credits:,.2f}"
                if result.frozen_credits is not None
                else "Frozen credits: not provided",
            )
            if line
        )
    return AccountUsageSnapshot(
        provider=PROVIDER,
        source=AUTHENTICATE_URL,
        fetched_at=datetime.now(timezone.utc),
        title="Boltzmann account",
        details=details,
        unavailable_reason=None
        if details
        else "Account balance unavailable; verify /boltzmann_login.",
    )
