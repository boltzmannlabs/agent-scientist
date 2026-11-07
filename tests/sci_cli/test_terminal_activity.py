"""Terminal titles reflect work without writing animation into the transcript."""

import pytest

from io import StringIO
from types import SimpleNamespace

from prompt_toolkit.data_structures import Size
from prompt_toolkit.output.vt100 import Vt100_Output

from sci_cli.terminal_activity import TerminalActivity


def test_activity_title_moves_only_while_busy_and_restores_shell_title(monkeypatch):
    class Terminal(StringIO):
        def isatty(self):
            return True

    monkeypatch.setenv("TERM_PROGRAM", "xterm")
    stream = Terminal()
    output = Vt100_Output(stream, lambda: Size(rows=24, columns=80), term='xterm')
    cli = SimpleNamespace(_app=SimpleNamespace(output=output, is_running=True), _agent_running=False)
    activity = TerminalActivity()
    clock = [0]
    monkeypatch.setattr('sci_cli.terminal_activity.time.monotonic', lambda: clock[0])
    activity.update(cli)
    idle = stream.getvalue()
    activity.update(cli)
    assert stream.getvalue() == idle
    assert '\033]2;· Agent Scientist\x07' in idle
    cli._agent_running = True
    activity.update(cli)
    first = activity.title
    clock[0] = 0.6
    activity.update(cli)
    assert activity.title != first
    cli._clarify_state = {'question': 'Choose'}
    activity.update(cli)
    assert activity.title.startswith('? ')
    awaiting = stream.getvalue()
    clock[0] = 1.2
    activity.update(cli)
    assert stream.getvalue() == awaiting
    activity.restore(output)
    assert stream.getvalue().endswith('\033[23;2t')
    restored = stream.getvalue()
    activity.restore(output)
    assert stream.getvalue() == restored
    cli._app.is_running = False
    activity.update(cli)
    assert stream.getvalue() == restored


def test_activity_never_writes_to_redirected_output():
    stream = StringIO()
    output = Vt100_Output(stream, lambda: Size(rows=24, columns=80), term='xterm')
    cli = SimpleNamespace(_app=SimpleNamespace(output=output, is_running=True), _agent_running=True)
    activity = TerminalActivity()
    activity.update(cli)
    activity.restore(output)
    assert stream.getvalue() == ''


@pytest.mark.platforms("posix")
def test_vscode_native_progress_over_a_real_terminal(monkeypatch):
    import os
    import pty
    import select
    master, slave = pty.openpty()
    monkeypatch.setenv('TERM_PROGRAM', 'vscode')
    try:
        with os.fdopen(slave, 'w', buffering=1) as stream:
            output = Vt100_Output(stream, lambda: Size(rows=24, columns=80), term='xterm')
            cli = SimpleNamespace(_app=SimpleNamespace(output=output, is_running=True), _agent_running=True)
            activity = TerminalActivity()
            def read():
                assert select.select([master], [], [], 2)[0], 'No terminal output'
                return os.read(master, 4096).decode()
            activity.update(cli)
            assert '\x1b]9;4;3;\x07' in read()
            cli._clarify_state = {'question': 'Choose'}
            activity.update(cli)
            assert '\x1b]9;4;0;\x07' in read()
            cli._clarify_state = None
            activity.update(cli)
            assert '\x1b]9;4;3;\x07' in read()
            cli._agent_running = False
            activity.update(cli)
            assert '\x1b]9;4;0;\x07' in read()
            cli._agent_running = True
            activity.update(cli)
            read()
            activity.restore(output)
            assert '\x1b]9;4;0;\x07' in read()
    finally:
        os.close(master)
