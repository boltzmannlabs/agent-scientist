"""Windows source preflight checks native paths without installing system software."""
from pathlib import Path
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.platforms('windows')
def test_directory_probe_and_controlled_capacity_failure(tmp_path):
    host = shutil.which('pwsh') or shutil.which('powershell')
    assert host, 'PowerShell is required on the Windows runner'
    helper = str(ROOT / 'scripts/source-install-preflight.ps1').replace("'", "''")
    directory = str(tmp_path / 'directory with spaces').replace("'", "''")
    script = tmp_path / 'probe.ps1'
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f". '{helper}'\nTest-SciInstallDirectory '{directory}'\n"
        # Mock just disk reporting, not the host OS or filesystem writes.
        "function Get-Item { [pscustomobject]@{ PSDrive = [pscustomobject]@{Free = 1024} } }\n"
        f"try {{ Test-SciInstallDirectory '{directory}'; throw 'unexpected success' }}\n"
        "catch { if ($_.Exception.Message -notlike 'Insufficient disk space*') { throw }; 'rejected-low-space' }\n",
        encoding='utf-8')
    result = subprocess.run([host, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'rejected-low-space' in result.stdout
    assert not list((tmp_path / 'directory with spaces').glob('.sci-write-check-*'))


@pytest.mark.platforms('windows')
def test_missing_git_requires_approval_and_is_rechecked(tmp_path):
    host = shutil.which('pwsh') or shutil.which('powershell')
    assert host, 'PowerShell is required on the Windows runner'
    helper = str(ROOT / 'scripts/source-install-preflight.ps1').replace("'", "''")
    script = tmp_path / 'prerequisites.ps1'
    script.write_text(
        "$ErrorActionPreference = 'Stop'\n"
        f". '{helper}'\n"
        "$global:GitAvailable = $false\n$global:PackageCalls = 0\n"
        "function Get-Command { param($Name, $CommandType, $ErrorAction)\n"
        "  if ($Name -eq 'git') { if ($global:GitAvailable) { 'git' }; return }\n"
        "  Microsoft.PowerShell.Core\\Get-Command -Name $Name -ErrorAction Stop\n}\n"
        "function git { $global:LASTEXITCODE = 0 }\n"
        "function winget { $global:PackageCalls++; $global:GitAvailable = $true; $global:LASTEXITCODE = 0 }\n"
        "function Test-SciInstallDirectory { param($Directory) }\n"
        "try { Invoke-SciSourcePreflight -Repo $PSScriptRoot -NonInteractive; throw 'unexpected success' }\n"
        "catch { if ($_.Exception.Message -notlike 'Git is required*') { throw } }\n"
        "if ($global:PackageCalls -ne 0) { throw 'installed without consent' }\n"
        "Invoke-SciSourcePreflight -Repo $PSScriptRoot -InstallPrerequisites\n"
        "if (-not $global:GitAvailable -or $global:PackageCalls -ne 1) { throw 'Git was not installed and rechecked' }\n"
        "'consent-and-recheck-passed'\n", encoding='utf-8')
    # WinGet presence is mocked in the command lookup too; the real executable is never called.
    text = script.read_text(encoding='utf-8').replace(
        "  Microsoft.PowerShell.Core\\Get-Command", "  if ($Name -eq 'winget') { 'winget'; return }\n  Microsoft.PowerShell.Core\\Get-Command")
    script.write_text(text, encoding='utf-8')
    result = subprocess.run([host, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(script)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'consent-and-recheck-passed' in result.stdout
