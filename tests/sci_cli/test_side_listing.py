"""Saved side branches stay recoverable without crowding normal CLI resume."""

from pathlib import Path
from types import SimpleNamespace


def test_side_filter_applies_before_pagination_search_and_profile_switch(tmp_path, monkeypatch):
    from sci_state import SessionDB
    from sci_cli.session_picker import SessionPicker
    from sci_cli.session_listing import query_session_listing

    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    for name in ('a', 'b', 'a'):
        home = tmp_path / name
        monkeypatch.setenv('SCI_HOME', str(home))
        with SessionDB(home / 'state.db') as db:
            if not db.get_session('main'):
                db.create_session('main', 'cli', system_prompt='unchanged cached prefix')
                db.set_session_title('main', 'Side: an ordinary conversation title')
                db.append_message('main', 'user', 'main question')
                # More side branches than the picker's first SQL page: filtering
                # after LIMIT would still hide the ordinary conversation.
                for i in range(205):
                    sid = f'side-{i}'
                    db.create_session(sid, 'cli', parent_session_id='main',
                                      model_config={'_branched_from': 'main', '_side_from': 'main'})
                    db.set_session_title(sid, f'Saved specialist discussion {i}')
                    db.append_message(sid, 'user', 'retained side question')
            before = db.get_messages('side-0')
            picker = SessionPicker(SimpleNamespace(_session_db=db, session_id='current'))
            assert [row['id'] for row in picker.rows] == ['main']
            assert [row['id'] for row in db.search_sessions(
                source=['cli', 'oneshot'], limit=1, include_side_conversations=False)] == ['main']
            picker.search.text = 'specialist'
            assert picker.rows == []
            assert query_session_listing(db, source='cli', search_query='side-0') == []
            explicit = query_session_listing(db, source='cli', include_all_sources=True,
                                             include_unnamed=True, search_query='side-0')
            assert [row['id'] for row in explicit] == ['side-0']
            assert db.get_messages('side-0') == before
            assert db.get_session('main')['system_prompt'] == 'unchanged cached prefix'
