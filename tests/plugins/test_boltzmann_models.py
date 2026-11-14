"""Platform model routing is profile-bound through real SDK, agent and auxiliary paths."""

import asyncio
import json
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from plugins.boltzmann.auth import authorize_saved_key
from sci_cli.config import atomic_config_replace, save_env_value_secure
from sci_cli.native_profile_creation import profile_scope


@pytest.fixture
def platform(tmp_path, monkeypatch):
    state = {
        "requests": [],
        "updates": [],
        "revoked": False,
        "credits": 2550,
        "auth_requests": 0,
        "models": [{"id": name} for name in ("qwen", "discoveryrsi", "discoveryrsi-q4ks", "glm", "codex")],
    }

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/v1/models":
                key = self.headers.get("Authorization", "")
                state.setdefault("model_requests", []).append(key)
                self.send_response(state.get("models_status", 200))
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"data": state.get("models", [])}).encode())
                return
            if self.path != "/auth":
                self.send_response(404)
                self.end_headers()
                return
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert self.path == "/auth" and body["apiToken"].startswith("fixture-")
            state["auth_requests"] += 1
            self.send_response(401 if state["revoked"] else 200)
            self.end_headers()
            self.wfile.write(
                json.dumps({
                    "success": not state["revoked"],
                    "email": "fixture@example.invalid",
                    "credits": float(state["credits"]),
                    "freezedCredits": 2156,
                }).encode()
            )

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            body = json.loads(raw)
            if self.path == "/update":
                state["updates"].append(raw)
                self.send_response(405)
                self.end_headers()
                return
            assert self.path == "/v1/chat/completions" and body["stream"] is False
            assert self.headers["Authorization"] in state.get(
                "allowed_keys", ["Bearer fixture-a"]
            )
            assert "stream_options" not in body
            state["requests"].append(body)
            message = {"role": "assistant", "content": "Fixture report: SCI_TOOL_OK"}
            finish = "stop"
            tools = body.get("tools", [])
            if tools and not any(m["role"] == "tool" for m in body["messages"]):
                name = next(
                    (
                        t["function"]["name"]
                        for t in tools
                        if t["function"]["name"].endswith("read_file")
                    ),
                    None,
                )
                if name:
                    message = {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {
                                "id": "fixture-call",
                                "type": "function",
                                "function": {
                                    "name": name,
                                    "arguments": json.dumps({
                                        "path": str(tmp_path / "fixture.txt")
                                    }),
                                },
                            }
                        ],
                    }
                    # These gateways can report stop even when a tool call is present.
                    finish = "stop"
            result = {
                "id": state.get(
                    "response_id", "fixture-response-" + str(len(state["requests"]))
                ),
                "object": "chat.completion",
                "created": 1,
                "model": "deployment-" + body["model"],
                "choices": [{"index": 0, "message": message, "finish_reason": finish}],
                "usage": {
                    "prompt_tokens": 1000,
                    "completion_tokens": 100,
                    "total_tokens": 1100,
                    "prompt_tokens_details": {"cached_tokens": 400},
                    "completion_tokens_details": {"reasoning_tokens": 50},
                },
            }
            result["usage"].update(state.get("usage_override", {}))
            result.update(state.get("metadata", {}))
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode())

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    root = tmp_path / ".sci"
    a, b = root / "profiles/a", root / "profiles/b"
    a.mkdir(parents=True)
    b.mkdir()
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(root))
    base = f"http://127.0.0.1:{server.server_port}/v1"
    for home in (root, a, b):
        atomic_config_replace(
            home / "config.yaml",
            {
                "providers": {"boltzmann_models": {"base_url": base}},
                "model": {
                    "provider": "boltzmann_models",
                    "default": "qwen",
                    "context_length": 32768,
                },
                "tool_search": {"enabled": "off"},
                "memory": {"enabled": False},
                "platform_toolsets": {"cli": ["file"]},
            },
        )
    monkeypatch.setattr(
        "plugins.boltzmann.nodeapi_helpers._AUTH_CHECK_URL",
        base.removesuffix("/v1") + "/auth",
    )

    def reject_credit_updates(*args, **kwargs):
        pytest.fail("SCI must not submit client-side credit deductions")

    monkeypatch.setattr("requests.post", reject_credit_updates)
    with profile_scope(root):
        save_env_value_secure("BOLTZMANN_API_KEY", "fixture-main")
        save_env_value_secure("OPENROUTER_API_KEY", "fixture-shared-llm")
        authorize_saved_key()
    with profile_scope(a):
        save_env_value_secure("BOLTZMANN_API_KEY", "fixture-a")
        authorize_saved_key()
    (tmp_path / "fixture.txt").write_text("SCI_TOOL_OK\n")
    try:
        from agent.secret_scope import set_multiplex_context, reset_multiplex_context

        with profile_scope(root):
            token = set_multiplex_context(True)
            try:
                yield state, root, a, b, base
            finally:
                reset_multiplex_context(token)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(5)


