# DyberPet Windows Portable — main personal candidate

**Purpose:** Produce a review-only portable Windows folder; not an official release, not yet a signed installer or a verified audio-device build.

## One-command build (PowerShell, Windows)

Clone `clonetimer/DyberPet` and check out `main`. Use Python 3.11.

```powershell
python -m pip install -r requirements-windows-portable.txt
powershell -ExecutionPolicy Bypass -File tools/build_windows_portable.ps1
```

The build creates `dist/DyberPet/DyberPet.exe` plus **editable** `res/` and `data/` directories. **正常个人构建默认移除 125 套程序生成的低保真角色画面**，只保留原项目自带角色与公开作者素材安装工具。角色模板清单仍保留，但真实角色素材在用户本机按需下载。CI 仅为运行真实 EXE 动画回归临时生成演示帧，并在上传 ZIP 前再次剔除。 The current script generates `DyberPet-Windows-Personal-PR5.zip` with SHA-256 in the build log (legacy file name; it includes later merged features too). Do not extract into `C:\Program Files` because the legacy application still writes under the portable `data` directory; use a user-writable directory such as Documents. Running the EXE should not require Python to be installed.

**CI:** `.github/workflows/windows-portable.yml` packages the app on Windows and executes the **packaged EXE**, not merely Python modules. It launches from a different working directory with `--assistant-smoke`, sets `QT_QPA_PLATFORM=offscreen`, reads a JSON report, checks the native Qt assistant dialog, editable resources, imports of pyttsx3, Vosk and sounddevice, and **performs a real PNG-to-role conversion using a disposable synthetic sprite**. The converter must produce action frames and a preview, and the built role must pass the DyberPet role structure validator. The package explicitly includes Pillow, character importer modules and their source registry metadata. A successful CI run attaches a ZIP artifact for 14 days. The test does not start microphone hardware, LM Studio or PPL.

## Local post-download testing

1. Unzip into a user-writable folder; leave `DyberPet.exe`, `res`, `data`, dynamic libraries and bundled Python modules **together**. Do not run the EXE from inside the ZIP.
2. Launch `DyberPet.exe`; it will select its executable folder as the resource root even when started from a shortcut or another working directory.
3. Right-click the pet and choose `Desktop Pet Assistant (Files / Voice / Persona)`. Create a new `note.txt` in the dedicated Documents workspace, then move it to the app's recoverable area and restore it.
4. Test default `Kitty` first. Configure LM Studio and PPL only if you run them separately; disabled integrations must not prevent basic desktop pet behavior.
5. If desired, download a local Vosk recognition model separately, grant microphone permissions and test `录音识别（4秒）`; check Chinese TTS availability on that Windows computer. The acoustic model, copyrighted audio and voice cloning models are **never** included in the ZIP.
6. Check actions, DPI, multi-monitor behavior, taskbar/tray, closing/reopening dialogs, and available character sprite packs **on a real Windows desktop**. A headless Actions smoke does not certify these.

## Verify built-in character importing (without installing Python)

In the unpacked portable application open **System → Character Management → Add Character**. Select one local asset that you have permission to use: an original main-role ZIP, an extracted DyberPet main-role folder, a Codex Pets atlas, or a GIF/PNG animation folder. The converter can create a preview; choose a Q-style template only if suitable for the artwork. **A template is not a model, and no third-party character images or audio are fetched.**

The automated EXE smoke uses temporary, original geometry and leaves `res/role` untouched. It verifies packaging dependencies but **cannot** certify the quality of any downloaded third-party character or long-running live Windows UI behavior. Keep real art/voice permission evidence separate from the package.

## Boundary and known gaps

- This is a **portable ZIP candidate**, not an MSI/NSIS installer, service, or automatic updater. The implementation has been merged into `main`; no official GitHub Stable Release, MSI/NSIS installer, or code-signing certification has been completed.
- Some older DyberPet code stores saves relative to the executable; choose a writable folder. Data migration/backup and a signed installer are not yet implemented.
- Character source and speech fidelity still require separately verified, licensed materials. CI only packages the already tracked resources.
- If Windows security products block execution, record the executable hash and exact warning. Do not disable security protections as a workaround.
- Voice import tests do not exercise audio drivers, audio output timing, or actual mic capture.
