"""Browser tool results survive live delivery and history projection without raw secrets."""

import copy
import json

from tui_gateway import server
from tui_gateway.methods_session import _Resume
from tui_gateway.tool_display import MAX_TOOL_DISPLAY_CHARS, tool_display_text
from sci_state import SessionDB


def test_live_and_saved_tool_output_preserve_results_and_redaction(tmp_path, monkeypatch):
    events = []
    monkeypatch.setattr(server, "_emit", lambda kind, sid, payload: events.append((kind, sid, payload)))
    # Alternate real profile scopes; display changes never mutate the stored/model history.
    for index, profile in enumerate(("a", "b", "a")):
        home = tmp_path / profile
        home.mkdir(exist_ok=True)
        monkeypatch.setenv("SCI_HOME", str(home))
        sid = f"web-{profile}"
        monkeypatch.setitem(server._sessions, sid, {"source": "web", "tool_progress_mode": "all"})
        result = json.dumps({"output": f"result-{profile}", "api_key": "secret-fixture-key", "output_path": str(home / "report.csv")})
        history = [
            {"role": "assistant", "content": "Checking files.", "tool_calls": [{"id": "tool-1", "function": {"name": "terminal", "arguments": '{"command":"pwd"}'}}]},
            {"role": "tool", "tool_call_id": "tool-1", "content": result},
        ]
        before = copy.deepcopy(history)
        server._on_tool_complete(sid, "tool-1", "terminal", {"command": "pwd"}, result)
        payload = events[-1][2]
        db = SessionDB(home / "state.db")
        try:
            db.create_session(str(index), source="web")
            db.append_messages_batch(str(index), copy.deepcopy(history))
            retained = db.get_messages_as_conversation(str(index), repair_alternation=False)
        finally:
            db.close()
        resume = _Resume.__new__(_Resume)
        resume.omit_messages = False
        resume.params = {"source": "web"}
        resume.profile_home = home
        saved = resume.messages(retained)[-1]
        assert events[-1][:2] == ("tool.complete", sid)
        assert payload["result_text"] == saved["text"]
        assert f"result-{profile}" in saved["text"]
        assert str(home / "report.csv") in saved["text"]
        assert "secret-fixture-key" not in saved["text"]
        assert saved["tool_call_id"] == "tool-1"
        assert history == before
        assert "text" not in server._history_to_messages(history)[-1]


def test_tool_display_bounds_and_fail_closed_redaction(monkeypatch):
    import agent.redact

    assert tool_display_text("") == ""
    assert tool_display_text(False) == "false"
    assert tool_display_text(0) == "0"
    large = tool_display_text("x" * (MAX_TOOL_DISPLAY_CHARS * 2))
    assert len(large) < MAX_TOOL_DISPLAY_CHARS + 100
    assert "Display truncated" in large
    def unavailable(*args, **kwargs):
        raise RuntimeError("fixture")
    monkeypatch.setattr(agent.redact, "redact_sensitive_text", unavailable)
    assert tool_display_text("secret-fixture-key") == "[Output unavailable: redaction failed.]"
