"""Live Qt action preview of an already-installed Guga/Doro role.

Preview is deliberately read-only; it neither changes the active pet nor
copies original fan-art. Nothing is uploaded and no network is used.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QPushButton, QVBoxLayout,
)

from tools.role_action_preview import action_preview_plan


class MascotActionPreview(QDialog):
    """Display real numbered animation frames on the current Qt/X11 screen."""

    def __init__(self, role_folder, *, original_demo=False, parent=None):
        super().__init__(parent)
        self.plan=action_preview_plan(role_folder)
        self.original_demo=bool(original_demo)
        self.frame_index=0
        self.current=None
        self.timer=QTimer(self)
        self.timer.timeout.connect(self._advance)
        self.setWindowTitle("角色动画预览 · "+self.plan["folder"])
        self.setMinimumWidth(370)

        layout=QVBoxLayout(self)
        if self.original_demo:
            message="程序原创演示：不代表咕嘎／Doro 原作者的素材或声音。"
        else:
            message="本地来源角色：仅预览实际动画，不认证原设一致性或授权。"
        self.disclaimer=QLabel(message,self)
        self.disclaimer.setWordWrap(True)
        layout.addWidget(self.disclaimer)

        self.actions=QComboBox(self)
        for entry in self.plan["actions"]:
            self.actions.addItem(
                f"{entry['name']} · {entry['frame_count']} 帧",entry["name"])
        self.actions.currentIndexChanged.connect(self._change_action)
        layout.addWidget(self.actions)

        self.frame=QLabel(self)
        self.frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frame.setFixedSize(320,280)
        layout.addWidget(self.frame,alignment=Qt.AlignmentFlag.AlignCenter)

        self.status=QLabel(self)
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)
        controls=QHBoxLayout()
        self.pauseButton=QPushButton("暂停",self)
        self.pauseButton.clicked.connect(self._toggle)
        close=QPushButton("关闭",self)
        close.clicked.connect(self.close)
        controls.addWidget(self.pauseButton)
        controls.addWidget(close)
        layout.addLayout(controls)
        self._change_action(0)

    def _change_action(self,index):
        self.timer.stop()
        if index<0 or index>=len(self.plan["actions"]):
            return
        self.current=self.plan["actions"][index]
        self.frame_index=0
        self._show_frame()
        if self.current["frame_count"]>1:
            self.pauseButton.setText("暂停")
            self.timer.start(self.current["interval_ms"])
        else:
            self.pauseButton.setText("播放")

    def _show_frame(self):
        if self.current is None:
            return
        path=self.current["frames"][self.frame_index]
        pixmap=QPixmap(str(path))
        if pixmap.isNull():
            self.timer.stop()
            self.frame.setText("PNG 图片无法读取："+path.name)
            self.status.setText("预览失败（不影响已安装角色文件）")
            return
        self.frame.setPixmap(pixmap.scaled(
            self.frame.size(),Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation))
        self.status.setText(
            f"{self.current['name']} · {self.frame_index+1}/"
            f"{self.current['frame_count']} 帧 · "
            f"{self.current['interval_ms']} ms/帧")

    def _advance(self):
        if not self.current:
            return
        self.frame_index=(self.frame_index+1)%self.current["frame_count"]
        self._show_frame()

    def _toggle(self):
        if self.timer.isActive():
            self.timer.stop()
            self.pauseButton.setText("播放")
        elif self.current and self.current["frame_count"]>1:
            self.timer.start(self.current["interval_ms"])
            self.pauseButton.setText("暂停")

    def closeEvent(self,event):
        self.timer.stop()
        super().closeEvent(event)
