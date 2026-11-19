"""Profile handoffs must survive sticky defaults and CLI entry-point imports."""

import json
import os
from pathlib import Path
import subprocess
import sys


def test_main_handoff_keeps_explicit_profile_after_entrypoint_reimport(tmp_path, monkeypatch):
    from sci_cli._launchers import runtime_command

    root = Path(__file__).resolve().parents[2]
    home = tmp_path / ".sci"
    other = home / "profiles" / "other"
    other.mkdir(parents=True)
    (home / "config.yaml").write_text("{}\n")
    (other / "config.yaml").write_text("{}\n")
    (home / "active_profile").write_text("other")
    monkeypatch.setenv("SCI_DISABLE_LAZY_INSTALLS", "1")
    code = """
import json, os, runpy
try:
    runpy.run_module('sci_cli.main', run_name='__main__', alter_sys=True)
except SystemExit as exc:
    assert exc.code == 0
from sci_cli import main
from sci_constants import get_sci_home
print('HANDOFF:' + json.dumps({'home': str(get_sci_home()), 'explicit': main.explicit_cli_profile()}))
"""
    for name, target in (("other", other), ("default", home), ("other", other)):
        command = runtime_command(root, ["--cli", "-p", name, "--help"],
                                  python=sys.executable, home=target, code=code)
        result = subprocess.run(command, cwd=tmp_path,
                                env={**os.environ, "HOME": str(tmp_path), "SCI_HOME": str(target)},
                                capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        record = json.loads(next(line.removeprefix("HANDOFF:") for line in result.stdout.splitlines()
                                 if line.startswith("HANDOFF:")))
        assert record == {"home": str(target), "explicit": name}
    assert (home / "active_profile").read_text() == "other"


def test_background_workers_keep_owning_profile_with_different_sticky_default(tmp_path, monkeypatch):
    from sci_cli.background_chat_service import ChatService, PtyBridge
    from sci_state import SessionDB

    home = tmp_path / ".sci"
    other = home / "profiles" / "other"
    other.mkdir(parents=True)
    for target in (home, other):
        (target / "config.yaml").write_text("{}\n")
        with SessionDB(target / "state.db") as db:
            db.create_session(target.name, "cli")
    (home / "active_profile").write_text("other")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("SCI_HOME", str(home))
    monkeypatch.setenv("SCI_DISABLE_LAZY_INSTALLS", "1")
    results = []

    def spawn(command, *, cwd, env, **kwargs):
        # Run the exact worker bootstrap/argv, stopping after startup parsing.
        # --help avoids all model requests; a subsequent import checks resume scope.
        probe = """
import json, sys
from pathlib import Path
try:
    exec(sys.argv.pop(1))
except SystemExit as exc:
    assert exc.code == 0
from sci_cli import main
from sci_constants import get_sci_home
from sci_state import SessionDB
home = get_sci_home()
session = sys.argv[sys.argv.index('--resume') + 1]
with SessionDB(home / 'state.db', read_only=True) as db:
    found = db.get_session(session) is not None
print('WORKER:' + json.dumps({'home': str(home), 'found': found}))
"""
        # runtime_command emits Python -I -c bootstrap followed by CLI arguments.
        result = subprocess.run([*command[:2], "-c", probe, command[3], *command[4:], "--help"],
                                cwd=cwd, env={**env, "SCI_STATE_DB_GUARD_BYPASS": "1"},
                                capture_output=True, text=True, timeout=45)
        assert result.returncode == 0, result.stdout + result.stderr
        results.append(json.loads(next(line.removeprefix("WORKER:") for line in result.stdout.splitlines()
                                       if line.startswith("WORKER:"))))

    monkeypatch.setattr(PtyBridge, "spawn", spawn)
    for target in (home, other, home):
        ChatService(target)._spawn(target.name, str(tmp_path), 80, 24)
        assert results[-1] == {"home": str(target), "found": True}
