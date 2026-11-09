"""File targets survive the real Markdown → Rich → prompt_toolkit output path."""

from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from prompt_toolkit.data_structures import Size
from prompt_toolkit.formatted_text import to_formatted_text
from prompt_toolkit.output.vt100 import Vt100_Output
from prompt_toolkit.renderer import print_formatted_text
from prompt_toolkit.styles import Style
from prompt_toolkit.widgets import TextArea
from rich.console import Console
from rich.text import Text


@pytest.mark.parametrize("message,target", [
    (r"[result](<C:\Users\Scientist\.sci\My Results\résult #1.csv>)",
     "file:///C:/Users/Scientist/.sci/My%20Results/r%C3%A9sult%20%231.csv"),
    (r"`D:\My Results\résult #1.csv`", "file:///D:/My%20Results/r%C3%A9sult%20%231.csv"),
    (r"`\\server\share\résult 1.csv`", "file://server/share/r%C3%A9sult%201.csv"),
    ("[result](file://server/share/result%201.csv)", "file://server/share/result%201.csv"),
    ("[result](file:///C:/My%20Results/result.csv)", "file:///C:/My%20Results/result.csv"),
    ("[result](</tmp/My Results/result.csv>)", "file:///tmp/My%20Results/result.csv"),
    ("/tmp/results/result.csv", "file:///tmp/results/result.csv"),
    ("[service](https://example.test/results?q=1)", "https://example.test/results?q=1"),
])
def test_links_survive_live_output_replay_and_side_view(monkeypatch, tmp_path, message, target):
    import cli
    from sci_cli.side_view import SideView, _TranscriptLexer

    monkeypatch.setenv("SCI_HOME", str(tmp_path))
    stream = StringIO()
    output = Vt100_Output(stream, lambda: Size(rows=30, columns=80), term="xterm", enable_cpr=False)
    monkeypatch.setattr(cli, "_pt_print", lambda value: print_formatted_text(output, value, Style([])))
    cli._configure_output_history(True, 100)
    try:
        renderable = cli._render_final_assistant_content(message)
        reference = StringIO()
        Console(file=reference, width=cli.ChatConsole().width, color_system=None).print(renderable)
        cli.ChatConsole().print(renderable)
        assert f"\x1b]8;;{target}\x1b\\" in stream.getvalue()
        assert Text.from_ansi(stream.getvalue()).plain.strip() == Text.from_ansi(reference.getvalue()).plain.strip()
        from sci_cli.cli_render import _line_rows
        for line in cli._OUTPUT_HISTORY:
            assert _line_rows(line, 80) == max(1, (Text.from_ansi(line).cell_len + 79) // 80)
        stream.seek(0)
        stream.truncate()
        cli._replay_output_history()
        assert f"\x1b]8;;{target}\x1b\\" in stream.getvalue()

        view = SideView.__new__(SideView)
        view.cli = SimpleNamespace(_app=SimpleNamespace(loop=None, invalidate=Mock()))
        view._ansi = ""
        view.follow = True
        view.lexer = _TranscriptLexer()
        view.transcript = TextArea()
        for line in cli._OUTPUT_HISTORY:
            view.append(line)
        assert "\x1b" not in view.transcript.text
        assert any(target in body for line in view.lexer.lines for style, body in line if "ZeroWidthEscape" in style)
    finally:
        cli._configure_output_history(False, 100)


def test_only_valid_hyperlinks_reach_terminal_and_paths_stay_literal():
    from sci_cli.terminal_links import TerminalANSI, file_link_uri, terminal_markdown

    close = "\x1b]8;;\x1b\\"
    content = ("\x1b]52;c;clipboard-data\x07\x1b]0;title\x07"
               "\x1b]8;;javascript:alert(1)\x07bad" + close +
               "\x01\x1b]52;c;injected\x07\x02"
               "\x1b]8;;https://example.test/%1b%5d52\x07bad" + close +
               "\x1b]8;;file:///C:/result.csv\x07result")
    fragments = to_formatted_text(TerminalANSI(content))
    escapes = "".join(body for style, body in fragments if "ZeroWidthEscape" in style)
    assert "file:///C:/result.csv" in escapes and escapes.endswith(close)
    assert "javascript" not in escapes and "]52;" not in escapes and "]0;" not in escapes
    assert "%1b" not in escapes
    assert "".join(body for style, body in fragments if "ZeroWidthEscape" not in style) == "badbadresult"
    assert file_link_uri("C:\\bad\x1b.csv") is None
    assert file_link_uri(r"\\.\COM1") is None
    assert file_link_uri("relative/result.csv") is None
    for source in ("/help", "```\nC:\\results\\file.csv\n```", "`relative/file.csv`"):
        parsed = terminal_markdown(source).parsed
        assert not any(t.type == "link_open" for block in parsed for t in (block.children or []))
