"""Regressions for #49 and #52: real compression and named-review continuation.

Model responses and the next pipeline operation are controlled locally. No
scientific service, production credential or remote job is used.
"""
from copy import deepcopy
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread
from types import SimpleNamespace

import pytest

from agent.specialist_store import Specialist, save
from sci_cli.native_profile_creation import profile_scope
from sci_constants import get_sci_home

REPORT = "# Exact review\n\n| Check | Result |\n|---|---|\n| 2 + 2 | 4 |\n\nOutcome: completed"
BLOCKED = "Outcome: BLOCKED BEFORE EXECUTION\nRequired evidence is missing."


@pytest.fixture
def provider(monkeypatch, tmp_path):
    requests, advances = [], []
    scenario = {"delivery": "final", "blocked": False}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            messages = body["messages"]
            child = "Saved specialist:" in json.dumps(messages)
            results = [m for m in messages if m["role"] == "tool"]
            text, name, args = "Pipeline finished.", None, None
            if child:
                text = BLOCKED if scenario["blocked"] else REPORT
            elif advances:
                pass
            elif results or "ASYNC_REVIEW" in json.dumps(messages):
                if scenario["blocked"]:
                    text = "Blocked: review evidence is missing; no next step ran."
                elif "CATALOG_ONLY" not in json.dumps(messages):
                    name, args = "pipeline_next_fixture", {}
            elif "CATALOG_ONLY" in json.dumps(messages):
                name, args = "delegate_task", {"action": "catalog"}
            else:
                name, args = "delegate_task", {"tasks": [{
                    "specialist": "reviewer", "goal": "Check the supplied arithmetic: 2 + 2 = 4.",
                    "delivery": scenario["delivery"],
                }]}
            message = {"role": "assistant", "content": text}
            finish = "stop"
            if name:
                if name not in {t["function"]["name"] for t in body.get("tools", [])}:
                    args, name = {"calls": [{"name": name, "arguments": args}]}, "tool_call"
                message = {"role": "assistant", "content": None, "tool_calls": [{
                    "id": "call-" + name, "type": "function", "function": {
                        "name": name, "arguments": json.dumps(args)}}]}
                finish = "tool_calls"
            response = {"id": "fixture", "object": "chat.completion", "model": "fixture",
                        "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                        "usage": {"prompt_tokens": 30, "completion_tokens": 10, "total_tokens": 40}}
            if body.get("stream"):
                delta = deepcopy(message)
                if "tool_calls" in delta:
                    delta["tool_calls"][0]["index"] = 0
                response["object"] = "chat.completion.chunk"
                response["choices"][0] = {"index": 0, "delta": delta, "finish_reason": finish}
                raw = ("data: " + json.dumps(response) + "\n\ndata: [DONE]\n\n").encode()
            else:
                raw = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream" if body.get("stream") else "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("agent.model_metadata.get_model_context_length", lambda *a, **k: 131072)
    monkeypatch.setattr("agent.context_compressor.get_model_context_length", lambda *a, **k: 131072)
    monkeypatch.setattr("agent.title_generator.maybe_auto_title", lambda *a, **k: None)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    from tools.registry import registry
    from tools import async_delegation
    from tools.process_registry import process_registry
    async_delegation._reset_for_tests()
    while not process_registry.completion_queue.empty():
        process_registry.completion_queue.get_nowait()
    registry.register(name="pipeline_next_fixture", toolset="file",
                      schema={"name": "pipeline_next_fixture", "description": "Record a harmless next step.",
                              "parameters": {"type": "object", "properties": {}}},
                      handler=lambda args, **kw: advances.append(str(get_sci_home())) or '{"completed":true}')
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests, advances, scenario
    finally:
        if async_delegation._executor is not None:
            async_delegation._executor.shutdown(wait=True)
        async_delegation._reset_for_tests()
        server.shutdown()
        server.server_close()
        thread.join(5)


def _parent(home, url, *, session_id=None, db=None):
    from run_agent import AIAgent
    from sci_cli.config import atomic_config_replace
    atomic_config_replace(home / "config.yaml", {
        "model": {"default": "fixture", "provider": "custom", "base_url": url, "context_length": 131072},
        "tool_search": {"enabled": "off"}, "memory": {"enabled": False},
        "delegation": {"max_iterations": 4, "child_timeout_seconds": 60},
        "compression": {"tail_mode": "legacy", "protect_first_n": 0, "protect_last_n": 2},
    })
    parent = AIAgent(model="fixture", provider="custom", api_key="fixture-key", base_url=url,
                     api_mode="chat_completions", enabled_toolsets=["file", "delegation"],
                     quiet_mode=True, skip_context_files=True, skip_memory=True,
                     session_db=db, session_id=session_id, max_iterations=5)
    parent._disable_streaming = True
    return parent


def _delegate_schema(tools):
    return next(t["function"] for t in tools if t["function"]["name"] == "delegate_task")


@pytest.fixture
def multiplex():
    from agent.secret_scope import is_multiplex_active, set_multiplex_active
    previous = is_multiplex_active()
    set_multiplex_active(True)
    try:
        yield
    finally:
        set_multiplex_active(previous)


def test_compression_and_resume_keep_the_reviewed_specialist_interface_a_b_a(provider, tmp_path, monkeypatch, multiplex):
    from agent.conversation_compression_manual import compress_now, parse_compress_args
    from agent.specialist_runtime import resolve
    from sci_state import SessionDB
    url, requests, _, _ = provider
    summary = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content="## Goal\nReview arithmetic.\n## Progress\nEarlier arithmetic was checked; keep the review pending."))])
    monkeypatch.setattr("agent.context_compressor.call_llm", lambda **kw: summary)
    for index, name in enumerate(("a", "b", "a")):
        home = tmp_path / name
        with profile_scope(home):
            if index == 2:
                from agent.specialist_store import load
                previous = load("reviewer")
                item = save(replace(previous, enabled=True), expected_revision=previous.revision)
            else:
                item = save(Specialist("reviewer", f"Private {name} arithmetic reviewer", automatic=True))
            with SessionDB(home / "state.db") as db:
                parent = _parent(home, url, db=db)
                resumed = None
                try:
                    parent._cached_system_prompt = "Keep arithmetic reviews separate."
                    parent._ensure_db_session()
                    for i in range(12):
                        db.append_message(parent.session_id, "user", f"Question {i}: " + "number " * 80)
                        db.append_message(parent.session_id, "assistant", f"Answer {i}: " + "checked " * 400)
                    history = db.get_messages_as_conversation(parent.session_id)
                    before = deepcopy(parent.tools)
                    preview = compress_now(parent, history, parse_compress_args("--preview"))
                    assert preview.status == "preview" and parent.tools == before
                    compressed = compress_now(parent, history, parse_compress_args(""), system_message="")
                    assert compressed.removed > 0
                    schema = _delegate_schema(parent.tools)
                    props = schema["parameters"]["properties"]
                    assert "specialist" in props["tasks"]["items"]["properties"]
                    assert "catalog" in props["action"]["enum"] and "query" in props and "page" in props
                    assert parent._specialist_snapshot["reviewer"].purpose == item.purpose
                    # A second content-aware refresh must be byte-stable and not duplicate decoration.
                    from agent.conversation_compression import _refresh_agent_tool_definitions
                    snapshot = deepcopy(parent.tools)
                    _refresh_agent_tool_definitions(parent)
                    assert parent.tools == snapshot
                    later = f"later-{index}"
                    save(Specialist(later, "Created after the session started", automatic=True))
                    resumed = _parent(home, url, session_id=parent.session_id, db=db)
                    assert resumed.tools == parent.tools and later not in resumed._specialist_snapshot
                    result = resumed.run_conversation("CATALOG_ONLY", conversation_history=compressed.after_messages)
                    assert result["completed"], result
                    assert _delegate_schema(requests[-1]["tools"]) == schema
                    tool_rows = [m for m in requests[-1]["messages"] if m["role"] == "tool"]
                    assert item.purpose in tool_rows[-1]["content"]
                    assert f"Private {'b' if name == 'a' else 'a'}" not in tool_rows[-1]["content"]
                    save(replace(item, enabled=False), expected_revision=item.revision)
                    with pytest.raises(ValueError, match="disabled or edited"):
                        resolve(resumed, {"specialist": "reviewer"})
                    with pytest.raises(ValueError, match="delivery must be"):
                        resolve(resumed, {"specialist": "reviewer", "delivery": "unsupported"})
                finally:
                    if resumed:
                        resumed.close()
                    parent.close()


