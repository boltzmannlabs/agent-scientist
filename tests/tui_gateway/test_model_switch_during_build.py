"""A picker change must switch the agent completing initialization, not just its label."""

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

from sci_constants import get_sci_home
from sci_cli.model_switch import ModelSwitchResult
from tui_gateway import server


@pytest.mark.parametrize('build_started', [True, False])
def test_model_selection_reaches_agent_in_owning_profile(tmp_path, monkeypatch, build_started):
    launch = tmp_path / '.sci'
    homes = [launch / 'profiles' / name for name in ('a', 'b')]
    for home in [launch, *homes]:
        home.mkdir(parents=True, exist_ok=True)
        (home / 'config.yaml').write_text(json.dumps({'model': {'default': 'old-model'}}))
    monkeypatch.setenv('SCI_HOME', str(launch))
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(server, '_sci_home', launch)
    monkeypatch.setattr(server, '_sessions', {})
    for name in ('_restart_slash_worker', '_persist_live_session_runtime',
                 '_persist_live_session_system_prompt', '_append_model_switch_marker',
                 '_emit_session_info', '_merge_preflight_warning'):
        monkeypatch.setattr(server, name, lambda *a, **kw: None)
    waits = []

    def wait_for_build(session, rid):
        assert get_sci_home() == Path(session['profile_home'])
        agent = SimpleNamespace(model='old-model', provider='custom:fixture',
                                base_url='https://fixture.invalid/v1', api_key='fixture-key',
                                api_mode='chat_completions')

        def switch_model(**kwargs):
            agent.model = kwargs['new_model']
            agent.provider = kwargs['new_provider']

        agent.switch_model = switch_model
        session['agent'] = agent
        session['agent_ready'].set()
        waits.append(get_sci_home())

    monkeypatch.setattr(server, '_wait_agent', wait_for_build)
    monkeypatch.setattr('sci_cli.model_switch.switch_model', lambda **kw: ModelSwitchResult(
        success=True, new_model=kw['raw_input'], target_provider=kw['explicit_provider'],
        base_url='https://fixture.invalid/v1', api_key='fixture-key', api_mode='chat_completions'))

    for index, home in enumerate([*homes, homes[0]]):
        sid = f'building-{index}'
        session = {'agent': None, 'agent_ready': threading.Event(), 'agent_build_started': build_started,
                   'session_key': sid, 'profile_home': str(home),
                   'resume_runtime_overrides': {'model_override': {'model': 'stored-model', 'provider': 'openrouter'}}}
        server._sessions[sid] = session
        response = server.handle_request({'id': sid, 'method': 'config.set', 'params': {
            'session_id': sid, 'key': 'model', 'value': 'selected-model --provider custom:fixture',
            'confirm_expensive_model': True,
        }})
        assert 'error' not in response, response
        if not build_started:
            kwargs = server._deferred_build_agent_kwargs(session, None)
            assert kwargs['model_override']['model'] == 'selected-model'
            wait_for_build_in_scope = server._session_profile_runtime_scope(session)
            with wait_for_build_in_scope:
                wait_for_build(session, sid)
            session['agent'].model = kwargs['model_override']['model']
        assert session['agent'] is not None
        assert session['agent'].model == response['result']['value'] == 'selected-model'
        assert session['model_override']['model'] == 'selected-model'
        assert get_sci_home() == launch
    assert waits == [*homes, homes[0]]
