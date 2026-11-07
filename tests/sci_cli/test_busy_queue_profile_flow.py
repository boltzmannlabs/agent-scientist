"""Normal follow-ups stay FIFO and bound to their original profile/conversation."""
from pathlib import Path
from queue import Queue
from types import SimpleNamespace
from unittest.mock import Mock
import threading

import pytest


def test_default_queue_preserves_active_work_across_main_a_b_a(tmp_path, monkeypatch):
    import cli as cli_module
    from sci_cli.config import load_config
    from sci_cli.profiles import create_profile, get_profile_dir
    from tui_gateway import server
    from agent.secret_scope import set_multiplex_context, reset_multiplex_context
    from gateway.run import GatewayRunner

    home = tmp_path / '.sci'
    home.mkdir()
    (home / 'config.yaml').write_text('display: {}\n')
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(home))
    monkeypatch.setattr(server, '_sci_home', home)
    for name in ('a', 'b'):
        create_profile(name)
        (get_profile_dir(name) / 'config.yaml').write_text('display: {}\n')
    homes = {'main': home, 'a': get_profile_dir('a'), 'b': get_profile_dir('b')}
    clients, sessions, original = {}, {}, {}
    for name in homes:
        original[name] = [{'role': 'system', 'content': 'stable cached prompt'},
                          {'role': 'user', 'content': name + ' original task'}]
        sessions[name] = {'profile_home': str(homes[name]), 'session_key': name,
                          'history': list(original[name]), 'history_lock': threading.RLock(),
                          'history_version': 0, 'running': True, 'attached_images': [],
                          'transport': None, 'agent': Mock(_supports_active_turn_redirect=True)}
    seen = []
    def run_prompt(rid, sid, session, text, **kwargs):
        from sci_constants import get_sci_home
        seen.append((sid, str(get_sci_home()), text))
        session['running'] = False
    monkeypatch.setattr(server, '_run_prompt_submit', run_prompt)
    token = set_multiplex_context(True)
    try:
        for name in ('main', 'a', 'b', 'a'):
            with server._session_profile_runtime_scope(sessions[name], hydrate_secrets=False):
                monkeypatch.setattr(cli_module, '_sci_home', homes[name])
                config = cli_module.load_cli_config()
                assert load_config()['display']['busy_input_mode'] == config['display']['busy_input_mode']
                monkeypatch.setattr(cli_module, 'CLI_CONFIG', config)
                if name not in clients:
                    obj = cli_module.SciCLI.__new__(cli_module.SciCLI)
                    obj._init_display_options(False, False)
                    obj._pending_input, obj._interrupt_queue = Queue(), Queue()
                    obj.agent = Mock(_supports_active_turn_redirect=True)
                    clients[name] = obj
                obj = clients[name]
                text = f'{name} follow-up {obj._pending_input.qsize()+1}'
                obj._tui_enter_while_busy(text, [], text)
                obj.agent.redirect.assert_not_called()
                obj.agent.steer.assert_not_called()
                obj.agent.interrupt.assert_not_called()
                assert obj._interrupt_queue.empty()
                assert GatewayRunner._load_busy_input_mode() == obj.busy_input_mode == 'queue'
                result = server._handle_busy_submit('r', name, sessions[name], text, None)
                assert result['result']['status'] == 'queued'
                assert sessions[name]['history'] == original[name]
                assert server._drain_queued_prompt('r', name, sessions[name]) is False
                sessions[name]['agent'].redirect.assert_not_called()
                sessions[name]['agent'].interrupt.assert_not_called()
        assert seen == []
        for name, session in sessions.items():
            with server._session_profile_runtime_scope(session, hydrate_secrets=False):
                expected = list(clients[name]._pending_input.queue)
                session['running'] = False
                while server._drain_queued_prompt('r', name, session):
                    pass
                assert [text for sid, _, text in seen if sid == name] == expected
                assert all(path == str(homes[name]) for sid, path, _ in seen if sid == name)
    finally:
        reset_multiplex_context(token)


def test_pending_followups_block_cli_context_switch_without_loss(tmp_path, monkeypatch):
    from sci_cli.profiles import create_profile
    from sci_cli.native_profile_session import request_switch, request_resume
    from sci_cli.cli_session_mixin import CLISessionMixin

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    home = tmp_path / '.sci'; home.mkdir()
    (home / 'config.yaml').write_text('{}\n')
    monkeypatch.setenv('SCI_HOME', str(home))
    create_profile('a')
    obj = SimpleNamespace(_agent_running=False, _pending_input=Queue(), agent=Mock(),
                          conversation_history=[{'role': 'user', 'content': 'original'}],
                          session_id='original', _app=Mock(is_running=True))
    obj._pending_input.put('belongs to original')
    ui = Mock()
    for switch in (lambda: request_switch(obj, 'a', ui),
                   lambda: request_resume(obj, 'other', ui),
                   lambda: CLISessionMixin.new_session(obj)):
        with pytest.raises(ValueError, match='Queued messages belong to this conversation'):
            switch()
        assert list(obj._pending_input.queue) == ['belongs to original']
        assert obj.session_id == 'original'
        assert not hasattr(obj, '_pending_relaunch')
    from sci_cli.cli_loops_mixin import CLILoopsMixin
    import cli as cli_module
    notices = []
    monkeypatch.setattr(cli_module, '_cprint', notices.append)
    for handler in (CLILoopsMixin._cmd_new, CLILoopsMixin._cmd_clear):
        assert handler(obj, '/new') is True
        assert 'Queued messages belong' in notices[-1]
        assert list(obj._pending_input.queue) == ['belongs to original']
    obj._app.exit.assert_not_called()
    obj._pending_input.get_nowait()
    request_switch(obj, 'a', ui)
    assert obj._pending_relaunch == ['--cli', '-p', 'a']
