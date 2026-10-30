"""A failed transcript read must not masquerade as an empty history (#100788).

The gateway restore path (``_handle_message``) already fails closed on
current main (#100910). This file covers the surviving half of PR #100887:
the slash-command handlers, which used to let ``TranscriptReadError``
propagate into the dispatch wrapper and reply with nothing at all.

Incident shape: a malformed ``state.db`` made every
``SessionStore.load_transcript`` raise; the except-block swallowed it and
returned ``[]``.  Restore then rebuilt the turn from "no history", so a
long-running chat silently restarted as a brand-new conversation and the
model happily answered as if nothing had ever been discussed.

Two guarantees under test:
  A. ``load_transcript`` raises ``TranscriptReadError`` on a read failure,
     while a genuinely empty session still returns ``[]``.
  B. Slash-command handlers that read the transcript reply with
     ``HISTORY_UNREADABLE`` instead of raising into the dispatch wrapper
     (which logs and sends nothing).

Offline: SQLite on tmp_path only, no network.
"""

import sqlite3

import pytest

from gateway.config import GatewayConfig
from gateway.session import SessionStore
from gateway.session_transcript import TranscriptReadError

@pytest.fixture
def store(tmp_path):
    return SessionStore(sessions_dir=tmp_path / "gw", config=GatewayConfig())

# --------------------------------------------------------------------------
# A. read failure != empty transcript (landed on main via #100910; kept as
#    the contract the slash-command handlers below rely on)
# --------------------------------------------------------------------------

class TestLoadTranscriptReadFailure:
    def test_read_failure_raises_instead_of_returning_empty(self, store, monkeypatch):
        db = store._db
        assert db is not None
        db.create_session("s1", "telegram", session_key="telegram:1")
        db.append_message("s1", "user", "the conversation we must not forget")

        boom = sqlite3.DatabaseError("database disk image is malformed")

        def _raise(*_args, **_kwargs):
            raise boom

        monkeypatch.setattr(db, "get_messages_as_conversation", _raise)

        with pytest.raises(TranscriptReadError) as excinfo:
            store.load_transcript("s1")

        assert excinfo.value.session_id == "s1"
        assert excinfo.value.__cause__ is boom

    def test_genuinely_empty_session_still_returns_empty_list(self, store):
        db = store._db
        assert db is not None
        db.create_session("s2", "telegram", session_key="telegram:2")

        assert store.load_transcript("s2") == []

    def test_no_db_still_returns_empty_list(self, store):
        # "No DB for this session" really is an empty transcript, not a
        # failure — that path must keep its [] contract.
        store._db = None
        assert store.load_transcript("nope") == []
