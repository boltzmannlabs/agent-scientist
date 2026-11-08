"""Native Ctrl+/ key events must switch views through foreground and persistent CLIs."""

import json
import os
import sqlite3
import sys
import time

import pytest

from tests.fakes.fake_llm_provider import FakeLLMServer, Text, write_sci_home
from tests.sci_cli.test_windows_background_chats import ROOT, finish_service
from sci_cli.win_pty_bridge import WinPtyBridge


@pytest.mark.platforms('windows')
@pytest.mark.live_system_guard_bypass  # Only ConPTYs/services created under this temporary home.
@pytest.mark.parametrize('foreground', [False, True])
@pytest.mark.asyncio
async def test_ctrl_slash_preserves_main_and_side_context(tmp_path, foreground):
    home = tmp_path / '.sci'
    output = bytearray()

    def rows():
        if not (home / 'state.db').exists():
            return []
        with sqlite3.connect(home / 'state.db') as db:
            return db.execute('SELECT session_id, role, content FROM messages ORDER BY id').fetchall()

    def until(predicate, timeout=120):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if chunk := viewer.read(.05):
                output.extend(chunk)
            if result := predicate():
                return result
        raise AssertionError(f'Windows side shortcut did not reach expected state: {output[-3500:]!r}')

    # The native event form emitted by Windows Terminal: VK_OEM_2, scan 53,
    # no Unicode character, key down, left Ctrl, repeat 1. Raw US alone
    # would miss the native Windows bug.
    slash = b'\x1b[191;53;0;1;8;1_'
    release = b'\x1b[191;53;0;0;8;1_'
    with FakeLLMServer([Text('Main answer.'), Text('Side answer.')]) as model:
        write_sci_home(home, model.base_url)
        env = {**os.environ, 'SCI_HOME': str(home), 'USERPROFILE': str(tmp_path),
               'HOME': str(tmp_path), 'PYTHONPATH': str(ROOT), 'TERM': 'xterm-256color',
               'SCI_DISABLE_LAZY_INSTALLS': '1', 'SCI_STATE_DB_GUARD_BYPASS': '1'}
        args = [sys.executable, '-m', 'sci_cli.main', '--cli']
        if foreground:
            args.append('--no-daemon')
        viewer = WinPtyBridge.spawn(args, cwd=str(ROOT), env=env, cols=110, rows=36)
        try:
            until(lambda: '❯'.encode() in output, timeout=180)
            await viewer.write(b'Main fixture question')
            until(lambda: b'Main fixture question' in output)
            time.sleep(.5)  # Match the CLI's paste-vs-Enter pacing.
            await viewer.write(b'\r')
            until(lambda: any(r[1:] == ('assistant', 'Main answer.') for r in rows()))
            parent = rows()
            await viewer.write(b'main draft')
            until(lambda: b'main draft' in output)
            output.clear()
            await viewer.write(slash + release)
            until(lambda: b'Ctrl+Q' in output, timeout=45)
            await viewer.write(b'Side fixture question')
            until(lambda: b'Side fixture question' in output)
            time.sleep(.5)
            await viewer.write(b'\r')
            until(lambda: any(r[1:] == ('assistant', 'Side answer.') for r in rows()))
            output.clear()
            await viewer.write(slash + release)
            until(lambda: b'main draft' in output, timeout=30)
            assert [r for r in rows() if r[0] == parent[0][0]] == parent
            with sqlite3.connect(home / 'state.db') as db:
                configs = [json.loads(r[0] or '{}') for r in db.execute('SELECT model_config FROM sessions')]
            assert sum(bool(c.get('_side_from')) for c in configs) == 1
            assert len(model.main_requests()) == 2
        finally:
            viewer.close()
            if not foreground:
                finish_service(home)
