import sys
from sys import platform
import ctypes
import os

# This explicit diagnostic exits before GUI imports, so a frozen-package
# namespace problem can be distinguished from a missing PyInstaller module.
if "--linux-bundle-diag" in sys.argv:
    import importlib.util
    import DyberPet as inspected_package
    print("LINUX_BUNDLE_DIAG", {
        "frozen": bool(getattr(sys, "frozen", False)),
        "module_file": getattr(inspected_package, "__file__", None),
        "module_path": list(getattr(inspected_package, "__path__", [])),
        "module_spec": str(getattr(inspected_package, "__spec__", None)),
        "sys_path": sys.path,
    }, flush=True)
    for module_name in ("DyberPet.assistant", "DyberPet.assistant.portable",
                        "DyberPet.DyberPet", "tools.genshin_library"):
        try:
            spec = importlib.util.find_spec(module_name)
            print("LINUX_IMPORT_SPEC", module_name, str(spec), flush=True)
        except Exception as exc:
            print("LINUX_IMPORT_SPEC_ERROR", module_name, repr(exc), flush=True)
    sys.exit(0)


# Bootstrap *before* any legacy module loads resources or writes save data.
# On Windows, DyberPet's base dir is the current working directory. This
# guarantees the EXE can be started from any user folder / desktop shortcut.
from DyberPet.assistant.portable import initialize_portable_directory
initialize_portable_directory()

# This check runs against the FINAL distributed personal package, after QA
# generation stubs were removed. It does not import Qt or initialize saves.
if "--personal-package-smoke" in sys.argv:
    import json
    from pathlib import Path
    root = Path.cwd()
    role_root = root / "res" / "role"
    if not ((role_root / "Kitty" / "pet_conf.json").is_file() and
            (root / "res" / "language" / "language.json").is_file()):
        raise RuntimeError("Personal package is missing starter art or UI assets")
    leaked = [p.name for p in role_root.iterdir() if p.is_dir() and
              ((p / "BUILTIN_CHIBI_DEMO.json").exists() or
               (p / "BUILTIN_MASCOT_DEMO.json").exists())]
    if leaked:
        raise RuntimeError("Low-fidelity generated characters still bundled: " +
                           ", ".join(leaked[:5]))
    print("PERSONAL_ART_PACKAGE_CLEAN", json.dumps({
        "creator_sources_installer_only": True,
        "included_generated_character_demos": 0,
        "native_role_count": sum(p.is_dir() for p in role_root.iterdir()),
    }), flush=True)
    sys.exit(0)

# RESTORE MUST BE HANDLED HERE, BEFORE importing settings/DyberPet.DyberPet.
# That legacy module calls settings.init() and writes live save files on import.
from DyberPet.assistant.offline_restore import data_directory, recover_interrupted_restore
if "--restore-save" in sys.argv:
    from DyberPet.assistant.restore_wizard import run_restore_wizard
    sys.exit(run_restore_wizard())
# Obtain exclusive process ownership BEFORE importing DyberPet.DyberPet;
# that legacy module initializes and rewrites user saves as an import side effect.
# A second launch must never write while the offline wizard holds the same lock.
from tendo import singleton
_SINGLE_INSTANCE = None
_SMOKE_MODE = ("--assistant-smoke" in sys.argv or
               "--linux-ui-smoke" in sys.argv)
if __name__ == "__main__" and not _SMOKE_MODE:
    try:
        _SINGLE_INSTANCE = singleton.SingleInstance()
    except singleton.SingleInstanceException:
        sys.exit(0)
    # Only the sole app owner may recover an interrupted directory switch.
    recover_interrupted_restore(data_directory())

# Capture clean-install state before DyberPet.DyberPet imports settings.init()
# (which creates settings.json even on the first execution).
import DyberPet.settings as settings
from DyberPet.assistant.first_run import needs_first_run
_FIRST_RUN = needs_first_run(settings.CONFIGDIR, sys.argv)
if "--assistant-smoke" in sys.argv:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tendo import singleton
from DyberPet.utils import read_json
from DyberPet.DyberPet import PetWidget
from DyberPet.Notification import DPNote
from DyberPet.Accessory import DPAccessory