@pytest.mark.parametrize("model", ["qwen", "discoveryrsi", "discoveryrsi-q4ks", "glm", "codex"])
def test_gateway_context_is_exact_profile_scoped_and_matches_display(platform, model, monkeypatch):
    from agent import model_metadata as mm
    from agent.model_metadata import fetch_endpoint_model_metadata, get_model_context_length
    from plugins.boltzmann.model_context import model_limits
    from providers import get_provider_profile
    from sci_cli.config import read_user_config_raw
    from sci_cli.model_switch import resolve_display_context_length

    state, root, a, b, base = platform
    # Exercise remote disk caching against the controlled local HTTP service.
    monkeypatch.setattr(mm, "is_local_endpoint", lambda url: False)
    provider = get_provider_profile("boltzmann_models")
    # Same key, same endpoint, two homes: neither an old generic context cache
    # nor the other home's model metadata may replace this deployment's answer.
    limits = {a: 180_000, b: 210_000}
    for home in (a, b, a):
        state["models"] = [{"id": model, "context_length": limits[home], "max_output_tokens": 8000}]
        with profile_scope(home):
            save_env_value_secure("BOLTZMANN_API_KEY", "fixture-a")
            authorize_saved_key()
            value = get_model_context_length(model, base_url=base, provider=provider.name)
            assert value == limits[home]
            assert resolve_display_context_length(model, provider.name, base_url=base) == value
            assert provider.get_model_context_note(model, value) == "gateway metadata"
            assert provider.get_output_reservation(model, None) == 8000
            assert provider.get_output_reservation(model, 100) == (8000 if model == "codex" else 100)
    assert len(state["model_requests"]) == 2
    with profile_scope(a):
        mm._endpoint_model_metadata_cache.clear()
        mm._endpoint_model_metadata_cache_time.clear()
        assert get_model_context_length(model, base_url=base, provider=provider.name) == limits[a]
        assert len(state["model_requests"]) == 2  # Disk cache in the owning home.
        save_env_value_secure("BOLTZMANN_API_KEY", "fixture-rotated")
        authorize_saved_key()
        state["models"] = [{"id": model, "context_length": 230_000}]
        assert get_model_context_length(model, base_url=base, provider=provider.name) == 230_000
        save_env_value_secure("BOLTZMANN_API_KEY", "fixture-a")
        authorize_saved_key()
        cfg = read_user_config_raw()
        cfg["model_overrides"] = {provider.name: {model: {"context_window": 160_000}}}
        atomic_config_replace(a / "config.yaml", cfg)
        assert get_model_context_length(model, base_url=base, provider=provider.name) == 160_000
        assert provider.get_model_context_note(model, 160_000) == "configured"
        cfg.pop("model_overrides")
        atomic_config_replace(a / "config.yaml", cfg)
        # No metadata, missing model, failure and malformed limits must not
        # borrow an unrelated model's window or label a fallback as verified.
        for status, rows in (
            (200, [{"id": model}]),
            (200, [{"id": "unrelated", "context_length": 900_000}]),
            (200, [{"id": model, "context_length": -1}]),
            (503, []),
        ):
            state.update(models_status=status, models=rows)
            fetch_endpoint_model_metadata(base, "fixture-a", force_refresh=True)
            resolved = model_limits(model)
            assert resolved.source == "estimate" and resolved.context != 900_000
            assert "estimate" in provider.get_model_context_note(model, resolved.context)
        mm.save_context_length(model, base, 140_000)
        assert model_limits(model).context == 140_000
        assert "saved endpoint limit" in model_limits(model).source
    assert state["requests"] == [] and state["updates"] == []


