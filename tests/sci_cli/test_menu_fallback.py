"""Real prompt_toolkit menus keep keyboard selection when native curses is unavailable."""
import sys
import threading

import pytest
from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput

from sci_cli import curses_ui as menus


@pytest.mark.parametrize(('kind', 'keys', 'expected'), [
    ('radio', '\x1b[B\r', 1),
    ('search', '/Beta\r', 2),
    ('multi', '\x1b[B \r', {0, 1}),
    ('single', '\x1b[B\r', 1),
    ('cancel', '\x1b', -1),
    ('back', '\x1b[D', -1),
    ('scroll', '\x1b[B' * 25 + '\r', 25),
])
def test_keyboard_fallback_preserves_menu_contract(tmp_path, monkeypatch, kind, keys, expected):
    monkeypatch.setitem(sys.modules, 'curses', None)
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: True)
    monkeypatch.setattr(sys.stdout, 'isatty', lambda: True)
    for function in ('_radio_numbered_fallback', '_numbered_single_fallback', '_numbered_fallback'):
        monkeypatch.setattr(menus, function, lambda *a: pytest.fail('opened numbered fallback'))
    events = []

    def navigation(event, *args):
        events.append(event)
        if event == menus.MenuNavigationEvent.BEGIN:
            return menus.MenuNavigationStart(allow_back=True)

    token = menus.set_menu_navigation_handler(navigation)
    with create_pipe_input() as keyboard, create_app_session(input=keyboard, output=DummyOutput()):
        timer = threading.Timer(8, lambda: keyboard.send_text('\x03'))
        timer.start()
        try:
            keyboard.send_text(keys)
            items = ['Alpha', 'Gamma', 'Beta']
            if kind == 'multi':
                result = menus.curses_checklist('Pick tools', items, {0})
            elif kind == 'single':
                result = menus.curses_single_select('Pick a tool', items)
            else:
                result = menus.curses_radiolist(
                    'Pick provider', [f'Item {i}' for i in range(40)] if kind == 'scroll' else items,
                    cancel_returns=-1, searchable=kind == 'search')
        finally:
            timer.cancel()
            menus.reset_menu_navigation_handler(token)
    assert result == expected
    assert menus.MenuNavigationEvent.RESOLVE in events
    if kind in {'cancel', 'back'}:
        expected_event = menus.MenuNavigationEvent.CANCEL if kind == 'cancel' else menus.MenuNavigationEvent.BACK
        assert expected_event in events


def test_no_terminal_never_opens_keyboard_application(monkeypatch):
    monkeypatch.setattr(sys.stdin, 'isatty', lambda: False)
    monkeypatch.setattr(menus, '_keyboard_menu', lambda **kw: pytest.fail('opened interactive menu without stdin'))
    assert menus.curses_radiolist('Pick', ['one', 'two'], cancel_returns=-1) == -1


def test_text_fallback_accepts_labels_without_numbering(monkeypatch, capsys):
    from sci_cli import curses_ui
    responses = iter(['Small Molecule Design', 'Protein Engineering', ''])
    monkeypatch.setattr(curses_ui, '_read_numbered_input', lambda _: next(responses))
    options = ['Protein Engineering', 'Small Molecule Design']
    assert curses_ui._numbered_single_fallback('Module', options + ['Cancel'], 2) == 1
    assert curses_ui._numbered_fallback('Modules', options, set(), set()) == {0}
    output = capsys.readouterr().out
    assert '1. Protein Engineering' not in output
    assert '2. Small Molecule Design' not in output
    assert all(option in output for option in options)
