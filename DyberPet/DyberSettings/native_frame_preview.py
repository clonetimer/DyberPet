"""Read-only frame scrubber for genuinely installed third-party sprite variants.

No network, import/install operation or persisted state. Every displayed PNG
is taken from a complete and bounded local native action sequence. This is
manual appearance/action review, NOT automatic approval of likeness or rights.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QSlider,
    QVBoxLayout,
)

from tools.artist_animation_audit import (
    _frames_for_action, _read_config, MAX_ACTIONS, MAX_PIXELS, MAX_SIDE)
from tools.character_interaction_coverage import _safe_installed_role


def safe_animation_inventory(role_root, folder):
    role = _safe_installed_role(Path(role_root).expanduser(), folder)
    if ((role / "BUILTIN_CHIBI_DEMO.json").exists() or
            (role / "BUILTIN_MASCOT_DEMO.json").exists()):
        raise ValueError("演示形象不是创作者原画，不能用作原设对照")
    actions = _read_config(role / "act_conf.json")
    if not isinstance(actions, dict) or not 1 <= len(actions) <= MAX_ACTIONS:
        raise ValueError("未找到可核对的原生动作列表")
    inventory = {}
    total = 0
    for title, conf in sorted(actions.items()):
        if not isinstance(title, str) or not isinstance(conf, dict):
            raise ValueError("损坏的动画定义")
        paths = _frames_for_action(role, conf.get("images"))
        if not paths:
            raise ValueError("动作缺少原画序列：" + title)
        total += len(paths)
        if total > 1800:
            raise ValueError("一次预览中动作帧过多，请检查素材")
        for path in paths:
            with Image.open(path) as img:
                if (img.format != "PNG" or img.width > MAX_SIDE or
                        img.height > MAX_SIDE or img.width * img.height > MAX_PIXELS):
                    raise ValueError("原画尺寸或编码不安全：" + path.name)
                img.load()
        inventory[title] = paths
    return inventory


class NativeFramePreviewDialog(QDialog):
    """Allows the user to inspect every frame, one installed version at a time."""

    def __init__(self, role_root, folders, parent=None):
        super().__init__(parent)
        if not folders or len(folders) > 40:
            raise ValueError("请选择已安装的真实角色素材版本")
        self._root = Path(role_root).expanduser()
        self._folders = list(folders)
        self._index = 0
        self._frames = []
        self.setWindowTitle("原生作者素材 · 逐帧动画预览（只读）")
        self.setMinimumSize(490, 420)
        layout = QVBoxLayout(self)
        note = QLabel("逐版本、逐帧查看本机真实 PNG；可解码不代表外观、动作或授权验收通过。")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.version = QComboBox(self)
        for folder in self._folders:
            self.version.addItem(folder, folder)
        layout.addWidget(self.version)
        self.action = QComboBox(self)
        layout.addWidget(self.action)
        self.canvas = QLabel(self)
        self.canvas.setMinimumSize(400, 240)
        self.canvas.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.canvas, 1)
        self.frame_slider = QSlider(Qt.Orientation.Horizontal, self)
        layout.addWidget(self.frame_slider)
        controls = QHBoxLayout()
        self.back = QPushButton("上一帧", self)
        self.play = QPushButton("播放", self)
        self.next = QPushButton("下一帧", self)
        self.status = QLabel(self)
        controls.addWidget(self.back)
        controls.addWidget(self.play)
        controls.addWidget(self.next)
        controls.addWidget(self.status)
        layout.addLayout(controls)
        self._clock = QTimer(self)
        self._clock.setInterval(150)
        self._clock.timeout.connect(self._advance)
        self._inventory = {}
        self.version.currentIndexChanged.connect(self._load_version)
        self.action.currentIndexChanged.connect(self._select_action)
        self.frame_slider.valueChanged.connect(self._set_frame)
        self.back.clicked.connect(lambda: self._set_frame(self._index - 1))
        self.next.clicked.connect(self._advance)
        self.play.clicked.connect(self._toggle_play)
        self._load_version()

    def _load_version(self, *_):
        self._clock.stop()
        self.play.setText("播放")
        # Validate every frame before the GUI offers to play this variant.
        try:
            self._inventory = safe_animation_inventory(
                self._root, self.version.currentData())
        except (OSError, ValueError, TypeError, KeyError) as exc:
            # Qt signal handlers must not let a broken third-party folder
            # abort the desktop process. Show a reviewable problem instead.
            self._inventory = {}
            self._frames = []
            self.canvas.clear()
            self.canvas.setText("无法打开此作者动画：" + str(exc)[:170])
            self.status.setText("版本不可用")
            self.play.setEnabled(False)
            # Clearing a QComboBox emits currentIndexChanged(-1). Without
            # suppressing that notification _select_action replaces the
            # useful source-error status with a misleading empty 0/0.
            self.action.blockSignals(True)
            self.action.clear()
            self.action.blockSignals(False)
            return
        self.play.setEnabled(True)
        self.action.blockSignals(True)
        self.action.clear()
        for name in self._inventory:
            self.action.addItem(name, name)
        self.action.blockSignals(False)
        self._select_action()

    def _select_action(self, *_):
        self._clock.stop()
        self.play.setText("播放")
        self._frames = self._inventory.get(self.action.currentData(), [])
        self._index = 0
        self.frame_slider.blockSignals(True)
        self.frame_slider.setRange(0, max(0, len(self._frames) - 1))
        self.frame_slider.setValue(0)
        self.frame_slider.blockSignals(False)
        self._render_frame()

    def _set_frame(self, index):
        if not self._frames:
            return
        self._index = index % len(self._frames)
        self._render_frame()

    def _advance(self):
        self._set_frame(self._index + 1)

    def _render_frame(self):
        if not self._frames:
            self.canvas.setText("该动作没有真实动画帧")
            self.status.setText("0 / 0")
            return
        pixmap = QPixmap(str(self._frames[self._index]))
        if pixmap.isNull():
            self._clock.stop()
            self.canvas.setText("无法解码此帧，请检查本地素材")
            self.status.setText("帧损坏")
            return
        self.canvas.setPixmap(pixmap.scaled(
            400, 240, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.frame_slider.blockSignals(True)
        self.frame_slider.setValue(self._index)
        self.frame_slider.blockSignals(False)
        self.status.setText(f"{self._index + 1} / {len(self._frames)}")

    def _toggle_play(self):
        if self._clock.isActive():
            self._clock.stop()
            self.play.setText("播放")
        elif self._frames:
            self._clock.start()
            self.play.setText("暂停")

    def closeEvent(self, event):
        self._clock.stop()
        super().closeEvent(event)
