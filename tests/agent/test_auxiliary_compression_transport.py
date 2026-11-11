"""Compression budgets and recovery must work without machine-specific routing."""

import asyncio
import json
from pathlib import Path

import httpx
import pytest
from openai import OpenAI

from agent import auxiliary_client as aux
from agent.secret_scope import get_secret, is_multiplex_active, set_multiplex_active
from sci_cli.native_profile_creation import profile_scope


@pytest.mark.parametrize("async_mode,wire", [(False, "codex_responses"), (True, "codex_responses"),
                                           (False, "chat_completions")])
def test_compression_rebuilds_closed_transport_in_owning_profile(tmp_path, monkeypatch, async_mode, wire):
    """Real resolution, cache, SDK, adapter and retry across A -> B -> A; no network."""
    homes = [tmp_path / name for name in ("a", "b")]
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for home in homes:
        home.mkdir()
        (home / "config.yaml").write_text(
            "auxiliary:\n  compression:\n    no_progress_timeout: 5\n"
        )
        (home / ".env").write_text("FIXTURE_MODEL_KEY=fixture-" + home.name + "\n")
    monkeypatch.setattr(aux, "_client_cache", {})
    monkeypatch.setattr(aux, "_TRANSIENT_RETRY_BACKOFF_BASE", 0)
    guards, clients, requests, failed = [], [], [], set()
    monkeypatch.setattr(aux._CodexStreamGuard, "start", lambda self: guards.append(self))

    def factory(*, api_key, base_url, **kwargs):
        def respond(request):
            payload = json.loads(request.content)
            requests.append((request.headers["authorization"], payload["model"], str(request.url)))
            if api_key not in failed:
                failed.add(api_key)
                # The actual watchdog cleanup poisons and evicts this leaf client.
                if wire == "codex_responses":
                    guards[-1]._close_client_on_timeout()
                else:
                    client.close()
                raise httpx.ReadError("controlled interrupted read", request=request)
            if wire == "chat_completions":
                assert "initial_response_timeout" not in payload
                assert "no_progress_timeout" not in payload
                return httpx.Response(200, json={
                    "id": "controlled", "object": "chat.completion", "created": 1,
                    "model": payload["model"], "choices": [{"index": 0, "finish_reason": "stop",
                        "message": {"role": "assistant", "content": "Retained summary."}}],
                })
            event = {
                "type": "response.completed",
                "response": {
                    "id": "controlled-response", "object": "response", "status": "completed",
                    "output": [{"type": "message", "id": "msg", "role": "assistant",
                                "status": "completed", "content": [
                                    {"type": "output_text", "text": "Retained summary.", "annotations": []}]}],
                },
            }
            item = {"type": "response.output_item.done", "output_index": 0,
                    "item": event["response"]["output"][0]}
            return httpx.Response(200, headers={"content-type": "text/event-stream"},
                                  text="".join("data: " + json.dumps(row) + "\n\n" for row in (item, event)))

        kwargs.pop("http_client", None)
        client = OpenAI(api_key=api_key, base_url=base_url,
                        http_client=httpx.Client(transport=httpx.MockTransport(respond)), **kwargs)
        clients.append(client)
        return client

    monkeypatch.setattr(aux, "_create_openai_client", factory)

    async def run():
        for home in (homes[0], homes[1], homes[0]):
            with profile_scope(home):
                runtime = dict(provider="custom", model="summary-" + home.name,
                               api_key=get_secret("FIXTURE_MODEL_KEY"),
                               base_url="http://compression.test/v1", api_mode=wire)
                arguments = dict(task="compression", main_runtime=runtime,
                                 messages=[{"role": "user", "content": "Summarize this conversation."}])
                response = (await aux.async_call_llm(**arguments) if async_mode
                            else aux.call_llm(**arguments))
                assert response.choices[0].message.content == "Retained summary."

    was_multiplex = is_multiplex_active()
    set_multiplex_active(True)
    try:
        asyncio.run(run())
        assert [(key, model) for key, model, _ in requests] == [
            ("Bearer fixture-a", "summary-a"), ("Bearer fixture-a", "summary-a"),
            ("Bearer fixture-b", "summary-b"), ("Bearer fixture-b", "summary-b"),
            ("Bearer fixture-a", "summary-a"),
        ]
        path = "responses" if wire == "codex_responses" else "chat/completions"
        assert all(url == "http://compression.test/v1/" + path for _, _, url in requests)
        assert sum(client.is_closed() for client in clients) == len(failed)
        assert {client.api_key for client in clients if not client.is_closed()} == failed
    finally:
        set_multiplex_active(was_multiplex)
        for client in clients:
            client.close()


@pytest.mark.parametrize("task,override", [("compression", None), ("compression", 5), ("title_generation", None)])
def test_initial_budget_and_subsequent_inactivity_are_separate(tmp_path, monkeypatch, task, override):
    """Task config reaches the real guard; keepalives cannot extend either deadline."""
    from types import SimpleNamespace

    (tmp_path / "config.yaml").write_text(
        f"auxiliary:\n  {task}:\n    timeout: 320\n"
        + (f"    no_progress_timeout: {override}\n" if override else "")
    )
    monkeypatch.setenv("SCI_HOME", str(tmp_path))
    captured = []

    class StopInspection(Exception):
        pass

    def start(guard):
        captured.append(guard)
        raise StopInspection()

    real = SimpleNamespace(api_key="fixture", base_url="http://compression.test/v1")
    client = aux.CodexAuxiliaryClient(real, "fixture-model")
    monkeypatch.setattr(aux, "_get_cached_client", lambda *a, **k: (client, "fixture-model"))
    monkeypatch.setattr(aux._CodexStreamGuard, "start", start)
    with pytest.raises(StopInspection):
        aux.call_llm(task=task, provider="custom", model="fixture-model",
                     messages=[{"role": "user", "content": "Summarize."}])
    guard = captured[0]
    initial = override or (320 if task == "compression" else guard.no_progress_timeout)
    assert guard.effective_deadline() - guard._start == pytest.approx(initial)
    if task == "compression" and override is None:
        assert not aux._should_retry_same_provider(task, TimeoutError(guard.timeout_message()), "")
    guard.on_event(SimpleNamespace(type="response.in_progress"))
    assert guard.effective_deadline() - guard._start == pytest.approx(initial)
    guard.record_progress()
    assert guard.effective_deadline() - aux.time.monotonic() == pytest.approx(
        guard.no_progress_timeout, abs=0.1
    )


def test_failure_report_retains_timeout_and_safe_connection_cause():
    from agent.auxiliary_transport_recovery import retain_initial_failure
    from agent.context_compressor import _short_error_text

    initial = TimeoutError("No output within the initial-response timeout")
    final = ConnectionError("Connection error.")
    final.__cause__ = ConnectionRefusedError(111, "private payload and secret must not appear")
    retain_initial_failure(final, initial)
    detail = _short_error_text(final)
    assert "initial-response timeout" in detail
    assert "Connection error." in detail
    assert "ConnectionRefusedError(errno=111)" in detail
    assert "private payload" not in detail
