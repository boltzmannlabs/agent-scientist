"""A long terminal replay must yield to keyboard input before draining everything."""

import base64
import io
import json
from types import SimpleNamespace


def test_detach_is_read_between_replay_batches(monkeypatch):
    from sci_cli import background_chat_terminal as terminal, background_chat_console

    frame = json.dumps({'output': base64.b64encode(b'frame').decode()}).encode() + b'\n'
    reply = json.dumps({'attached': 'fixture'}).encode() + b'\n'

    class Socket:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def settimeout(self, _): pass
        def recv(self, _): return reply + frame * 40

    class Output(io.StringIO):
        def __init__(self):
            super().__init__()
            self.buffer = io.BytesIO()

        def isatty(self): return True

    output = Output()
    polled = []

    class Console:
        stopped = resized = False
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def poll(self, sock, **kwargs):
            polled.append(output.buffer.getvalue().count(b'frame'))
            return False, b'\x1d'

    monkeypatch.setattr(terminal, 'connect', lambda *_: Socket())
    monkeypatch.setattr(terminal, 'send', lambda *_: None)
    monkeypatch.setattr(terminal.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(terminal.sys, 'stdout', output)
    monkeypatch.setattr(terminal.os, 'get_terminal_size', lambda: SimpleNamespace(columns=80, lines=24))
    monkeypatch.setattr(background_chat_console, 'terminal_console', lambda _: Console())
    terminal._attach_once('fixture')
    assert 0 < polled[0] < 40
