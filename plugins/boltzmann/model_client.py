"""Guarded OpenAI SDK clients for a gateway which currently supports JSON only."""

from types import SimpleNamespace

from .model_gateway import catalog_models, endpoint, owner_home, owner_scope
from .model_response import remember_response


def _request(home, base_url, kwargs):
    from .auth import require_authorized
    from sci_cli.shared_provider_lifecycle import enforce_runtime_access

    with owner_scope(home):
        enforce_runtime_access("boltzmann_models")
        if str(base_url).rstrip("/") != endpoint():
            raise PermissionError(
                "Boltzmann model endpoint changed. Re-select the provider before sending messages."
            )
        key = require_authorized()
        models = catalog_models()
    kwargs = dict(kwargs)
    model = kwargs.get("model")
    if not isinstance(model, str) or model not in (models or []):
        raise ValueError("Boltzmann model is unavailable in this account's gateway catalog. Refresh the model picker and check connectivity.")
    extra = dict(kwargs.get("extra_body") or {})
    if "model" in extra and extra["model"] != model:
        raise ValueError("extra_body cannot override the reviewed Boltzmann model.")
    extra.pop("model", None)
    streaming = bool(kwargs.pop("stream", False))
    kwargs.pop("stream_options", None)
    extra.pop("stream", None)
    extra.pop("stream_options", None)
    for field in ("reasoning_effort", "reasoning"):
        kwargs.pop(field, None)
        extra.pop(field, None)
    if model == "codex":
        kwargs.pop("max_tokens", None)
        extra.pop("max_tokens", None)
    kwargs["extra_body"] = extra
    kwargs["stream"] = False
    headers = {
        name: value
        for name, value in (kwargs.get("extra_headers") or {}).items()
        if name.lower() != "authorization"
    }
    kwargs["extra_headers"] = {**headers, "Authorization": "Bearer " + key}
    return kwargs, streaming


def _chunks(response):
    from agent.acp_openai_bridge import completion_to_stream_chunks

    chunks = completion_to_stream_chunks(response)
    for chunk in chunks:
        chunk.id, chunk.created = response.id, response.created
        chunk.object = "chat.completion.chunk"
    return chunks


class BoltzmannClient:
    def __init__(self, **kwargs):
        from openai import OpenAI

        self._home = owner_home()
        self._kwargs = {**kwargs, "max_retries": 0}
        self._kwargs.setdefault("api_key", "boltzmann-login-required")
        with owner_scope(self._home):
            self._kwargs.setdefault("base_url", endpoint())
        self._sdk = OpenAI(**self._kwargs)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def __getattr__(self, name):
        return getattr(self._sdk, name)

    def _create(self, **kwargs):
        kwargs, stream = _request(self._home, self._sdk.base_url, kwargs)
        response = self._sdk.chat.completions.create(**kwargs)
        remember_response(
            self._home,
            self._sdk.base_url,
            kwargs["extra_headers"]["Authorization"].removeprefix("Bearer "),
            kwargs["model"],
            response,
        )
        return _chunks(response) if stream else response

    def with_options(self, **kwargs):
        with owner_scope(self._home):
            return type(self)(**{**self._kwargs, **kwargs})

    def to_async_client(self):
        kwargs = dict(self._kwargs)
        kwargs.pop(
            "http_client", None
        )  # A synchronous HTTP transport cannot be borrowed by AsyncOpenAI.
        return AsyncBoltzmannClient(owner=self._home, **kwargs)


class AsyncChunks:
    def __init__(self, chunks):
        self.chunks = chunks

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        pass


class AsyncBoltzmannClient:
    def __init__(self, *, owner=None, **kwargs):
        from openai import AsyncOpenAI

        self._home = owner or owner_home()
        self._kwargs = {**kwargs, "max_retries": 0}
        self._sdk = AsyncOpenAI(**self._kwargs)
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def __getattr__(self, name):
        return getattr(self._sdk, name)

    def with_options(self, **kwargs):
        with owner_scope(self._home):
            return type(self)(owner=self._home, **{**self._kwargs, **kwargs})

    async def _create(self, **kwargs):
        import asyncio

        kwargs, stream = await asyncio.to_thread(
            _request, self._home, self._sdk.base_url, kwargs
        )
        response = await self._sdk.chat.completions.create(**kwargs)
        remember_response(
            self._home,
            self._sdk.base_url,
            kwargs["extra_headers"]["Authorization"].removeprefix("Bearer "),
            kwargs["model"],
            response,
        )
        return AsyncChunks(_chunks(response)) if stream else response
