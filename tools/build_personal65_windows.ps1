# Build both Windows personal65 variants from the exact same source tree.
# Call after installing requirements. Rust mode requires maturin-built dyberpet_native.
param(
    [ValidateSet("python", "rust")][string]$Backend = "python"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
# Keep temporary demo art only during the deep frozen Qt/action smoke.
# It MUST be stripped after that smoke and before user ZIP creation.
$env:DYBERPET_QA_KEEP_ABSTRACT_ART = "1"
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
    "--hidden-import", "tools.local_offline_bundle",
    "--hidden-import", "tools.personal_mascot_batch",
    "--hidden-import", "tools.install_creator_mascots",
    "--hidden-import", "tools.mascot_library",
    "--hidden-import", "tools.install_artist_genshin",
    "--hidden-import", "tools.install_artist_codex",
    "--hidden-import", "tools.install_artist_shimeji",
    "--hidden-import", "tools.install_nanopet_shimeji",
    "--hidden-import", "tools.install_external_codex",
    "--hidden-import", "tools.install_pinned_codexpetdb",
    "--hidden-import", "tools.install_pinned_kaveh_shimeji",
    "--hidden-import", "tools.install_pinned_eula_shimeji",
    "--hidden-import", "tools.probe_artist_eula_fanbox",
    "--hidden-import", "tools.probe_shimejishop_kaveh",
    "--hidden-import", "tools.install_verified_react_lfs",
    "--hidden-import", "tools.probe_missing_react_lfs",
    "--hidden-import", "tools.react_shimeji_source_leads",
    "--hidden-import", "tools.install_pinned_react_shimeji",
    "--hidden-import", "tools.install_personal_shimeji_zip",
    "--hidden-import", "tools.install_personal_codex_zip",
    "--hidden-import", "tools.artist_animation_audit",
    "--hidden-import", "tools.creator_motion_quality",
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

# Personal-only complete offline bundle generation: the art does not enter
# hosted CI or any GitHub Release, even when the repository is private.
Copy-Item -LiteralPath (Join-Path $root "tools/Make-Personal65-Offline.ps1") `
    -Destination (Join-Path $package "Make-Personal65-Offline.ps1") -Force
$fullPackCmd = '@echo off' + "`r`n" +
    'cd /d "%~dp0"' + "`r`n" +
    'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Make-Personal65-Offline.ps1"' + "`r`n" +
    'pause' + "`r`n"
[System.IO.File]::WriteAllText((Join-Path $package "Make-My-Offline-DyberPet.cmd"),
    $fullPackCmd, (New-Object System.Text.ASCIIEncoding))


$menu = @'
param([switch]$PreviewOnly, [ValidateRange(1,123)][int]$MaxRoles = 123)
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$tool = Join-Path $PSScriptRoot "DyberPet-Role-Installer.exe"
$roleDir = Join-Path $PSScriptRoot "res/role"
New-Item -ItemType Directory -Force -Path (Join-Path $PSScriptRoot "data") | Out-Null
$plan = Join-Path $PSScriptRoot "data/personal65-plan.json"
& $tool --role-root $roleDir --output $plan
if ($LASTEXITCODE -ne 0) { throw "Could not enumerate pinned sources" }
$manifest = Get-Content -LiteralPath $plan -Raw -Encoding UTF8 | ConvertFrom-Json
$available = $manifest.summary.ready_for_opt_in + $manifest.summary.already_installed_structurally + $manifest.summary.manual_import_only
Write-Host "123 character templates; $available have fixed candidate sources (not $available preinstalled animations)." -ForegroundColor Yellow
$MaxRoles = [Math]::Min($MaxRoles, [int]$available)
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
# Existing shortcut is supported, but avoid hard-coding the historical 65-role
# count in the new user-facing entry point.
[System.IO.File]::WriteAllText((Join-Path $package "Install-Available-Roles.ps1"), $menu, (New-Object System.Text.UTF8Encoding($false)))
$cmd = '@echo off' + "`r`n" + 'cd /d "%~dp0"' + "`r`n" +
       'powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-65-Roles.ps1"' + "`r`n" +
       'pause' + "`r`n"
[System.IO.File]::WriteAllText((Join-Path $package "Install-65-Roles.cmd"), $cmd, (New-Object System.Text.ASCIIEncoding))
$availableCmd = $cmd.Replace("Install-65-Roles.ps1", "Install-Available-Roles.ps1")
[System.IO.File]::WriteAllText((Join-Path $package "Install-Available-Roles.cmd"), $availableCmd, (New-Object System.Text.ASCIIEncoding))

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

# Verify packaged executable and its planning ledger agree with the
# 123-character registry. New creators can increase source coverage without
# breaking an unrelated EXE build because of a stale equality assertion.
$smokeDir = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { Join-Path $root "build/personal65-qa" }
New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null
$reportPath = Join-Path $smokeDir ("personal65-plan-" + $Backend + ".json")
& $helper --output $reportPath
if ($LASTEXITCODE -ne 0) { throw "Frozen personal source planner failed" }
$report = Get-Content -LiteralPath $reportPath -Raw -Encoding UTF8 | ConvertFrom-Json
$sourceCount = [int]$report.summary.ready_for_opt_in + [int]$report.summary.manual_import_only + [int]$report.summary.already_installed_structurally
$missingCount = [int]$report.summary.missing_source
if ($report.summary.selected_profiles -ne 123 -or
    $sourceCount -lt 66 -or
    $sourceCount + $missingCount -ne 123 -or
    $report.summary.manual_import_only -ne 0 -or
    $report.summary.already_installed_structurally -ne 0) {
    throw "Frozen source planner inconsistent with the 123-profile registry or R23 floor of 66 pinned sources: $($report.summary | ConvertTo-Json -Compress)"
}
Write-Host "Validated $sourceCount pinned-source candidates and $missingCount missing among 123 profiles. Neither implies installed artwork."
if ($report.summary.already_installed_structurally -ne 0) { throw "Creator art was prebundled" }

# Ensure the frozen role installer knows about the offline archive workflow;
# refusing to bundle without a local opt-in must not create an output file.
$unusedOutput = Join-Path $smokeDir ("no-consent-" + $Backend + ".zip")
& $helper --role-root $roles --bundle-output $unusedOutput
if ($LASTEXITCODE -eq 0 -or (Test-Path -LiteralPath $unusedOutput)) {
    throw "Offline art packer bypassed local consent"
}
if (-not (Test-Path -LiteralPath (Join-Path $package "Make-My-Offline-DyberPet.cmd"))) {
    throw "Personal offline bundling entry point not packaged"
}


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
# PyInstaller --noconsole is a Windows GUI executable: PowerShell '&' may return
# before it exits. Start-Process -Wait makes missing-report checks deterministic.
$smokeProcess = Start-Process -FilePath $exe -ArgumentList "--assistant-smoke" -WorkingDirectory $package -Wait -PassThru
if ($smokeProcess.ExitCode -ne 0) { throw "Frozen desktop assistant smoke failed: $($smokeProcess.ExitCode)" }
if (-not (Test-Path -LiteralPath $env:DYBERPET_SMOKE_REPORT)) { throw "Frozen desktop did not produce its smoke report" }
$smoke = Get-Content -LiteralPath $env:DYBERPET_SMOKE_REPORT -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $smoke.assistant_dialog -or -not $smoke.assets.ok -or $smoke.native_backend.active -ne $Backend) {
    throw "Desktop helper/Qt/native backend smoke failed for $Backend"
}
if ($Backend -eq "rust" -and -not $smoke.native_backend.rust_available) {
    throw "Rust extension not available in frozen executable"
}
# After deep Qt smoke, eliminate all 123 generic Genshin + 2 generic
# mascot placeholders from FINAL user package. Never delete imported author art.
python tools/strip_generated_demo_art.py --role-root $roles --expected 125
if ($LASTEXITCODE -ne 0) { throw "Failed to remove 125 QA-only chibi placeholders" }
$personalProcess = Start-Process -FilePath $exe -ArgumentList "--personal-package-smoke" -WorkingDirectory $package -Wait -PassThru
if ($personalProcess.ExitCode -ne 0) { throw "Final user binary still contains placeholders" }
# Intermediate QA ZIP contains temporary synthesized art and MUST NEVER ship.
$intermediate = if ($Backend -eq "rust") {
    Join-Path $root "DyberPet-Windows-Rust-Experimental.zip"
} else {
    Join-Path $root "DyberPet-Windows-Personal-PR5.zip"
}
if (Test-Path -LiteralPath $intermediate) {
    Remove-Item -LiteralPath $intermediate -Force
}

$metaPath = Join-Path $package "PERSONAL65_BUILD_INFO.json"
@{
    source_commit = (git rev-parse HEAD).Trim()
    variant = $Backend
    rust_is_optional_python_extension = ($Backend -eq "rust")
    character_templates = 123
    pinned_source_characters = $sourceCount
    missing_source_characters = $missingCount
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
