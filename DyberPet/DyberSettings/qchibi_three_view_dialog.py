"""R43: fixed-scale Q版 three-view comparison + real sprite action interaction.

The renderer uses EXACT pixels of the native installed role; it never
reconstructs a missing back view. Windows/Linux share the same Qt surface.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import (
    QDialog, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from tools.qchibi_native_threeview import native_threeview_interactions
from tools.qchibi_threeview_audit import audit_role

VIEW_LABELS = {"front": "正面参考", "side": "侧面参考", "back": "背面参考"}
BUTTONS = ("default", "left", "right", "patpat", "drag", "on_floor", "fall")


class QChibiThreeViewDialog(QDialog):
    """One source art/scale, honest missing directions and playable interactions."""

    def __init__(self, role_directory, parent=None):
        super().__init__(parent)
        self.plan = native_threeview_interactions(role_directory)
        self.designEvidence = audit_role(role_directory)
        self.untrustedViews = set()
        for issue in self.designEvidence["issues"]:
            # If two directions are just the same image / its exact mirror,
            # keep the first view and hide the suspicious later direction.
            if ":identical_visible_pixels" in issue or ":exact_horizontal_mirror" in issue:
                pair = issue.split(":", 1)[0].split("_")
                if len(pair) == 2:
                    self.untrustedViews.add(pair[1])
        self.frame_index = 0
        self.current_action = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.advance_frame)
        self.setWindowTitle("Q版三视图与真实交互 · " + self.plan["role"])
        self.setMinimumWidth(740)
        layout = QVBoxLayout(self)
        explanation = QLabel(
            "正/侧/背统一比例与着地线。缺失的背面不从正面镜像、"
            "不使用其他画师的造型拼凑。点击下方交互播放实际角色 PNG。",
            self)
        explanation.setWordWrap(True)
        layout.addWidget(explanation)

        self.viewLabels = {}
        self.viewNotes = {}
        panel = QGridLayout()
        for index, name in enumerate(("front", "side", "back")):
            title = QLabel(VIEW_LABELS[name], self)
            title.setAlignment(Qt.AlignmentFlag.AlignCenter)
            panel.addWidget(title, 0, index)
            sprite = QLabel(self)
            sprite.setAlignment(Qt.AlignmentFlag.AlignCenter)
            sprite.setFixedSize(222, 228)
            view = self.plan["views"][name]
            if name in self.untrustedViews:
                sprite.setText("此方向与另一视图重复/镜像，不作为独立三视图")
            elif view["file"] is None:
                sprite.setText("缺少独立背面原画" if name == "back" else "无可靠方向图")
            else:
                sprite.setPixmap(self._grounded_pixmap(
                    view["file"], self.plan["pose_geometry"]["views"][name]))
            self.viewLabels[name] = sprite
            panel.addWidget(sprite, 1, index)
            note = QLabel(view["evidence"], self)
            note.setAlignment(Qt.AlignmentFlag.AlignCenter)
            note.setWordWrap(True)
            self.viewNotes[name] = note
            panel.addWidget(note, 2, index)
        layout.addLayout(panel)

        # Native action previews alone are not orthographic source views.
        # Reject source sheets that just copy/flip the same pose.
        if self.designEvidence["ready_for_manual_art_review"]:
            reviewed = "三视图源图已核验为独立候选；原设和人设一致性仍待人工验收"
        elif self.designEvidence["status"] == "threeview_requires_source_correction":
            reviewed = "三视图来源可疑（复制/水平镜像/比例异常）：不得标记完成。"
        else:
            reviewed = "尚无可用的独立三视图证据，所示正/侧仅为动作参考，不能算三视图通过"
        self.sourceStatus = QLabel(reviewed, self)
        self.sourceStatus.setWordWrap(True)
        layout.addWidget(self.sourceStatus)
        alerts = self.plan["pose_geometry"]["warnings"]
        self.poseQA = QLabel(
            ("动作/形象复核提醒：" + "；".join(alerts[:4]) if alerts
             else "原生动作帧未发现上述机械异常；形象仍需人工验收"), self)
        self.poseQA.setWordWrap(True)
        layout.addWidget(self.poseQA)

        actions = QGridLayout()
        self.actionButtons = {}
        for i, key in enumerate(BUTTONS):
            item = self.plan["interactions"].get(key)
            button = QPushButton(
                item["label"] if item else {
                    "default": "正面待机", "left": "向左移动",
                    "right": "向右移动", "patpat": "摸头反馈",
                    "drag": "拖拽反馈", "on_floor": "休息 / 落地",
                    "fall": "下落",
                }[key], self)
            button.setEnabled(item is not None)
            button.clicked.connect(lambda _checked=False, k=key: self.play_interaction(k))
            actions.addWidget(button, i // 4, i % 4)
            self.actionButtons[key] = button
        layout.addLayout(actions)

        self.animated = QLabel(self)
        self.animated.setFixedSize(222, 228)
        self.animated.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.actionState = QLabel("交互预览尚未开始", self)
        self.actionState.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bottom = QHBoxLayout()
        bottom.addStretch()
        bottom.addWidget(self.animated)
        status = QVBoxLayout()
        status.addWidget(self.actionState)
        self.pauseButton = QPushButton("暂停", self)
        self.pauseButton.clicked.connect(self.toggle)
        status.addWidget(self.pauseButton)
        bottom.addLayout(status)
        bottom.addStretch()
        layout.addLayout(bottom)

        close = QPushButton("关闭", self)
        close.clicked.connect(self.close)
        layout.addWidget(close)
        self.play_interaction("default")

    def _grounded_pixmap(self, path, geometry):
        """Preserve unedited source PNG with constant alpha-silhouette anchor.

        Transparent author canvas padding no longer alters the apparent
        character scale or grounding. Crucially the SAME action-union anchor
        is used for every frame, preserving actual jumping and bobbing.
        """
        source = QPixmap(str(path))
        if source.isNull():
            raise ValueError("原画源 PNG 无法在 Qt 中读取：" + Path(path).name)
        full_w, full_h = self.plan["pose_geometry"]["reference_visible_dimensions"]
        scale = min(200 / full_w, 200 / full_h, 1.0)
        width = max(1, round(source.width() * scale))
        height = max(1, round(source.height() * scale))
        source = source.scaled(width, height,
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        anchor_x, anchor_y = geometry["anchor"]
        canvas = QPixmap(222, 228)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.drawPixmap(
            round(111 - anchor_x * scale),
            round(216 - anchor_y * scale), source)
        painter.end()
        return canvas

    def play_interaction(self, key):
        """Real action image sequence for actual left/right/pet/drag signals."""
        if key not in self.plan["interactions"]:
            return False
        self.timer.stop()
        self.current_action = key
        self.frame_index = 0
        self.show_frame()
        entry = self.plan["interactions"][key]
        if len(entry["frames"]) > 1:
            self.timer.start(entry["interval_ms"])
            self.pauseButton.setText("暂停")
        else:
            self.pauseButton.setText("播放")
        return True

    def show_frame(self):
        if self.current_action is None:
            return
        entry = self.plan["interactions"][self.current_action]
        path = entry["frames"][self.frame_index]
        self.animated.setPixmap(self._grounded_pixmap(
            path, self.plan["pose_geometry"]["interactions"][self.current_action]))
        self.actionState.setText(
            entry["label"] + " · 原生 " + entry["action"]
            + " · " + str(self.frame_index + 1)
            + "/" + str(len(entry["frames"]))
            + " 帧 · " + str(entry["interval_ms"]) + " ms")

    def advance_frame(self):
        if self.current_action is None:
            return
        count = len(self.plan["interactions"][self.current_action]["frames"])
        self.frame_index = (self.frame_index + 1) % count
        self.show_frame()

    def toggle(self):
        if self.timer.isActive():
            self.timer.stop()
            self.pauseButton.setText("播放")
        elif self.current_action is not None:
            entry = self.plan["interactions"][self.current_action]
            if len(entry["frames"]) > 1:
                self.timer.start(entry["interval_ms"])
                self.pauseButton.setText("暂停")

    def closeEvent(self, event):
        self.timer.stop()
        super().closeEvent(event)
