"""Native Windows dashboard update recovery; no production processes are stopped."""

import sys
import time

import psutil
import pytest

from sci_cli import dashboard_procs, main_dashboard


@pytest.mark.platforms('windows')
def test_update_captures_windows_dashboard_argv_before_stop(tmp_path, monkeypatch):
    monkeypatch.setenv('SCI_HOME', str(tmp_path / '.sci'))
    command = [sys.executable, '-m', 'sci_cli.main', 'dashboard', '--port', '17403']
    monkeypatch.setattr(main_dashboard, '_restart_managed_dashboard_service', lambda _: False)
    monkeypatch.setattr(main_dashboard, '_find_stale_dashboard_pids', lambda **_: [12345])
    monkeypatch.setattr(main_dashboard, '_dashboard_cmdline_for_pid', lambda _: command)
    monkeypatch.setattr(dashboard_procs, '_exclude_pids_from_env', lambda: set())
    monkeypatch.setattr(dashboard_procs, '_lock_owned_serve_pids', lambda: set())
    monkeypatch.setattr(dashboard_procs, '_sci_home_for_pid', lambda _: str(tmp_path / '.sci'))
    monkeypatch.setattr(dashboard_procs, '_kill_pids_windows', lambda pids, killed, failed: killed.extend(pids))
    recovered = []
    monkeypatch.setattr(main_dashboard, '_respawn_dashboard_processes', lambda commands: recovered.extend(commands) or [])
    result = dashboard_procs._kill_stale_dashboard_processes(restart_managed=True)
    assert recovered == [command]
    assert result['unrecovered'] == []


@pytest.mark.platforms('windows')
def test_respawn_starts_real_windows_child_with_exact_paths(tmp_path, monkeypatch):
    monkeypatch.setenv('SCI_HOME', str(tmp_path / '.sci'))
    monkeypatch.setattr(main_dashboard, '_RESPAWN_LIVENESS_GRACE_SECONDS', 2.0)
    child = tmp_path / 'child script.py'
    ready = tmp_path / 'ready.pid'
    child.write_text('import os, pathlib, sys, time\npathlib.Path(sys.argv[1]).write_text(str(os.getpid()))\ntime.sleep(60)\n')
    command = [sys.executable, str(child), str(ready)]
    proc = None
    try:
        assert main_dashboard._respawn_dashboard_processes([command]) == []
        deadline = time.monotonic() + 10
        while not ready.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert ready.exists()
        proc = psutil.Process(int(ready.read_text()))
        assert proc.is_running()
        assert main_dashboard._dashboard_cmdline_for_pid(proc.pid) == proc.cmdline()
        assert str(child) in proc.cmdline()
    finally:
        if proc is not None:
            proc.terminate()
            proc.wait(timeout=10)
