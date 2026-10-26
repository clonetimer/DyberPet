"""Search and filter all installed-character templates in one local Qt dialog.

No network, disk mutation or source-art verification occurs in this UI.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QFileDialog, QMessageBox,
)

from tools.character_catalog_search import (
    describe_character_status, query_character_catalog,
)
from tools.character_source_coverage import source_coverage
from tools.community_codex_leads import PROFILE_TO_SLUG
from tools.react_shimeji_source_leads import CANDIDATES as REACT_CANDIDATES, REPOSITORY as REACT_REPO, REVISION as REACT_REV


class CharacterCatalogDialog(QDialog):
    """Non-programmer-friendly browser across 123 Genshin and 2 mascots."""

    def __init__(self, progress_report, parent=None, role_root=None):
        super().__init__(parent)
        self._role_root = Path(role_root).expanduser() if role_root is not None else None
        entries = progress_report["characters"]
        self._entries = list(entries)
        self._source_by_id = {x["id"]: x for x in source_coverage()["characters"]}
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
        for label, value in (("原神人物与伙伴", "genshin"), ("全部角色", "all"),
                             ("咕嘎 / Doro", "mascot")):
            self.familyFilter.addItem(label, value)
        self.statusFilter = QComboBox(self)
        for label, value in (("有公开作者素材可获取（未必已安装）", "source"),
                             ("已安装真实来源素材", "personal"),
                             ("仍缺公开作者素材（待补齐）", "source_missing"),
                             ("有社区候选、待核验真实性", "lead"),
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
        self.results.currentItemChanged.connect(self._refresh_candidate_button)
        layout.addWidget(self.results)

        self.countLabel = QLabel(self)
        layout.addWidget(self.countLabel)
        self.disclaimer = QLabel(
            "默认显示有公开作者素材来源的人物（不表示素材已安装）。"
            "① 精细 Q 版优先，② 作者图集需看图，③ 小型 Shimeji 可接受。"
            "图集来源、安装成功与原设相似度人工验收是不同状态。", self)
        self.disclaimer.setWordWrap(True)
        layout.addWidget(self.disclaimer)

        buttons = QHBoxLayout()
        self.installArtistButton = QPushButton("安装真实作者素材", self)
        self.installArtistButton.clicked.connect(self._install_artist)
        self.communityButton = QPushButton("浏览本人物公开候选（待核验）", self)
        self.communityButton.clicked.connect(self._open_community_candidate)
        self.manageButton = QPushButton("管理原神素材关联", self)
        self.manageButton.clicked.connect(self._open_manage)
        self.openButton = QPushButton("查看角色 / 预览动作", self)
        self.openButton.clicked.connect(self._select)
        close = QPushButton("关闭", self)
        close.clicked.connect(self.reject)
        buttons.addWidget(self.installArtistButton)
        buttons.addWidget(self.communityButton)
        buttons.addWidget(self.manageButton)
        buttons.addStretch(1)
        buttons.addWidget(self.openButton)
        buttons.addWidget(close)
        layout.addLayout(buttons)

        self.exportGapButton = QPushButton("导出全部角色素材与互动缺口 JSON", self)
        self.exportGapButton.setToolTip(
            "只读汇总本机创作者原画和可解码的首帧动作，不会下载素材，"
            "也不会将原设视觉或实际桌面验收误判为通过")
        self.exportGapButton.setEnabled(self._role_root is not None)
        self.exportGapButton.clicked.connect(self._export_gap_report)
        layout.addWidget(self.exportGapButton)

        self.searchBox.textChanged.connect(self._refresh)
        self.familyFilter.currentIndexChanged.connect(self._refresh)
        self.statusFilter.currentIndexChanged.connect(self._refresh)
        self._refresh()

    def _refresh(self, *_):
        old = self.selected_character_id()
        self.results.clear()
        show_leads = self.statusFilter.currentData() == "lead"
        rows = query_character_catalog(
            self._entries, self.searchBox.text(),
            self.familyFilter.currentData(),
            "all" if show_leads else self.statusFilter.currentData(),
            source_lookup=self._source_by_id)
        if show_leads:
            candidates = set(PROFILE_TO_SLUG) | set(REACT_CANDIDATES)
            rows = [row for row in rows if row["id"] in candidates and
                    not self._source_by_id.get(row["id"], {}).get("source_found", False)]
        for row in rows:
            status = describe_character_status(row)
            prefix = "原神" if row["family"] == "genshin" else "吉祥物"
            source = self._source_by_id.get(row["id"])
            creator_info = (f" · {source['source_candidate_count']} 项作者来源"
                            f" · {source['style_preference_text']}"
                            if source is not None and source["source_found"] else
                            " · 暂无固定版本的作者素材" if row["family"] == "genshin" else "")
            lead = (" · 社区图集候选（未审核）"
                    if row["id"] in PROFILE_TO_SLUG and
                    (source is None or not source["source_found"]) else "")
            if row["id"] in REACT_CANDIDATES and (source is None or not source["source_found"]):
                lead += " · Git LFS 动画候选（原文件待核验）"
            title = f"【{prefix}】{row['name']} · {status}{creator_info}{lead}"
            item = QListWidgetItem(title)
            item.setToolTip(
                f"{row['id']} · 演示动作 {row['demo_actions']} 类 / "
                f"{row['demo_frames']} 帧；{creator_info.strip()}；"
                "作者来源不等于已安装，也未通过形象人工验收")
            item.setData(Qt.ItemDataRole.UserRole, row["id"])
            self.results.addItem(item)
            if row["id"] == old:
                self.results.setCurrentItem(item)
        if self.results.count() and self.results.currentItem() is None:
            self.results.setCurrentRow(0)
        self.countLabel.setText(
            f"当前筛选 {self.results.count()} / {len(self._entries)} 个角色。"
            "先选人物再点「安装真实作者素材」：只显示该人物对应的来源，精细版优先。")
        self.openButton.setEnabled(self.results.count() > 0)
        self._refresh_candidate_button()

    def selected_character_id(self):
        current = self.results.currentItem()
        return current.data(Qt.ItemDataRole.UserRole) if current else None

    def _refresh_candidate_button(self, *_):
        profile = self.selected_character_id()
        has_lead = profile in PROFILE_TO_SLUG or profile in REACT_CANDIDATES
        self.communityButton.setEnabled(has_lead)
        self.communityButton.setToolTip(
            "只打开外部来源的图集预览，需逐帧核验后自行下载并导入；不视为已安装或原设验收"
            if has_lead else "该人物目前没有登记可查看的社区素材候选")

    def _open_community_candidate(self):
        """Open an allowlisted preview only after an explicit user selection."""
        profile = self.selected_character_id()
        candidates = {}
        if profile in PROFILE_TO_SLUG:
            candidates["CodexPetDB 社区图集（未校验原画）"] = (
                "https://codexpetdb.com/en/pets/" + PROFILE_TO_SLUG[profile])
        if profile in REACT_CANDIDATES:
            slug = REACT_CANDIDATES[profile][0]
            candidates["React-Shimeji Git LFS 来源（动画文件尚待下载）"] = (
                f"https://github.com/{REACT_REPO}/tree/{REACT_REV}/"
                + "packages/character-" + slug)
        if not candidates:
            return
        if len(candidates) == 1:
            url = next(iter(candidates.values()))
        else:
            label, accepted = QInputDialog.getItem(
                self, "选择公开候选来源", "以下仅为线索，不代表已通过原设验收：",
                list(candidates), 0, False)
            if not accepted or label not in candidates:
                return
            url = candidates[label]
        QDesktopServices.openUrl(QUrl(url))

    def _export_gap_report(self):
        """Explicit export only: never alter source images or character saves."""
        if self._role_root is None:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "导出角色素材与互动缺口", "DyberPet_role_gaps.json",
            "JSON 文件 (*.json)")
        if not filename:
            return
        if Path(filename).suffix.lower() != ".json":
            QMessageBox.warning(self, "导出未执行", "请选用 .json 文件名。")
            return
        try:
            from tools.creator_assistant_gap_report import (
                make_gap_report, save_gap_report)
            report = make_gap_report(self._role_root)
            save_gap_report(Path(filename), report)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "导出失败", str(exc))
            return
        QMessageBox.information(
            self, "导出完成",
            "已导出可核实的素材和动作状态。"
            "原设相似度、实际动画播放、音色与来源使用条件仍需人工审核。")

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
