"""The installed Windows x64 runtime must provide the native curses menu API."""
import pytest


@pytest.mark.platforms('windows', arch='x64')
def test_native_curses_keyboard_api_is_installed():
    import curses

    assert callable(curses.wrapper)
    assert curses.KEY_UP != curses.KEY_DOWN
