"""Worker branding uses the viewer's terminal capabilities, never the daemon's."""

import json
import os
from pathlib import Path
import re
import time

import pytest


@pytest.mark.platforms("posix")
def test_worker_logo_colors_follow_each_terminal_without_profile_or_env_leaks(tmp_path, monkeypatch):
    from sci_cli.background_chat_service import ChatService
    from sci_cli import _launchers

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "main"))
    monkeypatch.setenv("TERM", "dumb")
    monkeypatch.setenv("NO_COLOR", "1")
    original_command = _launchers.runtime_command
    render = """
import json
from rich.console import Console
from sci_constants import get_sci_home
from sci_cli.banner import _agentic_sciences_logo
console = Console()
print('DISPLAY_INFO:' + json.dumps({'home': str(get_sci_home()), 'color': console.color_system, 'no_color': console.no_color}), flush=True)
console.print(_agentic_sciences_logo(100))
print('RENDER_COMPLETE', flush=True)
"""

    def render_command(root, args, **kwargs):
        return original_command(root, code=render, **kwargs)

    monkeypatch.setattr(_launchers, "runtime_command", render_command)
    for name, no_color in (("a", False), ("b", True), ("a", False)):
        home = tmp_path / name
        home.mkdir(exist_ok=True)
        terminal_env = {"TERM": "xterm-256color", "COLORTERM": "truecolor"}
        if no_color:
            terminal_env["NO_COLOR"] = "1"
        worker = ChatService(home)._spawn(None, str(tmp_path), 100, 35, terminal_env=terminal_env)
        output = bytearray()
        try:
            deadline = time.monotonic() + 30
            while b"RENDER_COMPLETE" not in output and time.monotonic() < deadline:
                data = worker.read(0.2)
                if data is None:
                    break
                output.extend(data)
            assert b"RENDER_COMPLETE" in output, output.decode(errors="replace")
            info = json.loads(next(line.partition(b"DISPLAY_INFO:")[2]
                                   for line in output.splitlines() if b"DISPLAY_INFO:" in line))
            assert info == {"home": str(home), "color": "truecolor", "no_color": no_color}
            assert bool(re.search(rb"\x1b\[[0-9;]*(?:38|48);2;", output)) is not no_color
        finally:
            worker.close()
    assert os.environ["TERM"] == "dumb" and os.environ["NO_COLOR"] == "1"


@pytest.mark.asyncio
async def test_terminal_metadata_cannot_override_credentials_or_execution_env(tmp_path, monkeypatch):
    from sci_cli.background_chat_service import ChatService
    from sci_cli.background_chats import terminal_environment
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("SCI_HOME", str(tmp_path / "main"))
    monkeypatch.setenv("OPENAI_API_KEY", "fixture-secret")
    assert "OPENAI_API_KEY" not in terminal_environment()

    def forbidden_spawn(*args, **kwargs):
        pytest.fail("Invalid terminal metadata reached process launch")

    service = ChatService(tmp_path / "a", worker_factory=forbidden_spawn)
    for values in ({"OPENAI_API_KEY": "fixture"}, {"PYTHONPATH": "/tmp/other"},
                   {"TERM": "bad\x00value"}, {"NO_COLOR": True}):
        with pytest.raises(ValueError, match="terminal display environment"):
            await service.start({"cwd": str(tmp_path), "terminal_env": values})
