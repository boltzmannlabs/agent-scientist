"""Native Windows PATH lifetime checks, including a real clean source install.

Run on a disposable Windows account with SCI_E2E_WINDOWS_INSTALL=1. The real
HKCU PATH is restored in finally; no model login or scientific job is used.
"""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import pytest

ROOT = Path(__file__).resolve().parents[3]
pytestmark = [
    pytest.mark.platforms("windows"),
    pytest.mark.integration,
    pytest.mark.skipif(os.environ.get("SCI_E2E_WINDOWS_INSTALL") != "1",
                       reason="requires a disposable Windows account and real downloads"),
]


@pytest.fixture
def saved_user_path():
    import winreg

    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, "Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
        try:
            previous = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            previous = None
        try:
            yield
        finally:
            if previous is None:
                try:
                    winreg.DeleteValue(key, "Path")
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(key, "Path", 0, previous[1], previous[0])
            from sci_cli._launchers import _broadcast_environment_change
            _broadcast_environment_change()


def _shells():
    hosts = [shutil.which(name) for name in ("powershell", "pwsh")]
    assert all(hosts), "acceptance runner needs Windows PowerShell 5.1 and PowerShell 7"
    return hosts


def _run(host, script, directory, environment, name, timeout=120):
    path = directory / f"{name}.ps1"
    path.write_text(script, encoding="utf-8-sig")
    result = subprocess.run([host, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)],
                            env=environment, cwd=directory, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    evidence = Path(os.environ["SCI_E2E_ARTIFACTS"])
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / f"{name}.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    assert result.returncode == 0, (result.stdout + result.stderr)[-16000:]
    return result.stdout


def _fresh_shell_probe(directory, environment, expected_bin):
    expected = str(expected_bin).replace("'", "''")
    script = f"""
$ErrorActionPreference = 'Stop'
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
foreach ($name in 'sci', 'agent-sci') {{
    $command = Get-Command $name -CommandType Application -ErrorAction Stop
    if ((Split-Path -Parent $command.Source) -ne '{expected}') {{ throw "Wrong launcher: $($command.Source)" }}
    & $name --version
    if ($LASTEXITCODE -ne 0) {{ throw "$name --version failed: $LASTEXITCODE" }}
    Write-Output "FRESH_PATH_OK $name $($command.Source)"
}}
"""
    for index, host in enumerate(_shells()):
        output = _run(host, script, directory, environment, f"{directory.name}-fresh-shell-{index}")
        assert "FRESH_PATH_OK sci" in output and "FRESH_PATH_OK agent-sci" in output


def test_registration_persists_without_the_installers_process_path(tmp_path, saved_user_path):
    from sci_cli.install_paths import register_user_path

    directory = tmp_path / "commands with spaces"
    directory.mkdir()
    for name in ("sci", "agent-sci"):
        (directory / f"{name}.cmd").write_text("@echo off\necho SCI PATH fixture\nexit /b 0\n", encoding="utf-8")
    stale = dict(os.environ)
    register_user_path(directory)
    register_user_path(directory)
    assert str(directory) not in stale["PATH"]
    _fresh_shell_probe(tmp_path, stale, directory)


@pytest.mark.timeout(2400)
def test_clean_source_install_and_later_short_command_launches(saved_user_path):
    # Windows checkouts contain long relative paths; don't add pytest's deep
    # per-test prefix to the user's repository and venv paths.
    root = Path(os.environ["SCI_E2E_MACHINE_ROOT"])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="source-", dir=root) as directory:
        _clean_source_install(Path(directory))


def _clean_source_install(directory):
    checkout = directory / "checkout with spaces"
    git = shutil.which("git")
    assert git
    cloned = subprocess.run([git, "clone", "--quiet", "--no-hardlinks", str(ROOT), str(checkout)],
                            capture_output=True, text=True, timeout=120)
    assert cloned.returncode == 0, cloned.stdout + cloned.stderr
    profile = directory / "new-user"
    profile.mkdir()
    environment = {name: value for name, value in os.environ.items()
                   if not name.startswith("SCI_") and name not in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV")}
    environment.update(USERPROFILE=str(profile), HOME=str(profile),
                       LOCALAPPDATA=str(profile / "AppData" / "Local"),
                       APPDATA=str(profile / "AppData" / "Roaming"),
                       SCI_STATE_DB_GUARD_BYPASS="1", PYTHONIOENCODING="utf-8")
    installer = str(checkout / "install-sci.ps1").replace("'", "''")
    expected = Path(environment["LOCALAPPDATA"]) / "sci" / "bin"
    assert str(expected) not in environment["PATH"]
    # Invoke in the caller, as in the documented install commands. Unlike
    # powershell -File, this must refresh that shell as well as User PATH.
    command = f"""
$ErrorActionPreference = 'Stop'
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
& '{installer}' -NonInteractive -NoLaunch
if ($LASTEXITCODE -ne 0) {{ throw "Installer failed: $LASTEXITCODE" }}
$command = Get-Command sci -CommandType Application -ErrorAction Stop
if ((Split-Path -Parent $command.Source) -ne '{str(expected).replace("'", "''")}') {{ throw 'Wrong immediate launcher' }}
sci --version
if ($LASTEXITCODE -ne 0) {{ throw 'Immediate sci launch failed' }}
Write-Output 'IMMEDIATE_PATH_OK'
"""
    output = _run(_shells()[0], command, directory, environment, "clean-install", timeout=2200)
    assert "IMMEDIATE_PATH_OK" in output
    _fresh_shell_probe(directory, environment, expected)
