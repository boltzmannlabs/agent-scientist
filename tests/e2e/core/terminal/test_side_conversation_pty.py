"""A real terminal detour while the parent is blocked in a loopback model request."""

import json
import sqlite3
from threading import Event

import pytest

# Prepare disposable PM tool copies at collection, before the per-test home-I/O guard.
from tests.e2e.core import _pm_dependencies  # noqa: F401


@pytest.mark.platforms("linux")
@pytest.mark.live_system_guard_bypass  # PTY harness only kills children in its own session.
def test_side_detour_rename_and_return_keep_parent_running(tmp_path):
    from tests.e2e.core.terminal._pty import PtySci, poll
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text

    entered, release = Event(), Event()

    def respond(record):
        messages = record['body'].get('messages') or []
        users = [m for m in messages if m.get('role') == 'user']
        text = str(users[-1].get('content')) if users else ''
        if text == 'parent-held-question':
            entered.set()
            assert release.wait(90)
            return Text('PARENT_HELD_DONE')
        if 'side-first-question' in text:
            return Text('\n'.join(f'context line {n}' for n in range(80)) + '\nSIDE_FIRST_DONE')
        if text == 'side-followup-question':
            assert 'SIDE_FIRST_DONE' in json.dumps(messages)
            return Text('SIDE_FOLLOWUP_DONE')
        return Text('PARENT_WARM_DONE')

    with FakeLLMServer(respond) as llm:
        child = PtySci(tmp_path, ['chat', '--cli'], llm, rows=45, cols=120)
        def renamed():
            with sqlite3.connect(f'file:{child.sci_home / "state.db"}?mode=ro', uri=True) as db:
                return db.execute('SELECT id FROM sessions WHERE title = ?', ('Study alpha',)).fetchone()
        try:
            child.wait_ready()
            child.submit('parent-warm-question')
            child.wait_for_text('PARENT_WARM_DONE')
            child.wait_turns_persisted(1)
            child.submit('parent-held-question')
            assert entered.wait(30), child.dump()
            child.submit('/side side-first-question')
            child.wait_for_text('SIDE_FIRST_DONE')
            assert child.screen.alt_active
            assert 'PARENT_WARM_DONE' not in child.text()
            child.write('\x1b[5~')  # Page Up reads side history, not composer history
            poll(lambda: child.count('SIDE_FIRST_DONE') == 0, timeout=5, what='side transcript scrolled')
            reading = [line.strip() for line in child.lines() if line.strip().startswith('context line')]
            assert reading
            child.write('\x1f')
            child.wait_for_text('PARENT_WARM_DONE')
            child.write('\x1f')
            child.wait_for_text(reading[0])
            assert [line.strip() for line in child.lines() if line.strip().startswith('context line')] == reading
            child.write('\x1b[6~')
            child.wait_for_text('SIDE_FIRST_DONE')
            child.write('wheel-keeps-draft')
            child.wait_for_text('wheel-keeps-draft')
            child.write('\x1b[<64;20;43M' * 4)  # Wheel over composer, not transcript.
            poll(lambda: child.count('SIDE_FIRST_DONE') == 0, timeout=5, what='wheel over composer scrolled side')
            assert 'wheel-keeps-draft' in child.text()
            child.write('\x1b[<65;20;43M' * 4)
            child.wait_for_text('SIDE_FIRST_DONE')
            child.write('\x1b[<64;20;10M' * 4)  # SGR mouse wheel up over transcript
            poll(lambda: child.count('SIDE_FIRST_DONE') == 0, timeout=5, what='mouse wheel scrolled side')
            assert 'wheel-keeps-draft' in child.text()
            child.write('\x1b[<65;20;10M' * 4)
            child.wait_for_text('SIDE_FIRST_DONE')
            # Input recovery disables terminal modes; side must re-enable its
            # alternate screen and mouse reporting, rather than only repainting.
            recovery_start = len(child.raw)
            child.write('\x1b[200~<64;20;43M\x1b[201~')
            poll(lambda: b'\x1b[?1006h' in child.raw[recovery_start:], timeout=5,
                 what='mouse reporting restored after terminal recovery')
            child.wait_for_text('SIDE_FIRST_DONE')
            child.write('\x1b[<64;20;43M' * 4)
            poll(lambda: child.count('SIDE_FIRST_DONE') == 0, timeout=5, what='scroll after terminal mode recovery')
            child.write('\x1b[1;5F')  # Ctrl+End returns to latest output.
            child.wait_for_text('SIDE_FIRST_DONE')
            child.write('\x15')
            child.resize(34, 92)
            child.write('\x0c')  # Ctrl+L must repaint side, never replay main history
            child.wait_for_text('SIDE_FIRST_DONE')
            assert 'PARENT_WARM_DONE' not in child.text()
            child.submit('side-followup-question')
            child.wait_for_text('SIDE_FOLLOWUP_DONE')
            child.write('side-unsent-draft')
            child.wait_for_text('side-unsent-draft')
            child.write('\x1f')  # Ctrl+/ in legacy terminals
            child.wait_for_text('PARENT_WARM_DONE')
            assert not child.screen.alt_active
            assert 'SIDE_FOLLOWUP_DONE' not in child.text()
            child.write('main-unsent-draft')
            child.wait_for_text('main-unsent-draft')
            child.write('\x1b[47;5u')  # Ctrl+/ in Kitty/CSI-u terminals
            child.wait_for_text('side-unsent-draft')
            assert 'main-unsent-draft' not in child.text()
            # Parent completion must remain in main even when it arrives in side mode.
            release.set()
            child.wait_turns_persisted(2)
            assert 'PARENT_HELD_DONE' not in child.text()
            child.write('\x1f')
            child.wait_for_text('main-unsent-draft')
            child.wait_for_text('PARENT_HELD_DONE')
            child.write('\x15')  # clear the retained main draft
            child.submit('/rename "Study alpha"')
            child.wait_for_text('Study alpha')
            poll(renamed, timeout=15, what='persisted manual conversation title')
            child.submit('/side')
            child.wait_for_text('side-unsent-draft')
            child.write('\x03')  # closes even with an unfinished side draft
            child.wait_for_text('PARENT_HELD_DONE')
            assert not child.screen.alt_active
            assert child.proc.poll() is None
            assert child.exit() == 0
            saved = child.persisted_messages()
            assert not any('side-first-question' in str(row) or 'side-followup-question' in str(row) for row in saved)
            assert any('PARENT_HELD_DONE' in str(row) for row in saved)
        finally:
            release.set()
            child.close()


