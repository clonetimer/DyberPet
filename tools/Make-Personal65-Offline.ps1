# Run inside an extracted Personal65 Windows portable distribution.
# This is PRIVATE LOCAL ASSEMBLY. Nothing containing artwork is uploaded.
param([switch]$PackOnly)
$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$helper = Join-Path $root "DyberPet-Role-Installer.exe"
$roleRoot = Join-Path $root "res/role"
if (-not (Test-Path -LiteralPath (Join-Path $root "DyberPet.exe")) -or
    -not (Test-Path -LiteralPath $helper) -or
    -not (Test-Path -LiteralPath $roleRoot)) {
    throw "Please run this inside the EXTRACTED Personal65 Python or RustHybrid folder."
}
$reportDir = Join-Path $root "data"
New-Item -ItemType Directory -Path $reportDir -Force | Out-Null

$genshinPlan = Join-Path $reportDir "personal65-preinstall-plan.json"
$mascotPlan = Join-Path $reportDir "mascots-preinstall-plan.json"
& $helper --role-root $roleRoot --output $genshinPlan
if ($LASTEXITCODE -ne 0) { throw "Unable to read 65-role source plan. Nothing downloaded." }
& $helper --mascots --role-root $roleRoot --output $mascotPlan
if ($LASTEXITCODE -ne 0) { throw "Unable to read Guga/Doro source plan. Nothing downloaded." }

$genshin = Get-Content -LiteralPath $genshinPlan -Raw -Encoding UTF8 | ConvertFrom-Json
$mascots = Get-Content -LiteralPath $mascotPlan -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host "Genshin templates: $($genshin.summary.selected_profiles)" -ForegroundColor Cyan
Write-Host "Source-covered character count: $($genshin.summary.selected_profiles - $genshin.summary.missing_source)"
Write-Host "Available for automatic local installation: $($genshin.summary.ready_for_opt_in)"
Write-Host "Manual-source only: $($genshin.summary.manual_import_only)"
Write-Host "No pinned source: $($genshin.summary.missing_source)"
Write-Host "Guga/Doro: $($mascots.summary.ready_for_opt_in) artist sources ready to install"
Write-Host ""
Write-Host "Source checksums do not prove rights, likeness, voice or desktop animation quality." -ForegroundColor Yellow
Write-Host "Check each creator's permitted personal use. No artwork is uploaded by this script."
Write-Host "Your existing role folders and local saves are never overwritten."
Write-Host ""

if (-not $PackOnly) {
    $choice = Read-Host "Type INSTALL to fetch source-pinned character art locally; PACK to archive only existing roles; any other input cancels"
    if ($choice -ceq "INSTALL") {
        $artReport = Join-Path $reportDir "personal65-source-install.json"
        & $helper --role-root $roleRoot --install --accept-personal-use --output $artReport
        $genshinExit = $LASTEXITCODE
        if ($genshinExit -ne 0) { Write-Warning "Not all Genshin sources installed; see $artReport" }

        $mascotReport = Join-Path $reportDir "personal65-mascots-install.json"
        & $helper --mascots --role-root $roleRoot --install --accept-personal-use --output $mascotReport
        $mascotExit = $LASTEXITCODE
        if ($mascotExit -ne 0) { Write-Warning "Guga/Doro installation may be partial; see $mascotReport" }
    } elseif ($choice -cne "PACK") {
        Write-Host "Cancelled: nothing has been bundled." -ForegroundColor Yellow
        exit 0
    }
} else {
    Write-Host "Pack-only mode: using only artist files already installed on this computer."
}

$build = Join-Path $root "PERSONAL65_BUILD_INFO.json"
$variant = "Python"
if (Test-Path -LiteralPath $build) {
    $metadata = Get-Content -LiteralPath $build -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($metadata.variant -eq "rust") { $variant = "RustHybrid" }
}
# Archive lives BESIDE the app folder, not within it. Existing zip is never overwritten.
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$archive = Join-Path (Split-Path -Parent $root) ("DyberPet-Personal65-" + $variant + "-LocalOffline-" + $timestamp + ".zip")
if (Test-Path -LiteralPath $archive) { throw "Local ZIP destination already exists" }

$bundleReport = Join-Path $reportDir "personal65-local-offline-result.json"
& $helper --role-root $roleRoot --bundle-output $archive --confirm-local-bundle > $bundleReport
if ($LASTEXITCODE -ne 0) { throw "Local role-embedded ZIP failed; no success claimed" }
$result = Get-Content -LiteralPath $bundleReport -Raw -Encoding UTF8 | ConvertFrom-Json
Write-Host ""
Write-Host "LOCAL OFFLINE PACKAGE CREATED: $archive" -ForegroundColor Green
Write-Host "SHA256: $($result.sha256)"
Write-Host "Genshin roles structurally installed: $($result.manifest.genshin_installed_distinct_profiles)"
Write-Host "Guga/Doro real creator assets installed: $($result.manifest.mascot_creator_art_installed)/2"
if (-not $result.manifest.genshin_65_source_target_reached) {
    Write-Warning "This is NOT yet a complete 65/65 art package. Check source installation logs and manual-only entries."
}
Write-Host "You can unzip this locally into a new folder and run Run-DyberPet.cmd offline."
Write-Host "Do NOT upload this private art-inclusive ZIP to GitHub or a public service."
