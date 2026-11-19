"""Browser planning uses the existing turn prompt without rebuilding cached conversation state."""

from pathlib import Path
from types import SimpleNamespace

from agent.plan_prompt import build_plan_prompt
from sci_constants import get_sci_home
from tui_gateway import server


def test_plan_dispatch_preserves_conversation_and_profile_scope(tmp_path, monkeypatch):
    launch = tmp_path / '.sci'
    homes = [launch / 'profiles' / name for name in ('a', 'b')]
    for home in [launch, *homes]:
        home.mkdir(parents=True, exist_ok=True)
        (home / 'config.yaml').write_text('{}', encoding='utf-8')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(launch))
    monkeypatch.setattr(server, '_sci_home', launch)
    monkeypatch.setattr(server, '_sessions', {})
    history = [{'role': 'user', 'content': 'We discussed onboarding.'}]
    agent = SimpleNamespace(model='fixture-model', system_prompt='cached-prefix')
    for index, home in enumerate([*homes, homes[0]]):
        sid = f'plan-{index}'
        session = {'session_key': sid, 'profile_home': str(home), 'agent': agent, 'history': history}
        server._sessions[sid] = session
        original = dict(session)
        task = '' if index == 0 else 'Improve onboarding'
        response = server.handle_request({'id': sid, 'method': 'slash.exec', 'params': {
            'session_id': sid, 'command': f'/plan {task}',
        }})
        assert 'error' not in response, response
        assert response['result']['type'] == 'send'
        assert response['result']['message'] == build_plan_prompt(task)
        assert session == original
        assert session['history'] is history
        assert agent.system_prompt == 'cached-prefix'
        assert get_sci_home() == launch
