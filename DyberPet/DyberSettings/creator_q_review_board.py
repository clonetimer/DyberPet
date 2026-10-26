"""R5 creator sprite comparison board for ordinary desktop users.

Renders only real, already installed author PNGs. All displayed statuses are
evidence or local user review; no hallucinated Q likeness and no downloading.
"""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QInputDialog,
    QLabel, QMessageBox, QPushButton, QScrollArea, QVBoxLayout, QWidget,
)

from tools.creator_q_review_board import make_review_board

PAGE_SIZE = 18
COLUMNS = 3
STATUS_LABELS = {
    "user_q_standard_eligible": "本人逐帧验收：Q版通过",
    "rejected_standee": "不合格：立牌/细长立绘",
    "rejected_visual": "不合格：外观不符合原设",
    "rejected_motion": "不合格：动作结构异常",
    "source_changed_recheck": "原画已变化：必须重审",
    "review_invalid": "评审记录损坏：不可认定合格",
    "unreviewed_candidate": "未人工验收：候选素材",
    "candidate_not_approved": "人审不完整：候选素材",
}


def review_visible_rows(board, kind="priority"):
    rows = board["rows"]
    if kind == "priority":
        rows = [x for x in rows if x["risk_priority"]]
    elif kind == "thin":
        rows = [x for x in rows if x["thin_silhouette_risk"]]
    elif kind == "motion":
        rows = [x for x in rows if x["weak_motion_risk"]]
    elif kind == "rejected":
        rows = [x for x in rows if x["human_q_status"] in (
            "rejected_standee", "rejected_visual", "rejected_motion")]
    elif kind == "approved":
        rows = [x for x in rows if x["human_q_status"] == "user_q_standard_eligible"]
    elif kind != "all":
        raise ValueError("Invalid creator-art comparison filter")
    return rows


def _valid_creator_link(url):
    if not isinstance(url, str) or len(url) > 2048:
        return False
    parsed = urlsplit(url)
    return parsed.scheme == "https" and parsed.hostname in {
        "github.com", "cdn.codexpetdb.com",
    } and not parsed.username and not parsed.password


