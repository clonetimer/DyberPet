"""Doro-specific native Live2D Cubism preview in existing PySide6 app.

Optional live2d-py/OpenGL runtime is loaded only when opened. All model files
remain in the owner's original local folder; no PNG conversion or upload.
"""
from __future__ import annotations

from pathlib import Path
import time
import zipfile

from PySide6.QtCore import Qt, QSettings, QTimer, Signal, QStandardPaths, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QInputDialog,
    QMenu, QMessageBox, QPushButton, QVBoxLayout,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from tools.doro_live2d_local import inspect_local_live2d
from tools.doro_live2d_interaction import click_expression_for_area, is_same_source_area_press
from tools.doro_personal_setup import find_doro_archives_in_directories, setup_personal_doro_zip
from tools.doro_window_placement import place_doro_window
from tools.doro_native_gait import STEP_ID, source_step_gait
from tools.doro_touch_drop import DoroTouchDrop, read_source_ranges
from tools.doro_host_bridge import DoroHostBridge

_SETTINGS_KEY = "character/doro_live2d_model3"
_AUTOSTART_KEY = "character/doro_live2d_auto_start"
_WINDOW_GEOMETRY_KEY = "character/doro_live2d_window_geometry"


class _DoroGLView(QOpenGLWidget):
    _framework_ready = False
    _backend_ready = False
    loadFailed = Signal(str)
    loadSucceeded = Signal()

    def __init__(self, model_info, parent=None):
        super().__init__(parent)
        self.model_info = model_info
        self.model = None
        self.live2d = None
        self.error = None
        self.setMinimumSize(360, 370)
        self.setMouseTracking(True)
        self.clock = QTimer(self)
        self.clock.timeout.connect(self._tick)

    def initializeGL(self):
        try:
            import live2d
            from OpenGL import GL
            self.gl = GL
            self.live2d = live2d
            if not _DoroGLView._framework_ready:
                live2d.init()
                _DoroGLView._framework_ready = True
            # The native SDK backend is process-global; initializing once per
            # QOpenGLWidget fails when preview and pet have separate contexts.
            if not _DoroGLView._backend_ready:
                live2d.glInit()
                _DoroGLView._backend_ready = True
            self.model = live2d.Model()
            self.model.LoadModelJson(self.model_info["model_json"])
            # Optional VTube Studio face shortcuts may reference local
            # author expression files not present in the Cubism model3 list.
            # Never synthesize missing assets or install global hotkeys.
            for name, path in self.model_info.get("extra_expressions", {}).items():
                self.model.LoadExtraExpression(name, path)
            for group, paths in self.model_info.get("extra_motions", {}).items():
                for path in paths:
                    self.model.LoadExtraMotion(group, path)
                if self.model.GetMotionGroups().get(group, 0) < len(paths):
                    raise RuntimeError("作者原生待机动作文件未实际加载：" + group)
            self.model.Resize(max(1, self.width()), max(1, self.height()))
            if "OwnerIdle" in self.model_info.get("extra_motions", {}):
                self.model.StartMotion("OwnerIdle", 0, 1)
            self.clock.start(33)
            self.loadSucceeded.emit()
        except Exception as exc:
            # SDK native errors may be raised outside the Python exception
            # families above. Never leave an unexplained, empty Qt viewport.
            self.error = (type(exc).__name__ + ": " + str(exc))[:300]
            self.model = None
            self.clock.stop()
            self.loadFailed.emit(self.error)

    def _tick(self):
        if self.model and "OwnerIdle" in self.model_info.get("extra_motions", {}):
            try:
                if self.model.IsMotionFinished():
                    self.model.StartMotion("OwnerIdle", 0, 1)
            except Exception as exc:
                self.error = (type(exc).__name__ + ": " + str(exc))[:300]
                self.clock.stop()
                self.loadFailed.emit(self.error)
                return
        self.update()

    def resizeGL(self, width, height):
        if self.model:
            self.gl.glViewport(0, 0, max(1, width), max(1, height))
            self.model.Resize(max(1, width), max(1, height))

    def paintGL(self):
        if self.model:
            self.live2d.clearBuffer()
            self.model.Update()
            self._after_native_update()
            self.model.Draw()

    def _after_native_update(self):
        """Hook called after Cubism Update and before Draw; no native mutations by default."""
        return

    def mouseMoveEvent(self, event):
        if self.model:
            point = event.position()
            self.model.Drag(point.x(), point.y())
        super().mouseMoveEvent(event)

    def _hit_area_at(self, position):
        """Use author-declared areas; never guess geometry from window bounds."""
        if not self.model:
            return None
        for name in self.model_info.get("hit_areas", {}):
            try:
                if self.model.IsAreaHit(name, float(position.x()), float(position.y())):
                    return name
            except (ValueError, RuntimeError, TypeError):
                # No visible Cubism target means there is no hit/pet feedback.
                return None
        return None

    def _visible_model_hit(self, position):
        """Allow dragging from real visible drawables, not the transparent box."""
        if not self.model:
            return False
        if self._hit_area_at(position):
            return True
        try:
            return bool(self.model.HitDrawable(
                float(position.x()), float(position.y()), topOnly=True))
        except (ValueError, RuntimeError, TypeError):
            return False

    def express(self, name, fadeout_ms=-1.0):
        if not self.model or name not in self.model_info["expressions"]:
            return False
        self.model.SetExpression(name, fadeout_ms)
        return True

    def motion(self, group, index):
        if not self.model or index not in range(self.model_info["motion_groups"].get(group, 0)):
            return False
        self.model.StartMotion(group, index, 3)
        return True

    def stop(self):
        self.clock.stop()
        self.model = None


