"""GUI discovery must not borrow another user's session or export their environment."""
from types import SimpleNamespace
import os

import pytest

from sci_platform.resolver import desktop_session


@pytest.mark.platforms('linux')
def test_discovery_filters_owner_and_returns_only_display_variables(monkeypatch):
    monkeypatch.setenv('SSH_CONNECTION', 'fixture ssh session')
    class Process:
        def __init__(self, uid, name, display):
            self.info = {'uids': SimpleNamespace(real=uid), 'name': name}
            self.display = display
        def environ(self):
            return {'DISPLAY': self.display, 'XAUTHORITY': '/fixture/auth', 'API_KEY': 'never-return'}
    monkeypatch.setattr(desktop_session.psutil, 'process_iter', lambda *args: [
        Process(os.getuid(), 'gnome-shell', ':1'),
        Process(os.getuid(), 'gnome-session-binary', ':1'),
        Process(os.getuid() + 1, 'gnome-shell', ':2'),
        Process(os.getuid(), 'unrelated', ':3'),
    ])
    targets = desktop_session.desktop_sessions()
    assert len(targets) == 1
    assert targets[0].env == {'DISPLAY': ':1', 'XAUTHORITY': '/fixture/auth'}
