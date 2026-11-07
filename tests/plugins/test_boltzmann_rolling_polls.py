"""Foreground status updates roll in place and never cross profile/chat boundaries."""

import asyncio
import importlib
import threading
from pathlib import Path
from types import SimpleNamespace

from prompt_toolkit.application import Application
from prompt_toolkit.data_structures import Size
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.layout import HSplit, Layout
from prompt_toolkit.output import DummyOutput
from prompt_toolkit.widgets import TextArea

from agent.secret_scope import reset_multiplex_context, set_multiplex_context
from gateway.session_context import scoped_current_session_id
from sci_cli.native_profile_creation import profile_scope
from sci_cli.plugins import get_plugin_manager
from sci_cli.plugins_manifest import parse_manifest_file
from sci_cli.cli_subagent_monitor import install_dock


def test_live_poll_window_replaces_old_rows_and_clears_on_completion(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    a, b = tmp_path / "a", tmp_path / "b"
    a.mkdir()
    b.mkdir()
    monkeypatch.setenv("SCI_HOME", str(a))
    token = set_multiplex_context(True)
    root = Path(__file__).resolve().parents[2] / "plugins/boltzmann"

    def load():
        manager = get_plugin_manager()
        manager._load_plugin(parse_manifest_file(root / "plugin.yaml", root, "bundled", ""))
        plugin = manager._plugins["boltzmann"]
        assert not plugin.error
        return plugin.module, importlib.import_module(plugin.module.__name__ + ".nodeapi_helpers")

    def surface():
        cli = SimpleNamespace(session_id="owner", agent=None)
        install_dock(cli)
        return cli

    try:
        with profile_scope(b):
            load()
            other_profile = surface()
        with profile_scope(a):
            plugin, helpers = load()
            owner = surface()
            foreign = surface()
            foreign.session_id = "other-chat"
            clock, count = [0.0], [0]
            ready, release = threading.Event(), threading.Event()

            def get(url, **kwargs):
                assert kwargs["json"] == {"docId": "fixture-job", "job_name": "fixture"}
                count[0] += 1
                status = f"check-{count[0]:02d}" if count[0] <= 8 else "success"
                return SimpleNamespace(status_code=200, json=lambda: {"status": status})

            def pause(*args):
                clock[0] += 3600
                ready.set()
                assert release.wait(10), "The UI did not consume a test poll"
                release.clear()

            monkeypatch.setattr(helpers.requests, "get", get)
            monkeypatch.setattr(helpers, "_poll_pause", pause)
            monkeypatch.setattr(helpers, "time", SimpleNamespace(monotonic=lambda: clock[0]))
            monkeypatch.setattr(helpers, "_log_platform_terminal", lambda *args: None)

            async def paint():
                editor = TextArea(height=1, multiline=False)
                output = DummyOutput()
                output.get_size = lambda: Size(rows=30, columns=140)
                with create_pipe_input() as pipe:
                    app = Application(layout=Layout(HSplit([owner._subagent_dock_widget, editor]), focused_element=editor),
                                      input=pipe, output=output)
                    painted = asyncio.Event()
                    app.after_render += lambda _: painted.set()
                    task = asyncio.create_task(app.run_async())
                    worker = None
                    try:
                        await asyncio.wait_for(painted.wait(), 5)
                        # The native plugin handler binds the caller's actual chat ID,
                        # even when an ambient session identity belongs to another chat.
                        worker = asyncio.create_task(asyncio.to_thread(
                            plugin._call, helpers.fetch_status,
                            {"collection_name": "fixture", "doc_id": "fixture-job",
                             "token": "fixture-key", "wait_until_terminal": True}, session_id="owner"))
                        for index in range(1, 9):
                            assert await asyncio.to_thread(ready.wait, 10)
                            ready.clear()
                            owner._subagent_monitor.refresh()
                            foreign._subagent_monitor.refresh()
                            with profile_scope(b):
                                other_profile._subagent_monitor.refresh()
                                # A's dock still resolves A when its ticker runs under B.
                                owner._subagent_monitor.refresh()
                            assert not foreign._subagent_monitor.jobs
                            assert not other_profile._subagent_monitor.jobs
                            painted.clear()
                            app.invalidate()
                            await asyncio.wait_for(painted.wait(), 5)
                            screen = app.renderer._last_screen
                            height = screen.visible_windows_to_write_positions[editor.window].ypos
                            text = "\n".join("".join(screen.data_buffer[y][x].char for x in range(140))
                                             for y in range(height))
                            assert "Background jobs" not in text
                            assert "Further polling updates hidden" not in text
                            assert text.count("[Boltzmann]") == min(index, 5)
                            for number in range(1, index + 1):
                                assert (f"check-{number:02d}" in text) is (number > index - 5)
                            assert app.layout.has_focus(editor)
                            release.set()
                        result = await asyncio.wait_for(worker, 10)
                        assert '"job_terminal_confirmed": true' in result
                        owner._subagent_monitor.refresh()
                        assert not owner._subagent_monitor.jobs
                    finally:
                        release.set()
                        if worker is not None and not worker.done():
                            await asyncio.wait_for(worker, 10)
                        app.exit()
                        await task
            with scoped_current_session_id("foreign-ambient-chat"):
                asyncio.run(paint())
            assert count[0] == 9
            output = capsys.readouterr()
            assert "[Boltzmann]" not in output.err + output.out
    finally:
        reset_multiplex_context(token)
