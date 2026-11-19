"""Non-streaming quiet chat must show assistant content before a question."""
from io import StringIO
from types import SimpleNamespace

import pytest
from rich.console import Console


def test_recipe_context_is_displayed_with_tool_progress_and_reasoning_off(monkeypatch):
    import cli as module
    from cli import SciCLI
    from run_agent import AIAgent
    from tools.clarify_tool import clarify_tool

    output = StringIO()
    console = Console(file=output, width=90, color_system=None)
    monkeypatch.setattr(module, 'ChatConsole', lambda: console)
    monkeypatch.setattr(module, 'CLI_CONFIG', {'display': {'tool_progress': 'off', 'show_reasoning': False}})
    view = SciCLI.__new__(SciCLI)
    view.final_response_markdown = 'raw'
    view._scrollback_box_width = lambda: 90
    view.agent = SimpleNamespace(suppress_status_output=False)
    agent = AIAgent.__new__(AIAgent)
    agent.interim_assistant_callback = view._on_interim_assistant_message
    agent._enqueue_stream_hook = lambda *a, **k: None
    agent._current_streamed_assistant_text = ''
    agent.show_commentary = True
    text = 'Recipe A — 500 g\nTebuconazole technical: 21.0526%, 105.263 g\nWater and excipients: balance.'
    agent._emit_interim_assistant_message({'role': 'assistant', 'content': text})

    def question(entries):
        assert '105.263 g' in output.getvalue()
        return {'answers': {entries[0]['qid']: 'Design'}, 'outcome': 'submitted'}

    clarify_tool([{'question': 'Choose the next mode', 'choices': ['Design', 'AI + Physics Design']}], callback=question)
    assert 'Recipe A' in output.getvalue()
    agent._emit_interim_assistant_message({'role': 'assistant', 'content': text})
    assert output.getvalue().count('Recipe A') == 1


@pytest.mark.parametrize('already_streamed,hidden,machine', [(True, False, False), (False, True, False), (False, False, True)])
def test_streamed_opted_out_or_machine_output_is_not_printed(monkeypatch, already_streamed, hidden, machine):
    import cli as module
    from cli import SciCLI
    output = StringIO()
    monkeypatch.setattr(module, 'ChatConsole', lambda: Console(file=output))
    monkeypatch.setattr(module, 'CLI_CONFIG', {'display': {'interim_assistant_messages': not hidden}})
    view = SciCLI.__new__(SciCLI)
    view.final_response_markdown = 'raw'
    view._scrollback_box_width = lambda: 90
    view.agent = SimpleNamespace(suppress_status_output=machine)
    view._on_interim_assistant_message('Already displayed context', already_streamed=already_streamed)
    assert output.getvalue() == ''


def test_quiet_display_does_not_print_preparing_tool_lines(monkeypatch):
    import cli as module
    from cli import SciCLI
    output = []
    monkeypatch.setattr(module, '_cprint', lambda *a, **kw: output.append(a))
    view = SciCLI.__new__(SciCLI)
    view.tool_progress_mode = 'off'
    view._on_tool_gen_start('clarify')
    view._on_tool_gen_start('terminal')
    assert output == []


def test_quiet_tool_lifecycle_keeps_backend_paths_out_of_spinner():
    from cli import SciCLI
    view = SciCLI.__new__(SciCLI)
    view.tool_progress_mode = 'off'
    view._spinner_text = 'Working'
    view._pending_tool_info = {}
    view._invalidate = lambda: None
    view._turn_summary_record = lambda *args: None
    view._on_tool_progress('tool.started', 'terminal',
                           preview='python /private/source_file.py',
                           function_args={'command': 'python /private/source_file.py'})
    assert view._spinner_text == 'Working'
    assert view._pending_tool_info == {}
    view._on_tool_progress('tool.completed', 'terminal')
    assert view._spinner_text == 'Working'


def test_quiet_generation_flushes_assistant_content_without_tool_label(monkeypatch):
    import cli as module
    from cli import SciCLI
    printed = []
    flushed = []
    monkeypatch.setattr(module, '_cprint', lambda *args: printed.append(args))
    view = SciCLI.__new__(SciCLI)
    view.tool_progress_mode = 'off'
    view._stream_box_opened = True
    view._flush_stream = lambda: flushed.append(True)
    view._on_tool_gen_start('clarify')
    assert flushed == [True]
    assert printed == []
    assert view._stream_box_opened is False


def test_question_flushes_pending_content_before_paint_even_without_tool_generation():
    from cli import SciCLI
    events = []
    view = SciCLI.__new__(SciCLI)
    view._stream_box_opened = True
    view._flush_stream = lambda: events.append('content')
    view._clarify_batch_set_active = lambda *args: None
    view._ring_bell = lambda **kwargs: None
    view._paint_now = lambda: events.append('question')
    view._poll_modal_queue = lambda *args: None
    response = view._clarify_callback([{'question': 'Choose a mode', 'qid': 'q1'}])
    assert events == ['content', 'question']
    assert response['outcome'] == 'cancelled'


def test_question_waits_for_queued_rows_and_async_terminal_paint(monkeypatch):
    import asyncio
    import threading
    from cli import SciCLI
    import sci_cli.cli_render as rendering
    monkeypatch.setattr(rendering, '_HELD_PAINTS', None)
    events = []
    loop = asyncio.new_event_loop()
    ready = threading.Event()
    def run_loop():
        asyncio.set_event_loop(loop)
        loop.call_soon(ready.set)
        loop.run_forever()
    thread = threading.Thread(target=run_loop)
    thread.start()
    assert ready.wait(3)
    app = SimpleNamespace(loop=loop, _is_running=True, _running_in_terminal_f=None)
    async def paint_rows():
        app._running_in_terminal_f = loop.create_future()
        await asyncio.sleep(.03)
        events.extend(['Recipe A', 'Recipe B', 'Total'])
        app._running_in_terminal_f.set_result(None)
    def flush_rows():
        loop.call_soon_threadsafe(lambda: events.append('Ingredients'))
        loop.call_soon_threadsafe(lambda: loop.create_task(paint_rows()))
    view = SciCLI.__new__(SciCLI)
    view._app = app
    view._stream_box_opened = True
    view._flush_stream = flush_rows
    view._clarify_batch_set_active = lambda *args: None
    view._ring_bell = lambda **kwargs: None
    view._paint_now = lambda: events.append('Question')
    view._poll_modal_queue = lambda *args: None
    try:
        view._clarify_callback([{'question': 'Choose a mode', 'qid': 'q1'}])
        assert events == ['Ingredients', 'Recipe A', 'Recipe B', 'Total', 'Question']
    finally:
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=3)
        loop.close()


def test_unavailable_output_cancels_question_instead_of_hiding_its_context(monkeypatch):
    from cli import SciCLI
    import sci_cli.cli_render as rendering
    monkeypatch.setattr(rendering, '_wait_for_pending_paints', lambda app: False)
    view = SciCLI.__new__(SciCLI)
    view._paint_now = lambda: pytest.fail('Question opened before its context was visible')
    result = view._clarify_callback([{'question': 'Choose a mode', 'qid': 'q1'}])
    assert result == {'answers': {}, 'outcome': 'cancelled'}
    assert not hasattr(view, '_clarify_state')
