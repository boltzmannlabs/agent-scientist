# Verify the public commands, not only the checkout-local bootstrap.
function Test-SciSavedPathLookup([hashtable]$Commands, [string]$UserPath) {
    # A successful absolute launch in the installer does not prove that a later
    # shell can find SCI. Discard all installer-only PATH entries for this child.
    $expectedJson = ($Commands | ConvertTo-Json -Compress).Replace("'", "''")
    $probe = @'
$ErrorActionPreference = 'Stop'
$expected = ConvertFrom-Json '__EXPECTED__'
foreach ($name in 'sci', 'agent-sci') {
    $command = Get-Command $name -CommandType Application -ErrorAction Stop
    if ($command.Source -ne $expected.$name) {
        throw "The saved Windows PATH resolves $name to $($command.Source), not $($expected.$name)."
    }
    & $name --version
    if ($LASTEXITCODE -ne 0) { throw "$name --version failed through saved Windows PATH (exit $LASTEXITCODE)." }
    Write-Output "Verified saved Windows PATH: $name"
}
'@
    $encoded = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($probe.Replace('__EXPECTED__', $expectedJson)))
    $hostExecutable = (Get-Process -Id $PID).Path
    $previousPath = $env:Path
    try {
        $machinePath = [Environment]::GetEnvironmentVariable('Path', 'Machine')
        $env:Path = [Environment]::ExpandEnvironmentVariables("$machinePath;$UserPath")
        $output = & $hostExecutable -NoProfile -NonInteractive -ExecutionPolicy Bypass -EncodedCommand $encoded 2>&1
        if ($LASTEXITCODE -ne 0) {
            throw "SCI cannot be launched through saved Windows PATH. $($output -join [Environment]::NewLine)"
        }
        $output | ForEach-Object { Write-Host $_ }
    } finally {
        $env:Path = $previousPath
    }
}

function Test-SciPublishedCommands([string]$BinDirectory, [string]$UserPath) {
    $expected = [IO.Path]::GetFullPath($BinDirectory).TrimEnd('\', '/')
    $registered = @($UserPath -split ';' | Where-Object { $_ } | ForEach-Object {
        [Environment]::ExpandEnvironmentVariables($_.Trim().Trim('"')).TrimEnd('\', '/')
    })
    if ($registered -notcontains $expected) {
        throw "SCI launcher directory is missing from persistent User PATH: $expected. Rerun the installer to repair PATH registration."
    }
    $commands = @{}
    foreach ($name in 'sci', 'agent-sci') {
        $launcher = @("$name.exe", "$name.cmd") | ForEach-Object { Join-Path $expected $_ } |
            Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
        if (-not $launcher) { throw "Published $name launcher is missing from $expected. Rerun the installer." }
        $version = & $launcher --version
        if ($LASTEXITCODE -ne 0) { throw "Published $name launcher failed --version (exit $LASTEXITCODE): $launcher" }
        if (-not ($version -join '').Trim()) { throw "Published $name launcher returned no version: $launcher" }
        $commands[$name] = $launcher
    }
    Test-SciSavedPathLookup -Commands $commands -UserPath $UserPath
    [pscustomobject]@{ Sci = $commands['sci']; AgentSci = $commands['agent-sci']; Version = ($version -join ' ').Trim() }
}

function Show-SciCommandInstructions($Verified) {
    Write-Output "Verified version: $($Verified.Version)"
    Write-Output "Sci executable: $($Verified.Sci)"
    $quoted = $Verified.Sci.Replace("'", "''")
    Write-Output "Verify immediately: & '$quoted' --version"
    Write-Output "Start immediately:  & '$quoted'"
    Write-Output 'User PATH is registered permanently for this Windows account.'
    Write-Output 'For VS Code: finish terminal work, then close old terminal tabs with their trash icons.'
    Write-Output 'Completely exit all VS Code windows and reopen VS Code from the Windows Start menu; create a new terminal.'
    Write-Output 'Restored terminal tabs can reuse their old PATH even after VS Code restarts.'
    $resolved = Get-Command sci -ErrorAction SilentlyContinue
    if (-not $resolved -or $resolved.Source -ne $Verified.Sci) {
        Write-Warning 'The short sci command is missing or shadowed in this shell. Use the absolute command above; inspect Get-Command sci -All after restarting the terminal.'
        $binQuoted = (Split-Path -Parent $Verified.Sci).Replace("'", "''")
        Write-Output "Refresh this terminal now: `$env:Path = '$binQuoted;' + `$env:Path"
    }
}
