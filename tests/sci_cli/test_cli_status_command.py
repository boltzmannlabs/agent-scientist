"""Tests for CLI /status command behavior."""
from datetime import datetime
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rich.console import Console

from cli import SciCLI
from agent.i18n import t


def _make_cli():
    cli_obj = SciCLI.__new__(SciCLI)
    cli_obj.config = {}
    cli_obj.console = MagicMock()
    cli_obj.agent = None
    cli_obj.conversation_history = []
    cli_obj.session_id = "session-123"
    cli_obj._pending_input = MagicMock()
    cli_obj._status_bar_visible = True
    cli_obj.model = "openai/gpt-5.4"
    cli_obj.provider = "openai"
    cli_obj.session_start = datetime(2026, 4, 9, 19, 24)
    cli_obj._agent_running = False
    cli_obj._session_db = MagicMock()
    cli_obj._session_db.get_session.return_value = None
    return cli_obj








def test_process_command_egress_prints_proxy_status(monkeypatch):
    cli_obj = _make_cli()
    monkeypatch.setattr(
        "sci_cli.proxy_cli.format_status_text",
        lambda: "Egress proxy status\nEnabled: no",
    )

    assert cli_obj.process_command("/egress") is True

    cli_obj.console.print.assert_called()
    printed = "\n".join(str(call.args[0]) for call in cli_obj.console.print.call_args_list)
    assert "Egress proxy status" in printed




def test_status_prefix_prefers_status_command_over_statusbar_toggle():
    cli_obj = _make_cli()

    with patch.object(cli_obj, "_show_session_status") as mock_status:
        assert cli_obj.process_command("/sta") is True

    mock_status.assert_called_once_with()
    assert cli_obj._status_bar_visible is True


def test_show_session_status_prints_gateway_style_summary():
    cli_obj = _make_cli()
    cli_obj.agent = SimpleNamespace(
        session_total_tokens=321,
        session_api_calls=4,
    )
    cli_obj._session_db.get_session.return_value = {
        "title": "My titled session",
        "started_at": 1775791440,
    }

    with patch("sci_constants.display_sci_home", return_value="~/.sci"):
        cli_obj._show_session_status()

    stream = StringIO()
    console = Console(file=stream, width=120, color_system=None)
    for call in cli_obj.console.print.call_args_list:
        console.print(call.args[0])
    printed = stream.getvalue()
    assert t("cli.session.status_title") in printed
    rows = {}
    for line in printed.splitlines():
        cells = line.split("│")
        if len(cells) == 4:
            rows[cells[1].strip()] = cells[2].strip()
    assert rows["Session ID"] == "session-123"
    assert rows["Path"] == "~/.sci"
    assert rows["Title"] == "My titled session"
    assert rows["Model"] == "openai/gpt-5.4 (openai)"
    assert rows["Tokens"] == "321"
    assert rows["Agent Running"] == "No"
    _, kwargs = cli_obj.console.print.call_args
    assert kwargs.get("highlight") is False
    assert kwargs.get("markup") is False




def test_profile_command_reports_custom_root_profile(monkeypatch, tmp_path, capsys):
    """Profile detection works for custom-root deployments (not under ~/.sci)."""
    cli_obj = _make_cli()
    profile_home = tmp_path / "profiles" / "coder"

    monkeypatch.setenv("SCI_HOME", str(profile_home))
    monkeypatch.setattr(Path, "home", lambda: tmp_path / "unrelated-home")

    cli_obj._handle_profile_command()

    out = capsys.readouterr().out
    assert "Profile: coder" in out
    assert f"Home:    {profile_home}" in out
