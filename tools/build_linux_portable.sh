#!/usr/bin/env bash
# Isolated Linux x86_64 review candidate; no external/game artwork is fetched.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "$(uname -s)" != Linux || "$(uname -m)" != x86_64 ]]; then
  echo "Linux x86_64 runner required" >&2
  exit 2
fi

python -m PyInstaller --paths . --noconfirm --clean --onedir \
  --contents-directory . --name DyberPetDesktop \
  --collect-all qfluentwidgets \
  --collect-submodules DyberPet \
  --collect-submodules DyberPet.assistant \
  --hidden-import DyberPet.assistant \
  --hidden-import DyberPet.assistant.portable \
  --hidden-import DyberPet.assistant.character_import_smoke \
  --hidden-import DyberPet.settings \
  --hidden-import DyberPet.DyberPet \
  --collect-data tools \
  --hidden-import tools.chibi_profiles \
  --hidden-import tools.chibi_layout \
  --hidden-import tools.chibi_preview \
  --hidden-import tools.import_codex_pet \
  --hidden-import tools.import_chibi_animations \
  --hidden-import tools.install_native_role \
  --hidden-import tools.character_pipeline \
  --hidden-import tools.genshin_roster \
  --hidden-import tools.genshin_complete_roster \
  --hidden-import tools.genshin_library \
  --hidden-import tools.genshin_role_bindings \
  --hidden-import tools.genshin_batch \
  --hidden-import tools.personal_role_import \
  --hidden-import tools.create_original_mascot \
  --hidden-import tools.generate_mascot_demos \
  --hidden-import tools.mascot_library \
  --hidden-import tools.role_family \
  --hidden-import tools.install_artist_genshin \
  --hidden-import tools.artist_visual_review \
  --hidden-import tools.install_artist_codex \
  --hidden-import tools.install_creator_mascots \
  --hidden-import tools.qchibi_native_threeview \
  --hidden-import tools.qchibi_pose_geometry \
  --hidden-import DyberPet.DyberSettings.qchibi_three_view_dialog \
  --hidden-import tools.role_action_preview \
  --hidden-import tools.character_progress \
  --hidden-import tools.character_catalog_search \
  --hidden-import DyberPet.DyberSettings.character_catalog_dialog \
  --hidden-import DyberPet.DyberSettings.mascot_preview_dialog \
  --hidden-import tools.linux_gui_smoke \
  --collect-submodules backports \
  --hidden-import backports.tarfile \
  --collect-submodules pyttsx3.drivers \
  --collect-all vosk \
  --hidden-import pynput.mouse._xorg \
  --hidden-import pynput.keyboard._xorg \
  run_DyberPet.py

# Fail at build time if PyInstaller failed to embed the actual Python package.
python - <<'PY'
from pathlib import Path
from PyInstaller.archive.readers import ZlibArchiveReader
source = Path("build/DyberPetDesktop/PYZ-00.pyz")
pyz = ZlibArchiveReader(str(source))
names = set(pyz.toc)
for name in ("DyberPet", "DyberPet.assistant",
             "DyberPet.assistant.portable", "DyberPet.DyberPet",
             "tools.genshin_library"):
    print("FROZEN_MODULE_CHECK", name, name in names, flush=True)
assert "DyberPet.assistant.portable" in names, (
    "PyInstaller did not include the required assistant module in PYZ")
PY

package="dist/DyberPetDesktop"
test -x "$package/DyberPetDesktop"
test -d res
cp -a res "$package/res"
# Pre-render truly playable but unmistakably first-party *demo* chibis.
# Never writes to repository assets or overwrites existing user MODs.
python tools/generate_builtin_chibi_demos.py --output-root "$package/res/role"
python tools/generate_mascot_demos.py --output-root "$package/res/role"
# CI deliberately keeps generated frames for runtime-only synthetic QA and
# strips them before distribution. A normal user-built tar contains NO demos.
if [[ "${DYBERPET_QA_KEEP_ABSTRACT_ART:-0}" != "1" ]]; then
  python tools/strip_generated_demo_art.py --role-root "$package/res/role" --expected 125
  "$package/DyberPetDesktop" --personal-package-smoke
fi
mkdir -p "$package/data"
cp docs/pet_assistant.md "$package/ASSISTANT_GUIDE.md"
cp docs/character_fidelity.md "$package/CHARACTER_FIDELITY.md"
cp docs/personal_character_install.md "$package/PERSONAL_CHARACTER_GUIDE.md"
cp docs/guga_doro_personal_install.md "$package/GUGA_DORO_GUIDE.md"
cp docs/original_chibi_starter.md "$package/ORIGINAL_MASCOT_GUIDE.md"
cp docs/linux_acceptance.md "$package/LINUX_ACCEPTANCE.md"

python - <<'PY'
import json
import subprocess
from pathlib import Path
meta = {
    "candidate": "linux-x86_64-ci-review",
    "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
    "python": "3.11", "environment": "Ubuntu 24.04 / X11-Xvfb",
    "unverified_external_character_art": False,
    "voice_models_bundled": False,
    "note": "CI candidate, not a public stable release or hardware/audio endorsement"
}
Path("dist/DyberPetDesktop/BUILD_INFO.json").write_text(
    json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY

archive="DyberPet-Linux-Personal-x86_64.tar.gz"
rm -f "$archive"
tar -czf "$archive" -C dist DyberPetDesktop
test -s "$archive"
printf 'LINUX_PORTABLE_ARCHIVE=%s\n' "$archive"
sha256sum "$archive"