@pytest.mark.parametrize("delivery", ["final", "intermediate"])
@pytest.mark.parametrize("carrier", ["sync", "async"])
@pytest.mark.parametrize("blocked", [False, True])
def test_named_review_delivery_preserves_reports_and_continues_only_intermediate_work(
        provider, delivery, carrier, blocked, monkeypatch):
    from agent.specialist_runs import history
    from sci_state import SessionDB
    from tools.delegate_tool import delegate_task
    url, requests, advances, scenario = provider
    scenario.update(delivery=delivery, blocked=blocked)
    home = get_sci_home()
    save(Specialist("reviewer", "Review the supplied arithmetic", automatic=True))
    with SessionDB(home / "state.db") as db:
        parent = _parent(home, url, db=db)
        try:
            parent._cached_system_prompt = "Review first, then run the approved next step. Report blockers."
            parent._ensure_db_session()
            prompt, tools = parent._cached_system_prompt, deepcopy(parent.tools)
            if carrier == "sync":
                result = parent.run_conversation("RUN_REVIEW")
            else:
                from tools import async_delegation
                from tools.process_registry import process_registry
                monkeypatch.setattr("gateway.session_context.async_delivery_supported", lambda: True)
                dispatched = json.loads(delegate_task(tasks=[{
                    "specialist": "reviewer", "goal": "Check 2 + 2 = 4.", "delivery": delivery,
                }], parent_agent=parent, background=True))
                assert dispatched["mode"] == "background", dispatched
                event = process_registry.completion_queue.get(timeout=30)
                assert event["delegation_id"] == dispatched["delegation_id"]
                claim = async_delegation.claim_event_delivery(event, "fixture-consumer")
                assert claim
                from sci_cli.cli_chat_turn_mixin import CLIChatTurnMixin
                from tools.process_registry_notifications import TimelineNotification
                notification = TimelineNotification.for_delegation("ASYNC_REVIEW " + json.dumps(event["results"]), event)
                cli = SimpleNamespace(conversation_history=[])
                CLIChatTurnMixin._chat_stage_user_message(cli, parent, notification)
                result = parent.run_conversation(str(notification), conversation_history=[])
                async_delegation.complete_event_delivery(event, claim)
                assert async_delegation.claim_event_delivery(event, "replayed-consumer") is None
            assert len(advances) == int(delivery == "intermediate" and not blocked), result
            saved = history()[0]["result"]
            assert saved["summary"] == (BLOCKED if blocked else REPORT)
            assert saved["delivery"] == delivery
            if delivery == "intermediate":
                assert result["final_response"] == ("Blocked: review evidence is missing; no next step ran."
                                                    if blocked else "Pipeline finished.")
            elif not blocked:
                assert result["final_response"] == REPORT
            assert parent._cached_system_prompt == prompt and parent.tools == tools
            parent_calls = [r for r in requests if "Saved specialist:" not in json.dumps(r["messages"])]
            if carrier == "sync" and delivery == "intermediate":
                assert len(parent_calls) == (3 if not blocked else 2)
            assert all(not any(m.get("content") == "Continue" for m in r["messages"]) for r in parent_calls)
            for request in parent_calls:
                assert not any(a["role"] == b["role"] and a["role"] in {"user", "assistant"}
                               for a, b in zip(request["messages"], request["messages"][1:]))
        finally:
            parent.close()
