# ============================================================================
# Sci Agent Setup Script (Windows) — THE dev-environment entry point.
# ============================================================================
# Sets up the pm-managed development environment from a fresh clone:
#   1. Stage the pinned uv from pm/lock.json (sha256-verified, into the pm
#      store slot) - pm needs uv to bootstrap, so it cannot stage uv itself.
#   2. Use uv to install and locate bootstrap Python, then let uv exit.
#      Run `python -m pm.cli install` directly so PM can safely replace uv.
#      PM owns the final interpreter, tool store, and dependency generation.
#   3. Point you at `.\activate.ps1` - the venv-style way to put the pm env
#      (PATH + tool vars) into your current session.
# ============================================================================
# Setup and activation both prepare the isolated test interpreter; installers
# invoke pm.cli directly and do not select it. -TestExtras overrides coverage.
# -UserInstall (install-sci.ps1, the end-user wrapper) skips the developer/test
# dependency groups and the .env template — the same contract as
# setup-sci.sh --user-install.
param([switch]$RuntimeOnly, [switch]$UserInstall, [switch]$InstallPrerequisites, [switch]$NonInteractive, [string]$TestExtras = '')
$ErrorActionPreference = 'Stop'

# Bootstrap runs before Python/PM exists. Keep its downloads pinned and bounded.
function Get-SciBootstrapArchive([string]$Uri, [string]$Sha256, [string]$OutFile) {
    $curl = Get-Command curl.exe -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    try {
        if ($curl) {
            Write-Host "Downloading uv with curl.exe: $Uri"
            & $curl.Source --fail --location --retry 3 --retry-delay 5 --connect-timeout 20 --max-time 600 --output $OutFile --url $Uri
            if ($LASTEXITCODE -ne 0) { throw "curl.exe exited with code $LASTEXITCODE" }
        } else {
            Write-Host "curl.exe unavailable; downloading uv with PowerShell: $Uri"
            for ($attempt = 1; $attempt -le 4; $attempt++) {
                try {
                    Invoke-WebRequest -UseBasicParsing -TimeoutSec 600 -Uri $Uri -OutFile $OutFile -ErrorAction Stop
                    break
                } catch {
                    $failure = $_.Exception
                    $status = if ($failure.Response) { [int]$failure.Response.StatusCode } else { 0 }
                    $transient = $status -in @(408, 429, 500, 502, 503, 504)
                    if (-not $status) {
                        $transient = ($failure -is [System.Net.WebException] -and $failure.Status -in @(
                            'Timeout', 'ConnectFailure', 'ConnectionClosed', 'ReceiveFailure', 'SendFailure', 'NameResolutionFailure')) -or
                            ($failure.InnerException -is [System.Net.Sockets.SocketException]) -or
                            ($failure.InnerException -is [System.TimeoutException])
                    }
                    if (-not $transient -or $attempt -eq 4) { throw }
                    if (Test-Path -LiteralPath $OutFile) { Remove-Item -LiteralPath $OutFile -Force }
                    Write-Warning "uv download attempt $attempt failed; retrying in 5 seconds (maximum 4 attempts)."
                    Start-Sleep -Seconds 5
                }
            }
        }
        $got = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutFile).Hash.ToLowerInvariant()
        if ($got -ne $Sha256.ToLowerInvariant()) {
            throw "sha256 mismatch for uv (got $got, pinned $Sha256)"
        }
    } catch {
        if (Test-Path -LiteralPath $OutFile) { Remove-Item -LiteralPath $OutFile -Force -ErrorAction SilentlyContinue }
        throw "uv bootstrap download failed from ${Uri}: $($_.Exception.Message). Check network/proxy access and rerun the installer."
    }
}

Write-Host ''
Write-Host 'Sci Agent Setup' -ForegroundColor Cyan
Write-Host ''