from PySide6.QtWidgets import QApplication
from PySide6 import QtCore
from PySide6.QtCore import Qt, QLocale, QTimer, QDateTime, QDate, Signal, QTime

from qfluentwidgets import  FluentTranslator, setThemeColor
from DyberPet.DyberSettings.DyberControlPanel import ControlMainWindow
from DyberPet.Dashboard.DashboardUI import DashboardMainWindow

try:
    size_factor = 1 #ctypes.windll.shcore.GetScaleFactorForDevice(0) / 100
except:
    size_factor = 1

import DyberPet.settings as settings


# For translation:
# pylupdate5 langs.pro
# lrelease langs.zh_CN.ts

# For .exe:
# Now we use pyinstaller 6.5.0
# pyinstaller --noconsole --icon="000.ico" --hidden-import="pynput.mouse._win32" --hidden-import="pynput.keyboard._win32" run_DyberPet.py

# For Mac:
# pyinstaller --windowed --icon 000.icns --add-data="res:res" --add-data="DyberPet:DyberPet" --hidden-import="pynput.mouse._darwin" --hidden-import="pynput.keyboard._darwin" run_DyberPet.py


class DyberPetApp(QApplication):
    date_changed = Signal(QDate)

    def __init__(self, *args, **kwargs):
        super(DyberPetApp, self).__init__(*args, **kwargs)

        self.setQuitOnLastWindowClosed(False)
        screens = self.screens()
        primary_screen = self.primaryScreen()

        if primary_screen in screens:
            screens.insert(0, screens.pop(screens.index(primary_screen)))
        else:
            screens.insert(0, primary_screen)

        # internationalization
        fluentTranslator = FluentTranslator(QLocale(settings.language_code))
        self.installTranslator(fluentTranslator)
        self.installTranslator(settings.translator)
        if settings.themeColor:
            setThemeColor(settings.themeColor)
        

        # Pet Object
        self.p = PetWidget(screens=screens)

        # Notification System
        self.note = DPNote()

        # Accessory System
        self.acc = DPAccessory()

        # System Panel
        self.conp = ControlMainWindow()

        # Dashboard
        self.board = DashboardMainWindow()

        # Midnight Timer
        self.current_date = QDate.currentDate()
        self.set_midnight_timer()

        # Signal Links
        self.__connectSignalToSlot()

    def show_first_run_guide(self):
        """Nonblocking-on-start (timer), no network or AI setup needed."""
        from pathlib import Path
        from PySide6.QtWidgets import QMessageBox
        from DyberPet.assistant.first_run_dialog import FirstRunRoleDialog
        role_root = Path(settings.BASEDIR) / "res" / "role"
        dialog = FirstRunRoleDialog(
            role_root, current_role=self.p.curr_pet_name, parent=self.conp)
        if not dialog.exec() or not dialog.selected_role:
            return
        role = dialog.selected_role
        if role not in settings.pets:
            QMessageBox.warning(self.conp, "桌宠选择失败", "角色已经不可用，请重新打开角色库。")
            return
        try:
            if role != self.p.curr_pet_name:
                self.p._change_pet(role)
            settings.default_pet = role
            settings.save_settings()
        except (OSError, ValueError, KeyError) as exc:
            QMessageBox.warning(self.conp, "桌宠切换失败", str(exc))

    def launch_offline_restore(self):
        """Start the independent wizard, then gracefully close the pet."""
        from pathlib import Path
        from PySide6.QtCore import QProcess
        from PySide6.QtWidgets import QMessageBox
        if getattr(sys, "frozen", False):
            executable, arguments = sys.executable, ["--restore-save"]
        else:
            executable = sys.executable
            arguments = [str(Path(__file__).resolve()), "--restore-save"]
        started, _pid = QProcess.startDetached(executable, arguments)
        if not started:
            QMessageBox.warning(
                self.conp, "恢复向导无法启动",
                "程序未能启动独立恢复窗口，桌宠将保持运行，数据不会被修改。")
            return
        # This runs PetWidget's existing flush/stop/close path.
        self.p.quit()

    def __connectSignalToSlot(self):
        # Main Widget - others
        self.p.setup_notification.connect(self.note.setup_notification)
        self.p.setup_bubbleText.connect(self.note.setup_bubbleText)
        self.p.change_note.connect(self.note.change_pet)
        self.p.change_note.connect(self.conp.charCardInterface._finishStateTooltip)
        self.p.close_bubble.connect(self.note.close_bubble)
        self.p.hptier_changed_main_note.connect(self.note.hpchange_note)
        self.p.fvlvl_changed_main_note.connect(self.note.fvchange_note)
        self.p.setup_acc.connect(self.acc.setup_accessory)
        self.p.move_sig.connect(self.acc.send_main_movement)
        self.p.move_sig.connect(self.note.send_main_movement)
        self.p.close_all_accs.connect(self.acc.closeAll)

        # System Widgets - others
        self.conp.settingInterface.ontop_changed.connect(self.acc.ontop_changed)
        self.conp.settingInterface.scale_changed.connect(self.acc.reset_size_sig)

        self.conp.settingInterface.ontop_changed.connect(self.p.ontop_update)
        self.conp.settingInterface.scale_changed.connect(self.p.reset_size)
        self.conp.settingInterface.lang_changed.connect(self.p.lang_changed)
        self.p.change_note.connect(self.conp.settingInterface._update_scale)

        self.conp.charCardInterface.change_pet.connect(self.p._change_pet)
        self.p.show_controlPanel.connect(self.conp.show_window)

        self.conp.gamesaveInterface.refresh_pet.connect(self.p.refresh_pet)
        self.conp.gamesaveInterface.restore_requested.connect(self.launch_offline_restore)

        # Dashboard - others
        self.p.show_dashboard.connect(self.board.show_window)
        self.note.noteToLog.connect(self.board.statusInterface._addNote)
        self.p.hp_updated.connect(self.board.statusInterface.StatusCard._updateHP)
        self.p.fv_updated.connect(self.board.statusInterface.StatusCard._updateFV)
        self.p.change_note.connect(self.board.statusInterface._changePet)
        self.board.statusInterface.changeStatus.connect(self.p._change_status)
        self.p.stopAllThread.connect(self.board.statusInterface.stopBuffThread)

        self.acc.acc_withdrawed.connect(self.board.backpackInterface.acc_withdrawed)
        self.board.backpackInterface.use_item_inven.connect(self.p.use_item)
        self.board.backpackInterface.item_note.connect(self.p.register_notification)
        self.board.backpackInterface.item_drop.connect(self.p.item_drop_anim)
        self.p.fvlvl_changed_main_inve.connect(self.board.backpackInterface.fvchange)
        self.p.fvlvl_changed_main_inve.connect(self.board.shopInterface.fvchange)
        self.p.addItem_toInven.connect(self.board.backpackInterface.add_items)
        self.p.compensate_rewards.connect(self.board.backpackInterface.compensate_rewards)
        self.p.refresh_bag.connect(self.board.backpackInterface.refresh_bag)
        self.p.autofeed.connect(self.board.backpackInterface.autofeed)
        self.p.refresh_bag.connect(self.board.shopInterface.refresh_shop)
        self.p.addCoins.connect(self.board.backpackInterface.addCoins)

        # Tasks and Timer
        self.board.taskInterface.focusPanel.start_pomodoro.connect(self.p.run_tomato)
        self.board.taskInterface.focusPanel.cancel_pomodoro.connect(self.p.cancel_tomato)
        self.board.taskInterface.focusPanel.start_focus.connect(self.p.run_focus)
        self.board.taskInterface.focusPanel.cancel_focus.connect(self.p.cancel_focus)
        self.p.taskUI_Timer_update.connect(self.board.taskInterface.focusPanel.update_Timer)
        self.p.taskUI_task_end.connect(self.board.taskInterface.focusPanel.taskFinished)
        self.p.single_pomo_done.connect(self.board.taskInterface.focusPanel.single_pomo_done)

        # Animation Panel
        self.board.animInterface.animatPanel.updateList.connect(self.p.updateList)
        self.board.animInterface.animatPanel.playAct.connect(self.p._show_act)
        self.p.refresh_acts.connect(self.board.animInterface.animatPanel.updateAct)
        self.p.refresh_acts.connect(self.board.animInterface.updateDesignUI)
        self.board.animInterface.loadNewAct.connect(self.p._addNewAct)
        self.board.animInterface.deletewAct.connect(self.p._deleteAct)

        # Midnight Trigger
        self.date_changed.connect(self.p._mightEventTrigger)
    
    def set_midnight_timer(self):
        now = QDateTime.currentDateTime()
        midnight = QDateTime(QDate.currentDate().addDays(1), QTime(0, 0, 0))  # Next midnight
        msecs_until_midnight = now.msecsTo(midnight)

        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.check_date)
        self.timer.start(msecs_until_midnight)
    
    def check_date(self):
        new_date = QDate.currentDate()
        if new_date != self.current_date:
            self.current_date = new_date
            self.date_changed.emit(new_date)
        self.set_midnight_timer()  # Reset the timer for the next midnight


        


