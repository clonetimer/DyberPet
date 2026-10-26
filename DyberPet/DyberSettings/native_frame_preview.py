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
    QCheckBox, QComboBox, QDialog, QFileDialog, QGridLayout, QHBoxLayout, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSlider, QVBoxLayout,
)

from tools.artist_animation_audit import (
    _frames_for_action, _read_config, MAX_ACTIONS, MAX_PIXELS, MAX_SIDE)
from tools.character_interaction_coverage import _safe_installed_role
from DyberPet.assistant.role_interactions import available_interactions
from tools.creator_art_manual_review import (
    GRADES, CHIBI_FORMS, create_manual_review_receipt, save_manual_review)
from tools.creator_chibi_quality import (
    load_local_quality_review, save_local_quality_review)


def _inventory_stat_snapshot(role_root, folder, inventory):
    """Detect files replaced during this review before recording seen frames."""
    role = _safe_installed_role(Path(role_root).expanduser(), folder)
    files = {role / "act_conf.json", role / "pet_conf.json"}
    files.update(p for frames in inventory.values() for p in frames)
    return tuple(sorted((str(p), p.stat().st_size, p.stat().st_mtime_ns)
                        for p in files))


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
        # A character gets ONLY genuine authored actions from this exact local
        # version. Missing categories are visibly disabled, never synthesized.
        self.interaction_summary = QLabel(self)
        self.interaction_summary.setWordWrap(True)
        layout.addWidget(self.interaction_summary)
        interaction_grid = QGridLayout()
        self.interaction_buttons = {}
        for index, item in enumerate(available_interactions(())):
            button = QPushButton(item["label"], self)
            button.setEnabled(False)
            button.setToolTip("当前作者素材未提供该互动动作")
            button.clicked.connect(
                lambda _checked=False, category=item["id"]:
                self._preview_interaction(category))
            interaction_grid.addWidget(button, index // 4, index % 4)
            self.interaction_buttons[item["id"]] = button
        layout.addLayout(interaction_grid)
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
        review = QHBoxLayout()
        self.grade = QComboBox(self)
        for label in GRADES:
            self.grade.addItem(label, label)
        review.addWidget(QLabel("原设外观", self))
        review.addWidget(self.grade)
        self.chibi_form = QComboBox(self)
        for form in CHIBI_FORMS:
            self.chibi_form.addItem(form, form)
        review.addWidget(QLabel("Q版体态", self))
        review.addWidget(self.chibi_form)
        self.compared = QCheckBox("已人工对照原设", self)
        self.motion_checked = QCheckBox("已人工检查动作", self)
        self.desktop_checked = QCheckBox("已在真实桌面测试", self)
        review.addWidget(self.compared)
        review.addWidget(self.motion_checked)
        review.addWidget(self.desktop_checked)
        layout.addLayout(review)
        self.review_note = QLineEdit(self)
        self.review_note.setMaxLength(500)
        self.review_note.setPlaceholderText("差异说明：发饰/服装/动作等（不填也可）")
        layout.addWidget(self.review_note)
        self.export_review = QPushButton("导出本版本人工核对记录 JSON", self)
        self.export_review.clicked.connect(self._export_review)
        layout.addWidget(self.export_review)
        self.save_q_grade = QPushButton("保存本机 Q版/立牌审核（不修改角色素材）", self)
        self.save_q_grade.setToolTip(
            "将逐版本人工评价存在软件 data 目录；"
            "未审核、立牌型、动作有缺陷的角色不进入合格推荐。"
            "素材图片变更后自动要求重审。")
        self.save_q_grade.clicked.connect(self._save_q_review)
        layout.addWidget(self.save_q_grade)
        self.quality_status = QLabel(self)
        self.quality_status.setWordWrap(True)
        layout.addWidget(self.quality_status)
        self._visited = {}
        self._snapshots = {}
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
        self.grade.setCurrentIndex(0)
        self.chibi_form.setCurrentIndex(0)
        self.desktop_checked.setChecked(False)
        self.compared.setChecked(False)
        self.motion_checked.setChecked(False)
        self.review_note.clear()
        # Validate every frame before the GUI offers to play this variant.
        try:
            self._inventory = safe_animation_inventory(
                self._root, self.version.currentData())
            folder = self.version.currentData()
            metadata = _inventory_stat_snapshot(
                self._root, folder, self._inventory)
            if self._snapshots.get(folder) != metadata:
                self._visited[folder] = {}
            self._snapshots[folder] = metadata
        except (OSError, ValueError, TypeError, KeyError) as exc:
            # Qt signal handlers must not let a broken third-party folder
            # abort the desktop process. Show a reviewable problem instead.
            self._inventory = {}
            self._frames = []
            self.canvas.clear()
            self.canvas.setText("无法打开此作者动画：" + str(exc)[:170])
            self.status.setText("版本不可用")
            self.play.setEnabled(False)
            self.export_review.setEnabled(False)
            self.save_q_grade.setEnabled(False)
            self.quality_status.setText("该版本素材不可用，不能进行Q版合格认证。")
            # Clearing a QComboBox emits currentIndexChanged(-1). Without
            # suppressing that notification _select_action replaces the
            # useful source-error status with a misleading empty 0/0.
            self.action.blockSignals(True)
            self.action.clear()
            self.action.blockSignals(False)
            self._refresh_interaction_shortcuts()
            return
        self.play.setEnabled(True)
        self.export_review.setEnabled(True)
        self.save_q_grade.setEnabled(True)
        self._show_current_quality()
        self.action.blockSignals(True)
        self.action.clear()
        for name in self._inventory:
            self.action.addItem(name, name)
        self.action.blockSignals(False)
        self._refresh_interaction_shortcuts()
        self._select_action()

    def _refresh_interaction_shortcuts(self):
        actions = available_interactions(self._inventory.keys())
        total = 0
        for item in actions:
            button = self.interaction_buttons[item["id"]]
            usable = bool(item["available"])
            button.setEnabled(usable)
            button.setToolTip(
                "预览当前版本的真实 PNG 动作：" + item["action"]
                if usable else "该素材版本没有可用的对应动作，未作合成")
            total += int(usable)
        self.interaction_summary.setText(
            f"本素材版本可预览 {total} / {len(actions)} 类真实互动；"
            "不可用的按钮保持禁用（不是多个版本的动作总和）。")

    def _preview_interaction(self, category):
        choices = available_interactions(self._inventory.keys())
        match = next((x for x in choices
                      if x["id"] == category and x["available"]), None)
        if match is None:
            return
        idx = self.action.findData(match["action"])
        if idx < 0:
            return  # Never dispatch a filename absent from this version.
        self.action.setCurrentIndex(idx)
        if not self._clock.isActive() and self._frames:
            self._toggle_play()

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
        folder = self.version.currentData()
        action = self.action.currentData()
        if isinstance(folder, str) and isinstance(action, str):
            self._visited.setdefault(folder, {}).setdefault(action, set()).add(
                self._index)

    def _show_current_quality(self):
        folder = self.version.currentData()
        if not isinstance(folder, str):
            self.quality_status.setText("候选角色：未完成逐版本Q版审核")
            return
        state = load_local_quality_review(self._root, folder, full_audit=False)
        labels = {
            "unreviewed_candidate": "待人工验收：仍为候选素材",
            "rejected_standee": "不推荐：本人已标记为立牌/细长立绘",
            "rejected_visual": "不推荐：外观与原设不符",
            "rejected_motion": "不推荐：原生动作质量未达标",
            "candidate_not_approved": "候选：原设/体态/动作/桌面测试证据不足",
            "source_changed_recheck": "素材已改变：原审核作废，请重新评审",
            "review_invalid": "审核记录失效：请重新评审",
        }
        # This quick status intentionally NEVER claims "passed" without deep audit.
        if state["status"] == "candidate_not_approved" and state.get("reason") == "full_png_audit_required":
            self.quality_status.setText("已有人工Q版审核记录；完整动作结构复核将在合格列表检查时执行。")
        else:
            self.quality_status.setText(labels.get(
                state["status"], "当前版本为候选素材：" + state["status"]))

    def _current_receipt(self):
        folder = self.version.currentData()
        if not folder or not self._inventory:
            raise ValueError("请先选择能够读取完整原画帧的角色素材")
        if _inventory_stat_snapshot(
                self._root, folder, self._inventory) != self._snapshots.get(folder):
            raise ValueError("原画在本次预览后已改变，必须重新打开该版本")
        return create_manual_review_receipt(
            self._root, folder, self._inventory,
            self._visited.get(folder, {}), self.grade.currentData(),
            self.compared.isChecked(), self.motion_checked.isChecked(),
            self.review_note.text(), chibi_form=self.chibi_form.currentData(),
            desktop_checked=self.desktop_checked.isChecked())

    def _save_q_review(self):
        folder = self.version.currentData()
        try:
            receipt = self._current_receipt()
            state = save_local_quality_review(self._root, folder, receipt)
            self._show_current_quality()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "Q版审核保存失败", str(exc))
            return
        description = {
            "user_q_standard_eligible": "本人Q版评审通过，已通过全帧结构门禁；非官方美术认证",
            "rejected_standee": "标为立牌/立绘型，已从本机合格推荐中排除",
            "rejected_visual": "形象不符，已从本机合格推荐中排除",
            "rejected_motion": "动作存在结构问题，暂不进入合格推荐",
        }.get(state["status"], "保留为候选素材，不计入Q版合格角色数")
        QMessageBox.information(self, "本机Q版审核已保存", description)

    def _export_review(self):
        folder = self.version.currentData()
        if not folder or not self._inventory:
            return
        filename, _ = QFileDialog.getSaveFileName(
            self, "保存本人逐版本视觉与动作核对",
            "DyberPet_manual_review_" + folder + ".json", "JSON 文件 (*.json)")
        if not filename:
            return
        try:
            receipt = self._current_receipt()
            save_manual_review(filename, receipt, role_root=self._root)
        except (OSError, ValueError, TypeError) as exc:
            QMessageBox.warning(self, "人工核对记录未保存", str(exc))
            return
        QMessageBox.information(
            self, "记录已保存",
            "仅保存本人对当前版本的视觉评价与已显示帧数；"
            "不能代替官方形象、授权或实际桌面验收。")

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