$repo = $PSScriptRoot
if (-not $RuntimeOnly) {
    . (Join-Path $repo 'scripts/source-install-preflight.ps1')
    Invoke-SciSourcePreflight -Repo $repo -InstallPrerequisites:$InstallPrerequisites -NonInteractive:$NonInteractive
}
$lockPath = Join-Path $repo 'pm/lock.json'
if (-not (Test-Path $lockPath)) { throw 'pm/lock.json not found' }
$lock = Get-Content -Raw $lockPath | ConvertFrom-Json

$machineArch = (Get-ItemProperty 'HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager\Environment').PROCESSOR_ARCHITECTURE
if ($machineArch -notin @('ARM64', 'AMD64')) { throw "Unsupported Windows architecture: $machineArch. Use x64 or ARM64." }
$arch = if ($machineArch -eq 'ARM64') { 'arm64' } else { 'x64' }
$target = "win32-$arch"

# ---------------------------------------------------------------------------
# Stage the pinned uv from pm/lock.json into the pm store slot
# ---------------------------------------------------------------------------
$uvPin = $lock.packages.uv
if (-not $uvPin) { throw 'no uv pin in pm/lock.json' }
$artifact = $uvPin.artifacts.$target
if (-not $artifact) { $artifact = $uvPin.artifacts.any }
if (-not $artifact) { throw "no uv artifact for $target" }

$pyPin = $lock.packages.python
$pyVersion = if ($pyPin) { ($pyPin.version -split '\+')[0] -replace '^(\d+\.\d+).*', '$1' } else { '3.11' }

$store = if ($env:SCI_RUNTIME_DIR) { $env:SCI_RUNTIME_DIR } else { Join-Path $HOME '.sci/tools' }
$entry = Join-Path $store "uv-$($uvPin.version)-$target"
$uv = Join-Path $entry 'uv.exe'

