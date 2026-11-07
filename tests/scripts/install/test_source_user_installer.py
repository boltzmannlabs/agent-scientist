"""The user wrapper quotes its checkout, propagates failures, and skips login unattended."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.platforms("posix")
@pytest.mark.parametrize("failure", [0, 23])
def test_user_installer_order_and_failure(tmp_path, failure):
    source = tmp_path / "checkout with spaces"
    (source / "pm").mkdir(parents=True)
    shutil.copy2(ROOT / "install-sci.sh", source / "install-sci.sh")
    (source / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/source-install-preflight.sh", source / "scripts/source-install-preflight.sh")
    for name in ("pyproject.toml", "uv.lock", "pm/lock.json"):
        (source / name).touch()
    log = tmp_path / "calls"
    (source / "setup-sci.sh").write_text(
        '#!/usr/bin/env bash\nset -e\nprintf "setup:%s\\n" "$*" >> "$CALL_LOG"\n'
        'if [ "$SETUP_FAILURE" != 0 ]; then exit "$SETUP_FAILURE"; fi\n'
        'mkdir -p "$(dirname "$0")/.sci/bin"\n'
        'cp "$FIXTURE_CLI" "$(dirname "$0")/.sci/bin/sci"\n'
        'chmod +x "$(dirname "$0")/.sci/bin/sci"\n')
    cli = tmp_path / "fixture-cli"
    cli.write_text('#!/usr/bin/env bash\nprintf "cli:%s\\n" "$*" >> "$CALL_LOG"\nif [ "$1" = --run-module ]; then exit 3; fi\n')
    env = {**os.environ, "CALL_LOG": str(log), "FIXTURE_CLI": str(cli),
           "SETUP_FAILURE": str(failure), "HOME": str(tmp_path)}
    result = subprocess.run(["bash", str(source / "install-sci.sh"), "--non-interactive"],
                            env=env, text=True, capture_output=True, timeout=20)
    assert result.returncode == failure
    calls = log.read_text().splitlines()
    assert calls[0] == "setup:--user-install --non-interactive"
    if failure:
        assert calls == ["setup:--user-install --non-interactive"]
        assert "stopped during installing runtime and dependencies" in result.stderr
        assert "is installed" not in result.stdout
    else:
        assert calls == ["setup:--user-install --non-interactive", "cli:--help", "cli:--run-module sci_cli.install_status"]
        assert "Agent Scientist is installed" in result.stdout
        assert "sci setup" in result.stdout


@pytest.mark.platforms("posix")
def test_unknown_option_stops_before_setup():
    result = subprocess.run(["bash", str(ROOT / "install-sci.sh"), "--invalid"],
                            text=True, capture_output=True, timeout=10)
    assert result.returncode == 2 and "Unknown option" in result.stderr


@pytest.mark.platforms('posix')
@pytest.mark.parametrize('mode', ['existing', 'configure', 'cancel', 'status-error'])
def test_interactive_completion_launches_only_with_configuration(tmp_path, mode):
    import pty

    source = tmp_path / 'source'
    (source / 'pm').mkdir(parents=True)
    (source / 'scripts').mkdir()
    shutil.copy2(ROOT / 'install-sci.sh', source / 'install-sci.sh')
    shutil.copy2(ROOT / 'scripts/source-install-preflight.sh', source / 'scripts/source-install-preflight.sh')
    for name in ('pyproject.toml', 'uv.lock', 'pm/lock.json'):
        (source / name).touch()
    (source / 'setup-sci.sh').write_text('#!/bin/bash\nexit 0\n')
    local = source / '.sci/bin'
    local.mkdir(parents=True)
    (local / 'sci').write_text(
        '#!/bin/bash\nprintf "%s\\n" "$*" >> "$CALL_LOG"\n'
        'case "$1" in\n'
        '  --help) exit 0 ;;\n'
        '  --run-module) if [ "$MODE" = status-error ]; then exit 19; fi; '
        'if [ -f "$READY" ]; then exit 0; else exit 3; fi ;;\n'
        '  setup) if [ "$MODE" = configure ]; then touch "$READY"; fi ;;\n'
        '  "") touch "$LAUNCHED" ;;\nesac\n')
    (local / 'sci').chmod(0o755)
    ready = tmp_path / 'ready'
    if mode == 'existing':
        ready.touch()
    log, launched = tmp_path / 'calls', tmp_path / 'launched'
    env = {**os.environ, 'HOME': str(tmp_path), 'MODE': mode, 'READY': str(ready),
           'CALL_LOG': str(log), 'LAUNCHED': str(launched)}
    master, slave = pty.openpty()
    try:
        child = subprocess.Popen(['/bin/bash', str(source / 'install-sci.sh')],
                                 env=env, stdin=slave, stdout=slave, stderr=slave)
        code = child.wait(timeout=15)
        os.close(slave)
        slave = None
        chunks = []
        while True:
            try:
                block = os.read(master, 65536)
            except OSError:
                break
            if not block:
                break
            chunks.append(block)
        output = b''.join(chunks).decode()
    finally:
        os.close(master)
        if slave is not None:
            os.close(slave)
    calls = log.read_text().splitlines()
    assert ('setup' in calls) == (mode in {'configure', 'cancel'})
    assert launched.exists() == (mode in {'existing', 'configure'})
    if mode == 'status-error':
        assert code == 19 and 'is installed' not in output
    else:
        assert code == 0 and 'Agent Scientist is installed' in output
        assert ('Model setup is incomplete' in output) == (mode == 'cancel')
