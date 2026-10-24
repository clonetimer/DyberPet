"""Small first-use chooser that reuses native role frames and animation preview.

Does not fetch third-party art or change a character until the user confirms.
"""
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem,
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
            "程序自绘的低保真演示已默认隐藏；可按需展开。"
            "建议优先安装原作者动画，而不是把演示当作原设。",
            self)
        self.notice.setWordWrap(True)
        layout.addWidget(self.notice)

        self.search = QLineEdit(self)
        self.search.setPlaceholderText("搜索本机角色名称，例如 Kitty、Doro")
        layout.addWidget(self.search)

        self.showDemos = QCheckBox("显示低保真程序演示（非原设还原）", self)
        self.showDemos.setChecked(False)
        layout.addWidget(self.showDemos)
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
        self.showDemos.toggled.connect(self.refresh)
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
            if entry["demo"] and not self.showDemos.isChecked():
                continue
            if text not in (entry["folder"] + " " + entry["display"]).casefold():
                continue
            name = entry["display"]
            if name != entry["folder"]:
                name += " (" + entry["folder"] + ")"
            origin = (" · 程序低保真演示（非原设）" if entry["demo"] else
                      " · 公开作者素材（待人工核对）" if entry.get("artist_source") else
                      " · 已安装本机角色")
            label = name + origin
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
            self.status.setText("没有匹配的真实素材。可点击「安装作者原画角色」，"
                                "或勾选上方选项查看程序演示；当前桌宠不会被修改。")
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
            + ("此形象是程序生成的低保真演示，并非真实角色画作。" if entry["demo"]
               else "这些是公开作者制作的原始帧，但具体版本的相似度仍需您预览。" if entry.get("artist_source")
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