if (Test-Path $uv) {
    Write-Host ("pinned uv found: " + (& $uv --version)) -ForegroundColor Green
} else {
    Write-Host "Staging pinned uv $($uvPin.version) ($target) into the pm store..." -ForegroundColor Cyan
    $tmp = Join-Path ([System.IO.Path]::GetTempPath()) ("sci-setup-" + [guid]::NewGuid().ToString('n'))
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        $archive = Join-Path $tmp ([uri]$artifact.url).Segments[-1]
        Get-SciBootstrapArchive -Uri $artifact.url -Sha256 $artifact.sha256 -OutFile $archive
        $tree = Join-Path $tmp 'tree'
        Expand-Archive -Path $archive -DestinationPath $tree
        # flatten a single wrapping dir
        $inner = @(Get-ChildItem $tree)
        $src = if ($inner.Count -eq 1 -and $inner[0].PSIsContainer) { $inner[0].FullName } else { $tree }
        New-Item -ItemType Directory -Force -Path $store | Out-Null
        if (Test-Path $entry) { Remove-Item -Recurse -Force $entry }
        Move-Item $src $entry
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
    Write-Host ("uv installed: " + (& $uv --version)) -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# PM installs the tools, then the venv. On ARM64 PM prepares the compiler and
# OpenSSL environment for that sync itself (pm/native_build.py), after its own
# git is published, so every install path builds the same way.
# Activation trusts the recorded tool digest. A direct setup re-checks it.
# ---------------------------------------------------------------------------
Write-Host 'Installing python + tools + dependencies via pm (hash-verified via uv.lock)...' -ForegroundColor Cyan
Write-Host '(first run on a fresh checkout can take 1-5 minutes)'
Push-Location $repo
try {
    # PM can replace its uv entry only after the bootstrap uv has exited.
    # A bare version lets uv pick emulated x86_64 on Windows-on-ARM.
    $pyRequest = "cpython-$pyVersion-windows-$(if ($arch -eq 'arm64') { 'aarch64' } else { 'x86_64' })-none"
    & $uv python install --no-bin --no-registry $pyRequest
    if ($LASTEXITCODE -ne 0) { throw 'bootstrap Python installation failed' }
    $bootPy = (& $uv python find --managed-python $pyRequest) -join "`n"
    if ($LASTEXITCODE -ne 0 -or -not $bootPy) { throw 'bootstrap Python lookup failed' }
    $pmArgs = @()
    if (-not $UserInstall) { $pmArgs += "--test-environment=$TestExtras" }
    if ($RuntimeOnly) { $pmArgs += '--trust-recorded' }
    & $bootPy.Trim() -m pm.cli install @pmArgs
    if ($LASTEXITCODE -ne 0) { throw 'pm install failed - see output above.' }
} finally {
    Pop-Location
}
Write-Host 'Tools + dependencies installed (hash-verified via pm + uv.lock)' -ForegroundColor Green

if ($RuntimeOnly) { exit 0 }

# ---------------------------------------------------------------------------
# Environment file
# ---------------------------------------------------------------------------
$envFile = Join-Path $repo '.env'
if ($UserInstall) {
    Write-Host 'Personal credentials are configured in the SCI setup wizard.' -ForegroundColor Cyan
} elseif (-not (Test-Path $envFile)) {
    if (Test-Path (Join-Path $repo '.env.example')) {
        Copy-Item (Join-Path $repo '.env.example') $envFile
        Write-Host 'Created .env from template' -ForegroundColor Green
    }
} else {
    Write-Host '.env exists' -ForegroundColor Green
}

# ---------------------------------------------------------------------------
# Publish user-facing launchers (checkout-local .sci\bin plus the user bin dir)
# ---------------------------------------------------------------------------
Write-Host 'Setting up sci command...' -ForegroundColor Cyan
$binDir = if ($env:SCI_HOME) { Join-Path $env:SCI_HOME 'bin' } else { Join-Path $env:LOCALAPPDATA 'sci\bin' }
& $bootPy.Trim() -I -X utf8 (Join-Path $repo 'sci_cli/_launchers.py') $binDir --register-path
if ($LASTEXITCODE -ne 0) { throw 'launcher publication failed' }
Write-Host "Published Sci commands in $binDir" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Seed bundled skills into ~/.sci/skills/
# ---------------------------------------------------------------------------
$skillsDir = if ($env:SCI_HOME) { Join-Path $env:SCI_HOME 'skills' } else { Join-Path $HOME '.sci/skills' }
New-Item -ItemType Directory -Force -Path $skillsDir | Out-Null
Write-Host "Syncing bundled skills to $skillsDir ..."
$localCli = @('sci.exe', 'sci.cmd') |
    ForEach-Object { Join-Path $repo ".sci/bin/$_" } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
if (-not $localCli) { throw 'checkout-local sci launcher is missing; launcher publication did not complete' }
& $localCli --run-module tools.skills_sync
if ($LASTEXITCODE -ne 0) { throw 'Bundled skill synchronization failed; installation is incomplete.' }
Write-Host 'Skills synced' -ForegroundColor Green

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host ''
Write-Host 'Runtime, launchers and bundled skills installed.' -ForegroundColor Green
if ($UserInstall) {
    Write-Host 'Start Agent Scientist with: sci'
    exit 0
}
Write-Host ''
Write-Host 'Next steps:'
Write-Host ''
Write-Host '  1. Activate the dev environment (venv-style, in THIS session):'
Write-Host '     .\activate.ps1'
Write-Host ''
Write-Host '  2. Run the setup wizard to configure API keys:'
Write-Host '     sci setup'
Write-Host ''
Write-Host '  3. Start chatting:'
Write-Host '     sci'
Write-Host ''
Write-Host 'Other commands:'
Write-Host '  sci pm install     # Re-run the tool + dependency install'
Write-Host '  sci status         # Check configuration'
Write-Host '  sci doctor         # Diagnose issues'
Write-Host '  deactivate            # Undo the activation (restore PATH etc.)'
Write-Host ''