@pytest.mark.parametrize("model", ["qwen", "discoveryrsi", "glm", "codex"])
def test_large_history_switch_uses_destination_budget_before_reply(platform, model, monkeypatch):
    from types import SimpleNamespace
    from agent.model_metadata import estimate_request_tokens_rough
    from run_agent import AIAgent
    from sci_cli.config import read_user_config_raw
    from sci_cli.context_switch_guard import merge_preflight_compression_warning
    from sci_cli.model_switch import ModelSwitchResult, resolve_display_context_length

    state, root, a, b, base = platform
    large_model = "codex" if model != "codex" else "glm"
    window, output = 150_000, 8000
    state["models"] = [
        {"id": large_model, "context_length": 500_000, "max_output_tokens": 32000},
        {"id": model, "context_length": window, "max_output_tokens": output},
    ]
    monkeypatch.setattr("agent.title_generator.maybe_auto_title", lambda *a, **k: None)
    with profile_scope(a):
        cfg = read_user_config_raw()
        cfg["model"] = {"provider": "boltzmann_models", "default": large_model}
        cfg["compression"] = {"threshold": 0.90, "protect_first_n": 1, "protect_last_n": 2}
        cfg["auxiliary"] = {"compression": {"provider": "auto", "model": ""}}
        atomic_config_replace(a / "config.yaml", cfg)
        agent = AIAgent(
            model=large_model, provider="boltzmann_models", api_key="fixture-a",
            base_url=base, api_mode="chat_completions", enabled_toolsets=[],
            quiet_mode=True, skip_context_files=True, skip_memory=True, max_iterations=2,
        )
        try:
            agent._cached_system_prompt = "Frozen fixture prompt"
            frozen = agent._cached_system_prompt
            cc = agent.context_compressor
            assert cc.max_tokens == 32000
            history = [
                {"role": "user" if i % 2 == 0 else "assistant", "content": f"record {i}: " + "context " * 4400}
                for i in range(40)
            ]
            assert estimate_request_tokens_rough(history) > 350_000
            switch = ModelSwitchResult(
                success=True, new_model=model, target_provider="boltzmann_models",
                api_key="fixture-a", base_url=base, api_mode="chat_completions",
            )
            merge_preflight_compression_warning(switch, agent=agent, messages=history)
            assert agent._cached_system_prompt == frozen
            expected_trigger = int((window - output) * .90)
            assert f"auto-compress at ~{expected_trigger:,}" in switch.warning_message
            switch.warning_message = ""
            merge_preflight_compression_warning(
                switch, agent=agent, messages=[{"role": "user", "content": "x" * 1_400_000}],
            )
            assert "preflight compression" in switch.warning_message  # Few large rows count too.
            agent.switch_model(model, "boltzmann_models", api_key="fixture-a", base_url=base, api_mode="chat_completions")
            assert cc.context_length == resolve_display_context_length(model, "boltzmann_models", base_url=base) == window
            assert cc.max_tokens == output and cc.threshold_tokens == expected_trigger
            from sci_cli.cli_model_switch_mixin import _print_switch_summary
            displayed = []
            monkeypatch.setattr("cli._cprint", displayed.append)
            _print_switch_summary(
                SimpleNamespace(agent=agent, base_url=base, api_key="fixture-a"),
                switch, large_model, one_turn=False, strict_context=True,
            )
            assert any(f"{window:,}" in line and "gateway metadata" in line for line in displayed)
            assert any(f"Auto-compaction: ~{expected_trigger:,}" in line for line in displayed)
            result = agent.run_conversation("Continue the fixture report.", conversation_history=history)
            assert "SCI_TOOL_OK" in result["final_response"]
            assert agent.context_compressor.compression_count > 0
            assert len(history) == 40  # The caller's retained transcript was not rewritten.
            assert len(state["requests"]) >= 2  # Summary, then the user's model response.
            for request in state["requests"]:
                assert request["model"] == model
                assert estimate_request_tokens_rough(request["messages"]) < window - output
            assert state["updates"] == []
        finally:
            agent.close()


