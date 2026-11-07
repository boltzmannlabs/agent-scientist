"""The verifier sends the documented body and never forwards or exposes tokens."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests

from plugins.boltzmann.authentication import authenticate, MAX_RESPONSE_BYTES


@pytest.mark.parametrize("http,payload,authenticated", [
    (200, {"success": True, "email": "fixture@example.invalid", "credits": 0, "freezedCredits": 335}, True),
    (200, {"success": True}, True),
    (200, {"success": False, "message": "fixture-token"}, False),
    (200, {"success": "true"}, False),
    (200, {"status": "success"}, False),
    (200, [], False),
    (200, "not json", False),
    (401, {"success": False}, False),
    (403, {"success": False}, False),
    (500, {"success": True}, False),
    (302, {"success": True}, False),
    (200, "x" * (MAX_RESPONSE_BYTES + 1), False),
])
def test_verification_request_and_explicit_success_contract(http, payload, authenticated, capsys):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            calls.append(self.path)
            assert self.path == "/api/agent-authenticate"
            assert self.headers.get("Authorization") is None
            assert self.headers["Content-Type"] == "application/json"
            assert json.loads(self.rfile.read(int(self.headers["Content-Length"]))) == {"apiToken": "fixture-token"}
            self.send_response(http)
            self.send_header("Location", "/must-not-follow")
            self.end_headers()
            self.wfile.write((payload if isinstance(payload, str) else json.dumps(payload)).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = authenticate("fixture-token", endpoint=f"http://127.0.0.1:{server.server_port}/api/agent-authenticate")
        assert result.authenticated is authenticated
        assert calls == ["/api/agent-authenticate"]
        assert "fixture-token" not in repr(result) + result.account_summary() + capsys.readouterr().out
        if authenticated and "email" in payload:
            assert result.email == "fixture@example.invalid" and result.credits == 0
            assert result.frozen_credits == 335
            assert "Credits: 0" in result.account_summary()
        if authenticated and "email" not in payload:
            assert "not provided by the service" in result.account_summary()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize("error", [requests.exceptions.Timeout, requests.exceptions.SSLError])
def test_verification_errors_never_leak_credentials_or_retry(monkeypatch, error):
    calls = []

    def failed(url, **kwargs):
        calls.append((url, kwargs))
        raise error("fixture-token must not leak")

    monkeypatch.setattr(requests, "get", failed)
    assert not authenticate("").authenticated and not calls
    result = authenticate("fixture-token")
    assert not result.authenticated and "fixture-token" not in repr(result)
    assert len(calls) == 1
    assert calls[0][1]["timeout"] == 15 and calls[0][1]["allow_redirects"] is False
