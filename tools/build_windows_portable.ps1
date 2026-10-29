# Review-only DyberPet Windows portable package. Run from repo root.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$argsPy = @("--noconfirm", "--clean", "--onedir", "--noconsole", "--contents-directory", ".", "--name", "DyberPet", "--collect-all", "qfluentwidgets", "--collect-submodules", "DyberPet.assistant", "--collect-data", "tools", "--hidden-import", "tools.chibi_profiles", "--hidden-import", "tools.chibi_layout", "--hidden-import", "tools.chibi_preview", "--hidden-import", "tools.import_codex_pet", "--hidden-import", "tools.import_chibi_animations", "--hidden-import", "tools.install_native_role", "--hidden-import", "tools.character_pipeline", "--hidden-import", "tools.genshin_roster", "--hidden-import", "tools.genshin_library", "--hidden-import", "tools.genshin_role_bindings", "--hidden-import", "tools.genshin_complete_roster", "--hidden-import", "tools.genshin_batch", "--hidden-import", "tools.personal_role_import", "--hidden-import", "tools.create_original_mascot", "--hidden-import", "tools.generate_mascot_demos", "--hidden-import", "tools.mascot_library", "--hidden-import", "tools.role_family", "--hidden-import", "tools.install_creator_mascots", "--hidden-import", "tools.install_artist_genshin", "--hidden-import", "tools.artist_visual_review", "--hidden-import", "tools.install_artist_codex", "--hidden-import", "tools.role_action_preview", "--hidden-import", "tools.qchibi_native_threeview", "--hidden-import", "tools.qchibi_threeview_audit", "--hidden-import", "tools.doro_live2d_local", "--hidden-import", "tools.doro_personal_setup", "--hidden-import", "tools.doro_live2d_interaction", "--hidden-import", "DyberPet.DyberSettings.doro_live2d_dialog", "--collect-all", "live2d", "--collect-submodules", "OpenGL", "--hidden-import", "tools.qchibi_pose_geometry", "--hidden-import", "tools.native_gesture_catalog", "--hidden-import", "tools.pet_pointer_gestures", "--hidden-import", "tools.native_sprite_canvas", "--hidden-import", "DyberPet.DyberSettings.qchibi_three_view_dialog", "--hidden-import", "tools.character_progress", "--hidden-import", "tools.character_catalog_search", "--hidden-import", "DyberPet.DyberSettings.character_catalog_dialog", "--hidden-import", "DyberPet.DyberSettings.mascot_preview_dialog", "--collect-submodules", "pyttsx3.drivers", "--collect-all", "vosk", "--hidden-import", "pynput.mouse._win32", "--hidden-import", "pynput.keyboard._win32", "run_DyberPet.py")
python -m PyInstaller @argsPy
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
$package = Join-Path $root "dist/DyberPet"
$exe = Join-Path $package "DyberPet.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "EXE not found: $exe" }
# Keep res/ editable beside the executable; do not embed user character art.
Copy-Item -LiteralPath (Join-Path $root "res") -Destination (Join-Path $package "res") -Recurse -Force
# Generate first-party geometric chibi demo frames for every roster profile.
# Does not overwrite imported character art; no copyrighted assets downloaded.
python tools/generate_builtin_chibi_demos.py --output-root (Join-Path $package "res/role")
if ($LASTEXITCODE -ne 0) { throw "Bundled Genshin demos did not generate" }
python tools/generate_mascot_demos.py --output-root (Join-Path $package "res/role")
if ($LASTEXITCODE -ne 0) { throw "Bundled character demos did not generate" }
# QA may need synthetic role frames for executable animation tests. Normal
# personal build MUST NOT ship the 125 generic lookalikes as real characters.
if ($env:DYBERPET_QA_KEEP_ABSTRACT_ART -ne "1") {
  python tools/strip_generated_demo_art.py --role-root (Join-Path $package "res/role") --expected 125
  if ($LASTEXITCODE -ne 0) { throw "Failed to remove placeholder demo art from personal package" }
  & $exe --personal-package-smoke
  if ($LASTEXITCODE -ne 0) { throw "Personal candidate art policy smoke failed" }
}
# Retain an honest inventory of ACTUAL bundled source images. Missing
# independent views are recorded, not fabricated; malformed/mirrored sources
# block packaging, while normal native-only characters remain playable.
$threeviewReport = Join-Path $package "THREEVIEW_AUDIT.json"
python tools/qchibi_threeview_audit.py --role-root (Join-Path $package "res/role") --out $threeviewReport --fail-on-invalid
if ($LASTEXITCODE -ne 0) { throw "Packaged Q-chibi three-view evidence audit failed" }
New-Item -ItemType Directory -Force -Path (Join-Path $package "data") | Out-Null
Copy-Item -LiteralPath (Join-Path $root "docs/pet_assistant.md") -Destination (Join-Path $package "ASSISTANT_GUIDE.md")
Copy-Item -LiteralPath (Join-Path $root "docs/character_fidelity.md") -Destination (Join-Path $package "CHARACTER_FIDELITY.md")
Copy-Item -LiteralPath (Join-Path $root "docs/qchibi_threeview_gate.md") -Destination (Join-Path $package "THREEVIEW_GUIDE.md")
Copy-Item -LiteralPath (Join-Path $root "docs/personal_character_install.md") -Destination (Join-Path $package "PERSONAL_CHARACTER_GUIDE.md")
Copy-Item -LiteralPath (Join-Path $root "docs/guga_doro_personal_install.md") -Destination (Join-Path $package "GUGA_DORO_GUIDE.md")
Copy-Item -LiteralPath (Join-Path $root "docs/original_chibi_starter.md") -Destination (Join-Path $package "ORIGINAL_MASCOT_GUIDE.md")
$commit = (git rev-parse HEAD).Trim()
$meta = @{candidate="portable-ci-review";source_commit=$commit;note="Not an official release; no unverified third-party character or voice packs.";optional_services=@("LM Studio localhost","PPL Character Governance localhost");voice="Vosk language model provided separately by user"} | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText((Join-Path $package "BUILD_INFO.json"), $meta, (New-Object System.Text.UTF8Encoding($false)))
$zip = Join-Path $root "DyberPet-Windows-Personal-PR5.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $package "*") -DestinationPath $zip -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $zip)) { throw "ZIP creation failed" }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
Write-Output "PORTABLE_ZIP=$zip"
Write-Output "PORTABLE_SHA256=$hash"