@pytest.mark.platforms("linux")
@pytest.mark.live_system_guard_bypass
def test_side_tools_and_questions_use_normal_ui_without_answering_parent(tmp_path):
    from tests.e2e.core.terminal._pty import PtySci, poll
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text, ToolCall

    marker = tmp_path / 'side-result.txt'
    marker.write_text('Disposable fixture; remove only after approval.')
    started, release = tmp_path / 'tool-started', tmp_path / 'release-output'
    emitted = tmp_path / 'output-emitted'
    plugin = tmp_path / 'home' / '.sci' / 'plugins' / 'side-output-fixture'
    plugin.mkdir(parents=True)
    (plugin / 'plugin.yaml').write_text('name: side-output-fixture\nversion: 1.0.0\ndescription: test output owner\n')
    (plugin / '__init__.py').write_text(
        'import sys, time\nfrom pathlib import Path\n'
        'def register(ctx):\n'
        '    def tool_output(*, tool_name, args, next_call, **kwargs):\n'
        '        result = next_call(args)\n'
        f'        if tool_name == "terminal" and {str(marker)!r} in args.get("command", ""):\n'
        f'            Path({str(started)!r}).touch()\n'
        '            deadline = time.monotonic() + 30\n'
        f'            while not Path({str(release)!r}).exists():\n'
        '                if time.monotonic() > deadline: raise TimeoutError("fixture output gate")\n'
        '                time.sleep(0.01)\n'
        '            print("SIDE_RAW_POLLING: result not ready", flush=True)\n'
        '            print("SIDE_RAW_DOWNLOADED: format.csv", file=sys.stderr, flush=True)\n'
        f'            Path({str(emitted)!r}).touch()\n'
        '        return result\n'
        '    ctx.register_middleware("tool_execution", tool_output)\n')
    side_results = []

    def respond(record):
        messages = record['body'].get('messages') or []
        last_user = max(i for i, m in enumerate(messages) if m.get('role') == 'user')
        question = str(messages[last_user].get('content'))
        results = [m for m in messages[last_user + 1:] if m.get('role') == 'tool']
        if 'parent-needs-answer' in question:
            if results:
                return Text('PARENT_QUESTION_FINISHED')
            return ToolCall('clarify', {'questions': [{'question': 'MAIN_ONLY_QUESTION', 'choices': ['Main approved']}]})
        if 'side-use-tools' in question:
            if not results:
                return ToolCall('clarify', {'questions': [{'question': 'SIDE_ONLY_QUESTION', 'choices': ['Side approved']}]})
            side_results[:] = results
            if len(results) == 1:
                assert 'Side approved' in str(results[0])
                return ToolCall('terminal', {'command': f'rm -rf {marker}'})
            return Text('SIDE_TOOL_FINISHED')
        if 'side-cancel-question' in question:
            if not results:
                return ToolCall('clarify', {'questions': [{'question': 'SIDE_CANCEL_QUESTION', 'choices': ['Continue']}]})
            return Text('SIDE_CANCEL_FINISHED')
        return Text('MAIN_READY')

    with FakeLLMServer(respond) as llm:
        child = PtySci(tmp_path, ['chat', '--cli'], llm, rows=40, cols=120,
                       extra_config='approvals:\n  mode: manual\n  timeout: 90\nplugins:\n  enabled: [side-output-fixture]\n')
        try:
            child.wait_ready()
            child.submit('warm up')
            child.wait_for_text('MAIN_READY')
            child.wait_turns_persisted(1)
            child.submit('parent-needs-answer')
            child.wait_for_text('MAIN_ONLY_QUESTION')
            child.write('\x1f')
            poll(lambda: child.screen.alt_active, timeout=10, what='side opened over main question')
            child.submit('side-use-tools')
            child.wait_for_text('SIDE_ONLY_QUESTION')
            assert 'MAIN_ONLY_QUESTION' not in child.text()
            assert marker.exists()
            child.write('\x1f')
            child.wait_for_text('MAIN_ONLY_QUESTION')
            assert 'SIDE_ONLY_QUESTION' not in child.text()
            child.write('\x1f')
            child.wait_for_text('SIDE_ONLY_QUESTION')
            child.write('\r')
            child.wait_for_text('Allow once')
            assert marker.exists(), 'Command executed before side approval'
            child.write('\x1f')
            child.wait_for_text('MAIN_ONLY_QUESTION')
            child.write('\x1f')
            child.wait_for_text('Allow once')
            child.write('\r')
            poll(started.exists, timeout=20, what='side tool worker reached fixture output gate')
            child.write('\x1f')
            child.wait_for_text('MAIN_ONLY_QUESTION')
            before_output = len(child.raw)
            release.touch()
            poll(emitted.exists, timeout=20, what='side tool emitted output while main visible')
            assert 'SIDE_RAW_' not in child.text()
            assert b'SIDE_RAW_' not in bytes(child.raw[before_output:])
            child.write('\x1f')
            child.wait_for_text('SIDE_TOOL_FINISHED')
            child.wait_for_text('SIDE_RAW_POLLING: result not ready')
            child.wait_for_text('SIDE_RAW_DOWNLOADED: format.csv')
            assert not marker.exists(), side_results
            assert any('exit_code' in str(result) for result in side_results)
            rendered = child.text()
            assert 'Sci' in rendered
            for stale in ('[Side] You:', '[Side] Answering', 'Tools and scientific execution are disabled', '/side close'):
                assert stale not in rendered
            child.submit('side-cancel-question')
            child.wait_for_text('SIDE_CANCEL_QUESTION')
            child.write('\x03')
            child.wait_for_text('MAIN_ONLY_QUESTION')
            assert not child.screen.alt_active
            child.write('\r')
            child.wait_for_text('PARENT_QUESTION_FINISHED')
            child.wait_turns_persisted(2)
            assert child.exit() == 0
            assert not any('side-use-tools' in str(row) or 'SIDE_TOOL_FINISHED' in str(row)
                           for row in child.persisted_messages())
        finally:
            release.touch()
            child.close()