class CreatorQReviewBoardDialog(QDialog):
    def __init__(self, role_root, parent=None, *, board=None):
        super().__init__(parent)
        self._root = Path(role_root).expanduser()
        self.board = board if board is not None else make_review_board(self._root)
        self._page = 0
        self._cards = []
        self.setWindowTitle("原设Q版对照墙 · 优先检查细长立牌与弱动画")
        self.setMinimumSize(1040, 760)

        layout = QVBoxLayout(self)
        title = QLabel(
            "实际安装作者 PNG 的首帧对比，不是生成的简笔画。"
            "画面宽高比按原样保留；风险只提示复核，不自动判定Q版好坏。",
            self)
        title.setWordWrap(True)
        layout.addWidget(title)
        options = QHBoxLayout()
        self.filter = QComboBox(self)
        for name, code in (
            ("优先核对（高瘦/弱运动）", "priority"),
            ("高瘦轮廓", "thin"),
            ("疑似弱运动", "motion"),
            ("本人判为立牌/不合格", "rejected"),
            ("本人Q版审查通过", "approved"),
            ("全部原画候选", "all"),
        ):
            self.filter.addItem(name, code)
        options.addWidget(self.filter)
        self.counter = QLabel(self)
        options.addWidget(self.counter)
        layout.addLayout(options)
        self.scroll = QScrollArea(self)
        self.scroll.setWidgetResizable(True)
        self.holder = QWidget()
        self.cards_layout = QGridLayout(self.holder)
        self.cards_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.holder)
        layout.addWidget(self.scroll, 1)

        pagination = QHBoxLayout()
        self.prev = QPushButton("上一批", self)
        self.next = QPushButton("下一批", self)
        self.page_number = QLabel(self)
        pagination.addWidget(self.prev)
        pagination.addWidget(self.next)
        pagination.addWidget(self.page_number)
        pagination.addStretch(1)
        self.refresh_button = QPushButton("重新读取本机人审记录", self)
        pagination.addWidget(self.refresh_button)
        layout.addLayout(pagination)
        self.footer = QLabel(
            "“浏览备用来源”仅显示已登记作者候选，并不保证更Q版或具有再分发许可。"
            "查看逐帧后可保存本机Q版/立牌评审；未经本人验收不进入Q版合格名单。",
            self)
        self.footer.setWordWrap(True)
        layout.addWidget(self.footer)

        self.filter.currentIndexChanged.connect(self._change_filter)
        self.prev.clicked.connect(lambda: self._page_change(-1))
        self.next.clicked.connect(lambda: self._page_change(1))
        self.refresh_button.clicked.connect(self._reload_reviews)
        self._render()

    def _change_filter(self, *_):
        self._page = 0
        self._render()

    def _page_change(self, delta):
        self._page += delta
        self._render()

    def _reload_reviews(self):
        try:
            self.board = make_review_board(self._root)
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "重新读取失败", str(exc))
            return
        self._render()

    def _clear_cards(self):
        while self.cards_layout.count():
            child = self.cards_layout.takeAt(0)
            widget = child.widget()
            if widget:
                widget.deleteLater()
        self._cards.clear()

    def _render(self):
        self._clear_cards()
        current = review_visible_rows(self.board, self.filter.currentData())
        pages = max(1, (len(current) + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page = max(0, min(self._page, pages - 1))
        show = current[self._page * PAGE_SIZE:(self._page + 1) * PAGE_SIZE]
        total = self.board["summary"]
        self.counter.setText(
            f"本机素材 {total['installed_artist_variants']} 套；"
            f"轮廓风险 {total['thin_risk_versions']}；"
            f"弱运动 {total['weak_motion_versions']}；"
            f"本人Q版审核通过 {total['personally_q_approved_versions']}")
        self.page_number.setText(f"第 {self._page + 1} / {pages} 页（筛选 {len(current)} 套）")
        self.prev.setEnabled(self._page > 0)
        self.next.setEnabled(self._page + 1 < pages)
        if not show:
            self.cards_layout.addWidget(QLabel("当前条件下没有已安装、可核对的作者素材", self), 0, 0)
        for i, item in enumerate(show):
            panel = self._new_card(item)
            self._cards.append(panel)
            self.cards_layout.addWidget(panel, i // COLUMNS, i % COLUMNS)

    def _new_card(self, item):
        box = QGroupBox(str(item["name"]), self.holder)
        contents = QVBoxLayout(box)
        photo = QLabel(box)
        photo.setMinimumSize(170, 175)
        photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        frame = item.get("first_png")
        if isinstance(frame, str):
            image = QPixmap(frame)
            if not image.isNull():
                photo.setPixmap(image.scaled(
                    185, 175, Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation))
            else:
                photo.setText("原画首帧无法解码")
        else:
            photo.setText("原画首帧不可用")
        contents.addWidget(photo)
        identity = QLabel(str(item["id"]) + " · " + str(item["folder"]), box)
        identity.setWordWrap(True)
        contents.addWidget(identity)
        receipt = QLabel(STATUS_LABELS.get(
            item["human_q_status"], "审核状态无效"), box)
        receipt.setWordWrap(True)
        contents.addWidget(receipt)
        flags = []
        if item["thin_silhouette_risk"]:
            flags.append("外观高瘦风险")
        if item["weak_motion_risk"]:
            flags.append("真实动画偏静止")
        if not flags:
            flags.append("自动检查暂未提示高风险≠Q版通过")
        detail = QLabel("；".join(flags), box)
        detail.setWordWrap(True)
        contents.addWidget(detail)
        actions = QHBoxLayout()
        preview = QPushButton("逐帧核对", box)
        preview.setEnabled(bool(frame))
        preview.clicked.connect(lambda _checked=False, x=item: self._open_role(x))
        actions.addWidget(preview)
        candidate = QPushButton("备用作者来源", box)
        candidate.setEnabled(bool(item.get("source_options")))
        candidate.clicked.connect(lambda _checked=False, x=item: self._open_sources(x))
        actions.addWidget(candidate)
        contents.addLayout(actions)
        box.setToolTip(
            "这张卡展示本机已安装的真实原始 PNG，未自动改动作者图像。"
            "高瘦或弱运动是审阅优先级而不是美术认定。")
        return box

    def _open_role(self, item):
        from DyberPet.DyberSettings.native_frame_preview import (
            NativeFramePreviewDialog)
        try:
            # Restrict to the exact installed creator source version.
            dlg = NativeFramePreviewDialog(self._root, [item["folder"]], self)
            dlg.exec()
            self._reload_reviews()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "原画核对无法启动", str(exc))

    def _open_sources(self, item):
        entries = [x for x in item.get("source_options", [])
                   if _valid_creator_link(x.get("url"))]
        if not entries:
            QMessageBox.information(self, "无可信备用来源", "暂无可展示的固定作者来源")
            return
        keys = [f"{x['provider']}: {x['source_key']}" for x in entries]
        # Multiple pinned sources are *candidates*, not a known superior Q art.
        answer, accepted = QInputDialog.getItem(
            self, "检查真实作者来源（不自动下载）",
            "所列来源的Q版品质尚未人工审定：", keys, 0, False)
        if accepted and answer in keys:
            entry = entries[keys.index(answer)]
            QDesktopServices.openUrl(QUrl(entry["url"]))
