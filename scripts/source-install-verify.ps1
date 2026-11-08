# Verify the public commands, not only the checkout-local bootstrap.
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
    [pscustomobject]@{ Sci = $commands['sci']; AgentSci = $commands['agent-sci']; Version = ($version -join ' ').Trim() }
}

function Show-SciCommandInstructions($Verified) {
    Write-Output "Verified version: $($Verified.Version)"
    Write-Output "Sci executable: $($Verified.Sci)"
    $quoted = $Verified.Sci.Replace("'", "''")
    Write-Output "Verify immediately: & '$quoted' --version"
    Write-Output "Start immediately:  & '$quoted'"
    Write-Output 'User PATH is registered. Completely exit all VS Code windows and reopen VS Code to refresh existing IDE environments.'
    Write-Output 'A new integrated terminal inside an already-running VS Code window may still have the old PATH.'
    $resolved = Get-Command sci -ErrorAction SilentlyContinue
    if (-not $resolved -or $resolved.Source -ne $Verified.Sci) {
        Write-Warning 'The short sci command is missing or shadowed in this shell. Use the absolute command above; inspect Get-Command sci -All after restarting the terminal.'
    }
}
