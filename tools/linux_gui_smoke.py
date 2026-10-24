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
        # Real X11 widget preview with moving native PNG frames. In source
        # mode use disposable original art; the bundled ELF uses built-in art.
        from DyberPet.DyberSettings.mascot_preview_dialog import MascotActionPreview
        from tools.generate_mascot_demos import generate_mascot_demos
        from tempfile import TemporaryDirectory
        with TemporaryDirectory(prefix="dyberpet-x11-preview-") as demo_temp:
            demo_root = (Path(settings.BASEDIR) / "res" / "role"
                         if getattr(sys, "frozen", False) else
                         Path(demo_temp) / "roles")
            if not getattr(sys, "frozen", False):
                generate_mascot_demos(demo_root, ["doro"])
            preview = MascotActionPreview(
                demo_root / "DemoMascotDoro", original_demo=True, parent=window)
            try:
                preview.show()
                app.processEvents()
                if not preview.isVisible() or preview.frame.pixmap().isNull():
                    raise RuntimeError("Native Doro animation preview did not render in X11")
                index = preview.actions.findData("left_walk")
                if index < 0:
                    raise RuntimeError("Doro four-leg action absent from Qt preview")
                preview.actions.setCurrentIndex(index)
                app.processEvents()
                preview._advance()
                if preview.frame_index != 1 or preview.frame.pixmap().isNull():
                    raise RuntimeError("X11 Doro walking animation failed to advance")
                preview._toggle()
                if preview.timer.isActive():
                    raise RuntimeError("Qt play/pause did not pause")
                preview._toggle()
                if not preview.timer.isActive():
                    raise RuntimeError("Qt play/pause did not resume")
                for special in ("run","failed","lookaround"):
                    special_index=preview.actions.findData(special)
                    if special_index<0:
                        raise RuntimeError("Missing original special animation: "+special)
                    preview.actions.setCurrentIndex(special_index)
                    app.processEvents()
                    preview._advance()
                    if preview.frame_index!=1 or preview.frame.pixmap().isNull():
                        raise RuntimeError("Special animation failed to advance: "+special)
            finally:
                preview.close()
                app.processEvents()
            if preview.timer.isActive():
                raise RuntimeError("Qt animation timer survived closed preview")
        # The exact same Qt viewer must work for a Genshin chibi, not only
        # the two mascot-specific body types.
        from tools.generate_builtin_chibi_demos import generate_demo_roles
        from tools.character_progress import character_progress
        with TemporaryDirectory(prefix="dyberpet-x11-genshin-") as gtemp:
            genshin_root = (Path(settings.BASEDIR) / "res" / "role"
                            if getattr(sys, "frozen", False) else
                            Path(gtemp) / "roles")
            if not getattr(sys, "frozen", False):
                generate_demo_roles(genshin_root, ["genshin_lisa"])
            viewer = MascotActionPreview(
                genshin_root / "DemoG_lisa", original_demo=True, parent=window)
            if len(viewer.plan["actions"]) != 10 or viewer.plan["total_frames"] != 66:
                raise RuntimeError("Genshin X11 native preview lacks 10/66 animations")
            try:
                viewer.show()
                app.processEvents()
                if not viewer.isVisible() or viewer.frame.pixmap().isNull():
                    raise RuntimeError("Shared Qt viewer failed on original Genshin demo")
                action = viewer.actions.findData("left_walk")
                if action < 0:
                    raise RuntimeError("Genshin left_walk missing from native viewer")
                viewer.actions.setCurrentIndex(action)
                viewer._advance()
                if viewer.frame_index != 1 or viewer.frame.pixmap().isNull():
                    raise RuntimeError("Genshin walking frames did not advance in Qt")
                for special in ("run", "failed", "lookaround"):
                    idx = viewer.actions.findData(special)
                    if idx < 0:
                        raise RuntimeError("Genshin X11 preview missing "+special)
                    viewer.actions.setCurrentIndex(idx)
                    viewer._advance()
                    if viewer.frame_index != 1 or viewer.frame.pixmap().isNull():
                        raise RuntimeError("Genshin X11 special animation failed "+special)
            finally:
                viewer.close()
                app.processEvents()
            if viewer.timer.isActive():
                raise RuntimeError("Genshin preview leaked its QTimer")
        progress = character_progress(Path(settings.BASEDIR) / "res" / "role")
        if progress["summary"]["template_total"] != 125:
            raise RuntimeError("Cross-family ability dashboard lost 125 character profiles")
        if (getattr(sys, "frozen", False) and
                progress["summary"]["native_preview_ready"] != 125):
            raise RuntimeError("Frozen GUI lacks usable animations for all 125 roles")
        # Exercise the real 125-item searchable catalogue against the X11 Qt
        # display, with genuine native demo assets in frozen mode.
        from DyberPet.DyberSettings.character_catalog_dialog import CharacterCatalogDialog
        search_dialog = CharacterCatalogDialog(progress, parent=window)
        try:
            search_dialog.show()
            app.processEvents()
            if (not search_dialog.isVisible() or search_dialog.results.count()!=0 or
                    search_dialog.statusFilter.currentData()!="personal"):
                raise RuntimeError("Low-fidelity demos unexpectedly offered as finished roles")
            search_dialog.statusFilter.setCurrentIndex(
                search_dialog.statusFilter.findData("all"))
            search_dialog.searchBox.setText("Lisa")
            app.processEvents()
            if (search_dialog.results.count()!=1 or
                    search_dialog.selected_character_id()!="genshin_lisa"):
                raise RuntimeError("English character search failed on X11")
            search_dialog.searchBox.setText("Doro")
            app.processEvents()
            if (search_dialog.results.count()!=1 or
                    search_dialog.selected_character_id()!="mascot_doro"):
                raise RuntimeError("Cross-family mascot search failed on X11")
            search_dialog.searchBox.clear()
            search_dialog.familyFilter.setCurrentIndex(
                search_dialog.familyFilter.findData("mascot"))
            app.processEvents()
            if search_dialog.results.count()!=2:
                raise RuntimeError("Cross-family filter failed on X11")
            search_dialog.familyFilter.setCurrentIndex(
                search_dialog.familyFilter.findData("all"))
            search_dialog.statusFilter.setCurrentIndex(
                search_dialog.statusFilter.findData("demo"))
            app.processEvents()
            expected_count=125 if getattr(sys,"frozen",False) else 0
            if search_dialog.results.count()!=expected_count:
                raise RuntimeError("Original demo availability filter fabricated assets")
        finally:
            search_dialog.close()
            app.processEvents()
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
        # Render the actual welcome dialog in X11 using only installed roles.
        from DyberPet.assistant.first_run_dialog import FirstRunRoleDialog
        welcome = FirstRunRoleDialog(root / "res" / "role", current_role="Kitty")
        try:
            welcome.show()
            app.processEvents()
            if (not welcome.isVisible() or welcome.roles.count() < 1 or
                    welcome.showDemos.isChecked()):
                raise RuntimeError("First-run guide failed low-fidelity hide policy")
            welcome.search.setText("Kitty")
            app.processEvents()
            if welcome.selected_id() != "Kitty" or welcome.frame.pixmap().isNull():
                raise RuntimeError("First-run guide failed local search/image preview")
        finally:
            welcome.close()
            app.processEvents()

        report = {
            "first_run_guide_visible": True,
            "first_run_local_preview_verified": True,
            "ok": True,
            "display_backend": os.getenv("QT_QPA_PLATFORM", "default"),
            "qscreen_available": True,
            "management_window_visible": True,
            "catalog_dialog_opened": True,
            "genshin_templates": 123,
            "mascot_original_demo_count": mascot_catalog["summary"]["original_demo_count"],
            "mascot_creator_art_count": mascot_catalog["summary"]["imported_creator_art_count"],
            "mascot_dialog_opened": True,
            "mascot_live_preview_visible": True,
            "mascot_live_walk_advanced": True,
            "mascot_live_preview_timer_stopped": True,
            "genshin_live_preview_rendered": True,
            "genshin_original_demo_actions_each": 10,
            "genshin_original_demo_frames_each": 66,
            "full_character_coverage_templates": progress["summary"]["template_total"],
            "full_character_coverage_ready": progress["summary"]["native_preview_ready"],
            "character_catalog_searchable": True,
            "character_catalog_english_search": True,
            "character_catalog_mascot_filter": True,
            "character_catalog_demo_count": expected_count,
            "mascot_special_actions_played": ["run","failed","lookaround"],
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
