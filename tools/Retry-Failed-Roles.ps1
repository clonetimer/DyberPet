# Retry ONLY failed source-pinned characters in the same unpacked Windows folder.
# Successful creator art and existing folders are never overwritten.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$exe = Join-Path $PSScriptRoot "DyberPet-Role-Installer.exe"
$roles = Join-Path $PSScriptRoot "res/role"
$prior = Join-Path $PSScriptRoot "data/personal65-install-report.json"
$planned = Join-Path $PSScriptRoot "data/personal65-retry-plan.json"
$next = Join-Path $PSScriptRoot "data/personal65-retry-report.json"
if (-not (Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Role installer is missing. Use the Windows personal release package."
}
if (-not (Test-Path -LiteralPath $prior -PathType Leaf)) {
    throw "Previous installation report missing: $prior"
}
$old = Get-Content -LiteralPath $prior -Raw -Encoding UTF8 | ConvertFrom-Json
$failed = @($old.installation.results | Where-Object { $_.status -eq "failed" })
Write-Host ("Original failed profiles: " + $failed.Count) -ForegroundColor Yellow
if ($failed.Count -eq 0) {
    Write-Host "No failed profiles in previous report."
    exit 0
}
Write-Host "Installed role folders stay unchanged. Current source manifest is used; previous source URLs are ignored."
& $exe --retry-failed-from $prior --role-root $roles --output $planned
if ($LASTEXITCODE -ne 0) { throw "Cannot safely parse prior report: $prior" }
$plan = Get-Content -LiteralPath $planned -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host ("Failed sources still eligible for opt-in retry: " + $plan.summary.ready_for_opt_in)
Write-Host ("Already installed (will skip): " + $plan.summary.already_installed_structurally)
Write-Host "Check creator artwork use conditions and local network availability before retrying."
$answer = Read-Host "Type RETRY to attempt ONLY missing failed roles"
if ($answer -cne "RETRY") {
    Write-Host "Cancelled. No source art fetched."
    exit 0
}
& $exe --retry-failed-from $prior --role-root $roles --install --accept-personal-use --output $next
$exitCode = $LASTEXITCODE
Write-Host "Previous report preserved: $prior"
Write-Host "New retry report: $next"
if (Test-Path -LiteralPath $next) {
    $latest = Get-Content -LiteralPath $next -Raw -Encoding UTF8 | ConvertFrom-Json
    Write-Host ("Newly installed: " + $latest.installation.installed_unreviewed)
    Write-Host ("Still failed: " + $latest.installation.failed)
    foreach ($item in @($latest.installation.results | Where-Object { $_.status -eq "failed" })) {
        Write-Warning ($item.profile + ": " + $item.reason)
    }
}
exit $exitCode
