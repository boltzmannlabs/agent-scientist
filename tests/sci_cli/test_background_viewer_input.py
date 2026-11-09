"""A long terminal replay must yield to keyboard input before draining everything."""

import base64
import io
import json
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('payload, copies', [(b'frame', 40), (b'frame' * 6500, 1)], ids=['many-frames', 'large-frame'])
def test_detach_is_read_between_replay_batches(monkeypatch, payload, copies):
    from sci_cli import background_chat_terminal as terminal, background_chat_console

    frame = json.dumps({'output': base64.b64encode(payload).decode()}).encode() + b'\n'
    reply = json.dumps({'attached': 'fixture'}).encode() + b'\n'

    class Socket:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def settimeout(self, _): pass
        def recv(self, _): return reply + frame * copies

    class Output(io.StringIO):
        def __init__(self):
            super().__init__()
            self.buffer = io.BytesIO()

        def isatty(self): return True

    output = Output()
    polled = []
    sent = []

    class Console:
        stopped = resized = False
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def poll(self, sock, **kwargs):
            polled.append(output.getvalue().count('frame'))
            return False, b'q\x1d'

    monkeypatch.setattr(terminal, 'connect', lambda *_: Socket())
    monkeypatch.setattr(terminal, 'send', lambda sock, message: sent.append(message))
    monkeypatch.setattr(terminal.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(terminal.sys, 'stdout', output)
    monkeypatch.setattr(terminal.os, 'get_terminal_size', lambda: SimpleNamespace(columns=80, lines=24))
    monkeypatch.setattr(background_chat_console, 'terminal_console', lambda _: Console())
    terminal._attach_once('fixture')
    assert 0 < polled[0] < payload.count(b'frame') * copies
    assert [base64.b64decode(event['data']) for event in sent if event['action'] == 'input'] == [b'q']


def test_replay_decodes_characters_across_service_frames(monkeypatch):
    from sci_cli import background_chat_terminal as terminal, background_chat_console

    events = [{'attached': 'fixture'},
              {'output': base64.b64encode(b'hello \xe2').decode()},
              {'output': base64.b64encode(b'\x94\x80 world').decode()},
              {'closed': 0}]
    wire = b''.join(json.dumps(event).encode() + b'\n' for event in events)

    class Socket:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def settimeout(self, _): pass
        def recv(self, _): return wire

    class Output(io.StringIO):
        def isatty(self): return True

    class Console:
        stopped = resized = False
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def poll(self, sock, **kwargs): return False, None

    output = Output()
    monkeypatch.setattr(terminal, 'connect', lambda *_: Socket())
    monkeypatch.setattr(terminal, 'send', lambda *_: None)
    monkeypatch.setattr(terminal.sys, 'stdin', SimpleNamespace(isatty=lambda: True))
    monkeypatch.setattr(terminal.sys, 'stdout', output)
    monkeypatch.setattr(terminal.os, 'get_terminal_size', lambda: SimpleNamespace(columns=80, lines=24))
    monkeypatch.setattr(background_chat_console, 'terminal_console', lambda _: Console())
    assert terminal._attach_once('fixture') == {'closed': 0}
    assert 'hello ─ world' in output.getvalue()
    assert '\ufffd' not in output.getvalue()