@pytest.mark.parametrize("model", ["qwen", "discoveryrsi", "discoveryrsi-q4ks", "glm", "codex"])
def test_gated_sdk_clients_sync_async_streaming_and_profiles(platform, model):
    from providers import get_provider_profile
    from sci_cli.runtime_provider import resolve_runtime_provider
    from sci_cli.shared_llm import with_shared_credentials
    from agent.secret_scope import get_secret_str
    from agent.auxiliary_client import resolve_provider_client

    state, root, a, b, base = platform
    profile = get_provider_profile("boltzmann_models")
    with profile_scope(a):
        runtime = resolve_runtime_provider(requested=profile.name, target_model=model)
        assert runtime["api_mode"] == "chat_completions"
        client = profile.create_client(
            api_key=runtime["api_key"], base_url=runtime["base_url"]
        )
        chunks = list(
            client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Fixture"}],
                stream=True,
                stream_options={"include_usage": True},
                max_tokens=32,
                extra_headers={"authorization": "Bearer must-not-be-used"},
            )
        )
        assert chunks[0].id.startswith("fixture-response-")
        assert chunks[0].choices[0].delta.content == "Fixture report: SCI_TOOL_OK"
        assert chunks[-1].usage.total_tokens == 1100
        sent = state["requests"][-1]
        assert sent["model"] == model
        assert ("max_tokens" in sent) is (model != "codex")
        async_client, selected = resolve_provider_client(
            profile.name, model, async_mode=True
        )
        assert selected == model

        async def request():
            selected_client = async_client.with_options(timeout=5)
            chunks = await selected_client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Fixture"}],
                stream=True,
            )
            items = [chunk async for chunk in chunks]
            assert items[-1].usage.total_tokens == 1100
            await selected_client.close()
            await async_client.close()

        asyncio.run(request())
        calls = len(state["requests"])
        with profile_scope(b):
            assert (
                with_shared_credentials(
                    lambda: get_secret_str("BOLTZMANN_API_KEY", "")
                )()
                == ""
            )
            with pytest.raises(PermissionError, match="not authorized"):
                resolve_runtime_provider(requested=profile.name, target_model=model)
            with pytest.raises(PermissionError, match="another profile"):
                client.chat.completions.create(model=model, messages=[], stream=False)
            with pytest.raises(PermissionError, match="another profile"):
                client.with_options(timeout=5)
            with pytest.raises(PermissionError, match="another profile"):
                async_client.with_options(timeout=5)
        assert len(state["requests"]) == calls
        state["revoked"] = True
        with pytest.raises(PermissionError):
            client.chat.completions.create(model=model, messages=[], stream=False)
        assert len(state["requests"]) == calls
        state["revoked"] = False
        details = profile.fetch_account_usage().details
        assert f"Available credits: {state['credits']:,.2f}" in details
        assert "Frozen credits: 2,156.00" in details
        assert state["updates"] == []
        client.close()


def test_required_client_and_recovery_cannot_bypass_platform_authorization(
    platform, monkeypatch
):
    from types import SimpleNamespace
    from providers import get_provider_profile
    from agent import auxiliary_client as aux
    from agent.agent_runtime_helpers import _provider_supplied_client
    from agent.error_classifier import classify_api_error
    from sci_cli.runtime_provider import resolve_runtime_provider

    state, root, a, b, base = platform
    profile = get_provider_profile("boltzmann_models")
    with profile_scope(a):
        for overrides, error in (
            ({"explicit_api_key": "fixture-main"}, PermissionError),
            ({"explicit_base_url": "http://another.invalid/v1"}, ValueError),
        ):
            with pytest.raises(error):
                resolve_runtime_provider(requested=profile.name, **overrides)
        verdict = classify_api_error(
            PermissionError("Login required"), provider=profile.name, model="glm"
        )
        assert not verdict.should_fallback and not verdict.should_rotate_credential
        route = SimpleNamespace(
            task="title_generation", tag="fixture", resolved_provider=profile.name
        )
        assert (
            list(aux._ladder_provider_fallback(PermissionError("Locked"), route)) == []
        )
        assert aux._try_configured_fallback_chain(
            "title_generation", profile.name, reason="fixture"
        ) == (None, None, "")
        assert aux._try_main_fallback_chain(
            "title_generation", profile.name, reason="fixture"
        ) == (None, None, "")
        assert not aux._recover_provider_pool(profile.name, PermissionError("Locked"))
        from sci_cli.config import read_user_config_raw
        from sci_cli.shared_provider_lifecycle import ProviderRemovedError

        client = profile.create_client(api_key="fixture-a", base_url=base)
        config = read_user_config_raw()
        config["providers"][profile.name]["enabled"] = False
        atomic_config_replace(a / "config.yaml", config)
        try:
            with pytest.raises(ValueError, match="disabled"):
                resolve_runtime_provider(requested="boltzmann-models")
            with pytest.raises(ProviderRemovedError):
                client.chat.completions.create(model="glm", messages=[], stream=False)
        finally:
            client.close()
        monkeypatch.setattr(profile, "create_client", lambda **kwargs: None)
        with pytest.raises(RuntimeError, match="requires its custom client"):
            _provider_supplied_client(SimpleNamespace(provider=profile.name), {})
        with pytest.raises(RuntimeError, match="requires its custom client"):
            aux._api_key_profile_supplied_client(profile.name)
    assert not state["requests"]


