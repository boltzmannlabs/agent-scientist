"""Resume and wizard Escape run through the real persistent classic CLI."""

import json

import pytest
from tests.e2e.core import _pm_dependencies  # noqa: F401


@pytest.mark.platforms("linux")
@pytest.mark.live_system_guard_bypass
def test_resume_search_cancel_selection_and_wizard_escape(tmp_path):
    from tests.e2e.core.terminal._pty import PtySci, poll
    from tests.fakes.fake_llm_provider import FakeLLMServer, Text
    from sci_state import SessionDB

    def respond(record):
        messages = record['body'].get('messages') or []
        if 'side-context-question' in str(messages[-1].get('content')):
            context = json.dumps(messages)
            assert 'SAVED_MESSAGE' in context and 'SAVED_SECOND_TURN' in context
            assert 'SAVED_REPLY' in context
            return Text('SIDE_CONTEXT_OK')
        return Text('MAIN_RESPONSE')

    with FakeLLMServer(respond) as llm:
        child = PtySci(tmp_path, ['chat', '--cli'], llm, rows=32, cols=100)
        try:
            child.wait_ready()
            child.submit('hello fixture')
            child.wait_for_text('MAIN_RESPONSE')
            child.wait_turns_persisted(1)
            for index in range(30):
                profile = child.sci_home / 'profiles' / f'project-{index:02}'
                profile.mkdir(parents=True)
                (profile / 'config.yaml').write_text('{}\n')
            child.submit('/activate')
            child.wait_for_text('Choose a profile')
            child.write('\x1b[B' * 60)
            child.wait_for_text('❯ Cancel')
            child.wait_quiet()
            copies = child.count('Choose a profile')
            child.write('\x1b[B' * 30)
            child.wait_quiet()
            assert child.count('Choose a profile') == copies
            child.write('\x1b[A' * 60)
            child.wait_for_text('❯ main — currently active')
            child.write('\x1b')
            child.wait_for_text('Activation cancelled')
            with SessionDB(child.sci_home / 'state.db') as db:
                db.create_session('picker-fixture-saved', source='cli')
                db.set_session_title('picker-fixture-saved', 'SAVED_CONVERSATION')
                db.append_message('picker-fixture-saved', 'user', 'SAVED_MESSAGE')
                db.append_message('picker-fixture-saved', 'assistant', 'SAVED_REPLY')
                db.append_message('picker-fixture-saved', 'user', 'SAVED_SECOND_TURN')
                db.append_message('picker-fixture-saved', 'assistant', 'SAVED_SECOND_REPLY')
                saved = db.get_messages_as_conversation('picker-fixture-saved')
            child.submit('/resume')
            child.wait_for_text('Enter resume')
            child.write('no-matching-title')
            child.wait_for_text('No conversations found')
            child.write('\x1b')
            child.wait_for_text('Conversation selection cancelled', timeout=10)
            child.submit('/Create_profile')
            child.wait_for_text('Name your science profile')
            child.write('\x1b')
            poll(lambda: child.count('Esc cancel') == 0, timeout=10, what='wizard closed on Escape')
            child.submit('/resume')
            child.wait_for_text('Enter resume')
            child.write('SAVED_CONVERSATION')
            child.wait_for_text('Search: SAVED_CONVERSATION')
            child.write('\r')
            child.wait_for_text('SAVED_SECOND_REPLY')
            assert '◆ Sci:' not in child.text() and '● You:' not in child.text()
            child.submit('/side side-context-question')
            child.wait_for_text('SIDE_CONTEXT_OK')
            child.write('\x1f')
            child.wait_for_text('SAVED_SECOND_REPLY')
            with SessionDB(child.sci_home / 'state.db') as db:
                assert db.get_messages_as_conversation('picker-fixture-saved') == saved
            child.write('\x1f')
            child.wait_for_text('SIDE_CONTEXT_OK')
            child.write('\x03')
            child.wait_for_text('SAVED_SECOND_REPLY')
            assert child.exit() == 0
            assert not child.leftover_processes()
        finally:
            child.close()
