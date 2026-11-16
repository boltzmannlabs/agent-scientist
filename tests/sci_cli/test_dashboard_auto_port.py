"""Implicit dashboard ports advance; explicit endpoints and profile intent survive."""
import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import pytest


def _occupied_pair(stack):
    # Use OS-assigned candidates so this test never takes the user's dashboard port.
    for _ in range(100):
        first = socket.socket()
        first.bind(('127.0.0.1', 0))
        port = first.getsockname()[1]
        second = socket.socket()
        third = socket.socket()
        try:
            if port > 65533:
                raise OSError('Need room for two successors')
            second.bind(('127.0.0.1', port + 1))
            third.bind(('127.0.0.1', port + 2))
        except OSError:
            first.close()
            second.close()
            third.close()
            continue
        third.close()
        first.listen()
        second.listen()
        stack.enter_context(first)
        stack.enter_context(second)
        return port
    pytest.fail('Could not reserve consecutive fixture ports')


@pytest.mark.parametrize('explicit', [False, True])
@pytest.mark.parametrize('instance_flag', ['--isolated', '--new-instance'])
def test_dashboard_launch_uses_next_port_only_when_implicit(tmp_path, explicit, instance_flag):
    with ExitStack() as stack:
        port = _occupied_pair(stack)
        home = tmp_path / 'home'
        home.mkdir()
        env = dict(os.environ, SCI_HOME=str(home), SCI_SERVE_HEADLESS='1', PYTHONUNBUFFERED='1')
        for key in ('SCI_DESKTOP', 'SCI_PARENT_PID', 'SCI_PARENT_START_MARKER', 'SCI_PARENT_NONCE'):
            env.pop(key, None)
        code = f'''
import argparse, sys
from sci_cli import main, web_server
from sci_cli.subcommands.dashboard import build_dashboard_parser
parser = argparse.ArgumentParser()
build_dashboard_parser(parser.add_subparsers(dest="command"), cmd_dashboard=main.cmd_dashboard,
                       cmd_dashboard_register=lambda args: None)
args = parser.parse_args(sys.argv[1:])
args.port = {port}
# Exercise command policy and the real server/socket, without UI builds or tool discovery.
main._dashboard_prepare_runtime = lambda *args: False
web_server._maybe_open_browser = lambda host, port, *args: print("BROWSER_PORT=" + str(port), flush=True)
main.cmd_dashboard(args)
'''
        argv = ['dashboard', instance_flag, '--no-open']
        if explicit:
            argv += ['--port', str(port)]
        log = tmp_path / 'server.log'
        with log.open('w', encoding='utf-8') as output:
            proc = subprocess.Popen([sys.executable, '-c', code, *argv], env=env,
                                    cwd=Path(__file__).resolve().parents[2],
                                    stdout=output, stderr=subprocess.STDOUT)
            try:
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    text = log.read_text(encoding='utf-8-sig')
                    if proc.poll() is not None or 'BROWSER_PORT=' in text:
                        break
                    time.sleep(0.1)
                if explicit:
                    assert proc.poll() == 75, text
                    assert f'BACKEND_PORT_IN_USE port={port}' in text
                    assert 'SCI_DASHBOARD_READY' not in text
                else:
                    assert proc.poll() is None, text
                    assert f'SCI_DASHBOARD_READY port={port + 2}' in text
                    assert f'BROWSER_PORT={port + 2}' in text
                    assert f'using port {port + 2}' in text
                    with socket.create_connection(('127.0.0.1', port + 2), timeout=5):
                        pass
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=20)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=10)


@pytest.mark.parametrize('mode,explicit', [('dashboard', False), ('dashboard', True), ('serve', False)])
def test_named_profile_reexec_preserves_port_intent(tmp_path, monkeypatch, mode, explicit):
    from sci_cli import main_dashboard
    from sci_cli.subcommands.dashboard import build_dashboard_parser

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('SCI_HOME', str(tmp_path / '.sci'))
    monkeypatch.setattr('sci_cli.profiles.get_active_profile_name', lambda: 'fixture')
    monkeypatch.setattr(main_dashboard, '_is_desktop_owned_backend', lambda: False)
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest='command')
    build_dashboard_parser(commands, cmd_dashboard=lambda args: None,
                           cmd_dashboard_register=lambda args: None)
    argv = [mode, '--no-open'] + (['--port=9234'] if explicit else [])
    monkeypatch.setattr(sys, 'argv', ['sci', *argv])
    args = parser.parse_args(argv)
    captured = []

    def stop_at_reexec(*positional, **kwargs):
        captured.append(positional[1] if len(positional) > 1 else positional[0])
        raise SystemExit(0)

    monkeypatch.setattr(main_dashboard.os, 'execvpe', stop_at_reexec, raising=False)
    monkeypatch.setattr(main_dashboard.subprocess, 'Popen', stop_at_reexec)
    with pytest.raises(SystemExit):
        main_dashboard._route_named_profile_dashboard(args, mode == 'serve', None, None)
    child = captured[0]
    assert ('--port' in child) == (explicit or mode == 'serve')
    if explicit:
        assert child[child.index('--port') + 1] == '9234'
