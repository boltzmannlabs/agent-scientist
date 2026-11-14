"""Deployment limits for gateway aliases; public model-family sizes are estimates only."""

from dataclasses import dataclass

from .model_gateway import PROVIDER, credentials, owner_scope


@dataclass(frozen=True)
class ModelLimits:
    context: int
    output: int | None
    source: str


def model_limits(model: str) -> ModelLimits | None:
    from agent.model_metadata import (
        DEFAULT_CONTEXT_LENGTHS, DEFAULT_FALLBACK_CONTEXT, _longest_key_match,
        fetch_endpoint_model_metadata, get_cached_context_length,
    )
    from agent.models_dev import _explicit_model_override, _override_int

    if not isinstance(model, str) or not model:
        return None
    with owner_scope():
        runtime = credentials()
        # A locked profile must not probe with main's key or infer access from a cache.
        metadata = fetch_endpoint_model_metadata(
            runtime["base_url"], api_key=runtime["api_key"]
        ) if runtime["api_key"] else {}
        entry = metadata.get(model, {})  # Never borrow another alias's window.
        override = _explicit_model_override(PROVIDER, model) or {}
        configured_context = _override_int(override, "context_window")
        saved_context = get_cached_context_length(model, runtime["base_url"])
    context = entry.get("context_length")
    output = entry.get("max_completion_tokens")
    if type(output) is not int or output <= 0:
        output = None
    if configured_context:
        return ModelLimits(configured_context, output, "configured")
    if type(context) is int and context > 0:
        return ModelLimits(context, output, "gateway metadata")
    if type(saved_context) is int and saved_context > 0:
        return ModelLimits(saved_context, output, "saved endpoint limit; gateway context limit unavailable")
    # Keep the previous budget when a deployment only advertises IDs, but clearly
    # identify it as an estimate rather than a verified deployment limit.
    family = _longest_key_match(DEFAULT_CONTEXT_LENGTHS, model.lower())
    return ModelLimits(family[1] if family else DEFAULT_FALLBACK_CONTEXT, output, "estimate")


def context_note(model: str, context_length: int) -> str:
    limits = model_limits(model)
    if limits is None:
        return ""
    if context_length != limits.context:
        return "configured override"
    if limits.source == "estimate":
        return "estimate; gateway context limit unavailable"
    return limits.source


def output_reservation(model: str, max_tokens: int | None) -> int | None:
    limits = model_limits(model)
    output = limits.output if limits else None
    # Codex's gateway route ignores max_tokens. A smaller caller cap cannot
    # provide a reliable reservation for its server-managed completion budget.
    if model == "codex":
        return output if output is not None else max_tokens
    return max_tokens if max_tokens is not None else output
