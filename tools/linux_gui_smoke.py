"""X11/Xvfb acceptance of real character-management widgets on Linux.

This test uses a disposable HOME from the CI workflow, real PySide6 and
qfluentwidgets, no third-party character artwork or microphone/audio device.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from unittest.mock import patch


def verify_linux_gui():
    if sys.platform != "linux":
        raise RuntimeError("Linux-only X11/Xvfb GUI acceptance")
    if os.getenv("QT_QPA_PLATFORM") == "offscreen":
        raise RuntimeError("Linux GUI acceptance must use XCB/Xvfb, not offscreen")
    from PySide6.QtWidgets import QApplication, QInputDialog
    from DyberPet.assistant.portable import resource_root, inspect_assets
    import DyberPet.settings as settings
    from DyberPet.DyberSettings.CharCardUI import CharInterface
    from tools.genshin_library import scan_genshin_library
    from tools.mascot_library import scan_mascot_library

    root = resource_root(__file__)
    if getattr(sys, "frozen", False):
        expected = Path(sys.executable).resolve().parent
    else:
        expected = Path(__file__).resolve().parents[1]
    if root != expected or Path(settings.BASEDIR).resolve() != expected:
        raise RuntimeError("Linux frozen resource root differs from executable directory")
    assets = inspect_assets(root)
    if not assets["ok"]:
        raise RuntimeError("Missing runtime assets: " + repr(assets["missing"]))
    app = QApplication.instance() or QApplication([])
    if app.primaryScreen() is None:
        raise RuntimeError("No actual X11 screen (Xvfb display missing)")

    window = CharInterface(sizeHintDyber=(960, 780))
    try:
        window.resize(820, 720)
        window.show()
        app.processEvents()
        if not window.isVisible():
            raise RuntimeError("Character management window failed to show")
        if not window.catalogButton.isEnabled():
            raise RuntimeError("Genshin collection action is disabled")
        if not window.mascotButton.isEnabled():
            raise RuntimeError("Guga / Doro status action is disabled")
        with patch.object(QInputDialog, "getItem", return_value=("", False)) as mascot_dialog:
            window._showMascotLibrary()
            if not mascot_dialog.called:
                raise RuntimeError("Guga / Doro selection dialog did not open")
        with patch.object(QInputDialog, "getItem", return_value=("", False)) as select:
            window._showGenshinLibrary()
            if not select.called:
                raise RuntimeError("Character collection dialog did not open")
        local_catalog = scan_genshin_library(Path(settings.BASEDIR) / "res" / "role")
        mascot_catalog = scan_mascot_library(Path(settings.BASEDIR) / "res" / "role")
        if local_catalog["summary"]["template_count"] != 123:
            raise RuntimeError("Genshin character catalogue not loaded in Linux UI")
        expected_demos = 123 if getattr(sys, "frozen", False) else 0
        if (getattr(sys, "frozen", False) and
                local_catalog["summary"]["original_demo_profile_count"] != expected_demos):
            raise RuntimeError("Linux packaged GUI does not have all 123 rendered demo roles")
        if getattr(sys,"frozen",False) and mascot_catalog["summary"]["original_demo_count"] != 2:
            raise RuntimeError("Linux Qt binary missing Guga/Doro animated original mascots")
        report = {
            "ok": True,
            "display_backend": os.getenv("QT_QPA_PLATFORM", "default"),
            "qscreen_available": True,
            "management_window_visible": True,
            "catalog_dialog_opened": True,
            "genshin_templates": 123,
            "mascot_original_demo_count": mascot_catalog["summary"]["original_demo_count"],
            "mascot_creator_art_count": mascot_catalog["summary"]["imported_creator_art_count"],
            "mascot_dialog_opened": True,
            "local_profile_count": local_catalog["summary"]["installed_profile_count"],
            "original_demo_profile_count": local_catalog["summary"]["original_demo_profile_count"],
            "personal_art_profile_count": local_catalog["summary"]["personal_art_profile_count"],
            "resource_root_is_executable_directory": True,
            "real_audio_hardware_tested": False,
            "actual_character_likeness_verified": False,
            "user_role_files_modified": False,
        }
        dest = os.getenv("DYBERPET_LINUX_GUI_REPORT")
        if dest:
            Path(dest).write_text(json.dumps(report, indent=2, ensure_ascii=False),
                                  encoding="utf-8")
        print("DYBERPET_LINUX_GUI_SMOKE_OK", json.dumps(report), flush=True)
        return report
    finally:
        window.close()
        app.processEvents()
