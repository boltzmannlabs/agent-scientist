# Dot-sourced before the managed Python runtime exists. No work at import time.
function Test-SciInstallDirectory([string]$Directory) {
    New-Item -ItemType Directory -Force -Path $Directory | Out-Null
    $probe = Join-Path $Directory ('.sci-write-check-' + [guid]::NewGuid().ToString('n'))
    try { [IO.File]::WriteAllText($probe, '') }
    finally { if (Test-Path -LiteralPath $probe) { Remove-Item -LiteralPath $probe } }
    $drive = (Get-Item -LiteralPath $Directory).PSDrive
    if ($null -eq $drive.Free) { throw "Cannot determine free disk space at $Directory" }
    if ($drive.Free -lt 2GB) { throw "Insufficient disk space at ${Directory}: at least 2 GiB free is required for bootstrap. Full dependencies and scientific models may need more." }
    Write-Host "Writable directory: $Directory (2 GiB bootstrap minimum passed)"
}

function Invoke-SciSourcePreflight([string]$Repo, [switch]$InstallPrerequisites, [switch]$NonInteractive) {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) { throw 'Use install-sci.sh on Linux and macOS.' }
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'SCI requires 64-bit Windows (x64 or ARM64).' }
    if ($PSVersionTable.PSVersion -lt [version]'5.1') { throw 'SCI requires PowerShell 5.1 or newer.' }
    foreach ($command in 'Invoke-WebRequest', 'Get-FileHash', 'Expand-Archive') {
        if (-not (Get-Command $command -ErrorAction SilentlyContinue)) { throw "Required PowerShell command missing: $command. Install Windows PowerShell 5.1 or PowerShell 7 and retry." }
    }
    if (-not (Get-Command git -CommandType Application -ErrorAction SilentlyContinue)) {
        Write-Host 'Missing prerequisite: Git.'
        if (-not (Get-Command winget -CommandType Application -ErrorAction SilentlyContinue)) {
            throw 'Install Git for Windows from https://git-scm.com/download/win, reopen PowerShell, and retry. WinGet is unavailable on this machine.'
        }
        $approved = [bool]$InstallPrerequisites
        if (-not $approved -and -not $NonInteractive -and -not [Console]::IsInputRedirected -and -not [Console]::IsOutputRedirected) {
            $approved = (Read-Host 'Install Git.Git using WinGet? [y/N]') -match '^(y|yes)$'
        }
        if (-not $approved) { throw 'Git is required. Install it, or rerun with -InstallPrerequisites to approve its installation.' }
        & winget install --id Git.Git --exact --source winget --accept-source-agreements --accept-package-agreements
        if ($LASTEXITCODE -ne 0) { throw 'Git installation failed; see WinGet output above.' }
        $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + $env:Path
    }
    & git --version | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Git is installed but cannot run. Repair Git and retry.' }
    $runtime = if ($env:SCI_RUNTIME_DIR) { $env:SCI_RUNTIME_DIR } else { Join-Path $HOME '.sci/tools' }
    $sciHome = if ($env:SCI_HOME) { $env:SCI_HOME } else { Join-Path $HOME '.sci' }
    $bin = if ($env:SCI_HOME) { Join-Path $env:SCI_HOME 'bin' } else { Join-Path $env:LOCALAPPDATA 'sci/bin' }
    foreach ($directory in @($Repo, $runtime, $sciHome, $bin, [IO.Path]::GetTempPath())) { Test-SciInstallDirectory $directory }
    Write-Host 'OS prerequisites passed. Required HTTPS downloads verify network access; cached artifacts can be reused.'
}