def test_specialist_uses_owner_auth_and_footer_reports_account_separately(
    platform, tmp_path, monkeypatch
):
    from types import SimpleNamespace
    from agent.specialist_policy import SpecialistPolicy, specialist_scope
    from plugins.boltzmann.model_client import BoltzmannClient
    from plugins.boltzmann.model_gateway import credentials
    from sci_cli.cli_chat_turn_mixin import CLIChatTurnMixin

    state, root, a, b, base = platform
    private = tmp_path / "private-specialist"
    private.mkdir()
    policy = SpecialistPolicy(
        name="fixture",
        home=str(a.resolve()),
        execution_home=str(private.resolve()),
        revision="fixture",
        tools=frozenset(),
        skills=frozenset(),
        children=frozenset(),
        ancestry=(),
        deadline=float("inf"),
    )
    with specialist_scope(policy), profile_scope(private):
        assert credentials(strict=True)["api_key"] == "fixture-a"
        # Construct and invoke the guarded wrapper, including its default endpoint resolution.
        client = BoltzmannClient()
        try:
            response = client.chat.completions.create(
                model="glm", messages=[], stream=False
            )
            assert response.usage.total_tokens == 1100
        finally:
            client.close()
    lines = []
    monkeypatch.setattr("cli._cprint", lines.append)
    cli = SimpleNamespace(
        _agent_or_self=lambda name: {"provider": "boltzmann_models", "base_url": base}[
            name
        ]
    )
    with profile_scope(a):
        CLIChatTurnMixin._chat_print_token_usage(
            cli, {"token_usage": {"status": "unavailable"}}
        )
    assert f"Available credits: {state['credits']:,.2f}" in "\n".join(lines)
    assert "Frozen credits: 2,156.00" in "\n".join(lines)
    assert "priced request" not in "\n".join(lines)
    assert "fixture-a" not in "\n".join(lines)
    with profile_scope(b):
        with pytest.raises(PermissionError):
            credentials(strict=True)
    with profile_scope(a):
        assert credentials(strict=True)["api_key"] == "fixture-a"


