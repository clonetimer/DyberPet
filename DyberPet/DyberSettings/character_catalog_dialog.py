"""Search and filter all installed-character templates in one local Qt dialog.

No network, disk mutation or source-art verification occurs in this UI.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)

from tools.character_catalog_search import (
    describe_character_status, query_character_catalog,
)


class CharacterCatalogDialog(QDialog):
    """Non-programmer-friendly browser across 123 Genshin and 2 mascots."""

    def __init__(self, progress_report, parent=None):
        super().__init__(parent)
        entries = progress_report["characters"]
        self._entries = list(entries)
        self._selected_id = None
        self.setWindowTitle("DyberPet · 全部角色库（本机状态）")
        self.setMinimumSize(600, 520)
        layout = QVBoxLayout(self)
        self.searchBox = QLineEdit(self)
        self.searchBox.setPlaceholderText(
            "搜索中文、英文或角色 ID，例如 丽莎 / Lisa / Doro")
        layout.addWidget(self.searchBox)

        filters = QHBoxLayout()
        self.familyFilter = QComboBox(self)
        for label, value in (("全部角色", "all"), ("原神人物与伙伴", "genshin"),
                             ("咕嘎 / Doro", "mascot")):
            self.familyFilter.addItem(label, value)
        self.statusFilter = QComboBox(self)
        for label, value in (("已安装真实来源素材（优先）", "personal"),
                             ("全部角色（含低保真演示）", "all"),
                             ("程序绘制演示（非原设）", "demo"),
                             ("待安装素材", "missing")):
            self.statusFilter.addItem(label, value)
        filters.addWidget(self.familyFilter)
        filters.addWidget(self.statusFilter)
        layout.addLayout(filters)

        self.results = QListWidget(self)
        self.results.setAlternatingRowColors(True)
        self.results.itemDoubleClicked.connect(lambda _item: self._select())
        layout.addWidget(self.results)

        self.countLabel = QLabel(self)
        layout.addWidget(self.countLabel)
        self.disclaimer = QLabel(
            "默认优先展示真实来源素材；程序低保真演示须主动切换筛选。"
            "安装成功也不等于已经通过原设相似度人工验收。", self)
        self.disclaimer.setWordWrap(True)
        layout.addWidget(self.disclaimer)

        buttons = QHBoxLayout()
        self.manageButton = QPushButton("管理原神素材关联", self)
        self.manageButton.clicked.connect(self._open_manage)
        self.openButton = QPushButton("查看角色 / 预览动作", self)
        self.openButton.clicked.connect(self._select)
        close = QPushButton("关闭", self)
        close.clicked.connect(self.reject)
        buttons.addWidget(self.manageButton)
        buttons.addStretch(1)
        buttons.addWidget(self.openButton)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.searchBox.textChanged.connect(self._refresh)
        self.familyFilter.currentIndexChanged.connect(self._refresh)
        self.statusFilter.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self, *_):
        old = self.selected_character_id()
        self.results.clear()
        rows = query_character_catalog(
            self._entries, self.searchBox.text(),
            self.familyFilter.currentData(), self.statusFilter.currentData())
        for row in rows:
            status = describe_character_status(row)
            prefix = "原神" if row["family"] == "genshin" else "吉祥物"
            title = f"【{prefix}】{row['name']} · {status}"
            item = QListWidgetItem(title)
            item.setToolTip(
                f"{row['id']} · 演示动作 {row['demo_actions']} 类 / "
                f"{row['demo_frames']} 帧；不提供原设一致性认证")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.results.addItem(item)
            if row["id"] == old:
                self.results.setCurrentItem(item)
        if self.results.count() and self.results.currentItem() is None:
            self.results.setCurrentRow(0)
        self.countLabel.setText(
            f"当前筛选 {self.results.count()} / {len(self._entries)} 个角色。"
            "可切换为「全部角色」查看程序演示，或点击素材管理安装真实角色。")
        self.openButton.setEnabled(self.results.count() > 0)

    def selected_character_id(self):
        current = self.results.currentItem()
        return current.data(Qt.ItemDataRole.UserRole) if current else None

    def _select(self):
        selected = self.selected_character_id()
        if selected:
            self._selected_id = selected
            self.accept()

    def _open_manage(self):
        self._selected_id = "__manage_genshin__"
        self.accept()

    @property
    def selection(self):
        return self._selected_id
