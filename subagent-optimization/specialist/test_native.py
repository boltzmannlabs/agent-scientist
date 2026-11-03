"""Native integration canary: real saved child, loopback fixture, no scientific/model inference.

Run through Agent Scientist's scripts/run_tests.sh with this explicit file path.
All profile state is temporary. Fixture answers/usage are synthetic, not LLM work.
"""
from contextlib import contextmanager
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import socket
import sys
import threading

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from specialist.advisor import prepare, accept, parse_answer
from specialist.fixtures import source, canned_answer

DEFINITION = Path(__file__).with_name("definition.json")


@pytest.fixture
def isolated_home(tmp_path, monkeypatch):
    home = tmp_path / ".sci"
    home.mkdir()
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setenv("SCI_TEST_ISOLATION", str(home))
    monkeypatch.setenv("SCI_DISABLE_LAZY_INSTALLS", "1")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    monkeypatch.setenv("TIRITH_ENABLED", "false")
    monkeypatch.setenv("SCI_GATEWAY_LOCK_DIR", str(tmp_path / "gateway-locks"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    from sci_constants import set_sci_home_override, reset_sci_home_override
    scope_token = set_sci_home_override(home)
    # This external file does not inherit the host tests/conftest.py. Pin
    # pre-existing module defaults too, rather than leaking the first test home.
    state = sys.modules.get("sci_state")
    if state is not None:
        monkeypatch.setattr(state, "DEFAULT_DB_PATH", home / "state.db")
    # Only loopback inference fixtures are allowed in this test, including DNS.
    original_connect, original_resolve = socket.socket.connect, socket.getaddrinfo
    def connect(sock, address):
        if sock.family in (socket.AF_INET, socket.AF_INET6):
            assert address[0] in {"127.0.0.1", "::1"}, "Non-loopback connection blocked by canary"
        return original_connect(sock, address)
    def resolve(host, *args, **kwargs):
        assert host in {None, "localhost", "127.0.0.1", "::1", b"127.0.0.1"}, "External DNS blocked by canary"
        return original_resolve(host, *args, **kwargs)
    monkeypatch.setattr(socket.socket, "connect", connect)
    monkeypatch.setattr(socket, "getaddrinfo", resolve)
    try:
        yield home
    finally:
        reset_sci_home_override(scope_token)


def test_portable_definition_imports_disabled_without_tool_grants(isolated_home):
    from sci_cli.specialist_portability import import_definition
    from agent.specialist_store import load
    class ImportUI:
        def show(self, text):
            pass
        def choose(self, question, options):
            assert options == ["Import", "Cancel"]
            return "Import"  # Fixture confirmation applies only to the temporary home.
    import_definition(None, ImportUI(), [str(DEFINITION)])
    item = load("smallmol-investigation")
    assert not item.enabled and item.needs_review
    assert not item.tools and not item.skills and not item.children and not item.sources
    assert (isolated_home / "subagents" / (item.name + ".json")).is_file()


@contextmanager
def model_fixture(answer):
    calls = []
    content = json.dumps(answer)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append(payload)
            usage = {"prompt_tokens": 40, "completion_tokens": 12, "total_tokens": 52}
            result = {"id": "local-contract-fixture", "object": "chat.completion", "model": "fixture-model",
                      "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                                   "finish_reason": "stop"}], "usage": usage}
            if payload.get("stream"):
                chunks = [
                    {"id": result["id"], "object": "chat.completion.chunk", "model": "fixture-model",
                     "choices": [{"index": 0, "delta": {"role": "assistant", "content": content}, "finish_reason": None}]},
                    {"id": result["id"], "object": "chat.completion.chunk", "model": "fixture-model",
                     "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}], "usage": usage}]
                raw = ("".join("data: " + json.dumps(c) + "\n\n" for c in chunks) + "data: [DONE]\n\n").encode()
            else:
                raw = json.dumps(result).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream" if payload.get("stream") else "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", calls
    finally:
        server.shutdown(); server.server_close(); thread.join(5)


def test_native_child_handoff_no_tools_freshness_and_revocation(isolated_home, monkeypatch):
    from agent.specialist_store import Specialist, save
    from agent.specialist_runtime import resolve
    from agent.specialist_policy import specialist_scope, check_call
    from agent.specialist_runs import history
    from sci_cli.config import atomic_config_replace
    from run_agent import AIAgent
    from tools.delegate_tool import delegate_task
    from sci_state import SessionDB
    monkeypatch.setattr("agent.model_metadata.get_model_context_length", lambda *a, **k: 131072)
    monkeypatch.setattr("agent.context_compressor.get_model_context_length", lambda *a, **k: 131072)
    snapshot = source(); assignment = prepare(snapshot)
    definition = Specialist.parse(json.loads(DEFINITION.read_text()))
    with model_fixture(canned_answer(assignment["input_digest"])) as (url, calls):
        atomic_config_replace(isolated_home / "config.yaml", {
            "model": {"default": "fixture-model", "provider": "custom", "base_url": url, "context_length": 131072},
            "tool_search": {"enabled": "off"}, "memory": {"enabled": False},
            "delegation": {"max_iterations": 3, "child_timeout_seconds": 120}, "agent": {"max_iterations": 3}})
        # Test-only activation in a disposable home; no production review is bypassed.
        saved = save(replace(definition, enabled=True, needs_review=False))
        db = SessionDB(isolated_home / "state.db")
        parent = AIAgent(model="fixture-model", provider="custom", api_key="local-fixture-key",
                         base_url=url, api_mode="chat_completions", enabled_toolsets=["file", "delegation"],
                         quiet_mode=True, skip_context_files=True, skip_memory=True, session_db=db)
        try:
            parent._cached_system_prompt = "Parent cache sentinel."
            before_tools = json.dumps(parent.tools, sort_keys=True)
            _, policy = resolve(parent, assignment["request"])
            assert not policy.tools and not policy.skills and not policy.children
            with specialist_scope(policy):
                for name in ("read_file", "terminal", "boltzmann_submit", "delegate_task"):
                    assert check_call(name, {}) is not None
            native = json.loads(delegate_task(tasks=[assignment["request"]], parent_agent=parent))
            result = native["results"][0]
            assert result["status"] == "completed", native
            receipt = accept(assignment, parse_answer(result["summary"]), snapshot)
            assert receipt["status"] == "mechanically_valid_advice"
            assert calls and all(not p.get("tools") for p in calls)
            assert assignment["input_digest"] in json.dumps(calls)
            assert parent._cached_system_prompt == "Parent cache sentinel."
            assert json.dumps(parent.tools, sort_keys=True) == before_tools
            assert any(r["specialist"] == saved.name and r["status"] == "completed" for r in history())
            save(replace(saved, enabled=False), expected_revision=saved.revision)
            count = len(calls)
            denied = json.loads(delegate_task(tasks=[assignment["request"]], parent_agent=parent))
            assert "error" in denied and len(calls) == count
        finally:
            parent.close()
            db.close()
