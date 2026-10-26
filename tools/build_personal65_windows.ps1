# Build both Windows personal65 variants from the exact same source tree.
# Call after installing requirements. Rust mode requires maturin-built dyberpet_native.
param(
    [ValidateSet("python", "rust")][string]$Backend = "python"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$env:DYBERPET_QA_KEEP_ABSTRACT_ART = "0"
$env:DYBERPET_NATIVE_BACKEND = $Backend
if ($Backend -eq "rust") {
    $env:DYBERPET_REQUIRE_RUST = "1"
    & (Join-Path $root "tools/build_windows_portable.ps1") -IncludeRust
} else {
    Remove-Item Env:DYBERPET_REQUIRE_RUST -ErrorAction SilentlyContinue
    & (Join-Path $root "tools/build_windows_portable.ps1")
}
if ($LASTEXITCODE -ne 0) { throw "Desktop PyInstaller failed: $LASTEXITCODE" }

$package = Join-Path $root "dist/DyberPet"
$exe = Join-Path $package "DyberPet.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "Missing Windows executable" }
$installerArgs = @(
    "--noconfirm", "--clean", "--onefile", "--console",
    "--name", "DyberPet-Role-Installer",
    "--distpath", $package,
    "--workpath", (Join-Path $root "build/role-installer"),
    "--specpath", (Join-Path $root "build/role-installer-spec"),
    "--collect-data", "tools",
    "--hidden-import", "tools.personal_source_batch",
    "--hidden-import", "tools.personal_mascot_batch",
    "--hidden-import", "tools.install_creator_mascots",
    "--hidden-import", "tools.mascot_library",
    "--hidden-import", "tools.install_artist_genshin",
    "--hidden-import", "tools.install_artist_codex",
    "--hidden-import", "tools.install_artist_shimeji",
    "--hidden-import", "tools.install_nanopet_shimeji",
    "--hidden-import", "tools.install_external_codex",
    "--hidden-import", "tools.install_pinned_codexpetdb",
    "--hidden-import", "tools.install_personal_codex_zip",
    "--hidden-import", "tools.artist_animation_audit",
    "--hidden-import", "tools.genshin_library",
    "--hidden-import", "tools.character_source_coverage",
    "--hidden-import", "PIL",
    "tools/personal_source_batch.py"
)
python -m PyInstaller @installerArgs
if ($LASTEXITCODE -ne 0) { throw "Personal role installer build failed" }
$helper = Join-Path $package "DyberPet-Role-Installer.exe"
if (-not (Test-Path -LiteralPath $helper)) { throw "Missing personal role installer" }

# Character material is acquired by the user on their own machine, after opt-in.
$roles = Join-Path $package "res/role"
$sourceDirs = @(Get-ChildItem -LiteralPath $roles -Directory -ErrorAction Stop |
    Where-Object { $_.Name -like "Source*" })
if ($sourceDirs.Count -ne 0) { throw "Third-party Source* art accidentally included" }

Copy-Item -LiteralPath (Join-Path $root "docs/personal_source_batch.md") -Destination (Join-Path $package "PERSONAL65_INSTALL.md") -Force

$menu = @'
param([switch]$PreviewOnly, [ValidateRange(1,65)][int]$MaxRoles = 65)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$tool = Join-Path $PSScriptRoot "DyberPet-Role-Installer.exe"
$roleDir = Join-Path $PSScriptRoot "res/role"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
$plan = Join-Path $PSScriptRoot "data/personal65-plan.json"
& $tool --role-root $roleDir --output $plan
if ($LASTEXITCODE -ne 0) { throw "Could not enumerate pinned sources" }
Write-Host "123 character templates; 65 have pinned candidate sources (not 65 preinstalled animations)." -ForegroundColor Yellow
Write-Host "Plan: $plan"
Write-Host "Art sources have separate creator use conditions; verify them before installing."
Write-Host "Source integrity is not a likeness, voice, rights, or physical playback approval."
if ($PreviewOnly) { exit 0 }
$confirm = Read-Host "Type INSTALL to fetch and install up to $MaxRoles creator roles to this PC"
if ($confirm -cne "INSTALL") { Write-Host "Cancelled. No art fetched."; exit 0 }
$report = Join-Path $PSScriptRoot "data/personal65-install-report.json"
& $tool --role-root $roleDir --install --accept-personal-use --max-roles $MaxRoles --output $report
$exit = $LASTEXITCODE
Write-Host "Report: $report"
if ($exit -ne 0) { Write-Warning "Some sources failed. See report for details." }
exit $exit
'@
[System.IO.File]::WriteAllText((Join-Path $package "Install-65-Roles.ps1"), $menu, (New-Object System.Text.UTF8Encoding($false)))
$cmd = '@echo off' + "`r`n" + 'cd /d "%~dp0"' + "`r`n" +
       'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-65-Roles.ps1"' + "`r`n" +
       'pause' + "`r`n"
[System.IO.File]::WriteAllText((Join-Path $package "Install-65-Roles.cmd"), $cmd, (New-Object System.Text.ASCIIEncoding))

# Guga and Doro are two ADDITIONAL mascot sources; not part of the 65 Genshin count.
# Keep both artist atlases off GitHub and outside the portable archive.
$mascotMenu = @'
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$tool = Join-Path $PSScriptRoot "DyberPet-Role-Installer.exe"
$roleDir = Join-Path $PSScriptRoot "res/role"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
$plan = Join-Path $PSScriptRoot "data/personal-guga-doro-plan.json"
& $tool --mascots --role-root $roleDir --output $plan
if ($LASTEXITCODE -ne 0) { throw "Mascot source planning failed" }
Write-Host "Guga and Doro: 2 pinned creator fan-art sources, NOT preinstalled original art." -ForegroundColor Yellow
Write-Host "Artist reuse/voice rights are separate; check source conditions before opt-in."
$confirm = Read-Host "Type INSTALL to download creator fan-art to this PC, or anything else to cancel"
if ($confirm -cne "INSTALL") { Write-Host "Cancelled; no mascot art fetched."; exit 0 }
$report = Join-Path $PSScriptRoot "data/personal-guga-doro-install-report.json"
& $tool --mascots --role-root $roleDir --install --accept-personal-use --output $report
$exit = $LASTEXITCODE
Write-Host "Report: $report"
if ($exit -ne 0) { Write-Warning "Some mascot sources failed; inspect report." }
exit $exit
'@
[System.IO.File]::WriteAllText((Join-Path $package "Install-Guga-Doro.ps1"), $mascotMenu, (New-Object System.Text.UTF8Encoding($false)))
$mascotCmd = '@echo off' + "`r`n" + 'cd /d "%~dp0"' + "`r`n" +
            'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-Guga-Doro.ps1"' + "`r`n" +
            'pause' + "`r`n"
[System.IO.File]::WriteAllText((Join-Path $package "Install-Guga-Doro.cmd"), $mascotCmd, (New-Object System.Text.ASCIIEncoding))

$launcher = if ($Backend -eq "rust") {
    '@echo off' + "`r`n" + 'cd /d "%~dp0"' + "`r`n" +
    'set "DYBERPET_NATIVE_BACKEND=rust"' + "`r`n" +
    'set "DYBERPET_REQUIRE_RUST=1"' + "`r`n" +
    '"%~dp0DyberPet.exe"' + "`r`n"
} else {
    '@echo off' + "`r`n" + 'cd /d "%~dp0"' + "`r`n" +
    'set "DYBERPET_NATIVE_BACKEND=python"' + "`r`n" +
    '"%~dp0DyberPet.exe"' + "`r`n"
}
[System.IO.File]::WriteAllText((Join-Path $package "Run-DyberPet.cmd"), $launcher, (New-Object System.Text.ASCIIEncoding))

# Verify the FROZEN helper can enumerate exactly the same 65 fixed-source characters.
$smokeDir = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { Join-Path $root "build/personal65-qa" }
New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null
$reportPath = Join-Path $smokeDir ("personal65-plan-" + $Backend + ".json")
& $helper --output $reportPath
if ($LASTEXITCODE -ne 0) { throw "Frozen personal source planner failed" }
$report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($report.summary.selected_profiles -ne 123 -or
    $report.summary.missing_source -ne 58 -or
    ($report.summary.ready_for_opt_in + $report.summary.manual_import_only + $report.summary.already_installed_structurally) -ne 65) {
    throw "Expected 65 pinned-source profiles, 58 uncovered, and 123 total: $($report.summary | ConvertTo-Json -Compress)"
}
if ($report.summary.already_installed_structurally -ne 0) { throw "Creator art was prebundled" }

$mascotReportPath = Join-Path $smokeDir ("personal-mascots-" + $Backend + ".json")
& $helper --mascots --role-root $roles --output $mascotReportPath
if ($LASTEXITCODE -ne 0) { throw "Frozen mascot source planner failed" }
$mascots = Get-Content -LiteralPath $mascotReportPath -Raw -Encoding UTF8 | ConvertFrom-Json
if ($mascots.summary.mascot_templates -ne 2 -or
    $mascots.summary.ready_for_opt_in -ne 2 -or
    $mascots.summary.installed_creator_profiles -ne 0) {
    throw "Guga/Doro real artist art was already bundled or mascot installer unusable"
}

# Verify packaged EXE and REQUIRE_RUST on the actual native compiled mode.
$env:QT_QPA_PLATFORM = "offscreen"
$env:DYBERPET_SMOKE_REPORT = Join-Path $smokeDir ("personal65-desktop-smoke-" + $Backend + ".json")
Push-Location $package
try {
    & $exe --assistant-smoke
    if ($LASTEXITCODE -ne 0) { throw "Frozen desktop assistant smoke failed" }
} finally {
    Pop-Location
}
$smoke = Get-Content -LiteralPath $env:DYBERPET_SMOKE_REPORT -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $smoke.assistant_dialog -or -not $smoke.assets.ok -or $smoke.native_backend.active -ne $Backend) {
    throw "Desktop helper/Qt/native backend smoke failed for $Backend"
}
if ($Backend -eq "rust" -and -not $smoke.native_backend.rust_available) {
    throw "Rust extension not available in frozen executable"
}
$metaPath = Join-Path $package "PERSONAL65_BUILD_INFO.json"
@{
    source_commit = (git rev-parse HEAD).Trim()
    variant = $Backend
    rust_is_optional_python_extension = ($Backend -eq "rust")
    character_templates = 123
    pinned_source_characters = 65
    missing_source_characters = 58
    prebundled_third_party_art = $false
    private_personal_use = $true
    release_is_prerelease = $true
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $metaPath -Encoding UTF8

$archiveName = if ($Backend -eq "rust") { "DyberPet-Personal65-Windows-RustHybrid.zip" } else { "DyberPet-Personal65-Windows-Python.zip" }
$archive = Join-Path $root $archiveName
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
Compress-Archive -Path (Join-Path $package "*") -DestinationPath $archive -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $archive)) { throw "Final portable archive missing" }
$sha = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output "PRIVATE65_ARCHIVE=$archive"
Write-Output "PRIVATE65_SHA256=$sha"
