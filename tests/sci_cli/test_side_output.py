"""Raw tool writes stay with side, including late output after cancellation."""

import io
import sys
from threading import Event, Thread
from types import SimpleNamespace


def test_fragmented_tool_output_and_late_cancelled_worker_never_reach_main(monkeypatch):
    from sci_cli import side_commands
    from sci_cli.side_surface import tool_output_scope
    from tools.thread_context import propagate_context_to_thread

    main = io.StringIO()
    monkeypatch.setattr(sys, 'stdout', main)
    monkeypatch.setattr(sys, 'stderr', main)
    shown = []
    monkeypatch.setattr(side_commands, '_show', lambda cli, text: shown.append(text))
    controller = object.__new__(side_commands.SideController)
    controller.cli = object()
    controller.conversation = SimpleNamespace(closed=Event())
    entered, release = Event(), Event()

    def tool():
        print('poll', end='')
        print('ing')
        print('downloaded', file=sys.stderr)
        entered.set()
        assert release.wait(10)
        print('late output after close', flush=True)

    thread = None
    try:
        with tool_output_scope(controller.emit):
            thread = Thread(target=propagate_context_to_thread(tool))
            thread.start()
            assert entered.wait(10)
            print('unterminated', end='')
        assert shown == ['polling', 'downloaded', 'unterminated']
        controller.conversation.closed.set()
        print('main still works')
        release.set()
        thread.join(10)
        assert not thread.is_alive()
        assert shown == ['polling', 'downloaded', 'unterminated']
        assert main.getvalue() == 'main still works\n'
    finally:
        release.set()
        if thread is not None:
            thread.join(10)
