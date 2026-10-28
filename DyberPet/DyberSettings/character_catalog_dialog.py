"""Search and filter all installed-character templates in one local Qt dialog.

No network, disk mutation or source-art verification occurs in this UI.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)

from tools.character_catalog_search import (
    describe_character_status, query_character_catalog,
)
from tools.character_art_source_index import sources_for_role, source_coverage


class CharacterCatalogDialog(QDialog):
    """Non-programmer-friendly browser across 123 Genshin and 2 mascots."""

    def __init__(self, progress_report, parent=None):
        super().__init__(parent)
        entries = progress_report["characters"]
        self._entries = list(entries)
        self._selected_id = None
        self._sources = []
        self._sourceCoverage = source_coverage()
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
        self.results.currentItemChanged.connect(lambda _new, _old: self._refresh_sources())
        layout.addWidget(self.results)

        self.countLabel = QLabel(self)
        layout.addWidget(self.countLabel)

        # Only trusted creator URLs, no automatic model/animation downloads.
        sourceRow = QHBoxLayout()
        self.sourceChoice = QComboBox(self)
        self.sourceChoice.setAccessibleName("当前角色的原画与动态素材来源")
        self.sourceChoice.currentIndexChanged.connect(self._update_source_note)
        self.openSourceButton = QPushButton("打开作者作品页", self)
        self.openSourceButton.clicked.connect(self._open_source)
        sourceRow.addWidget(self.sourceChoice, 1)
        sourceRow.addWidget(self.openSourceButton)
        layout.addLayout(sourceRow)
        self.sourceNote = QLabel(self)
        self.sourceNote.setWordWrap(True)
        layout.addWidget(self.sourceNote)
        self.disclaimer = QLabel(
            "默认优先展示真实来源素材；程序低保真演示须主动切换筛选。"
            "安装成功也不等于已经通过原设相似度人工验收。", self)
        self.disclaimer.setWordWrap(True)
        layout.addWidget(self.disclaimer)

        buttons = QHBoxLayout()
        self.installArtistButton = QPushButton("安装真实作者素材", self)
        self.installArtistButton.clicked.connect(self._install_artist)
        self.manageButton = QPushButton("管理原神素材关联", self)
        self.manageButton.clicked.connect(self._open_manage)
        self.openButton = QPushButton("查看角色 / 预览动作", self)
        self.openButton.clicked.connect(self._select)
        close = QPushButton("关闭", self)
        close.clicked.connect(self.reject)
        buttons.addWidget(self.installArtistButton)
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
            f"当前筛选 {self.results.count()} / {len(self._entries)} 个角色；"
            f"已有专属来源线索 {self._sourceCoverage['specific_source_leads']} 位，"
            f"仅有系列查找入口 {self._sourceCoverage['family_discovery_only']} 位。"
            "来源不代表真实素材已安装或完成验收。")
        self.openButton.setEnabled(self.results.count() > 0)
        self._refresh_sources()

    def _refresh_sources(self):
        selected = self.selected_character_id()
        self._sources = sources_for_role(selected) if selected else []
        self.sourceChoice.blockSignals(True)
        self.sourceChoice.clear()
        for source in self._sources:
            scope = "角色专属线索" if source["scope"] == "role" else "系列查找入口（非角色证据）"
            self.sourceChoice.addItem(scope + " · " + source["name"], source["url"])
        self.sourceChoice.blockSignals(False)
        self._update_source_note()

    def _update_source_note(self, *_):
        index = self.sourceChoice.currentIndex()
        if index < 0 or index >= len(self._sources):
            self.openSourceButton.setEnabled(False)
            self.sourceNote.setText(
                "暂无已核对的角色专属来源。请按角色中文名寻找画师原始作品，"
                "不要使用简笔画或用系列链接冒充角色素材。")
            return
        source = self._sources[index]
        self.openSourceButton.setEnabled(True)
        self.sourceNote.setText(
            "作者：" + source["creator"] + "。"
            + ("该来源对应当前角色；" if source["scope"] == "role"
               else "这只是系列发现入口，尚未确认包含当前角色；")
            + source["note"]
            + " 原画一致性、素材许可与 Windows 实机尚未经软件自动核实。")

    def _open_source(self):
        index = self.sourceChoice.currentIndex()
        if 0 <= index < len(self._sources):
            # Only HTTPS creator URLs from a fixed, prevalidated index.
            QDesktopServices.openUrl(QUrl(self._sources[index]["url"]))

    def selected_character_id(self):
        current = self.results.currentItem()
        return current.data(Qt.ItemDataRole.UserRole) if current else None

    def _select(self):
        selected = self.selected_character_id()
        if selected:
            self._selected_id = selected
            self.accept()

    def _install_artist(self):
        self._selected_id = "__install_artist__"
        self.accept()

    def _open_manage(self):
        self._selected_id = "__manage_genshin__"
        self.accept()

    @property
    def selection(self):
        return self._selected_id
