"""Profile-local authorization granted only by the reviewed /add_boltzmann flow."""

import hashlib
import hmac

from agent.secret_scope import build_profile_secret_scope
from sci_constants import get_sci_home, profile_name_for_home, sci_home_key
from sci_cli.plugins_state import PluginState

from .nodeapi_helpers import validate_api_key

KEY_NAME = "BOLTZMANN_API_KEY"
AUTH_MESSAGE = "Boltzmann is locked. Run /boltzmann_login or /add_boltzmann in this profile and enter a valid API key."


def _profile_context():
    home = get_sci_home()
    name = profile_name_for_home(home)
    label = "main (default)" if name == "default" else name or "custom SCI_HOME"
    return f"Active profile: {label}. Resolved SCI_HOME: {home}. Profile .env location: {home / '.env'}."


def current_key():
    # Read the owning profile, never a different profile's inherited process env.
    # Re-reading also notices local key removal/rotation between calls.
    return (build_profile_secret_scope(get_sci_home()).get(KEY_NAME) or "").strip()


def fingerprint(key):
    return hashlib.sha256(f"{sci_home_key()}\0{key}".encode()).hexdigest()


def available():
    """Cheap discovery gate; execution independently revalidates with the service."""
    key = current_key()
    if not key:
        return False
    try:
        receipt = PluginState("boltzmann").get("authorization", "")
    except RuntimeError:
        return False
    return isinstance(receipt, str) and hmac.compare_digest(receipt, fingerprint(key))


def authorize_saved_key(*, expected_fingerprint=None):
    """Called only after the secure prompt validated and persisted the supplied key."""
    key = current_key()
    if not key:
        raise ValueError("No saved Boltzmann credential")
    verified = fingerprint(key)
    if expected_fingerprint is not None and not hmac.compare_digest(verified, expected_fingerprint):
        raise ValueError("Boltzmann key changed after verification. Verify the current key before authorizing it.")
    PluginState("boltzmann").set("authorization", verified)


def require_authorized():
    key = current_key()
    context = _profile_context()
    if not key:
        raise PermissionError(
            f"No Boltzmann API key is configured in this profile's credential scope. {context} "
            "Keys from main or other profiles are not used as a fallback. "
            f"{AUTH_MESSAGE} The requested operation was not started."
        )
    if not available():
        raise PermissionError(
            f"A Boltzmann API key is configured, but its profile authorization record is missing, "
            f"unreadable, or does not match. {context} {AUTH_MESSAGE} "
            "The requested operation was not started."
        )
    if not validate_api_key(key):
        raise PermissionError(
            f"A Boltzmann API key is configured and locally authorized. {context} "
            "The service credential check did not succeed; this is NOT a missing-key diagnosis. "
            "The check may have failed due to authorization, connectivity, or a service response error. "
            "The requested operation was not started. This does not determine or change any existing job's outcome. "
            "Check service connectivity and credential validity before retrying."
        )
    return key
