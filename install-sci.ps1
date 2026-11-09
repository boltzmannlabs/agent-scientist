# Install Agent Scientist from this source checkout using its managed runtime.
# Windows twin of install-sci.sh; the setup engine is setup-sci.ps1.
param(
    [switch]$NonInteractive,
    [switch]$NoLaunch,
    [switch]$InstallPrerequisites,
    [switch]$Help,
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$Rest
)
$ErrorActionPreference = 'Stop'

function Show-Usage {
    Write-Output 'Usage: .\install-sci.ps1 [-NonInteractive] [-NoLaunch] [-InstallPrerequisites] [-Help]'
    Write-Output ''
    Write-Output 'Installs the managed Python/tools, application dependencies, SCI launchers'
    Write-Output 'and bundled skills. Interactive mode configures a provider, then launches SCI.'
    Write-Output '-NonInteractive installs the software without asking for credentials.'
    Write-Output '-NoLaunch completes setup without opening chat.'
    Write-Output '-InstallPrerequisites explicitly approves missing Git installation using WinGet.'
}
if ($Help) { Show-Usage; exit 0 }
if ($Rest) {
    [Console]::Error.WriteLine("Unknown option: $($Rest -join ' ')")
    Show-Usage | ForEach-Object { [Console]::Error.WriteLine($_) }
    exit 2
}

if ([System.Environment]::OSVersion.Platform -ne [System.PlatformID]::Win32NT) {
    [Console]::Error.WriteLine('Use install-sci.sh for Linux and macOS. This installer supports native Windows.')
    exit 1
}

$sourceDir = $PSScriptRoot
foreach ($file in 'setup-sci.ps1', 'scripts/source-install-preflight.ps1', 'scripts/source-install-verify.ps1', 'pyproject.toml', 'uv.lock', 'pm/lock.json') {
    if (-not (Test-Path -LiteralPath (Join-Path $sourceDir $file))) {
        [Console]::Error.WriteLine("Incomplete SCI checkout: $file is missing. Obtain the complete repository and retry.")
        exit 1
    }
}

$setup = -not $NonInteractive
$launch = -not ($NonInteractive -or $NoLaunch)
if ($setup -and ([Console]::IsInputRedirected -or [Console]::IsOutputRedirected)) {
    Write-Output 'No interactive terminal detected; installing software without credential setup.'
    $setup = $false
    $launch = $false
}

# Mirrors install-sci.sh's ERR trap: every failure names its stage and
# preserves the child's exit code; a stopped installer is never "successful".
$script:stage = 'checking prerequisites'
function Stop-Install([int]$Code) {
    if ($Code -eq 0) { $Code = 1 }
    [Console]::Error.WriteLine('')
    [Console]::Error.WriteLine("Installation stopped during $($script:stage) (exit $Code). See the error above.")
    exit $Code
}

trap {
    [Console]::Error.WriteLine($_.Exception.Message)
    Stop-Install 1
}

Write-Output 'Agent Scientist installation'
Write-Output "Source: $sourceDir"

$script:stage = 'installing runtime and dependencies'
# A child process (not dot-sourcing or &) keeps the engine's exit/throw
# behavior out of this wrapper and preserves its exact exit code.
$psHost = (Get-Process -Id $PID).Path
$engineOptions = @('-UserInstall')
if (-not $setup) { $engineOptions += '-NonInteractive' }
if ($InstallPrerequisites) { $engineOptions += '-InstallPrerequisites' }
& $psHost -NoProfile -ExecutionPolicy Bypass -File (Join-Path $sourceDir 'setup-sci.ps1') @engineOptions
if ($LASTEXITCODE -ne 0) { Stop-Install $LASTEXITCODE }

$script:stage = 'checking the installed CLI'
$installedCli = @('sci.exe', 'sci.cmd') |
    ForEach-Object { Join-Path $sourceDir ".sci\bin\$_" } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
if (-not $installedCli) {
    [Console]::Error.WriteLine('The checkout-local launcher .sci\bin\sci is missing.')
    Stop-Install 1
}
& $installedCli --help > $null
if ($LASTEXITCODE -ne 0) { Stop-Install $LASTEXITCODE }

# The engine registered persistent User PATH. Refresh this PowerShell process too.
$binDir = if ($env:SCI_HOME) { Join-Path $env:SCI_HOME 'bin' } else { Join-Path $env:LOCALAPPDATA 'sci\bin' }
$env:Path = "$binDir;$env:Path"
$script:stage = 'verifying public launchers and User PATH'
. (Join-Path $sourceDir 'scripts/source-install-verify.ps1')
$verified = Test-SciPublishedCommands -BinDirectory $binDir -UserPath ([Environment]::GetEnvironmentVariable('Path', 'User'))
$script:stage = 'checking model configuration'
function Test-InstalledProvider {
    & $installedCli --run-module sci_cli.install_status
    $code = $LASTEXITCODE
    if ($code -ne 0 -and $code -ne 3) { Stop-Install $code }
    $script:providerReady = $code -eq 0
}
Test-InstalledProvider
if ($setup -and -not $script:providerReady) {
    $script:stage = 'configuring your model provider'
    & $installedCli setup
    if ($LASTEXITCODE -ne 0) { Stop-Install $LASTEXITCODE }
    Test-InstalledProvider
}

Write-Output ''
Write-Output 'Agent Scientist is installed.'
Write-Output 'Start: sci (agent-sci is also available).'
Show-SciCommandInstructions $verified
Write-Output "Keep this source checkout at: $sourceDir"
if (-not $script:providerReady) {
    Write-Output 'Model setup is incomplete; software is installed. Run sci setup before chatting.'
    $launch = $false
}
Write-Output 'Optional service credentials are configured separately inside SCI.'
if ($launch) {
    $script:stage = 'launching SCI'
    & $installedCli
    if ($LASTEXITCODE -ne 0) { Stop-Install $LASTEXITCODE }
}
# The provider probe may return 3 for an installed-but-unconfigured model.
# Direct invocation must report installation success to the caller as well.
exit 0
