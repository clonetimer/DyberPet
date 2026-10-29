"""Doro-specific native Live2D Cubism preview in existing PySide6 app.

Optional live2d-py/OpenGL runtime is loaded only when opened. All model files
remain in the owner's original local folder; no PNG conversion or upload.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QSettings, QTimer
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QVBoxLayout,
)
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from tools.doro_live2d_local import inspect_local_live2d

_SETTINGS_KEY = "character/doro_live2d_model3"


class _DoroGLView(QOpenGLWidget):
    _framework_ready = False

    def __init__(self, model_info, parent=None):
        super().__init__(parent)
        self.model_info = model_info
        self.model = None
        self.live2d = None
        self.error = None
        self.setMinimumSize(360, 370)
        self.setMouseTracking(True)
        self.clock = QTimer(self)
        self.clock.timeout.connect(self.update)

    def initializeGL(self):
        try:
            import live2d
            from OpenGL import GL
            self.gl = GL
            self.live2d = live2d
            if not _DoroGLView._framework_ready:
                live2d.init()
                _DoroGLView._framework_ready = True
            live2d.glInit()
            self.model = live2d.Model()
            self.model.LoadModelJson(self.model_info["model_json"])
            self.model.Resize(max(1, self.width()), max(1, self.height()))
            self.clock.start(33)
        except (ImportError, OSError, RuntimeError, ValueError) as exc:
            self.error = str(exc)[:300]
            self.clock.stop()

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
        close = QPushButton("关闭（保留原始本地模型文件）", self)
        close.clicked.connect(self.close)
        layout.addWidget(close)

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
