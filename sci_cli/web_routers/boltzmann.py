"""Profile-scoped web adapters for the existing Boltzmann CLI workflows."""
import hmac
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, SecretStr

from ._common import config_scoped_to_thread, destructive_profile, _CONFIG_MUTATION_LOCK

router = APIRouter(prefix="/api/boltzmann")


class LoginBody(BaseModel):
    api_key: SecretStr


def account_status(verify=False):
    from plugins.boltzmann.auth import available, current_key
    from plugins.boltzmann.nodeapi_helpers import authenticate_api_key
    key = current_key()
    authorized = bool(key and available())
    result = {"authorized": authorized, "verified": False,
              "message": "Account connected. Check status to refresh credits." if authorized else "Connect your Boltzmann account to enable scientific tools."}
    if verify and authorized:
        receipt = authenticate_api_key(key)
        if current_key() != key or not available():
            return {"authorized": False, "verified": False, "message": "Login changed during verification. Check status again."}
        result.update(verified=receipt.authenticated, message=receipt.message)
        if receipt.authenticated:
            result.update(email=receipt.email, credits=receipt.credits, frozen_credits=receipt.frozen_credits)
    return result


def login(key):
    from sci_cli.boltzmann_setup import run, _saved
    from sci_cli.callbacks import _secret_result
    from sci_cli.plugins import get_plugin_manager
    if not key.strip():
        raise HTTPException(400, "Enter a Boltzmann API key.")
    from ._common import is_redacted_credential_preview
    if is_redacted_credential_preview(key):
        raise HTTPException(400, "Enter the complete API key, not a masked preview.")
    # Reuse CLI validation, secure storage, science-profile policy review and
    # deferred activation. Restore its callback even when setup fails.
    with _CONFIG_MUTATION_LOCK:
        from plugins.boltzmann.auth import current_key, available
        if hmac.compare_digest(key.strip().encode(), current_key().encode()) and available():
            return {"ok": True, "already_connected": True,
                    "message": "This API key is already connected to this profile. Nothing was changed. Use Check status to verify current access and credits."}
        manager = get_plugin_manager()
        previous = manager._cli_ref
        cli = SimpleNamespace(agent=None, _secret_capture_callback=lambda name, prompt, **kw: _secret_result(name, key.strip(), **kw))
        try:
            message = run(cli, "--replace")
        finally:
            manager._cli_ref = previous
    notice = next((line for line in message.splitlines() if line.startswith((
        "New-conversation default:", "Model default unchanged:", "Boltzmann is connected, but"))), "")
    return {"ok": _saved(message), "message": ("Boltzmann is connected. Your tools will be available in a new conversation. " + notice).strip() if _saved(message) else message}


@router.get("/status")
async def status(profile: str | None = None, verify: bool = False):
    return await config_scoped_to_thread(profile, lambda: account_status(verify))


@router.post("/login")
async def connect(body: LoginBody, profile: str | None = None):
    profile = destructive_profile(profile, "Boltzmann login")
    return await config_scoped_to_thread(profile, lambda: login(body.api_key.get_secret_value()))


@router.get("/tools")
async def tools(profile: str | None = None, query: str = ""):
    def read():
        from sci_cli.science_catalog_view import catalog_rows, _section, authorization_summary
        from sci_cli.boltzmann_descriptions import descriptions
        definitions = descriptions()
        return {"tools": [dict(row, section=_section(row), description=definitions.get((row["module"], row["name"]), "Definition not yet available.")) for row in catalog_rows(query=query)],
                "notice": authorization_summary()}
    return await config_scoped_to_thread(profile, read)