def test_real_agent_auxiliary_model_picker_and_saved_default(
    platform, tmp_path, monkeypatch
):
    from providers import get_provider_profile
    from run_agent import AIAgent
    from agent.auxiliary_client import resolve_provider_client
    from sci_cli.model_switch_providers import list_authenticated_providers
    from sci_cli.model_setup_flows import _model_flow_plugin_provider
    from sci_cli.config import read_user_config_raw

    state, root, a, b, base = platform
    monkeypatch.setattr("agent.title_generator.maybe_auto_title", lambda *a, **k: None)
    with profile_scope(a):
        profile = get_provider_profile("boltzmann_models")
        rows = list_authenticated_providers(
            current_provider=profile.name,
            current_model="qwen",
            non_blocking_catalogs=True,
        )
        row = next(r for r in rows if r["slug"] == profile.name)
        assert set(row["models"]) >= set(profile.fallback_models)
        before = (root / ".env").read_bytes(), (root / "config.yaml").read_bytes()
        monkeypatch.setattr(
            "sci_cli.model_setup_flows_common._pick_model_or_prompt",
            lambda *a, **k: "glm",
        )
        _model_flow_plugin_provider({}, profile.name)
        assert read_user_config_raw()["model"]["default"] == "glm"
        assert before == (
            (root / ".env").read_bytes(),
            (root / "config.yaml").read_bytes(),
        )
        agent = AIAgent(
            model="qwen",
            provider=profile.name,
            api_key="fixture-a",
            base_url=base,
            api_mode="chat_completions",
            enabled_toolsets=["file"],
            quiet_mode=True,
            skip_context_files=True,
            skip_memory=True,
            max_iterations=3,
        )
        try:
            agent._cached_system_prompt = "Frozen fixture prompt"
            result = agent.run_conversation(
                f"Read {tmp_path / 'fixture.txt'} and report its content."
            )
            assert "SCI_TOOL_OK" in result["final_response"], result
            assert any(
                any(
                    m["role"] == "tool" and "SCI_TOOL_OK" in str(m.get("content"))
                    for m in r["messages"]
                )
                for r in state["requests"]
            )
            assert agent._cached_system_prompt == "Frozen fixture prompt"
        finally:
            agent.close()
        client, model = resolve_provider_client(provider=profile.name, model="glm")
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": "Fixture"}],
                stream=False,
            )
            assert "SCI_TOOL_OK" in response.choices[0].message.content
        finally:
            client.close()
        with profile_scope(b):
            rows = list_authenticated_providers(non_blocking_catalogs=True)
            locked = next(r for r in rows if r["slug"] == profile.name)
            assert "login required" in locked["name"].lower()


def test_no_client_deductions_or_legacy_ledger_mutations(platform):
    import sqlite3
    from plugins.boltzmann.model_client import BoltzmannClient
    from sci_cli.plugins_state import PluginState
    from providers import get_provider_profile

    state, root, a, b, base = platform
    with profile_scope(a):
        ledger = (
            PluginState("boltzmann").path.parent / "model-billing-v1" / "ledger.sqlite3"
        )
        ledger.parent.mkdir()
        with sqlite3.connect(ledger) as db:
            db.execute("CREATE TABLE requests (id TEXT, status TEXT, charge TEXT)")
            db.executemany(
                "INSERT INTO requests VALUES (?, ?, ?)",
                [
                    (
                        "old-paid",
                        "confirmed",
                        '{"input_credits":"1.57","output_credits":"0.01"}',
                    ),
                    ("old-unpriced", "unpriced", "{}"),
                    ("old-unknown", "posting", "{}"),
                ],
            )
        before = ledger.read_bytes()
        state["usage_override"] = {"prompt_tokens_details": None}
        client = BoltzmannClient(api_key="fixture-a", base_url=base)
        try:
            response = client.chat.completions.create(
                model="discoveryrsi", messages=[], stream=False
            )
            assert "SCI_TOOL_OK" in response.choices[0].message.content
            assert response.usage.prompt_tokens_details is None
            assert not hasattr(response, "boltzmann_billing")
            async_client = client.to_async_client()

            async def request():
                result = await async_client.chat.completions.create(
                    model="discoveryrsi", messages=[], stream=False
                )
                assert "SCI_TOOL_OK" in result.choices[0].message.content
                await async_client.close()

            asyncio.run(request())
            details = (
                get_provider_profile("boltzmann_models").fetch_account_usage().details
            )
            assert "Available credits: 2,550.00" in details
            assert not any(
                "Billing" in line or "priced request" in line for line in details
            )
        finally:
            client.close()
        assert ledger.read_bytes() == before
        assert state["updates"] == []
        assert len(state["requests"]) == 2
        assert all(
            "input_credits" not in request and "output_credits" not in request
            for request in state["requests"]
        )


