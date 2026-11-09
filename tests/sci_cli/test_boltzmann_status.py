"""Status reads owning-profile credentials without changing login or session state."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from plugins.boltzmann import authentication


class Response:
    def __init__(self, code=200, payload=None):
        self.status_code = code
        self.payload = payload if payload is not None else {
            "success": True, "email": "scientist@example.test", "credits": 1234.5, "freezedCredits": 60,
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def iter_content(self, chunk_size):
        yield json.dumps(self.payload).encode()


@pytest.mark.parametrize("unconfigured_key", [False, True])
def test_status_command_is_read_only_and_profile_scoped(tmp_path, monkeypatch, unconfigured_key):
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from cli import SciCLI
    from plugins.boltzmann.auth import authorize_saved_key, available
    from sci_cli.commands import COMMANDS, resolve_command
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.skin_engine import init_skin_from_config, get_active_skin

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    main = tmp_path / ".sci"
    monkeypatch.setenv("SCI_HOME", str(main))
    monkeypatch.setattr("sci_constants.get_default_sci_root", lambda: main)
    a, b = main / "profiles" / "a", main / "profiles" / "b"
    for home in (main, a, b):
        home.mkdir(parents=True, exist_ok=True)
        (home / "config.yaml").write_text("plugins: {enabled: []}\n")
        if home != b or unconfigured_key:
            (home / ".env").write_text(f"BOLTZMANN_API_KEY=fixture-{home.name}-secret\n")
        with profile_scope(home):
            # A running CLI initializes its profile's skin before slash commands.
            init_skin_from_config({})
            if home != b:
                authorize_saved_key()
            else:
                available()  # Pre-create any state lock before the read-only snapshot.

    calls = []

    def get(endpoint, **kwargs):
        calls.append(kwargs["json"]["apiToken"])
        assert endpoint == authentication.AUTHENTICATE_URL
        assert kwargs["allow_redirects"] is False
        assert kwargs["timeout"] == authentication.TIMEOUT_SECONDS
        return Response()

    monkeypatch.setattr(authentication.requests, "get", get)
    cli = SciCLI.__new__(SciCLI)
    output = []
    cli._console_print = output.append
    cli.messages = [{"role": "user", "content": "keep this history"}]
    cli.system_prompt = "cached prompt"
    cli.enabled_toolsets = ["file"]
    session_before = (list(cli.messages), cli.system_prompt, list(cli.enabled_toolsets))
    before = {p: p.read_bytes() for p in main.rglob("*") if p.is_file()}
    assert "/boltzmann_status" in COMMANDS
    definition = resolve_command("/BOLTZMANN_STATUS")
    handler, takes_arg = cli._slash_handler(definition.name)
    assert takes_arg
    token = set_multiplex_context(True)
    try:
        for home in (main, a, b, a, main):
            with profile_scope(home):
                getattr(cli, handler)("/boltzmann_status")
                assert output[-1].border_style == get_active_skin().get_color("banner_border")
            text = output[-1].renderable.plain
            assert "SCI home:" not in text and str(home) not in text
            assert f"Profile: {'main (default)' if home == main else home.name}" in text
            assert "secret" not in text
            if home == b:
                assert "Not logged in" in text and "Email:" not in text
            else:
                assert "Logged in" in text and "scientist@example.test" in text
                assert "Available credits: 1,234.50" in text and "Frozen credits: 60.00" in text
    finally:
        reset_multiplex_context(token)
    assert calls == ["fixture-.sci-secret", "fixture-a-secret", "fixture-a-secret", "fixture-.sci-secret"]
    assert before == {p: p.read_bytes() for p in main.rglob("*") if p.is_file()}
    assert (cli.messages, cli.system_prompt, cli.enabled_toolsets) == session_before


@pytest.mark.parametrize("response", ["rejected", "unavailable", "timeout", "missing-fields", "rotated"])
def test_status_verification_never_reports_stale_or_unconfirmed_account(tmp_path, monkeypatch, response):
    from plugins.boltzmann.auth import authorize_saved_key
    from sci_cli.boltzmann_status import run
    from sci_cli.native_profile_creation import profile_scope

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path))
    secret = tmp_path / ".env"
    secret.write_text("BOLTZMANN_API_KEY=fixture-private-secret\n")
    output, calls = [], []

    def get(endpoint, **kwargs):
        calls.append(endpoint)
        if response == "timeout":
            raise authentication.requests.exceptions.Timeout("fixture-private-secret")
        if response == "rotated":
            secret.write_text("BOLTZMANN_API_KEY=replacement-fixture-secret\n")
        if response == "missing-fields":
            return Response(payload={"success": True})
        return Response(code={"rejected": 401, "unavailable": 503}.get(response, 200))

    monkeypatch.setattr(authentication.requests, "get", get)
    with profile_scope(tmp_path):
        authorize_saved_key()
        before = {p: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
        run(SimpleNamespace(_console_print=output.append), "/boltzmann_status")
    text = output[-1].renderable.plain
    assert len(calls) == 1 and "fixture-private-secret" not in text
    if response == "missing-fields":
        assert "Logged in" in text and text.count("Not provided by the service") == 3
    else:
        assert "Logged in" not in text and "Email:" not in text
        assert ("Login changed" if response == "rotated" else "Verification failed") in text
    for path, content in before.items():
        if not (response == "rotated" and path == secret):
            assert path.read_bytes() == content
