"""Passive Qt choices for worker-owned audio operations."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QPushButton,
    QSizePolicy, QSpinBox, QToolButton, QVBoxLayout, QWidget,
)


class AudioSettingsWidget(QGroupBox):
    settings_changed = Signal()
    refresh_requested = Signal()
    preview_requested = Signal()
    stop_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mutating = False
        self._catalog_loaded = False
        self._microphones = ()
        self._voices = ()
        layout = QVBoxLayout(self)
        self.toggle_button = QToolButton()
        self.toggle_button.setText("麦克风与朗读设置")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setArrowType(Qt.ArrowType.RightArrow)
        self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        layout.addWidget(self.toggle_button)
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.summary_label)
        self.details = QWidget()
        form = QFormLayout(self.details)
        self.form_layout = form
        form.setContentsMargins(0, 0, 0, 0)
        self.device_selector = QComboBox()
        self.voice_selector = QComboBox()
        for selector in (self.device_selector, self.voice_selector):
            selector.setMinimumContentsLength(14)
            selector.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            selector.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.device_selector.addItem("系统默认麦克风", None)
        self.voice_selector.addItem("系统默认音色", "")
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(100, 230)
        self.rate_spin.setValue(170)
        self.rate_spin.setSuffix(" · 语速")
        self.rate_spin.setToolTip("100–230，默认 170；实际听感由系统音色决定。")
        form.addRow("输入设备", self.device_selector)
        form.addRow("当前角色音色", self.voice_selector)
        form.addRow("朗读语速", self.rate_spin)
        controls = QHBoxLayout()
        self.refresh_button = QPushButton("刷新设备与音色")
        self.preview_button = QPushButton("试听当前音色")
        self.stop_button = QPushButton("停止当前语音")
        self.stop_button.setEnabled(False)
        for button in (self.refresh_button, self.preview_button, self.stop_button):
            button.setAutoDefault(False)
            controls.addWidget(button)
        form.addRow(controls)
        self.status_label = QLabel(
            "点击刷新后读取本机目录，不录音、不发声。音色与语速按角色保存；"
            "输入设备为全局选择。系统音色与角色原声素材独立。")
        self.status_label.setWordWrap(True)
        self.status_label.setTextFormat(Qt.TextFormat.PlainText)
        form.addRow(self.status_label)
        layout.addWidget(self.details)
        self.details.hide()
        self.toggle_button.toggled.connect(self._toggle)
        self.device_selector.currentIndexChanged.connect(self._changed)
        self.voice_selector.currentIndexChanged.connect(self._changed)
        self.rate_spin.valueChanged.connect(self._changed)
        self.refresh_button.clicked.connect(self.refresh_requested.emit)
        self.preview_button.clicked.connect(self.preview_requested.emit)
        self.stop_button.clicked.connect(self.stop_requested.emit)
        self._update_summary()

    def _toggle(self, expanded):
        self.details.setVisible(expanded)
        self.toggle_button.setArrowType(
            Qt.ArrowType.DownArrow if expanded else Qt.ArrowType.RightArrow)

    def microphone(self):
        selected = self.device_selector.currentData()
        return dict(selected) if selected is not None else None

    def voice_id(self):
        return self.voice_selector.currentData() or ""

    def rate(self):
        return self.rate_spin.value()

    def snapshot(self):
        selected = self.microphone()
        key = None if selected is None else (selected["name"], selected["host_api"])
        return key, self.voice_id(), self.rate()

    def set_values(self, microphone, voice_id, rate):
        self._mutating = True
        try:
            self._replace_microphones(microphone)
            self._replace_voices(voice_id)
            self.rate_spin.setValue(rate)
        finally:
            self._mutating = False
        self._update_summary()

    def apply_catalog(self, catalog):
        microphone, voice_id = self.microphone(), self.voice_id()
        self._microphones = catalog.microphones
        self._voices = catalog.voices
        self._catalog_loaded = True
        self.set_values(microphone, voice_id, self.rate())
        self.status_label.setText(
            "麦克风：" + catalog.microphone_message + "\n音色：" + catalog.voice_message
            + "\n设备更换后可刷新；如果列表仍未更新，请重启桌宠。")

    def _replace_microphones(self, selected):
        self.device_selector.clear()
        self.device_selector.addItem("系统默认麦克风", None)
        index = 0
        for item in self._microphones:
            key = {"name": item.name, "host_api": item.host_api}
            self.device_selector.addItem(item.name + "（" + item.host_api + "）", key)
            if key == selected:
                index = self.device_selector.count() - 1
        if selected is not None and index == 0:
            prefix = "不可用：" if self._catalog_loaded else "已保存，待刷新："
            self.device_selector.addItem(prefix + selected["name"] + "（"
                                         + selected["host_api"] + "）", dict(selected))
            index = self.device_selector.count() - 1
        self.device_selector.setCurrentIndex(index)

    def _replace_voices(self, selected):
        self.voice_selector.clear()
        self.voice_selector.addItem("系统默认音色", "")
        index = 0
        for item in self._voices:
            label = item.name + (" · " + ", ".join(item.languages) if item.languages else "")
            self.voice_selector.addItem(label, item.id)
            if item.id == selected:
                index = self.voice_selector.count() - 1
        if selected and index == 0:
            prefix = "不可用：" if self._catalog_loaded else "已保存，待刷新："
            self.voice_selector.addItem(prefix + selected[:64], selected)
            index = self.voice_selector.count() - 1
        self.voice_selector.setCurrentIndex(index)

    def _changed(self, *_args):
        if self._mutating:
            return
        self._update_summary()
        self.settings_changed.emit()

    def _update_summary(self):
        microphone = self.device_selector.currentText()
        voice = self.voice_selector.currentText()
        self.summary_label.setText(
            microphone[:60] + " · " + voice[:60] + " · 语速 " + str(self.rate()))
        self.device_selector.setToolTip(microphone)
        self.voice_selector.setToolTip(self.voice_id() or "使用系统默认音色")

    def set_busy(self, busy, *, can_stop=False):
        for control in (self.refresh_button, self.preview_button, self.device_selector,
                        self.voice_selector, self.rate_spin):
            control.setEnabled(not busy)
        self.stop_button.setEnabled(can_stop)
