"""32K routes must work through real startup, switching, compression and preflight."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
from threading import Thread

import pytest


@pytest.fixture
def small_context_server(monkeypatch, tmp_path):
    requests = []
    windows = {"fixture-small": 32768, "fixture-large": 131072}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_GET(self):
            raw = json.dumps({"data": [
                {"id": model, "context_length": window} for model, window in windows.items()
            ]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            if not self.path.endswith("/chat/completions"):
                self.send_error(404)
                return
            requests.append(body)
            text = "## Goal\nContinue the saved task.\n## Progress\nEarlier work is complete; job fixture-123 remains pending."
            choice = {"index": 0, "message": {"role": "assistant", "content": text}, "finish_reason": "stop"}
            response = {"id": "fixture", "object": "chat.completion", "model": body["model"],
                        "choices": [choice], "usage": {"prompt_tokens": 100, "completion_tokens": 30, "total_tokens": 130}}
            if body.get("stream"):
                choice["delta"] = choice.pop("message")
                response["object"] = "chat.completion.chunk"
                raw = ("data: " + json.dumps(response) + "\n\ndata: [DONE]\n\n").encode()
            else:
                raw = json.dumps(response).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream" if body.get("stream") else "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr("agent.title_generator.maybe_auto_title", lambda *a, **k: None)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


def _build(home, url, *, output=2048):
    from run_agent import AIAgent
    from sci_cli.config import atomic_config_replace
    atomic_config_replace(home / "config.yaml", {
        "model": {"default": "fixture-small", "provider": "custom", "base_url": url, "context_length": 32768},
        "agent": {"max_tokens": 2048}, "memory": {"enabled": False},
        "tool_search": {"enabled": "off"},
        "auxiliary": {"compression": {"provider": "auto", "model": "fixture-small", "context_length": 32768}},
        "compression": {"tail_mode": "legacy", "protect_first_n": 0, "protect_last_n": 2},
    })
    agent = AIAgent(model="fixture-small", provider="custom", api_key="fixture-key", base_url=url,
                    api_mode="chat_completions", enabled_toolsets=["file"], quiet_mode=True,
                    skip_context_files=True, skip_memory=True, max_iterations=2, max_tokens=output)
    agent._disable_streaming = True
    return agent


@pytest.mark.parametrize("summary_parent", ["fixture-small", "fixture-large"])
def test_small_route_start_switch_compress_and_profile_isolation(small_context_server, tmp_path, summary_parent):
    from agent.conversation_compression_manual import compress_now, parse_compress_args
    from agent.secret_scope import is_multiplex_active, set_multiplex_active
    from sci_cli.native_profile_creation import profile_scope
    from agent.model_metadata import estimate_request_tokens_rough
    from sci_cli.model_switch import switch_model
    url, requests = small_context_server
    previous = is_multiplex_active()
    set_multiplex_active(True)
    try:
        for name in ("a", "b", "a"):
            with profile_scope(tmp_path / name):
                agent = _build(tmp_path / name, url)
                try:
                    assert agent.context_compressor.context_length == 32768
                    assert 0 < agent.context_compressor.threshold_tokens < 32768 - agent.max_tokens
                    result = agent.run_conversation("Hello", system_message="You are a helpful assistant.")
                    assert result["completed"], result
                    for model, window in (("fixture-large", 131072), ("fixture-small", 32768)):
                        selected = switch_model(model, agent.provider, agent.model, current_base_url=url,
                                                current_api_key="fixture-key", explicit_provider="custom")
                        assert selected.success, selected
                        agent.switch_model(selected.new_model, selected.target_provider, api_key=selected.api_key,
                                           base_url=selected.base_url, api_mode=selected.api_mode)
                        assert agent.context_compressor.context_length == window
                        assert agent.context_compressor.threshold_tokens < window - agent.max_tokens
                    agent.switch_model(summary_parent, "custom", api_key="fixture-key", base_url=url, api_mode="chat_completions")
                    history = []
                    for i in range(64):
                        history.extend([{"role": "user", "content": f"Review {i}: " + "value " * 100},
                                        {"role": "assistant", "content": "job fixture-123 pending; " + "evidence " * 400}])
                    before = len(requests)
                    compressed = compress_now(agent, history, parse_compress_args(""), system_message="Keep pending job IDs.")
                    assert compressed.removed > 0, compressed
                    assert len(requests) > before  # the real auxiliary route reached the local fixture
                    for request in requests[before:]:
                        assert request["model"] == "fixture-small"
                        assert estimate_request_tokens_rough(request["messages"], tools=request.get("tools")) < 32768 * 0.75
                    assert "fixture-123" in json.dumps(compressed.after_messages)
                    assert agent._compression_feasibility_checked
                finally:
                    agent.close()
    finally:
        set_multiplex_active(previous)


@pytest.mark.parametrize("compression,output,message", [
    (True, 2048, "uncompressible " * 40000),
    (False, 2048, "uncompressible " * 40000),
    (False, 32768, "Hello"),
])
def test_oversized_protected_input_is_not_sent_on_small_route(small_context_server, tmp_path, compression, output, message):
    from sci_cli.native_profile_creation import profile_scope
    url, requests = small_context_server
    with profile_scope(tmp_path / "oversized"):
        agent = _build(tmp_path / "oversized", url, output=output)
        try:
            agent.compression_enabled = compression
            result = agent.run_conversation(message, system_message="Keep user input intact.")
            assert not result["completed"], result
            assert not requests, "An oversized protected request must be refused before contacting the model"
        finally:
            agent.close()
