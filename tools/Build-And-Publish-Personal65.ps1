# One-command local fallback when GitHub hosted private runners refuse to start.
# Builds both portable variants, audits them, optionally publishes to the private repo.
param([switch]$Publish)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
if ($env:OS -ne "Windows_NT") { throw "Run this script using Windows PowerShell on Windows x64" }
$branch = (git branch --show-current).Trim()
if ($branch -ne "release/personal65-python-rust-20261026") {
    throw "Checkout release/personal65-python-rust-20261026 first (current: $branch)"
}
$dirty = @(git status --porcelain)
if ($dirty.Count -gt 0) { throw "Commit/stash local modifications before building; do not risk mixing private assets" }
$sha = (git rev-parse HEAD).Trim()
Write-Host "Source commit: $sha"

$python = Get-Command py -ErrorAction SilentlyContinue
if (-not $python) { throw "Python 3.11 launcher missing. Install Python 3.11 (64-bit) first." }
& py -3.11 -c "import sys; assert sys.maxsize > 2**32; print(sys.version)"
if ($LASTEXITCODE -ne 0) { throw "Python 3.11 x64 required" }
$venv = Join-Path $root ".venv-personal65"
if (-not (Test-Path -LiteralPath (Join-Path $venv "Scripts/python.exe"))) {
    & py -3.11 -m venv $venv
    if ($LASTEXITCODE -ne 0) { throw "Python virtual environment creation failed" }
}
$env:PATH = (Join-Path $venv "Scripts") + ";" + $env:PATH
python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed" }
python -m pip install -r requirements-windows-portable.txt
if ($LASTEXITCODE -ne 0) { throw "Windows build dependency installation failed" }
python -m unittest discover -s tests -p "test_personal_source_batch.py" -v
if ($LASTEXITCODE -ne 0) { throw "Offline personal source planner tests failed" }

# Complete Python distribution.
& (Join-Path $root "tools/build_personal65_windows.ps1") -Backend python
if ($LASTEXITCODE -ne 0) { throw "Python release build failed" }

# Complete Rust extension, still using the same PySide6 desktop UI.
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Rust toolchain missing. Install rustup + stable MSVC Rust before local Rust-hybrid build."
}
if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    throw "rustc missing. Install a stable Rust MSVC toolchain."
}
python -m pip install "maturin>=1.7,<2"
if ($LASTEXITCODE -ne 0) { throw "maturin installation failed" }
maturin build --release --manifest-path rust/pet_core/Cargo.toml --interpreter python --out wheelhouse
if ($LASTEXITCODE -ne 0) { throw "Rust wheel failed to compile" }
python -m pip install --no-index --find-links wheelhouse dyberpet-native-core
if ($LASTEXITCODE -ne 0) { throw "Native core wheel could not be installed" }
$env:DYBERPET_NATIVE_BACKEND = "rust"
python -c "from DyberPet.assistant.native_bridge import backend_status; r=backend_status(); print(r); assert r['active']=='rust'"
if ($LASTEXITCODE -ne 0) { throw "Rust extension was not activated" }
python -m unittest discover -s tests -p "test_rust_bridge.py" -v
if ($LASTEXITCODE -ne 0) { throw "Rust parity tests failed" }
& (Join-Path $root "tools/build_personal65_windows.ps1") -Backend rust
if ($LASTEXITCODE -ne 0) { throw "Rust-hybrid release build failed" }

$pythonZip = Join-Path $root "DyberPet-Personal65-Windows-Python.zip"
$rustZip = Join-Path $root "DyberPet-Personal65-Windows-RustHybrid.zip"
foreach ($item in @($pythonZip, $rustZip)) {
    if (-not (Test-Path -LiteralPath $item)) { throw "Missing output: $item" }
}
$manifest = Join-Path $root "SHA256SUMS.txt"
$lines = @($pythonZip, $rustZip) | ForEach-Object {
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $_).Hash.ToLowerInvariant()
    "$hash  $(Split-Path $_ -Leaf)"
}
[System.IO.File]::WriteAllLines($manifest, $lines, (New-Object System.Text.UTF8Encoding($false)))
Write-Host "Both outputs built from commit $sha"
$lines | ForEach-Object { Write-Host $_ }

if ($Publish) {
    if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "GitHub CLI missing; install gh and login with 'gh auth login' before -Publish"
    }
    gh auth status
    if ($LASTEXITCODE -ne 0) { throw "GitHub CLI login required" }
    $private = gh api repos/clonetimer/DyberPet --jq ".private"
    if ($LASTEXITCODE -ne 0 -or $private.Trim() -ne "true") {
        throw "Refusing upload: cannot verify private GitHub repository"
    }
    $tag = "v0.13.0-private65-rc1"
    $existing = gh release view $tag --repo clonetimer/DyberPet --json tagName 2>$null
    if ($LASTEXITCODE -eq 0) {
        gh release upload $tag $pythonZip $rustZip $manifest --clobber --repo clonetimer/DyberPet
    } else {
        gh release create $tag $pythonZip $rustZip $manifest --repo clonetimer/DyberPet --target $sha --title "DyberPet Personal65 - Python and Rust-hybrid (Private RC1)" --prerelease --latest=false --notes "Personal-use prerelease: 66 exact-source candidates across 123 templates (57 missing); these are not 66 preinstalled animated characters. Two Windows x64 portable variants with a local opt-in role installer. Third-party art and original voice are never embedded or uploaded. Visual/voice and physical Windows user tests remain pending."
    }
    if ($LASTEXITCODE -ne 0) { throw "Private GitHub Release publish failed" }
    gh release view $tag --repo clonetimer/DyberPet --json url,assets,isPrerelease
}
