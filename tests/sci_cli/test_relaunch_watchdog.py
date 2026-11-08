"""A waiting Windows CLI launcher must outlive its completed cleanup timers."""

import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]


def run_parent(tmp_path, body):
    home = tmp_path / "profile"
    home.mkdir()
    env = dict(os.environ, SCI_HOME=str(home), SCI_EXIT_WATCHDOG_S="0.5")
    env.pop("PYTEST_CURRENT_TEST", None)
    source = f"""
import sys, time, subprocess, logging
sys.path.insert(0, {str(ROOT)!r})
import cli
from sci_cli.cli_shutdown import logger
logger.handlers = [logging.StreamHandler()]
logger.propagate = False
logger.setLevel(logging.WARNING)
cli._arm_exit_watchdog_on_shutdown_signal()
cli._arm_exit_watchdog()
{body}
print('HANDOFF_RETURNED', flush=True)
# A fresh watchdog must still bound interpreter teardown after the child exits.
time.sleep(15)
raise SystemExit('shutdown watchdog was not restored')
"""
    result = subprocess.run([sys.executable, "-c", source], env=env,
                            capture_output=True, text=True, encoding="utf-8", timeout=45)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "HANDOFF_RETURNED" in result.stdout, result.stdout + result.stderr
    assert result.stderr.count("Exit watchdog fired") == 1, result.stderr
    return result


@pytest.mark.parametrize("failed_start", [False, True])
def test_wait_suspends_old_watchdogs_and_restores_shutdown_protection(tmp_path, failed_start):
    body = """
from sci_cli.cli_shutdown import pause_exit_watchdogs_for_relaunch
with pause_exit_watchdogs_for_relaunch():
    subprocess.run([sys.executable, '-c', 'import time; time.sleep(2.5)'], check=True)
"""
    if failed_start:
        body = """
from sci_cli.cli_shutdown import pause_exit_watchdogs_for_relaunch
try:
    with pause_exit_watchdogs_for_relaunch():
        raise OSError('controlled child-start failure')
except OSError:
    pass
"""
    run_parent(tmp_path, body)


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("route", ["profile", "relaunch"])
def test_windows_real_handoff_waits_and_preserves_child_exit_code(tmp_path, route):
    # Native Windows execution, with real child processes and real watchdogs.
    # Only the child command is substituted; no profile/model services run.
    body = """
child = [sys.executable, '-c', 'import time; time.sleep(2.5); raise SystemExit(37)']
try:
"""
    if route == "profile":
        body += """
    from types import SimpleNamespace
    from sci_constants import get_sci_home
    from sci_cli import _launchers, native_profile_session
    _launchers.runtime_command = lambda *args, **kwargs: child
    native_profile_session.relaunch_profile(SimpleNamespace(
        _pending_profile_home=str(get_sci_home()), _pending_relaunch=[]))
"""
    else:
        body += """
    from sci_cli import relaunch
    relaunch.build_relaunch_argv = lambda *args, **kwargs: child
    relaunch.relaunch([])
"""
    body += """
except SystemExit as exc:
    assert exc.code == 37, exc.code
    print('CHILD_EXIT_37', flush=True)
"""
    result = run_parent(tmp_path, body)
    assert "CHILD_EXIT_37" in result.stdout
