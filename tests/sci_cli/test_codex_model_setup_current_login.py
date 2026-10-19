"""Model setup must reuse the current Codex login, not an expired SCI copy."""

import base64
import json
from pathlib import Path
import time
from types import SimpleNamespace

import pytest


def _token(label, *, expired=False):
    claims = {"sub": "fixture-user", "generation": label,
              "https://api.openai.com/auth": {"chatgpt_account_id": "fixture-account"},
              "exp": 1 if expired else time.time() + 3600}
    payload = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return "fixture." + payload + ".signature"


@pytest.fixture
def setup(tmp_path, monkeypatch):
    from agent.secret_scope import set_multiplex_active
    from sci_cli import auth, auth_codex
    from sci_cli.config import atomic_config_replace

    main = tmp_path / "science-root"
    homes = main, main / "profiles" / "a", main / "profiles" / "b"
    external = tmp_path / "codex-current"
    external.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(main))
    monkeypatch.setenv("CODEX_HOME", str(external))
    for home in homes:
        home.mkdir(parents=True, exist_ok=True)
        atomic_config_replace(home / "config.yaml", {
            "model": {"provider": "lmstudio", "default": "kept-" + home.name},
            "mcp_servers": {"private": {"url": "https://research.invalid"}}})
        (home / ".env").write_text("BOLTZMANN_API_KEY=private-fixture\n")
    expired = _token("old-sci", expired=True)
    (main / "auth.json").write_text(json.dumps({"version": 1, "providers": {"openai-codex": {
        "tokens": {"access_token": expired, "refresh_token": "old-sci-refresh"}}},
        "credential_pool": {"openai-codex": [{"id": "stale", "label": "old login", "auth_type": "oauth",
            "source": "device_code", "priority": 0, "access_token": expired, "refresh_token": "old-sci-refresh"}]}}))
    requests = []
    response = {"status": 200}

    class HTTP:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, url, *, headers):
            requests.append((url, headers["Authorization"]))
            if response.get("unreachable"):
                import httpx
                raise httpx.ConnectError("fixture unreachable")
            return SimpleNamespace(status_code=response["status"])

        def post(self, *args, **kwargs):
            pytest.fail("Reusing Codex must not refresh or start a new login")

    monkeypatch.setattr(auth_codex, "_codex_http_client", lambda **kw: HTTP())
    monkeypatch.setattr("sci_cli.auth_codex_browser.codex_oauth_login", lambda *a, **kw: pytest.fail("New OAuth login"))
    monkeypatch.setattr(auth, "_login_openai_codex", lambda *a, **kw: pytest.fail("New OAuth login"))
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("Unnecessary authentication prompt"))
    set_multiplex_active(True)
    try:
        yield homes, external, requests, response
    finally:
        set_multiplex_active(False)


@pytest.mark.parametrize("saved_login", [True, False], ids=["stale-sci-login", "fresh-install"])
def test_model_setup_links_current_login_for_all_profiles_and_follows_rotation(setup, monkeypatch, capsys, saved_login):
    from sci_cli.model_setup_flows import _model_flow_openai_codex
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.runtime_provider import resolve_runtime_provider
    from agent.auxiliary_client import _resolve_codex_credential_and_base
    from sci_cli import auth

    homes, external, requests, _ = setup
    main, a, b = homes
    if not saved_login:
        (main / "auth.json").unlink()
    config_before = {p: p.read_bytes() for h in homes for p in (h / "config.yaml", h / ".env")}
    catalogs, confirmations = [], []
    monkeypatch.setattr("sci_cli.codex_models.get_codex_model_ids",
                        lambda **kw: catalogs.append(kw) or ["fixture-model"])
    monkeypatch.setattr(auth, "_prompt_model_selection", lambda *a, **kw: confirmations.append(kw))
    for generation in ("current", "rotated"):
        current = _token(generation)
        (external / "auth.json").write_text(json.dumps({
            "tokens": {"access_token": current, "refresh_token": "external-owner-only"}}))
        source_before = (external / "auth.json").read_bytes()
        with profile_scope(a):
            _model_flow_openai_codex({}, current_model="kept-a")
        assert catalogs[-1]["access_token"] == current
        assert confirmations[-1]["confirm_api_key"] == current
        for home in (main, a, b, a):
            with profile_scope(home):
                assert resolve_runtime_provider(requested="openai-codex")["api_key"] == current
                assert _resolve_codex_credential_and_base()[0] == current
        assert (external / "auth.json").read_bytes() == source_before
        store = (main / "auth.json").read_text()
        assert current not in store and "external-owner-only" not in store
    assert len(requests) == 2  # one validation per explicit setup, no hidden runtime probes
    assert all(p.read_bytes() == original for p, original in config_before.items())
    assert "verified" in capsys.readouterr().out.lower()


@pytest.mark.parametrize("case", ["expired", "rejected", "unreachable", "keyring", "malformed", "account-changed"])
def test_invalid_current_login_stops_without_fresh_auth_or_partial_save(setup, monkeypatch, capsys, case):
    from sci_cli.model_setup_flows import _model_flow_openai_codex
    from sci_cli.native_profile_creation import profile_scope

    homes, external, requests, response = setup
    main, a, _ = homes
    current = _token("current", expired=case == "expired")
    (external / "auth.json").write_text(json.dumps({"tokens": {"access_token": current}}))
    if case == "rejected":
        response["status"] = 401
    if case == "unreachable":
        response["unreachable"] = True
    if case == "keyring":
        (external / "config.toml").write_text('cli_auth_credentials_store = "keyring"\n')
    if case == "malformed":
        (external / "auth.json").write_text("{broken")
    if case == "account-changed":
        store = json.loads((main / "auth.json").read_text())
        store["providers"]["openai-codex"] = {
            "external_codex_home": str(external), "external_codex_identity": ["different-account", "different-user"]}
        (main / "auth.json").write_text(json.dumps(store))
    before = {p: p.read_bytes() for h in homes for p in h.iterdir() if p.is_file()}
    monkeypatch.setattr("sci_cli.codex_models.get_codex_model_ids", lambda **kw: pytest.fail("Unverified catalog"))
    with profile_scope(a):
        _model_flow_openai_codex({})
    assert all(p.read_bytes() == original for p, original in before.items())
    assert len(requests) == (1 if case in {"rejected", "unreachable"} else 0)
    output = capsys.readouterr().out
    assert "Codex login check failed:" in output
    assert "verified" not in output.lower()
