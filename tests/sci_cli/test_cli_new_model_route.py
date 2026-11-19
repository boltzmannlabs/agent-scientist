"""A new conversation restores the entire saved model route, including same-name providers."""
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('different', ['provider', 'base_url', 'api_mode', None])
def test_new_boundary_compares_provider_endpoint_and_mode_not_only_model(monkeypatch, different):
    import cli
    from sci_cli.cli_session_mixin import _reset_model_to_config_default
    from sci_cli.model_switch import ModelSwitchResult

    saved = {'default': 'same-model', 'provider': 'custom:saved',
             'base_url': 'https://fixture.invalid/v1', 'api_mode': 'chat_completions'}
    monkeypatch.setattr(cli, 'CLI_CONFIG', {'model': saved})
    shell = SimpleNamespace(model='same-model', provider=saved['provider'], requested_provider=saved['provider'],
        base_url=saved['base_url'], api_mode=saved['api_mode'], api_key='fixture-key', agent=None)
    if different:
        setattr(shell, different, {'provider': 'custom:other', 'base_url': 'https://other.invalid/v1',
                                 'api_mode': 'codex_responses'}[different])
        if different == 'provider': shell.requested_provider = shell.provider
    calls = []

    def switch(**kwargs):
        calls.append(kwargs)
        return ModelSwitchResult(success=True, new_model='same-model', target_provider=saved['provider'],
            base_url=saved['base_url'], api_mode=saved['api_mode'], api_key='fixture-key')

    monkeypatch.setattr('sci_cli.model_switch.switch_model', switch)
    _reset_model_to_config_default(shell, silent=True)
    assert bool(calls) is bool(different)
    assert (shell.provider, shell.base_url, shell.api_mode) == (saved['provider'], saved['base_url'], saved['api_mode'])
