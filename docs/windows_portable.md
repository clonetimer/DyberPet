# DyberPet Windows Portable — PR #2 Candidate

**Purpose:** Produce a review-only portable Windows folder; not an official release, not yet a signed installer or a verified audio-device build.

## One-command build (PowerShell, Windows)

Clone the development branch `feat/pet-actions-voice-persona-20261023`. Use Python 3.11.

```powershell
python -m pip install -r requirements-windows-portable.txt
powershell -ExecutionPolicy Bypass -File tools/build_windows_portable.ps1
```

The build creates `dist/DyberPet/DyberPet.exe` plus **editable** `res/` and `data/` directories. It also generates `DyberPet-Windows-Portable-PR2.zip` with SHA-256 in the build log. Do not extract into `C:\Program Files` because the legacy application still writes under the portable `data` directory; use a user-writable directory such as Documents. Running the EXE should not require Python to be installed.

**CI:** `.github/workflows/windows-portable.yml` packages the app on Windows and executes the **packaged EXE**, not merely Python modules. It launches from a different working directory with `--assistant-smoke`, sets `QT_QPA_PLATFORM=offscreen`, reads a JSON report, checks the native Qt assistant dialog, editable resources, and imports of pyttsx3, Vosk and sounddevice. A successful CI run attaches a ZIP artifact for 14 days. The test does not start microphone hardware, LM Studio or PPL.

## Local post-download testing

1. Unzip into a user-writable folder; leave `DyberPet.exe`, `res`, `data`, dynamic libraries and bundled Python modules **together**. Do not run the EXE from inside the ZIP.
2. Launch `DyberPet.exe`; it will select its executable folder as the resource root even when started from a shortcut or another working directory.
3. Right-click the pet and choose `Desktop Pet Assistant (Files / Voice / Persona)`. Create a new `note.txt` in the dedicated Documents workspace, then move it to the app's recoverable area and restore it.
4. Test default `Kitty` first. Configure LM Studio and PPL only if you run them separately; disabled integrations must not prevent basic desktop pet behavior.
5. If desired, download a local Vosk recognition model separately, grant microphone permissions and test `录音识别（4秒）`; check Chinese TTS availability on that Windows computer. The acoustic model, copyrighted audio and voice cloning models are **never** included in the ZIP.
6. Check actions, DPI, multi-monitor behavior, taskbar/tray, closing/reopening dialogs, and available character sprite packs **on a real Windows desktop**. A headless Actions smoke does not certify these.

## Boundary and known gaps

- This is a **portable ZIP candidate**, not an MSI/NSIS installer, service, or automatic updater. No main-branch merge or GitHub Release is part of this change.
- Some older DyberPet code stores saves relative to the executable; choose a writable folder. Data migration/backup and a signed installer are not yet implemented.
- Character source and speech fidelity still require separately verified, licensed materials. CI only packages the already tracked resources.
- If Windows security products block execution, record the executable hash and exact warning. Do not disable security protections as a workaround.
- Voice import tests do not exercise audio drivers, audio output timing, or actual mic capture.