def test_gateway_metadata_reaches_usage_and_footer_without_deductions(
    platform, monkeypatch
):
    from types import SimpleNamespace
    from agent.account_usage import fetch_account_usage, render_account_usage_lines
    from plugins.boltzmann.model_client import BoltzmannClient
    from sci_cli.cli_chat_turn_mixin import CLIChatTurnMixin

    state, root, a, b, base = platform
    state["metadata"] = {
        "billing": {
            "managed_by": "boltzmann_gateway",
            "status": "submitted",
            "currency": "INR",
            "pricing_model": "gpt-6.1-terra",
            "cache_usage_source": "reported",
            "input_tokens": 214,
            "cached_input_tokens": 0,
            "uncached_input_tokens": 214,
            "output_tokens": 115,
            "input_credits": "0.02",
            "output_credits": "0.05",
            "total_credits": "0.07",
        },
        "account": {
            "email": "a@example.invalid",
            "credits": 2253.93,
            "freezedCredits": 320,
        },
    }
    state["usage_override"] = {
        "prompt_tokens": 214,
        "completion_tokens": 115,
        "total_tokens": 329,
    }
    with profile_scope(a):
        before = (a / ".env").read_bytes(), (a / "config.yaml").read_bytes()
        client = BoltzmannClient(api_key="fixture-a", base_url=base)
        for stream in (False, True):
            result = client.chat.completions.create(
                model="codex", messages=[], stream=stream
            )
            if stream:
                assert list(result)[-1].usage.total_tokens == 329
            else:
                assert result.billing == state["metadata"]["billing"]
                assert (
                    result.choices[0].message.content == "Fixture report: SCI_TOOL_OK"
                )
        async_client = client.to_async_client()

        async def request():
            for stream in (False, True):
                result = await async_client.chat.completions.create(
                    model="codex", messages=[], stream=stream
                )
                if stream:
                    assert [chunk async for chunk in result][
                        -1
                    ].usage.total_tokens == 329
                else:
                    assert result.account == state["metadata"]["account"]
            await async_client.close()

        asyncio.run(request())
        client.close()
        auth_count = state["auth_requests"]
        snapshot = fetch_account_usage("boltzmann_models", base_url=base)
        text = "\n".join(render_account_usage_lines(snapshot))
        assert "Gateway billing: submitted" in text
        assert (
            "Input credits: 0.02 · Output credits: 0.05 · Total credits: 0.07" in text
        )
        assert "input 214 (cached 0 · uncached 214) · output 115" in text
        assert "Pricing model: gpt-6.1-terra · Currency: INR" in text
        assert "Available credits: 2,253.93" in text and "Frozen credits: 320.00" in text
        assert "fixture-a" not in text and "confirmed" not in text
        lines = []
        monkeypatch.setattr("cli._cprint", lines.append)
        cli = SimpleNamespace(
            _agent_or_self=lambda name: {
                "provider": "boltzmann_models",
                "base_url": base,
            }[name]
        )
        CLIChatTurnMixin._chat_print_token_usage(
            cli, {"token_usage": {"status": "unavailable"}}
        )
        from rich.text import Text
        assert [Text.from_ansi(line).plain.strip() for line in lines] == [
            "Token usage: input 214 · output 115 · total 329",
            "Input credits: 0.02 · Output credits: 0.05 · Total credits: 0.07"
            " Available Credits: 2,253.93",
            "Type /usage to view detailed token usage, credits, and account information.",
        ]
        assert (
            state["auth_requests"] == auth_count
        )  # Rendering consumes the response, not another service call.
        assert before == ((a / ".env").read_bytes(), (a / "config.yaml").read_bytes())
    with profile_scope(b):
        save_env_value_secure("BOLTZMANN_API_KEY", "fixture-b")
        authorize_saved_key()
        state["allowed_keys"] = ["Bearer fixture-b"]
        state["metadata"]["account"] = {
            "email": "b@example.invalid",
            "credits": 10,
            "freezedCredits": 0,
        }
        client = BoltzmannClient(api_key="fixture-b", base_url=base)
        client.chat.completions.create(model="glm", messages=[], stream=False)
        client.close()
        assert (
            "Email: b@example.invalid"
            in fetch_account_usage("boltzmann_models").details
        )
    with profile_scope(a):
        assert (
            "Email: a@example.invalid"
            in fetch_account_usage("boltzmann_models").details
        )
        save_env_value_secure("BOLTZMANN_API_KEY", "fixture-rotated")
        authorize_saved_key()
        assert not any(
            "a@example.invalid" in line
            for line in fetch_account_usage("boltzmann_models").details
        )
    with profile_scope(root):
        assert not any(
            "gateway response" in line
            for line in render_account_usage_lines(
                fetch_account_usage("boltzmann_models")
            )
        )
    assert state["updates"] == []
    assert len(state["requests"]) == 5
    assert all(
        "billing" not in r and "input_credits" not in r and "output_credits" not in r
        for r in state["requests"]
    )


