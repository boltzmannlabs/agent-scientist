"""A retained transcript is display data, independent of compressed model context."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


def test_resume_hides_tools_but_viewer_retains_details_and_profile_boundaries(tmp_path, monkeypatch):
    from sci_state import SessionDB
    from sci_cli.cli_agent_setup_mixin import CLIAgentSetupMixin
    from sci_cli.cli_session_mixin import CLISessionMixin
    from rich.console import Console
    from io import StringIO
    from types import MethodType
    from sci_cli.native_profile_creation import profile_scope
    from sci_cli.transcript_viewer import load_transcript, TranscriptView
    from prompt_toolkit.widgets import TextArea
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / ".sci"))
    for home in (tmp_path / "a", tmp_path / "b", tmp_path / "a"):
        home.mkdir(exist_ok=True)
        with profile_scope(home), SessionDB(home / "state.db") as db:
            if not db.get_session("session"):
                db.create_session("session", source="cli", system_prompt="frozen-" + home.name)
                for i in range(19):
                    db.append_message("session", "user" if i % 2 == 0 else "assistant", home.name + str(i))
                db.append_message("session", "tool", "X" * 13000 + home.name + "-end", tool_name="fixture")
            prompt = db.get_session("session")["system_prompt"]
            _, rows = db.get_resume_conversations("session")
            assert len(rows) == 20 and rows[-1]["content"].endswith(home.name + "-end")
            assert all(r["content"].startswith(home.name) or r["role"] == "tool" for r in rows)
            output = StringIO()
            cli = SimpleNamespace(_session_db=db, session_id="session", _resume_display_history=rows,
                                  conversation_history=[{"role": "user", "content": "compressed"}],
                                  _console_print=Console(file=output, width=100).print)
            cli._render_resume_history_panel_lines = MethodType(CLISessionMixin._render_resume_history_panel_lines, cli)
            CLIAgentSetupMixin._display_resumed_history(cli)
            assert "X" * 100 not in output.getvalue()
            assert "Result fixture" not in output.getvalue()
            # A stale resume cache must never leak another profile into the viewer.
            cli._resume_display_history = [{"role": "user", "content": "other-profile-private"}]
            view = TranscriptView(load_transcript(cli), TextArea(read_only=True))
            assert "other-profile-private" not in view.area.text
            assert home.name + "18" in view.area.text
            assert "X" * 100 not in view.area.text
            view.next_tool(1)
            view.toggle()
            assert "X" * 13000 + home.name + "-end" in view.area.text
            assert cli.conversation_history == [{"role": "user", "content": "compressed"}]
            assert db.get_session("session")["system_prompt"] == prompt


def test_resume_keeps_all_text_and_history_command_is_removed():
    from sci_cli.cli_agent_setup_mixin import _collect_resume_entries
    from cli import SciCLI, _strip_reasoning_tags
    from sci_cli.commands import resolve_command, COMMANDS
    import copy
    rows = []
    for n in range(30):
        rows.extend([{"role": "user", "content": f"Question {n} " + "long " * 200},
                     {"role": "assistant", "content": f"Answer {n}\n" + "long answer\n" * 100}])
    rows.append({"role": "assistant", "content": "<think>private thought</think>Visible answer"})
    snapshot = copy.deepcopy(rows)
    entries = _collect_resume_entries(rows, _strip_reasoning_tags)
    assert len(entries) == len(rows)
    assert entries[0][1] == rows[0]["content"]
    assert entries[-2][1] == _strip_reasoning_tags(rows[-2]["content"])
    assert "private thought" not in str(entries) and rows == snapshot
    assert resolve_command("history") is None and "/history" not in COMMANDS
    assert SciCLI._slash_handler("history") is None


def test_picker_paginates_searches_and_switch_refuses_failed_flush(tmp_path, monkeypatch):
    from sci_cli.session_browser import flush_before_switch
    from sci_cli.session_picker import SessionPicker
    from sci_state import SessionDB
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / ".sci"))
    with SessionDB(tmp_path / "state.db") as db:
        for i in range(18):
            db.create_session(f"s-{i}", source="cli")
            db.set_session_title(f"s-{i}", f"Conversation {i}")
            db.append_message(f"s-{i}", "user", "fixture")
        cli = SimpleNamespace(_session_db=db, session_id="current")
        picker = SessionPicker(cli)
        picker.limit = 8
        picker.refresh()
        assert len(picker.rows) == 8 and picker.more
        picker.move(8)
        assert picker.selected == 8 and len(picker.rows) > 8
        picker.search.text = "Conversation 17"
        assert [row["id"] for row in picker.rows] == ["s-17"]
        cli.agent = SimpleNamespace(_flush_messages_to_session_db=Mock(side_effect=OSError("disk failure")))
        cli.conversation_history = [{"role": "user", "content": "unsaved"}]
        with pytest.raises(OSError):
            flush_before_switch(cli)
        assert cli.session_id == "current"
