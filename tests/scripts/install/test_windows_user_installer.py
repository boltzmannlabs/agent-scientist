"""The Windows user wrapper quotes its checkout, propagates failures, and skips login unattended."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _powershell_host() -> str:
    for name in ("pwsh", "powershell"):
        found = shutil.which(name)
        if found:
            return found
    pytest.fail("no PowerShell host on a Windows runner")


@pytest.mark.platforms("windows")
@pytest.mark.parametrize("failure", [0, 23])
def test_user_installer_order_and_failure(tmp_path, failure):
    source = tmp_path / "checkout with spaces"
    (source / "pm").mkdir(parents=True)
    shutil.copy2(ROOT / "install-sci.ps1", source / "install-sci.ps1")
    (source / "scripts").mkdir()
    shutil.copy2(ROOT / "scripts/source-install-preflight.ps1", source / "scripts/source-install-preflight.ps1")
    for name in ("pyproject.toml", "uv.lock", "pm/lock.json"):
        (source / name).touch()
    log = tmp_path / "calls.txt"
    (source / "setup-sci.ps1").write_text(
        "param([switch]$UserInstall, [switch]$NonInteractive)\n"
        "$mark = if ($UserInstall) { '-UserInstall' } else { '' }\n"
        "if ($NonInteractive) { $mark += ' -NonInteractive' }\n"
        'Add-Content -LiteralPath $env:CALL_LOG -Value "setup:$mark"\n'
        "if ($env:SETUP_FAILURE -ne '0') { exit ([int]$env:SETUP_FAILURE) }\n"
        'New-Item -ItemType Directory -Force -Path "$PSScriptRoot\\.sci\\bin" | Out-Null\n'
        "Copy-Item -LiteralPath $env:FIXTURE_CLI -Destination"
        ' "$PSScriptRoot\\.sci\\bin\\sci.cmd"\n'
        "exit 0\n")
    cli = tmp_path / "fixture-cli.cmd"
    cli.write_text('@echo off\r\n>> "%CALL_LOG%" echo cli:%*\r\nif "%1"=="--run-module" exit /b 3\r\nexit /b 0\r\n')
    env = {**os.environ, "CALL_LOG": str(log), "FIXTURE_CLI": str(cli),
           "SETUP_FAILURE": str(failure)}
    result = subprocess.run(
        [_powershell_host(), "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(source / "install-sci.ps1"), "-NonInteractive"],
        env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == failure
    calls = log.read_text().splitlines()
    assert calls[0] == "setup:-UserInstall -NonInteractive"
    if failure:
        assert calls == ["setup:-UserInstall -NonInteractive"]
        assert "stopped during installing runtime and dependencies" in result.stderr
        assert "is installed" not in result.stdout
    else:
        assert calls == ["setup:-UserInstall -NonInteractive", "cli:--help", "cli:--run-module sci_cli.install_status"]
        assert "Agent Scientist is installed" in result.stdout
        assert "sci setup" in result.stdout


@pytest.mark.platforms("windows")
def test_unknown_option_stops_before_setup():
    result = subprocess.run(
        [_powershell_host(), "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-File", str(ROOT / "install-sci.ps1"), "--invalid"],
        text=True, capture_output=True, timeout=30)
    assert result.returncode == 2 and "Unknown option" in result.stderr
