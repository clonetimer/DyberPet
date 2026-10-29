"""Doro-specific native Live2D Cubism preview in existing PySide6 app.

Optional live2d-py/OpenGL runtime is loaded only when opened. All model files
remain in the owner's original local folder; no PNG conversion or upload.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QMenu, QMessageBox, QPushButton, QVBoxLayout,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from tools.doro_live2d_local import inspect_local_live2d
from tools.doro_live2d_interaction import click_expression_for_area, is_same_source_area_press

_SETTINGS_KEY = "character/doro_live2d_model3"


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
            self.model.Draw()

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

    def express(self, name):
        if not self.model or name not in self.model_info["expressions"]:
            return False
        self.model.SetExpression(name)
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
        self.loadFailed.connect(self._on_load_failed)

    def _on_load_failed(self, message):
        self.close()
        QTimer.singleShot(0, lambda: QMessageBox.warning(
            None, "Doro 原生模型启动失败",
            "本机 Live2D 模型未能加载。源文件未更改。\n" + message))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
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
                    self.express(name)
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
        menu.addAction("关闭 Doro 桌宠", self.close)
        menu.exec(position)

    def closeEvent(self, event):
        self._press_area = None
        self._pressed_model = False
        self.stop()
        if self in _ACTIVE_DORO_WINDOWS:
            _ACTIVE_DORO_WINDOWS.remove(self)
        super().closeEvent(event)


def open_doro_desktop(model_info):
    """One live Doro per application; do not exhaust GPU or duplicate pets."""
    for existing in tuple(_ACTIVE_DORO_WINDOWS):
        if existing.isVisible() and existing.model_info["model_json"] == model_info["model_json"]:
            existing.raise_()
            existing.activateWindow()
            return existing
        existing.close()
    window = DoroDesktopWindow(model_info)
    _ACTIVE_DORO_WINDOWS.append(window)
    window.show()
    return window


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
        choose = QPushButton("更换本机 Live2D 模型文件", self)
        choose.clicked.connect(self._choose_another_model)
        layout.addWidget(choose)
        close = QPushButton("关闭（保留原始本地模型文件）", self)
        close.clicked.connect(self.close)
        layout.addWidget(close)

    def _choose_another_model(self):
        selected, _ = QFileDialog.getOpenFileName(
            self, "选择另一个已合法取得的 Live2D 模型",
            str(Path(self.model_info["model_json"]).parent),
            "Live2D Cubism (*.model3.json)")
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


def open_doro_live2d(parent=None):
    """Remember only a path, never copy restricted model files into app data."""
    settings = QSettings("DyberPet", "DyberPet")
    remembered = settings.value(_SETTINGS_KEY, "", type=str)
    if remembered and Path(remembered).is_file():
        selected = remembered
    else:
        selected, _ = QFileDialog.getOpenFileName(
            parent, "选择已合法取得的 Doro Cubism 模型（只需选择一次）",
            str(Path.home()), "Live2D Cubism (*.model3.json)")
    if not selected:
        return False
    try:
        dialog = DoroLive2DPreviewDialog(selected, parent)
    except (ValueError, OSError, TypeError, KeyError, ImportError) as exc:
        QMessageBox.warning(parent, "Doro 源模型加载前检查未通过", str(exc)[:450])
        return False
    settings.setValue(_SETTINGS_KEY, selected)
    dialog.exec()
    return True
