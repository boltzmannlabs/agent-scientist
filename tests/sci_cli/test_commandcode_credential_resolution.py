"""External catalog additions must not hide an installed provider's existing key."""

from types import SimpleNamespace

import pytest


@pytest.fixture
def commandcode(monkeypatch):
    from providers import get_provider_profile
    from sci_cli import providers

    profile = get_provider_profile("commandcode")
    assert profile is not None
    info = SimpleNamespace(name="CommandCode", env=("CMD_API_KEY",), api=profile.base_url,
                           doc="https://commandcode.invalid/docs")
    monkeypatch.setattr(providers, "_models_dev_info", lambda name, allow_network=True:
                        info if name == "commandcode" else None)
    return profile


@pytest.mark.parametrize("catalog_present", [True, False])
def test_commandcode_keeps_registered_credential_and_endpoint_contract(commandcode, monkeypatch, catalog_present):
    from sci_cli import providers

    if not catalog_present:
        monkeypatch.setattr(providers, "_models_dev_info", lambda *a, **kw: None)
    resolved = providers.resolve_provider_full(commandcode.name, {}, [])
    assert resolved is not None
    assert providers.TRANSPORT_TO_API_MODE[resolved.transport] == commandcode.api_mode
    assert resolved.base_url == commandcode.base_url
    assert resolved.base_url_env_var in commandcode.env_vars
    expected_keys = {name for name in commandcode.env_vars if not name.endswith("_BASE_URL")}
    assert expected_keys <= set(resolved.api_key_env_vars)
    assert "CMD_API_KEY" in resolved.api_key_env_vars


@pytest.mark.parametrize("key_name", ["COMMANDCODE_API_KEY", "CMD_API_KEY"])
@pytest.mark.parametrize("requested", ["commandcode", "commandcode-chat", "commandcode-anthropic", "commandcode-claude"])
def test_commandcode_runtime_resolves_either_saved_key_without_rewriting_it(commandcode, tmp_path, monkeypatch, key_name, requested):
    from pathlib import Path
    from sci_cli.config import atomic_config_replace
    from sci_cli.runtime_provider import resolve_runtime_provider

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    home = tmp_path / "sci-test"
    home.mkdir()
    monkeypatch.setenv("SCI_HOME", str(home))
    for name in ("COMMANDCODE_API_KEY", "CMD_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    config = home / "config.yaml"
    atomic_config_replace(config, {"model": {"provider": requested, "default": "fixture-model"}})
    secrets = home / ".env"
    secrets.write_text(f"{key_name}=fixture-commandcode-secret\n")
    before = config.read_bytes(), secrets.read_bytes()
    from sci_cli.native_profile_creation import profile_scope
    with profile_scope(home):
        runtime = resolve_runtime_provider(requested=requested, target_model="fixture-model")
    assert runtime["api_key"] == "fixture-commandcode-secret"
    assert runtime["base_url"] == commandcode.base_url
    assert (config.read_bytes(), secrets.read_bytes()) == before