_ACTIVE_DORO_WINDOWS = []


class DoroDesktopWindow(_DoroGLView):
    """Actual independent, frameless Doro Live2D desktop window.

    Only the locally owned source model is rendered. Pointer drag moves the
    whole pet window; right click offers its REAL expression/motion groups.
    """

    def __init__(self, model_info):
        super().__init__(model_info, parent=None)
        self.setWindowTitle("Doro · 真实 Live2D 单角色桌宠")
        self.setWindowFlags(
            Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(360, 370)
        self._press_global = None
        self._window_origin = None
        self._moved = False
        self._press_area = None
        self._pressed_model = False
        self._legacy_hidden_by_doro = False
        self._model_loaded = False
        self._gait = None
        self._touch_drop = DoroTouchDrop()
        self._last_action_tick = 0.0
        self._walk_x = 0.0
        self._last_gait_tick = 0.0
        self.loadSucceeded.connect(self._on_model_ready)
        self.loadFailed.connect(self._on_load_failed)
        self._restore_window_geometry()

    @staticmethod
    def _available_screens():
        app = QApplication.instance()
        if not app:
            return []
        primary = app.primaryScreen()
        screens = ([primary] if primary else [])
        screens.extend(s for s in app.screens() if s is not primary)
        return [
            (s.availableGeometry().x(), s.availableGeometry().y(),
             s.availableGeometry().width(), s.availableGeometry().height())
            for s in screens
        ]

    def _restore_window_geometry(self):
        saved = QSettings("DyberPet", "DyberPet").value(
            _WINDOW_GEOMETRY_KEY, None)
        x, y, w, h = place_doro_window(saved, self._available_screens())
        self.resize(w, h)
        self.move(x, y)

    def _recover_screen_position(self):
        x, y, w, h = place_doro_window(None, self._available_screens())
        self.resize(w, h)
        self.move(x, y)

    def _on_model_ready(self):
        # Hide the original only AFTER Cubism loaded; this also covers a
        # manually launched Doro when 'start with Doro' is not enabled.
        self._model_loaded = True
        try:
            self._gait = source_step_gait(self.model)
        except (AttributeError, RuntimeError, TypeError):
            self._gait = None
        try:
            self._touch_drop = DoroTouchDrop(read_source_ranges(self.model))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            self._touch_drop = DoroTouchDrop()
        self._walk_x = float(self.x())
        self._last_gait_tick = time.monotonic()
        self._last_action_tick = self._last_gait_tick
        # Only create Doro's progress after the actual Cubism model loads.
        # Uses the same PetData writer, never changes current sprite role.
        self._doro_bridge().activate_doro_profile()
        self._connect_host_task_signals()
        app = QApplication.instance()
        if (app and hasattr(app, "p") and app.p.isVisible()
                and not self._legacy_hidden_by_doro):
            app.p.hide()
            self._legacy_hidden_by_doro = True

    def _connect_host_task_signals(self):
        """Observe real completed work; no synthetic timer or parallel task engine."""
        self._host_task_links = []
        app = QApplication.instance()
        pet = getattr(app, "p", None)
        if pet is None:
            return
        for name, event in (("taskUI_task_end", "task_finished"),
                            ("single_pomo_done", "pomodoro_finished")):
            signal = getattr(pet, name, None)
            if not callable(getattr(signal, "connect", None)):
                continue
            callback = lambda e=event: self._on_host_task_completed(e)
            signal.connect(callback)
            self._host_task_links.append((signal, callback))

    def _on_host_task_completed(self, event):
        if self._model_loaded and self.isVisible():
            self._doro_bridge().record_completed_task(event)

    def _doro_bridge(self):
        return DoroHostBridge(QApplication.instance())

    def _record_doro_action(self, action):
        return self._doro_bridge().record_doro_action(action)

    def start_walk(self, direction):
        """Walk with the original Cubism ParamStep rig only, never fake motion."""
        if not self._model_loaded or self._gait is None:
            return False
        self._touch_drop.cancel()
        self._walk_x = float(self.x())
        self._last_gait_tick = time.monotonic()
        started = self._gait.start(direction)
        if started:
            self._record_doro_action("walk_left" if direction == -1 else "walk_right")
        return started

    def stop_walk(self):
        if self._gait is not None:
            self._gait.stop()

    def start_pat(self):
        if not self._model_loaded or not self.model:
            return False
        self.stop_walk()
        if "Amaze" in self.model_info.get("expressions", []):
            self.express("Amaze", fadeout_ms=700)
        self._last_action_tick = time.monotonic()
        began = self._touch_drop.pat()
        if began:
            self._record_doro_action("pat")
        return began

    def start_drop(self, from_drag=False):
        """Physical desktop fall; optional native rig bounce on landing."""
        if not self._model_loaded or not self.model:
            return False
        self.stop_walk()
        screens = self._available_screens()
        cy = self.y() + self.height() // 2
        cx = self.x() + self.width() // 2
        screen = next((
            r for r in screens
            if r[0] <= cx < r[0] + r[2]
            and r[1] <= cy < r[1] + r[3]
        ), screens[0] if screens else None)
        if screen is None:
            return False
        floor = screen[1] + screen[3] - self.height()
        if floor < screen[1]:
            return False
        start = min(self.y(), floor)
        # The explicit menu action also works for a pet already on the floor.
        # A drag release never lifts a pet again on its own.
        if not from_drag and start >= floor - 1:
            start = max(screen[1], floor - 85)
            self.move(self.x(), round(start))
        self._last_action_tick = time.monotonic()
        falling = self._touch_drop.drop(start, floor)
        if self._touch_drop.active:
            self._record_doro_action("drop")
            if self._touch_drop.phase == "land":
                self._record_doro_action("land")
        return falling


    def _after_native_update(self):
        # The original renderer updates deformation in Draw(). Apply Step
        # after Update() so source motions do not overwrite our gait value.
        if self.model is not None and self._gait is not None:
            self.model.SetParamById(STEP_ID, self._gait.value)
        if self.model is not None:
            for key, value in self._touch_drop.overrides.items():
                self.model.SetParamById(key, value)

    def _tick(self):
        now = time.monotonic()
        dt_action = min(0.08, max(0.0, now - self._last_action_tick))
        self._last_action_tick = now
        if self.model and self._touch_drop.active:
            previous_phase = self._touch_drop.phase
            y = self._touch_drop.tick(dt_action)
            if previous_phase == "fall" and self._touch_drop.phase == "land":
                self._record_doro_action("land")
            if self._touch_drop.phase in ("fall", "land"):
                if round(y) != self.y():
                    self.move(self.x(), round(y))
        if self._gait is not None and self._gait.active and self.model:
            now = time.monotonic()
            dt = min(0.1, max(0.0, now - self._last_gait_tick))
            self._last_gait_tick = now
            screen = self._available_screens()
            center_x = self.x() + self.width() // 2
            center_y = self.y() + self.height() // 2
            active_screen = next((
                r for r in screen
                if r[0] <= center_x < r[0] + r[2]
                and r[1] <= center_y < r[1] + r[3]
            ), screen[0] if screen else None)
            if active_screen is None:
                self.stop_walk()
            else:
                left = active_screen[0]
                right = active_screen[0] + active_screen[2] - self.width()
                self._walk_x = self._gait.tick(dt, self._walk_x, left, right)
                new_x = round(self._walk_x)
                if new_x != self.x():
                    self.move(new_x, self.y())
        super()._tick()

    def _on_load_failed(self, message):
        self.close()
        QTimer.singleShot(0, lambda: QMessageBox.warning(
            None, "Doro 原生模型启动失败",
            "本机 Live2D 模型未能加载。源文件未更改。\n" + message))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.stop_walk()
            self._touch_drop.cancel()
            self._press_global = event.globalPosition().toPoint()
            self._window_origin = self.pos()
            self._moved = False
            self._press_area = self._hit_area_at(event.position())
            self._pressed_model = self._visible_model_hit(event.position())
        elif event.button() == Qt.MouseButton.RightButton:
            self._show_actions(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if (self._press_global is not None and self._pressed_model
                and event.buttons() & Qt.MouseButton.LeftButton):
            offset = event.globalPosition().toPoint() - self._press_global
            if (self._moved or offset.manhattanLength() >=
                    max(6, QApplication.startDragDistance())):
                self._moved = True
                self.move(self._window_origin + offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self._press_global is not None:
            if not self._moved and self.model and is_same_source_area_press(
                    self._press_area, self._hit_area_at(event.position())):
                # Real Doro face/leg hit -> original Cubism expression.
                # Empty/transparent background never triggers petting.
                name = click_expression_for_area(
                    self._press_area, self.model_info["expressions"])
                if name:
                    self.express(name, fadeout_ms=700)
                if self._press_area == "HitAreaFace":
                    self._touch_drop.pat()
                    self._record_doro_action("pat")
            elif self._moved and self._pressed_model and self.model:
                # Releasing a dragged pet lets it drop to the active floor.
                self.start_drop(from_drag=True)
            self._press_area = None
            self._pressed_model = False
            self._press_global = None
            self._window_origin = None
            self._moved = False
        super().mouseReleaseEvent(event)

    def wheelEvent(self, event):
        factor = 1.08 if event.angleDelta().y() > 0 else 1 / 1.08
        width = min(1000, max(200, round(self.width() * factor)))
        height = min(1000, max(200, round(self.height() * factor)))
        self.resize(width, height)
        event.accept()

    def _buy_doro_food(self, name):
        """One native shop purchase against Doro's own earned coins."""
        if not self._model_loaded:
            return False
        ok = self._doro_bridge().buy_doro_food(name)
        if not ok:
            QMessageBox.information(
                self, "Doro 食物购买", "余额不足、商品不可用或 Doro 的独立库存无法写入。")
        return ok

    def _feed_doro_food(self, name):
        """Only consume food in Doro Live2D's inventory, never hidden sprite's."""
        if not self._model_loaded:
            return False
        ok = self._doro_bridge().feed_doro(name)
        if not ok:
            QMessageBox.information(
                self, "Doro 投喂", "Doro 没有这件食物，或该商品已经不可用。")
        else:
            if "Amaze" in self.model_info.get("expressions", []):
                self.express("Amaze", fadeout_ms=700)
        return ok

    def _browse_doro_food(self):
        catalog = self._doro_bridge().available_doro_food()
        if not catalog:
            return False
        labels = [
            "%s · %d 金币（活力 %+d / 亲密 %+d）" %
            (food["name"], food["cost"], food["energy"], food["bond"])
            for food in catalog
        ]
        choice, confirmed = QInputDialog.getItem(
            self, "Doro 的食物商店", "选择已有物品目录中的食物", labels, 0, False)
        if not confirmed:
            return False
        try:
            return self._buy_doro_food(catalog[labels.index(choice)]["name"])
        except ValueError:
            return False

    def _show_actions(self, position):
        menu = QMenu(self)
        for name in self.model_info["expressions"]:
            action = menu.addAction("表情 · " + name)
            action.triggered.connect(lambda _checked=False, n=name: self.express(n))
        if self.model_info["expressions"]:
            menu.addSeparator()
        for group, count in self.model_info["motion_groups"].items():
            for idx in range(count):
                action = menu.addAction("原生动作 · %s / %d" % (group, idx + 1))
                action.triggered.connect(
                    lambda _checked=False, g=group, i=idx: self.motion(g, i))
        menu.addSeparator()
        if self._gait is not None and self._model_loaded:
            menu.addAction("向左走 3 秒 · 模型原生 Step", lambda: self.start_walk(-1))
            menu.addAction("向右走 3 秒 · 模型原生 Step", lambda: self.start_walk(1))
            menu.addAction("停止行走 · 恢复待机", self.stop_walk)
        else:
            action = menu.addAction("当前模型无可用 ParamStep，不能播放步态")
            action.setEnabled(False)
        menu.addSeparator()
        pat_action = menu.addAction("摸摸头 · 原生角度反馈", self.start_pat)
        pat_action.setEnabled(self._model_loaded and
                              "ParamAngleZ" in self._touch_drop.parameters)
        landing_label = ("轻跃下落、落地恢复 · 原生弹性反馈"
                         if ("ParamBounceInput1" in self._touch_drop.parameters or
                             "ParamBodyAngleZ" in self._touch_drop.parameters)
                         else "轻跃下落、落地恢复 · 仅窗口物理运动")
        menu.addAction(landing_label, self.start_drop)
        menu.addSeparator()
        # The original PySide6 PetWidget remains the unique owner of
        # tasks, status, inventory and saves. Surface those existing windows
        # from Doro rather than creating a second, divergent system.
        host = DoroHostBridge(QApplication.instance())
        if host.pet is not None:
            menu.addSeparator()
            context = host.doro_display_context()
            interactions = context.get("interactions")
            if interactions is not None:
                total = sum(interactions.values())
                role = menu.addAction(
                    "当前角色 · Doro Live2D（累计互动 %d 次）" % total)
                role.setEnabled(False)
                counts = menu.addAction(
                    "摸头 %d / 行走 %d / 落地 %d" %
                    (interactions["pat"],
                     interactions["walk_left"] + interactions["walk_right"],
                     interactions["land"]))
                counts.setEnabled(False)
            doro_status = context.get("doro_status")
            if doro_status is not None:
                state = menu.addAction(
                    "Doro 自身 · 活力 %d / 亲密 %d" %
                    (doro_status["energy"], doro_status["bond"]))
                state.setEnabled(False)
                finished = doro_status["tasks"]
                task_row = menu.addAction(
                    "Doro 完成任务 · 专注 %d / 番茄 %d" %
                    (finished["task_finished"], finished["pomodoro_finished"]))
                task_row.setEnabled(False)
            backpack = context.get("doro_inventory")
            if backpack is not None:
                wallet = menu.addAction(
                    "Doro 自有金币 · %d（只在完成任务后增加）" % backpack["coins"])
                wallet.setEnabled(False)
                purchase = menu.addMenu("Doro · 购买食物（使用自有金币）")
                foods = host.available_doro_food()
                for food in sorted(foods, key=lambda v: (v["cost"], v["name"]))[:8]:
                    buy_action = purchase.addAction(
                        "%s · %d 金币" % (food["name"], food["cost"]))
                    buy_action.setEnabled(backpack["coins"] >= food["cost"])
                    buy_action.triggered.connect(
                        lambda _checked=False, n=food["name"]: self._buy_doro_food(n))
                if len(foods) > 8:
                    purchase.addAction("浏览全部已有食物…", self._browse_doro_food)
                if not foods:
                    action = purchase.addAction("当前没有可购买的真实消耗品")
                    action.setEnabled(False)
                feeding = menu.addMenu("Doro · 投喂（只消耗 Doro 库存）")
                for food in backpack["food"]:
                    eat = feeding.addAction(
                        "%s × %d · 活力 %+d / 亲密 %+d" %
                        (food["name"], food["quantity"],
                         food["energy"], food["bond"]))
                    eat.triggered.connect(
                        lambda _checked=False, n=food["name"]: self._feed_doro_food(n))
                if not backpack["food"]:
                    empty = feeding.addAction("Doro 库存暂无食物，先通过任务赚金币购买")
                    empty.setEnabled(False)
            snapshot = host.current_host_status()
            if snapshot is not None:
                status = menu.addAction(
                    "主程序状态（%s） · 饱食 %d / 好感 %d" %
                    (snapshot["base_role"], snapshot["hp"], snapshot["fv"]))
                status.setEnabled(False)
            menu.addAction("主程序 · 任务／背包／状态面板", host.open_dashboard)
            menu.addAction("主程序 · 角色管理／设置", host.open_control_panel)
        menu.addSeparator()
        menu.addAction("移回主显示器（恢复位置）", self._recover_screen_position)
        menu.addAction("切换回普通桌宠（记住此选择）", choose_standard_visual_role)
        menu.addAction("暂时关闭 Doro（下次仍优先）", self.close)
        menu.exec(position)

    def closeEvent(self, event):
        for signal, callback in getattr(self, "_host_task_links", []):
            try:
                signal.disconnect(callback)
            except (RuntimeError, TypeError):
                pass
        self._host_task_links = []
        self.stop_walk()
        self._touch_drop.cancel()
        if self._model_loaded:
            QSettings("DyberPet", "DyberPet").setValue(
                _WINDOW_GEOMETRY_KEY,
                [self.x(), self.y(), self.width(), self.height()])
        self._press_area = None
        self._pressed_model = False
        self.stop()
        if self in _ACTIVE_DORO_WINDOWS:
            _ACTIVE_DORO_WINDOWS.remove(self)
        if self._legacy_hidden_by_doro:
            self._legacy_hidden_by_doro = False
            app = QApplication.instance()
            if app and hasattr(app, "p"):
                app.p.show()
        super().closeEvent(event)


def open_doro_desktop(model_info, on_ready=None, on_failed=None):
    """One visible Doro, with caller callbacks wired BEFORE the GL show event."""
    for existing in tuple(_ACTIVE_DORO_WINDOWS):
        if (existing.isVisible() and
                existing.model_info["model_json"] == model_info["model_json"]):
            if callable(on_ready):
                if existing._model_loaded:
                    on_ready()
                else:
                    existing.loadSucceeded.connect(on_ready)
            if callable(on_failed):
                existing.loadFailed.connect(on_failed)
            existing.raise_()
            existing.activateWindow()
            return existing
        existing.close()
    window = DoroDesktopWindow(model_info)
    if callable(on_ready):
        window.loadSucceeded.connect(on_ready)
    if callable(on_failed):
        window.loadFailed.connect(on_failed)
    _ACTIVE_DORO_WINDOWS.append(window)
    window.show()
    return window


def doro_visual_role_selected():
    """One persistent character-visual choice; saved native PetData is intact."""
    return QSettings("DyberPet", "DyberPet").value(
        _AUTOSTART_KEY, False, type=bool)


def choose_doro_visual_role(parent=None):
    """Select Doro as the primary *displayed* pet through character management.

    The official model is resolved locally; if unavailable, offer the existing
    one-time author ZIP chooser. Commit the choice only once GL actually loads.
    """
    cfg = QSettings("DyberPet", "DyberPet")
    selected = _resolve_installed_doro(cfg.value(_SETTINGS_KEY, "", type=str))
    if not selected:
        selected = _select_local_doro_model(parent)
    if not selected:
        return None
    try:
        info = inspect_local_live2d(selected)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        QMessageBox.warning(parent, "Doro 角色无法选择", str(exc)[:350])
        return None

    def confirmed():
        current = QSettings("DyberPet", "DyberPet")
        current.setValue(_SETTINGS_KEY, selected)
        current.setValue(_AUTOSTART_KEY, True)

    # Do not persist an invalid model as the primary character when the
    # native Cubism engine crashes. The original PetWidget remains visible.
    def failed(_message):
        if not doro_visual_role_selected():
            QSettings("DyberPet", "DyberPet").setValue(_AUTOSTART_KEY, False)

    try:
        return open_doro_desktop(info, on_ready=confirmed, on_failed=failed)
    except (RuntimeError, ValueError, OSError, TypeError) as exc:
        QMessageBox.warning(parent, "Doro 角色启动失败", str(exc)[:350])
        return None


def choose_standard_visual_role():
    """Return to the existing ordinary pet and persist that choice."""
    QSettings("DyberPet", "DyberPet").setValue(_AUTOSTART_KEY, False)
    for window in tuple(_ACTIVE_DORO_WINDOWS):
        window.close()
    return True


class DoroLive2DPreviewDialog(QDialog):
    """Render locally obtained target artwork directly, without exporting sprites."""

    def __init__(self, model_json, parent=None):
        super().__init__(parent)
        self.model_info = inspect_local_live2d(model_json)
        self.setWindowTitle("Doro · 本机四足 Live2D 动态预览（不包含模型素材）")
        self.resize(560, 620)
        layout = QVBoxLayout(self)
        tip = QLabel(
            "仅在本机打开你合法取得的 Cubism 模型。不会下载、复制、导出或上传原画。"
            "这是形象/交互预览，不代表正/侧/背三视图已完成，也不代表获准再分发。", self)
        tip.setWordWrap(True)
        layout.addWidget(tip)
        self.canvas = _DoroGLView(self.model_info, self)
        self.canvas.loadFailed.connect(self._on_model_failed)
        self.canvas.loadSucceeded.connect(self._on_model_ready)
        layout.addWidget(self.canvas)
        controls = QHBoxLayout()
        self.expressions = QComboBox(self)
        self.expressions.addItem("选择原作者已有表情", "")
        for name in self.model_info["expressions"]:
            self.expressions.addItem(name, name)
        self.expressions.currentIndexChanged.connect(self._expression_changed)
        controls.addWidget(self.expressions)
        self.motions = QComboBox(self)
        self.motions.addItem("选择模型已有动作", None)
        for group, count in self.model_info["motion_groups"].items():
            for i in range(count):
                self.motions.addItem(f"{group} / {i+1}", (group, i))
        self.motions.currentIndexChanged.connect(self._motion_changed)
        controls.addWidget(self.motions)
        layout.addLayout(controls)
        self.status = QLabel(
            "读取实际模型表情 %s 个、动作 %s 段；实际 OpenGL 载入后可播放。"
            % (len(self.model_info["expressions"]),
               sum(self.model_info["motion_groups"].values())), self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        desktop = QPushButton("在桌面独立运行 Doro（置顶、拖动、滚轮缩放）", self)
        desktop.clicked.connect(lambda: open_doro_desktop(self.model_info))
        layout.addWidget(desktop)
        self.start_with_doro = QCheckBox(
            "以后启动 DyberPet 时优先显示 Doro（原桌宠暂时隐藏；关闭 Doro 后恢复）", self)
        self.start_with_doro.setChecked(QSettings("DyberPet", "DyberPet").value(
            _AUTOSTART_KEY, False, type=bool))
        self.start_with_doro.toggled.connect(self._set_doro_as_startup)
        layout.addWidget(self.start_with_doro)
        auto = QPushButton("从下载文件夹自动启用原版 Doro（个人本地）", self)
        auto.clicked.connect(self._auto_install_from_downloads)
        layout.addWidget(auto)
        choose = QPushButton("更换本机 Live2D 模型文件", self)
        choose.clicked.connect(self._choose_another_model)
        layout.addWidget(choose)
        close = QPushButton("关闭（保留原始本地模型文件）", self)
        close.clicked.connect(self.close)
        layout.addWidget(close)

    def _set_doro_as_startup(self, checked):
        QSettings("DyberPet", "DyberPet").setValue(_AUTOSTART_KEY, bool(checked))

    def _auto_install_from_downloads(self):
        archives = _find_personal_doro_downloads()
        if not archives:
            QMessageBox.information(
                self, "Doro 原模型尚未下载",
                "未发现原作者的 Doro ZIP。请从作者页面下载一次。\n"
                + _CREATOR_DORO_URL)
            return
        errors = []
        for archive in archives:
            try:
                selected = str(setup_personal_doro_zip(
                    archive, _personal_doro_root()))
                self._switch_to_model(selected)
                return
            except (ValueError, OSError, KeyError, TypeError,
                    zipfile.BadZipFile) as exc:
                errors.append(archive.name + ": " + str(exc)[:120])
        QMessageBox.warning(self, "Doro ZIP 自动检查未通过",
                            "\n".join(errors[:3]))

    def _switch_to_model(self, selected):
        if not selected or selected == self.model_info["model_json"]:
            return
        try:
            replacement = DoroLive2DPreviewDialog(selected, self.parentWidget())
        except (ValueError, OSError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "模型校验失败", str(exc)[:450])
            return
        QSettings("DyberPet", "DyberPet").setValue(_SETTINGS_KEY, selected)
        self.canvas.stop()
        self.hide()
        replacement.exec()
        self.close()

    def _choose_another_model(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择另一个已合法取得的 Live2D 模型",
            str(Path(self.model_info["model_json"]).parent),
            "Live2D Cubism (*.model3.json)")
        self._switch_to_model(selected)

    def _on_model_failed(self, message):
        self.status.setText("Doro Live2D 模型加载失败：" + message)
        QTimer.singleShot(0, lambda: QMessageBox.warning(
            self, "Doro Live2D 加载失败",
            "本机原画未被修改。\n" + message))

    def _on_model_ready(self):
        self.status.setText("Doro 原始 Live2D 已载入。可预览源模型已有动作/表情；"
                            "未提供的四足动作不会凭空生成。")

    def _expression_changed(self, *_):
        name = self.expressions.currentData()
        if name and self.canvas.express(name):
            self.status.setText("正在播放真实模型表情：" + name)

    def _motion_changed(self, *_):
        item = self.motions.currentData()
        if item and self.canvas.motion(*item):
            self.status.setText("正在播放真实模型动作：%s / %s" % item)

    def closeEvent(self, event):
        self.canvas.stop()
        super().closeEvent(event)


_CREATOR_DORO_URL = "https://booth.pm/zh-cn/items/5867617"


def _personal_doro_root():
    """User-writable local files: never inside a cloned repository/release."""
    base = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.AppLocalDataLocation)
    if not base:
        raise OSError("Could not find local app data directory")
    return Path(base) / "PersonalDoro"


def _find_personal_doro_downloads():
    """Windows native Downloads KnownFolder, with legacy path fallback."""
    windows_downloads = QStandardPaths.writableLocation(
        QStandardPaths.StandardLocation.DownloadLocation)
    return find_doro_archives_in_directories(
        [windows_downloads, Path.home() / "Downloads"])


def _resolve_installed_doro(remembered=""):
    """No dialogue, no network. Existing valid art or user's own local ZIP."""
    if remembered and Path(remembered).is_file():
        try:
            inspect_local_live2d(remembered)
            return str(Path(remembered))
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
            pass
    for archive in _find_personal_doro_downloads():
        try:
            return str(setup_personal_doro_zip(
                archive, _personal_doro_root()))
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile):
            continue
    return ""


def launch_personal_doro_at_startup():
    """Opt-in only. Never show a chooser on boot or hide the original on failure."""
    cfg = QSettings("DyberPet", "DyberPet")
    if not cfg.value(_AUTOSTART_KEY, False, type=bool):
        return False
    model = _resolve_installed_doro(cfg.value(_SETTINGS_KEY, "", type=str))
    if not model:
        # Keep the original pet visible if source ZIP has been moved/deleted.
        return False
    try:
        info = inspect_local_live2d(model)
        open_doro_desktop(info)
        cfg.setValue(_SETTINGS_KEY, model)
        return True
    except (ValueError, OSError, RuntimeError, TypeError, KeyError):
        return False


def _select_local_doro_model(parent, remembered=""):
    """No importing procedure for the user: find official ZIP in Downloads."""
    resolved = _resolve_installed_doro(remembered)
    if resolved:
        return resolved
    choice = QMessageBox(parent)
    choice.setWindowTitle("Doro · 个人本地使用")
    choice.setText("DyberPet 会自动从「下载」文件夹识别并安装原版 Doro ZIP，"
                   "不用手动解压、导入或安装开发环境。")
    choice.setInformativeText(
        "当前未发现有效的原作者模型。下载一次后重新进入即可自动启用；"
        "所有文件只保存到当前 Windows 用户本机，不会上传 GitHub。")
    get_original = choice.addButton(
        "打开原作者免费下载页", QMessageBox.ButtonRole.ActionRole)
    select_zip = choice.addButton(
        "选择已经下载的 ZIP（自动安装）", QMessageBox.ButtonRole.ActionRole)
    select_model = choice.addButton(
        "使用已有解压模型", QMessageBox.ButtonRole.ActionRole)
    choice.addButton("取消", QMessageBox.ButtonRole.RejectRole)
    choice.exec()
    action = choice.clickedButton()
    if action is get_original:
        QDesktopServices.openUrl(QUrl(_CREATOR_DORO_URL))
        return ""
    if action is select_zip:
        file, _ = QFileDialog.getOpenFileName(
            parent, "选择原作者下载的 Doro ZIP",
            str(Path.home() / "Downloads"), "Doro ZIP (*.zip)")
        if not file:
            return ""
        try:
            return str(setup_personal_doro_zip(file, _personal_doro_root()))
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(parent, "Doro 本地安装失败",
                                "源 ZIP 未被修改。\n" + str(exc)[:450])
            return ""
    if action is select_model:
        file, _ = QFileDialog.getOpenFileName(
            parent, "选择已在本机取得的 Cubism Doro 模型",
            str(Path.home()), "Live2D Cubism (*.model3.json)")
        return file
    return ""


def open_doro_live2d(parent=None):
    """Own-use setup: local ZIP auto-install and model launch, with no uploads."""
    settings = QSettings("DyberPet", "DyberPet")
    remembered = settings.value(_SETTINGS_KEY, "", type=str)
    selected = _select_local_doro_model(parent, remembered)
    if not selected:
        return False
    try:
        dialog = DoroLive2DPreviewDialog(selected, parent)
    except (ValueError, OSError, TypeError, KeyError, ImportError) as exc:
        QMessageBox.warning(parent, "Doro 原版模型检查失败", str(exc)[:450])
        return False
    settings.setValue(_SETTINGS_KEY, selected)
    dialog.exec()
    return True
