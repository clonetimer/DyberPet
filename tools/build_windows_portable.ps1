# Review-only DyberPet Windows portable package. Run from repo root.
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$argsPy = @("--noconfirm", "--clean", "--onedir", "--noconsole", "--contents-directory", ".", "--name", "DyberPet", "--collect-all", "qfluentwidgets", "--collect-submodules", "DyberPet.assistant", "--collect-data", "tools", "--hidden-import", "tools.chibi_profiles", "--hidden-import", "tools.chibi_layout", "--hidden-import", "tools.chibi_preview", "--hidden-import", "tools.import_codex_pet", "--hidden-import", "tools.import_chibi_animations", "--hidden-import", "tools.install_native_role", "--hidden-import", "tools.character_pipeline", "--collect-submodules", "pyttsx3.drivers", "--collect-all", "vosk", "--hidden-import", "pynput.mouse._win32", "--hidden-import", "pynput.keyboard._win32", "run_DyberPet.py")
python -m PyInstaller @argsPy
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }
$package = Join-Path $root "dist/DyberPet"
$exe = Join-Path $package "DyberPet.exe"
if (-not (Test-Path -LiteralPath $exe)) { throw "EXE not found: $exe" }
# Keep res/ editable beside the executable; do not embed user character art.
Copy-Item -LiteralPath (Join-Path $root "res") -Destination (Join-Path $package "res") -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $package "data") | Out-Null
Copy-Item -LiteralPath (Join-Path $root "docs/pet_assistant.md") -Destination (Join-Path $package "ASSISTANT_GUIDE.md")
Copy-Item -LiteralPath (Join-Path $root "docs/character_fidelity.md") -Destination (Join-Path $package "CHARACTER_FIDELITY.md")
$commit = (git rev-parse HEAD).Trim()
$meta = @{candidate="portable-ci-review";source_commit=$commit;note="Not an official release; no unverified third-party character or voice packs.";optional_services=@("LM Studio localhost","PPL Character Governance localhost");voice="Vosk language model provided separately by user"} | ConvertTo-Json -Depth 4
[System.IO.File]::WriteAllText((Join-Path $package "BUILD_INFO.json"), $meta, (New-Object System.Text.UTF8Encoding($false)))
$zip = Join-Path $root "DyberPet-Windows-Portable-PR2.zip"
if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
Compress-Archive -Path (Join-Path $package "*") -DestinationPath $zip -CompressionLevel Optimal
if (-not (Test-Path -LiteralPath $zip)) { throw "ZIP creation failed" }
$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $zip).Hash
Write-Output "PORTABLE_ZIP=$zip"
Write-Output "PORTABLE_SHA256=$hash"
