"""Retained replies use the same presentation as new replies without replaying tools."""

from io import StringIO
from types import SimpleNamespace

from rich.console import Console


def test_resume_and_live_reply_share_presentation(monkeypatch):
    from sci_cli.cli_chat_turn_mixin import CLIChatTurnMixin
    from sci_cli.cli_status_bar_mixin import CLIStatusBarMixin
    from sci_cli.resume_transcript import render_transcript

    live, replay = [], []
    monkeypatch.setattr('cli.ChatConsole', lambda: SimpleNamespace(print=live.append))
    monkeypatch.setattr('cli._record_output_history_entry', lambda _: None)
    monkeypatch.setattr(CLIStatusBarMixin, '_scrollback_box_width', staticmethod(lambda: 80))
    cli = SimpleNamespace(
        final_response_markdown='render', _last_turn_interrupted=False,
        _streamed_text_this_turn='', _stream_started=False, _stream_box_opened=False,
        _scrollback_box_width=lambda: 80, _console_print=replay.append)
    response = 'A **retained** reply.\n\n- first point\n- second point'
    turn = SimpleNamespace(result={}, use_streaming_tts=False, box_opened=False)
    CLIChatTurnMixin._chat_print_response_panel(cli, turn, response)
    render_transcript(cli, [('user', 'question'), ('tool', 'hidden tool details'), ('assistant', response)])

    def rendered(item):
        output = StringIO()
        Console(file=output, width=80).print(item)
        return output.getvalue()

    assert rendered(live[0]) == rendered(replay[1])
    assert '● question' in rendered(replay[0])
    # The accent belongs to the bullet, not the Text object's inherited body style.
    segments = list(Console(width=80).render(replay[0]))
    body = next(segment for segment in segments if segment.text == 'question')
    bullet = next(segment for segment in segments if segment.text == '● ')
    assert body.style.color is None
    assert bullet.style.color is not None
    assert 'You:' not in rendered(replay[0])
    assert '◆ Sci' not in rendered(replay[1])
    assert all('hidden tool details' not in rendered(item) for item in replay)
