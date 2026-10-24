"""Small first-use chooser that reuses native role frames and animation preview.

Does not fetch third-party art or change a character until the user confirms.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QMessageBox, QPushButton, QVBoxLayout,
)

from .first_run import installed_playable_roles


class FirstRunRoleDialog(QDialog):
    """Select an actually installed role in two user-visible steps."""

    def __init__(self, role_root, *, current_role="Kitty", parent=None):
        super().__init__(parent)
        self.role_root = Path(role_root)
        self.entries = installed_playable_roles(self.role_root)
        self.current_role = current_role
        self.selected_role = None
        self.setWindowTitle("DyberPet · 欢迎使用桌宠")
        self.setMinimumSize(480, 530)
        layout = QVBoxLayout(self)

        heading = QLabel("欢迎！选择一个喜欢的桌宠，就可以开始使用。", self)
        heading.setWordWrap(True)
        layout.addWidget(heading)
        self.notice = QLabel(
            "无需 AI 模型、麦克风或登录。角色库中只列出本机可播放的素材；"
            "标记为「原创演示」的形象不是原作者的游戏美术或配音。",
            self)
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("搜索本机角色名称，例如 Kitty、Doro")
        layout.addWidget(self.search)

        self.roles = QListWidget(self)
        self.roles.setMinimumHeight(145)
        self.roles.itemDoubleClicked.connect(lambda _item: self.choose())
        layout.addWidget(self.roles)

        self.frame = QLabel(self)
        self.frame.setFixedHeight(155)
        self.frame.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.frame)

        self.status = QLabel(self)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        controls = QHBoxLayout()
        self.preview = QPushButton("预览角色动作", self)
        self.preview.clicked.connect(self.preview_animation)
        self.use = QPushButton("使用这个桌宠", self)
        self.use.clicked.connect(self.choose)
        self.skip = QPushButton("保留当前桌宠", self)
        self.skip.clicked.connect(self.reject)
        controls.addWidget(self.preview)
        controls.addWidget(self.use)
        controls.addWidget(self.skip)
        layout.addLayout(controls)
        self.search.textChanged.connect(self.refresh)
        self.roles.currentItemChanged.connect(lambda _now, _old: self.refresh_preview())
        self.refresh()
        for i in range(self.roles.count()):
            if self.roles.item(i).data(Qt.ItemDataRole.UserRole) == current_role:
                self.roles.setCurrentRow(i)
                break

    def refresh(self, *_):
        previous = self.selected_id()
        self.roles.clear()
        text = self.search.text().casefold().strip()
        for entry in self.entries:
            if text not in entry["folder"].casefold():
                continue
            label = entry["folder"] + (" · 程序原创演示" if entry["demo"] else " · 本机角色")
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, entry["folder"])
            self.roles.addItem(item)
            if entry["folder"] == previous:
                self.roles.setCurrentItem(item)
        if self.roles.count() and self.roles.currentRow() < 0:
            self.roles.setCurrentRow(0)
        self.use.setEnabled(self.roles.count() > 0)
        self.preview.setEnabled(self.roles.count() > 0)
        self.refresh_preview()

    def selected_id(self):
        item = self.roles.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _selected_entry(self):
        role = self.selected_id()
        return next((item for item in self.entries if item["folder"] == role), None)

    def refresh_preview(self):
        entry = self._selected_entry()
        if entry is None:
            self.frame.clear()
            self.status.setText("本机没有匹配的可播放角色。可以先使用默认角色或在角色管理中导入。")
            return
        pixmap = QPixmap(entry["preview"])
        if pixmap.isNull():
            self.frame.setText("该角色缩略图无法读取，可尝试动作预览")
        else:
            self.frame.setPixmap(pixmap.scaled(
                180, 150, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        self.status.setText(
            f"将使用本机文件：{entry['folder']}。"
            + ("此形象是原创 Q 版演示，不代表角色原设。" if entry["demo"]
               else "这是已安装的本地素材，不自动认证原设或许可。"))

    def preview_animation(self):
        entry = self._selected_entry()
        if entry is None:
            return
        try:
            from DyberPet.DyberSettings.mascot_preview_dialog import MascotActionPreview
            viewer = MascotActionPreview(
                self.role_root / entry["folder"],
                original_demo=entry["demo"], parent=self)
            viewer.exec()
        except (OSError, ValueError, KeyError, TypeError) as exc:
            QMessageBox.warning(self, "动作预览不可用", str(exc))

    def choose(self):
        role = self.selected_id()
        if role:
            # No mutations occur here: the caller performs the switch and save.
            self.selected_role = role
            self.accept()