if platform == 'win32':
    basedir = ''
else:
    basedir = os.path.dirname(__file__)

def _assistant_package_smoke():
    """Dry-run genuine frozen imports/Qt dialog without hardware or network."""
    import json
    import tempfile
    from pathlib import Path
    from DyberPet.assistant.portable import inspect_assets
    from DyberPet.assistant.ui import PetAssistantDialog
    from DyberPet.assistant.persona import PERSONAS
    report = {"resource_root": os.getcwd(), "assets": inspect_assets(os.getcwd()),
              "persona_count": len(PERSONAS), "assistant_dialog": False,
              "optional_voice_imports": {}}
    if not report["assets"]["ok"]:
        raise RuntimeError("Missing portable resources: " + repr(report["assets"]["missing"]))
    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory() as temp:
        dialog = PetAssistantDialog(
            "Kitty", Path(temp) / "sandbox",
            role_root=Path(os.getcwd()) / "res" / "role")
        report["assistant_dialog"] = bool(
            dialog.workspace.root.is_dir() and dialog.persona.count() >= 7)
        dialog.close()
    # Exercise the actual packaged role converter with an original synthetic
    # PNG so missing Pillow/tool modules cannot pass an EXE startup-only smoke.
    from DyberPet.assistant.character_import_smoke import verify_portable_character_importer
    report["character_importer"] = verify_portable_character_importer()
    if not report["character_importer"]["ok"]:
        raise RuntimeError("Portable character import conversion failed")
    # Only packaged releases must contain pre-rendered demo animations.
    # Exercise genuine packaged backup creation/verification in a temporary
    # sandbox so CI cannot pass just because source-level helpers are importable.
    from DyberPet.assistant.save_snapshot import create_backup, verify_backup
    with tempfile.TemporaryDirectory(prefix="dyberpet-save-smoke-") as temp:
        savedir = Path(temp) / "data"
        savedir.mkdir()
        (savedir / "settings.json").write_text("{}", encoding="utf-8")
        (savedir / "pet_data.json").write_text("{}", encoding="utf-8")
        archive_path = Path(temp) / "backup.zip"
        create_backup(savedir, archive_path)
        report["backup_snapshot_verified"] = (
            verify_backup(archive_path)["files"] == ["settings.json", "pet_data.json"])
        if not report["backup_snapshot_verified"]:
            raise RuntimeError("Frozen complete-backup functionality unavailable")

    # Real offline restore exercise in an isolated data directory, including
    # retaining the original state and confirming the standalone Qt wizard.
    from DyberPet.assistant.offline_restore import restore_backup
    from DyberPet.assistant.restore_wizard import RestoreWizard
    with tempfile.TemporaryDirectory(prefix="dyberpet-restore-smoke-") as temp:
        home = Path(temp)
        current = home / "data"
        current.mkdir()
        old_pet = {"Kitty": {"HP": 80, "HP_tier": 3, "FV": 0, "FV_lvl": 0}}
        new_pet = {"Kitty": {"HP": 40, "HP_tier": 3, "FV": 2, "FV_lvl": 1}}
        (current / "settings.json").write_text('{"default_pet":"Kitty"}', encoding="utf-8")
        (current / "pet_data.json").write_text(json.dumps(old_pet), encoding="utf-8")
        candidate = home / "candidate"
        candidate.mkdir()
        (candidate / "settings.json").write_text('{"default_pet":"Kitty"}', encoding="utf-8")
        (candidate / "pet_data.json").write_text(json.dumps(new_pet), encoding="utf-8")
        zip_path = home / "candidate.zip"
        create_backup(candidate, zip_path)
        changed = restore_backup(zip_path, current)
        report["offline_restore_verified"] = (
            json.loads((current / "pet_data.json").read_text()) == new_pet
            and Path(changed["pre_restore_directory"]).is_dir()
            and verify_backup(changed["pre_restore_archive"])["ok"])
    wizard = RestoreWizard()
    report["offline_restore_wizard_verified"] = (
        wizard.commit.isEnabled() is False and wizard.browse.isEnabled())
    wizard.close()
    if not report["offline_restore_verified"] or not report["offline_restore_wizard_verified"]:
        raise RuntimeError("Frozen offline restore failed safety smoke")

    # Exercise the real bundled first-run dialog without showing it on
    # existing installs and without touching a live data directory.
    from DyberPet.assistant.first_run_dialog import FirstRunRoleDialog
    from DyberPet.assistant.first_run import needs_first_run
    with tempfile.TemporaryDirectory(prefix="dyberpet-first-run-smoke-") as temp:
        assert needs_first_run(temp)
        (Path(temp) / "data").mkdir()
        (Path(temp) / "data" / "settings.json").write_text("{}", encoding="utf-8")
        assert not needs_first_run(temp)
    welcome = FirstRunRoleDialog(Path(os.getcwd()) / "res" / "role", current_role="Kitty")
    report["first_run_guide_verified"] = (
        welcome.roles.count() >= 1 and not welcome.showDemos.isChecked() and
        welcome.selected_id() in
        [welcome.roles.item(i).data(Qt.ItemDataRole.UserRole)
         for i in range(welcome.roles.count())])
    welcome.close()
    if not report["first_run_guide_verified"]:
        raise RuntimeError("Frozen first-run role chooser cannot select an installed role")
    # Enforce presence of concrete pinned, opt-in artist source installers in
    # the *frozen* EXE/ELF; this does not download art or publish images.
    from tools.install_artist_genshin import ROLES as original_genshin
    from tools.install_artist_codex import SOURCES as codex_art
    from tools.install_artist_shimeji import source_manifest
    from tools.install_creator_mascots import UPSTREAM as mascot_art
    from tools.character_source_coverage import source_coverage
    from tools.install_nanopet_shimeji import source_manifest as nano_manifest
    from tools.install_external_codex import source_manifest as external_manifest
    creator = source_coverage()["summary"]
    report["public_art_sources_ready"] = (
        len(original_genshin) == 3 and len(codex_art) == 15
        and len(source_manifest()["roles"]) == 8
        and creator["template_count"] == 123
        and len(nano_manifest()["roles"]) == 17
        and len(external_manifest()["sources"]) == 10
        and creator["characters_with_pinned_sources"] == 30
        and {"guga", "doro"}.issubset(mascot_art))
    if not report["public_art_sources_ready"]:
        raise RuntimeError("Pinned original-art installers missing from executable")
    # Source CI deliberately tests an untouched checkout and does not seed it.
    if getattr(sys, "frozen", False):
        from tools.genshin_library import scan_genshin_library
        lib = scan_genshin_library(os.path.join(os.getcwd(), "res", "role"))
        counts = lib["summary"]
        report["built_in_demo_profiles"] = counts["original_demo_profile_count"]
        report["built_in_playable_profiles"] = counts["installed_profile_count"]
        report["built_in_unfilled_profiles"] = counts["pending_template_count"]
        if (counts["original_demo_profile_count"] != 123 or
                counts["installed_profile_count"] < 123 or
                counts["pending_template_count"] != 0):
            raise RuntimeError("Packaged install lacks full 123 playable original demo animations")
        # Two genuinely different demo bodies must also be available:
        # penguin-hoodie Guga / horizontally moving four-legged Doro.
        from tools.mascot_library import scan_mascot_library
        mascots=scan_mascot_library(os.path.join(os.getcwd(),"res","role"))
        report["mascot_original_demo_count"]=mascots["summary"]["original_demo_count"]
        report["mascot_imported_creator_art_count"]=mascots["summary"]["imported_creator_art_count"]
        report["mascot_character_likeness_verified"]=mascots["summary"]["character_likeness_verified"]
        if report["mascot_original_demo_count"] != 2:
            raise RuntimeError("Packaged application missing playable Guga/Doro original demo animations")
        if report["mascot_character_likeness_verified"]:
            raise RuntimeError("Demo assets must never assert original creator identity")
        # Actually construct the preview Qt dialog from this frozen EXE:
        # synthetic Guga/Doro artwork only, no source downloads.
        from DyberPet.DyberSettings.mascot_preview_dialog import MascotActionPreview
        for role in ("DemoMascotGuga", "DemoMascotDoro"):
            viewer=MascotActionPreview(
                Path(os.getcwd()) / "res" / "role" / role,
                original_demo=True)
            try:
                if (len(viewer.plan["actions"]) != 10 or
                        viewer.plan["total_frames"] != 66):
                    raise RuntimeError("Frozen mascot lacks 10 distinct 66-frame actions: "+role)
                viewer.show()
                app.processEvents()
                if not viewer.isVisible() or viewer.frame.pixmap().isNull():
                    raise RuntimeError("Frozen mascot Qt live preview did not render: " + role)
                idx=viewer.actions.findData("left_walk")
                if idx < 0:
                    raise RuntimeError("Frozen mascot missing native left_walk: " + role)
                viewer.actions.setCurrentIndex(idx)
                viewer._advance()
                if viewer.frame_index != 1 or viewer.frame.pixmap().isNull():
                    raise RuntimeError("Frozen mascot preview did not animate: " + role)
                for special in ("run", "failed", "lookaround"):
                    special_index=viewer.actions.findData(special)
                    if special_index < 0:
                        raise RuntimeError("Frozen mascot missing special action "+special)
                    viewer.actions.setCurrentIndex(special_index)
                    viewer._advance()
                    if viewer.frame_index != 1 or viewer.frame.pixmap().isNull():
                        raise RuntimeError("Frozen mascot special animation failed: "+special)
                viewer._toggle()
                if viewer.timer.isActive():
                    raise RuntimeError("Frozen mascot pause control failed: " + role)
            finally:
                viewer.close()
                app.processEvents()
            if viewer.timer.isActive():
                raise RuntimeError("Frozen mascot preview leaked a Qt timer")
        report["mascot_live_preview_count"]=2
        report["mascot_special_actions_each"]=10
        report["mascot_special_frames_each"]=66
        report["mascot_live_preview_timer_safe"]=True
        # Shared non-mascot viewer: actually render an original Genshin role
        # inside the frozen Windows EXE / Linux ELF rather than only AST-check.
        from tools.character_progress import character_progress
        coverage = character_progress(Path(os.getcwd()) / "res" / "role")
        if (coverage["summary"]["template_total"] != 125 or
                coverage["summary"]["native_preview_ready"] != 125):
            raise RuntimeError("Frozen character coverage is not 125/125")
        # Verify the *frozen* Windows EXE / Linux ELF has a working native
        # search UI, not just 125 strings in a JSON manifest.
        from DyberPet.DyberSettings.character_catalog_dialog import CharacterCatalogDialog
        selector=CharacterCatalogDialog(coverage)
        try:
            selector.show()
            app.processEvents()
            if (not selector.isVisible() or selector.results.count()!=30 or
                    selector.statusFilter.currentData()!="source"):
                raise RuntimeError("Default catalog must show 30 authentic-art SOURCE CANDIDATES")
            if any("作者来源" not in selector.results.item(i).text()
                   for i in range(selector.results.count())):
                raise RuntimeError("Source filter exposed an unverified demo without author provenance")
            # A creator source must NOT be confused with the installed role:
            # an untouched portable build has 125 temporary QA demos only.
            selector.statusFilter.setCurrentIndex(
                selector.statusFilter.findData("personal"))
            app.processEvents()
            if selector.results.count()!=0:
                raise RuntimeError("Uninstalled creator candidates falsely marked as installed")
            selector.statusFilter.setCurrentIndex(selector.statusFilter.findData("all"))
            selector.familyFilter.setCurrentIndex(selector.familyFilter.findData("all"))
            selector.searchBox.setText("Lisa")
            app.processEvents()
            if (selector.results.count()!=1 or
                    selector.selected_character_id()!="genshin_lisa"):
                raise RuntimeError("English character search failed in packaged app")
            selector.searchBox.setText("Doro")
            app.processEvents()
            if (selector.results.count()!=1 or
                    selector.selected_character_id()!="mascot_doro"):
                raise RuntimeError("Mascot name search failed in packaged app")
            selector.searchBox.clear()
            selector.statusFilter.setCurrentIndex(
                selector.statusFilter.findData("demo"))
            app.processEvents()
            if selector.results.count()!=125:
                raise RuntimeError("Packaged catalog falsely dropped demo characters")
        finally:
            selector.close()
            app.processEvents()
        report["character_search_catalog_count"]=125
        report["character_search_demo_count"]=125
        report["character_search_bilingual_verified"]=True
        viewer = MascotActionPreview(
            Path(os.getcwd()) / "res" / "role" / "DemoG_lisa",
            original_demo=True)
        try:
            if (len(viewer.plan["actions"]) != 10 or
                    viewer.plan["total_frames"] != 66):
                raise RuntimeError("Shared character viewer lost Genshin 10/66 playback")
            viewer.show()
            app.processEvents()
            if not viewer.isVisible() or viewer.frame.pixmap().isNull():
                raise RuntimeError("Frozen Genshin preview is not visible")
            idx = viewer.actions.findData("left_walk")
            if idx < 0:
                raise RuntimeError("Genshin native walking action missing")
            viewer.actions.setCurrentIndex(idx)
            viewer._advance()
            if viewer.frame_index != 1 or viewer.frame.pixmap().isNull():
                raise RuntimeError("Genshin walking preview did not advance")
            for special in ("run", "failed", "lookaround"):
                idx = viewer.actions.findData(special)
                if idx < 0:
                    raise RuntimeError("Frozen Genshin missing "+special)
                viewer.actions.setCurrentIndex(idx)
                viewer._advance()
                if viewer.frame_index != 1 or viewer.frame.pixmap().isNull():
                    raise RuntimeError("Frozen Genshin special animation cannot advance "+special)
        finally:
            viewer.close()
            app.processEvents()
        if viewer.timer.isActive():
            raise RuntimeError("Frozen Genshin preview leaked timer")
        report["genshin_native_preview_verified"] = True
        report["genshin_original_demo_actions_each"] = 10
        report["genshin_original_demo_frames_each"] = 66
        report["character_templates"] = coverage["summary"]["template_total"]
        report["character_native_preview_ready"] = coverage["summary"]["native_preview_ready"]
        report["genshin_demo_actions"] = coverage["summary"]["genshin_demo_actions"]
        report["mascot_demo_actions"] = coverage["summary"]["mascot_demo_actions"]

    for module in ("pyttsx3", "vosk", "sounddevice"):
        try:
            __import__(module)
            report["optional_voice_imports"][module] = True
        except Exception as exc:
            report["optional_voice_imports"][module] = str(exc)
    if not report["assistant_dialog"]:
        raise RuntimeError("Portable assistant dialog did not initialize")
    path = os.environ.get("DYBERPET_SMOKE_REPORT")
    if path:
        Path(path).write_text(json.dumps(report, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    print("DYBERPET_ASSISTANT_SMOKE_OK", flush=True)


if __name__ == '__main__':
    if "--assistant-smoke" in sys.argv:
        _assistant_package_smoke()
        sys.exit(0)
    if "--linux-ui-smoke" in sys.argv:
        from tools.linux_gui_smoke import verify_linux_gui
        verify_linux_gui()
        sys.exit(0)

    # Single-instance lock was acquired before importing any save-writing
    # modules. Keep its reference alive for the whole GUI process.
    if _SINGLE_INSTANCE is None:
        raise RuntimeError("Normal startup requires exclusive DyberPet lock")

    # Create App
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    #QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    #QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = DyberPetApp(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)
    if _FIRST_RUN:
        QTimer.singleShot(400, app.show_first_run_guide)

    sys.exit(app.exec())


