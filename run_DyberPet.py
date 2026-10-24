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

    # Avoid multiple process
    try:
        me = singleton.SingleInstance()
    except:
        sys.exit()


    # Create App
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    #QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    #QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

    app = DyberPetApp(sys.argv)
    app.setAttribute(Qt.AA_DontCreateNativeWidgetSiblings)

    sys.exit(app.exec())