def test_missing_or_malformed_metadata_never_reuses_or_invents_charges(platform):
    from plugins.boltzmann.model_client import BoltzmannClient
    from plugins.boltzmann.model_gateway import account_usage

    state, root, a, b, base = platform
    with profile_scope(a):
        client = BoltzmannClient(api_key="fixture-a", base_url=base)
        state["metadata"] = {
            "billing": {
                "status": "pending",
                "input_credits": "0.02",
                "output_credits": "0.05",
                "total_credits": "9.99",
            },
            "account": {
                "email": "fixture-a\nuser@example.invalid\x1b",
                "credits": 0,
                "freezedCredits": 0,
            },
        }
        client.chat.completions.create(model="qwen", messages=[], stream=False)
        text = "\n".join(account_usage().details)
        assert (
            "Gateway billing: pending" in text and "Total credits: 9.99" in text
        )  # Server value, never recomputed.
        assert "Available credits: 0.00" in text and "Frozen credits: 0.00" in text
        assert (
            "fixture-a" not in text
            and "\x1b" not in text
            and "[redacted]user@example.invalid" in text
        )
        state["metadata"] = {
            "billing": {
                "status": "failed",
                "input_credits": "NaN",
                "output_credits": -1,
            },
            "account": {"credits": True},
        }
        result = client.chat.completions.create(model="qwen", messages=[], stream=False)
        assert result.choices[0].message.content == "Fixture report: SCI_TOOL_OK"
        text = "\n".join(account_usage().details)
        assert "Gateway billing: failed" in text
        assert (
            "Input credits: not provided · Output credits: not provided · Total credits: not provided"
            in text
        )
        assert "9.99" not in text and "Available credits: not provided" in text
        state["metadata"] = {"billing": None, "account": []}
        client.chat.completions.create(model="qwen", messages=[], stream=False)
        text = "\n".join(account_usage().details)
        assert "Gateway billing" not in text and "Available credits: 2,550.00" in text
        client.close()
    assert len(state["requests"]) == 3 and state["updates"] == []


def test_gateway_catalog_admits_new_ids_with_owner_auth_and_rejects_unknown(platform):
    from plugins.boltzmann.model_gateway import catalog_models
    from providers import get_provider_profile

    state, root, a, b, base = platform
    name = "gateway-new-fixture"
    state["models"] = [{"id": name}, {"id": name}, {"id": "another-fixture"}]
    provider = get_provider_profile("boltzmann_models")
    for home, allowed in ((a, True), (b, False), (a, True)):
        with profile_scope(home):
            before = len(state.get("model_requests", []))
            ids = catalog_models(force_refresh=True)
            if not allowed:
                assert ids == [] and len(state.get("model_requests", [])) == before
                assert provider.fetch_models(api_key="fixture-a", base_url=base) == []
                continue
            assert ids == [name, "another-fixture"]
            assert provider.fetch_models(api_key="wrong-caller-key", base_url=base) == ids
            client = provider.create_client(api_key="fixture-a", base_url=base)
            try:
                reply = client.chat.completions.create(model=name, messages=[{"role": "user", "content": "Fixture"}])
                assert reply.choices[0].message.content == "Fixture report: SCI_TOOL_OK"
                assert state["requests"][-1]["model"] == name
                sent = len(state["requests"])
                with pytest.raises(ValueError, match="gateway catalog"):
                    client.chat.completions.create(model="not-advertised", messages=[])
                assert len(state["requests"]) == sent
            finally:
                client.close()
    assert set(state["model_requests"]) == {"Bearer fixture-a"}


def test_gateway_catalog_refresh_and_setup_follow_server_inventory(platform, monkeypatch):
    from plugins.boltzmann.model_gateway import catalog_models, setup_model

    state, root, a, b, base = platform
    seen = []
    monkeypatch.setattr("sci_cli.model_setup_flows_common._pick_model_or_prompt",
                        lambda models, *args, **kwargs: seen.append(models) or None)
    with profile_scope(a):
        state["models"] = [{"id": "old-fixture"}]
        assert catalog_models(force_refresh=True) == ["old-fixture"]
        state["models"] = [{"id": "new-fixture"}]
        setup_model()
        assert seen == [["new-fixture"]]
        state["models"] = []
        assert catalog_models(force_refresh=True) == []
