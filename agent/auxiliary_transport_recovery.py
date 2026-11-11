"""Recover invalidated auxiliary transports without changing the resolved route."""

from __future__ import annotations

import logging
from typing import Any

from agent.redact import redact_sensitive_text

logger = logging.getLogger(__name__)


def compression_stream_kwargs(client: Any, kwargs: dict, task: str | None) -> dict:
    """Apply adapter-only deadlines on primary, credential-retry and fallback routes."""
    from agent import auxiliary_client as aux

    if task != "compression" or not isinstance(client, (aux.CodexAuxiliaryClient, aux.AsyncCodexAuxiliaryClient)):
        return kwargs
    override = kwargs.get("no_progress_timeout") or aux._get_task_no_progress_timeout(task)
    updated = dict(kwargs)
    if override is not None:
        updated["no_progress_timeout"] = override
    updated["initial_response_timeout"] = override or kwargs.get("timeout") or aux._effective_aux_timeout(task, None)
    return updated


def refresh_closed_request(req: Any, *, task: str | None, main_runtime: dict | None,
                           async_mode: bool) -> Any:
    """Replace a closed client, preserving request bytes and the owning profile scope.

    Cache eviction alone cannot repair the client already captured by a retry closure.
    Healthy transports are reused; credential recovery remains the router's responsibility.
    """
    from agent import auxiliary_client as aux

    client = req.client
    leaf = getattr(client, "_real_client", client)
    is_closed = getattr(leaf, "is_closed", None)
    closed = is_closed() if callable(is_closed) else is_closed
    if closed is not True and getattr(leaf, "_sci_aux_transport_invalidated", False) is not True:
        return req
    aux._evict_cached_client_instance(leaf)
    aux._evict_cached_client_instance(client)
    # Pin the actual destination, including custom endpoint and wire protocol. Do not
    # re-enter auto discovery after a transport failure and silently select another provider.
    provider = req.request_provider
    runtime = aux._normalize_main_runtime(main_runtime)
    mode = req.resolved_api_mode
    if isinstance(client, (aux.CodexAuxiliaryClient, aux.AsyncCodexAuxiliaryClient)):
        mode = "codex_responses"
    elif not mode and runtime.get("provider") == provider:
        mode = runtime.get("api_mode")
    base = req.base_info or req.resolved_base_url
    key = req.resolved_api_key or getattr(client, "api_key", None)
    replacement, model = aux._get_cached_client(
        provider, req.final_model, async_mode=async_mode, base_url=base,
        api_key=key, api_mode=mode, main_runtime=runtime,
        is_vision=task == "vision", task=task,
    )
    if replacement is None:
        raise aux.AuxiliaryClientUnavailable("The selected auxiliary provider could not rebuild its transport.")
    actual_base = str(getattr(replacement, "base_url", "") or "")
    if (model != req.final_model
            or aux._effective_provider_for_client(replacement, provider) != provider
            or (base and actual_base.rstrip("/") != str(base).rstrip("/"))):
        raise aux.AuxiliaryClientUnavailable(
            "Auxiliary transport recovery changed the selected route; no retry was sent."
        )
    logger.info("Auxiliary %s: replaced closed transport on the same provider (%s)",
                task or "call", provider)
    return req._replace(client=replacement)


def failure_detail(exc: Exception) -> str:
    """Retain useful transport cause types without logging payloads or credentials."""
    message = redact_sensitive_text(str(exc).strip() or type(exc).__name__, force=True)
    causes, seen = [], {id(exc)}
    cause = exc.__cause__ or exc.__context__
    while cause is not None and id(cause) not in seen and len(causes) < 5:
        seen.add(id(cause))
        name = type(cause).__name__
        errno = getattr(cause, "errno", None)
        causes.append(f"{name}(errno={errno})" if isinstance(errno, int) else name)
        cause = cause.__cause__ or cause.__context__
    return message[:300] + ("; caused by " + " -> ".join(causes) if causes else "")


def retain_initial_failure(final: Exception, initial: Exception) -> None:
    """Keep the first failure visible without changing exception classification/recovery."""
    if final is not initial:
        final.add_note("Initial auxiliary attempt: " + failure_detail(initial))


def compression_failure_detail(exc: Exception) -> str:
    notes = [note for note in getattr(exc, "__notes__", ())
             if isinstance(note, str) and note.startswith("Initial auxiliary attempt: ")]
    final = failure_detail(exc)
    return (notes[0] + "; final attempt: " + final) if notes else final
