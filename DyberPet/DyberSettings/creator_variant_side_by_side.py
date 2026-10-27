"""R6: side-by-side, frame-synchronous comparison of installed ORIGINAL creator art.

Both sides keep their OWN exact native action + PNG sequence: never merge
actions across versions, stretch the original silhouette, or call a source
Q-style-approved without the user's full human inspection. Screens are local;
no uploads, scraping, copy-overwrites or automatic change of active pet.
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox, QDialog, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QMessageBox, QPushButton, QSlider, QVBoxLayout,
)

from tools.character_interaction_coverage import _safe_installed_role
from tools.genshin_library import _profile_of
from tools.role_family import known_mascot_family
from tools.creator_chibi_quality import load_local_quality_review
from tools.creator_motion_quality import analyze_creator_actions
from tools.creator_motion_alternatives import compare_motion_evidence
from tools.creator_reference_cues import cues_for_local_role, cue_text
from tools.genshin_role_bindings import binding_status, load_bindings
from DyberPet.assistant.role_interactions import available_interactions
from DyberPet.DyberSettings.native_frame_preview import (
    NativeFramePreviewDialog, safe_animation_inventory,
)


def checked_variant_pair(role_root, options, left=None, right=None):
    """Validate two distinct source directories *before* loading any frame."""
    root = Path(role_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("角色原画目录不存在或是符号链接")
    if (not isinstance(options, (tuple, list)) or
            not 2 <= len(options) <= 40 or
            any(not isinstance(x, str) for x in options) or
            len(set(options)) != len(options)):
        raise ValueError("同一角色至少需要两个不同的作者素材版本")
    bound_profiles = set()
    local_bindings = load_bindings(root)
    for folder in options:
        role = _safe_installed_role(root, folder)
        if ((role / "BUILTIN_CHIBI_DEMO.json").exists() or
                (role / "BUILTIN_MASCOT_DEMO.json").exists()):
            raise ValueError("不能将简笔演示形象当成作者原画进行比较")
        mascot = known_mascot_family(role)
        profile = ("mascot_" + mascot if mascot is not None else _profile_of(role))
        if profile is None and mascot is None:
            profile = binding_status(role, local_bindings.get(folder))
        if not isinstance(profile, str) or not profile:
            raise ValueError("作者原画缺少明确的角色来源绑定，不能A/B对照")
        bound_profiles.add(profile)
    if len(bound_profiles) != 1:
        raise ValueError("左右两份原画对应不同人物，禁止混合对照")
    a = left or options[0]
    b = right or next(x for x in options if x != a)
    if a not in options or b not in options or a == b:
        raise ValueError("对照必须使用同一人物的两个不同素材版本")
    return a, b


def display_pixmap_for_comparison(frame_path, *, trim_transparent):
    """Display-only alpha crop; author bytes and visible pixels are untouched."""
    px = QPixmap(str(frame_path))
    if px.isNull() or not trim_transparent:
        return px
    with Image.open(frame_path) as original:
        original.load()
        bbox = original.convert("RGBA").getchannel("A").getbbox()
    if bbox is None:
        return QPixmap()
    x0, y0, x1, y1 = bbox
    return px.copy(x0, y0, x1 - x0, y1 - y0)


def shared_native_interactions(left_actions, right_actions):
    """Map only actually matching interaction *semantics*, never union them."""
    a = {x["id"]: x for x in available_interactions(left_actions) if x["available"]}
    b = {x["id"]: x for x in available_interactions(right_actions) if x["available"]}
    shared = [{
        "category": k, "label": x["label"],
        "left_native_action": x["action"],
        "right_native_action": b[k]["action"],
    } for k, x in a.items() if k in b]
    # Falling, dragging and landing are critical desktop-pet experiences but
    # aren't among the 12 generic clickable interaction categories. Permit
    # ONLY exact native action names that exist in BOTH actual artist packs.
    left = set(left_actions)
    right = set(right_actions)
    for native, label in (("drag", "拖拽动作"), ("fall", "下落动作"),
                          ("landing", "落地动作"), ("onfloor", "落地待机")):
        if native in left and native in right:
            shared.append({
                "category": "native_" + native, "label": label,
                "left_native_action": native, "right_native_action": native,
            })
    return shared


class CreatorVariantSideBySideDialog(QDialog):
    """Manual sprite-fidelity inspection; a synchronized preview is NOT animation QA."""
    def __init__(self, role_root, folders, parent=None):
        super().__init__(parent)
        self._root = Path(role_root).expanduser()
        self._folders = list(folders)
        self._initial = checked_variant_pair(self._root, self._folders)
        self._inventories = [{}, {}]
        self._motion = [{}, {}]
        self._frames = [[], []]
        self._pixels = [None, None]
        self._tick = 0
        self._playing = False
        self._recommendation_index = None
        self.setWindowTitle("同人物原画 A/B 对照 · Q版圆润体态与立牌风险")
        self.setMinimumSize(950, 610)
        body = QVBoxLayout(self)
        instruction = QLabel(
            "仅显示本机两个实际安装的作者 PNG，保留每张图片的原始比例。"
            "动画同时前进、帧数独立循环，不会从另一个版本借动作或伪造图片。"
            "透明画布补齐的版本也不意味着原设外观已经审核通过。",
            self)
        instruction.setWordWrap(True)
        body.addWidget(instruction)

        self.choices = []
        self.action_choices = []
        self.viewports = []
        self.qa = []
        self.motion_labels = []
        self.identity_labels = []
        self.frame_counts = []
        choose = QGridLayout()
        for index, label in enumerate(("左侧 A · 原始或备选", "右侧 B · 对照版本")):
            group = QGroupBox(label, self)
            inner = QVBoxLayout(group)
            version = QComboBox(group)
            for folder in self._folders:
                version.addItem(folder, folder)
            version.setCurrentIndex(self._folders.index(self._initial[index]))
            inner.addWidget(version)
            act = QComboBox(group)
            inner.addWidget(act)
            picture = QLabel(group)
            picture.setAlignment(Qt.AlignmentFlag.AlignCenter)
            picture.setMinimumSize(380, 320)
            inner.addWidget(picture, 1)
            grade = QLabel("未审核", group)
            grade.setWordWrap(True)
            inner.addWidget(grade)
            identity = QLabel("尚未检查本角色原设特征", group)
            identity.setWordWrap(True)
            inner.addWidget(identity)
            motion = QLabel("逐帧动作质量：未分析", group)
            motion.setWordWrap(True)
            inner.addWidget(motion)
            position = QLabel("帧 0 / 0", group)
            inner.addWidget(position)
            check = QPushButton("逐帧核对并保存此版本Q版/立牌意见", group)
            check.clicked.connect(lambda _checked=False, i=index: self._review(i))
            inner.addWidget(check)
            choose.addWidget(group, 0, index)
            self.choices.append(version)
            self.action_choices.append(act)
            self.viewports.append(picture)
            self.qa.append(grade)
            self.identity_labels.append(identity)
            self.motion_labels.append(motion)
            self.frame_counts.append(position)
        body.addLayout(choose, 1)

        shared = QHBoxLayout()
        shared.addWidget(QLabel("两版本都有的真实互动：", self))
        self.shared = QComboBox(self)
        shared.addWidget(self.shared, 1)
        self.apply_shared = QPushButton("两侧同步切到该动作", self)
        shared.addWidget(self.apply_shared)
        body.addLayout(shared)
        # Only source-authored *pose evidence* is compared. The user, not the
        # software, decides whether the picture looks like the true character.
        self.motion_recommendation = QLabel(
            "请选择两套素材都具备的真实动作，检查可用替代版本", self)
        self.motion_recommendation.setWordWrap(True)
        body.addWidget(self.motion_recommendation)
        self.review_recommended = QPushButton(
            "逐帧核查姿态更丰富的版本（不更换当前桌宠）", self)
        self.review_recommended.setEnabled(False)
        self.review_recommended.clicked.connect(self._review_recommended)
        body.addWidget(self.review_recommended)
        mode = QHBoxLayout()
        mode.addWidget(QLabel("画面呈现方式：", self))
        self.crop_mode = QComboBox(self)
        self.crop_mode.addItem("只裁透明边缘 · 方便比较真实头身比例", True)
        self.crop_mode.addItem("保留原始画布 · 检查动画定位", False)
        mode.addWidget(self.crop_mode)
        mode.addWidget(QLabel("只裁预览画面，不改原始PNG", self))
        mode.addStretch()
        body.addLayout(mode)
        controls = QHBoxLayout()
        self.play = QPushButton("同步播放", self)
        self.prev = QPushButton("上一帧", self)
        self.next = QPushButton("下一帧", self)
        self.slider = QSlider(Qt.Orientation.Horizontal, self)
        self.slider.setRange(0, 99)
        self.counter = QLabel("帧序号 0", self)
        controls.addWidget(self.play)
        controls.addWidget(self.prev)
        controls.addWidget(self.next)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.counter)
        body.addLayout(controls)
        note = QLabel(
            "同屏只是为了人工核对头身比例、发饰服装和动作帧；"
            "同步预览统一节奏并非原作者动作真实运行帧率；"
            "完整原设辨识与桌面手感仍须逐版本查看。"
            "不得仅凭轮廓比例自动判定合格或把本功能当作认证。",
            self)
        note.setWordWrap(True)
        body.addWidget(note)

        self._clock = QTimer(self)
        self._clock.setInterval(175)
        self._clock.timeout.connect(self._advance)
        for i in range(2):
            self.choices[i].currentIndexChanged.connect(
                lambda _value, j=i: self._load(j))
            self.action_choices[i].currentIndexChanged.connect(
                lambda _value, j=i: self._set_action(j))
        self.play.clicked.connect(self._toggle)
        self.prev.clicked.connect(lambda: self._seek(self._tick - 1))
        self.next.clicked.connect(self._advance)
        self.slider.valueChanged.connect(self._slider_seek)
        self.apply_shared.clicked.connect(self._choose_shared)
        self.shared.currentIndexChanged.connect(self._refresh_recommendation)
        self.crop_mode.currentIndexChanged.connect(self._render_both)
        self._load(0)
        self._load(1)

    def _load(self, i):
        if self.choices[0].currentData() == self.choices[1].currentData():
            # Don't make the user compare a version with itself by accident.
            self._stop()
            self.qa[i].setText("请选择两个不同版本；不能拿同一张图冒充A/B对照")
            self.viewports[i].setText("版本重复")
            self._inventories[i] = {}
            self._motion[i] = {}
            self.identity_labels[i].setText("同一版本，无法完成双素材对照")
            self.motion_labels[i].setText("双版本比较不可用")
            self.action_choices[i].clear()
            self._frames[i] = []
            self._shared_refresh()
            return
        name = self.choices[i].currentData()
        try:
            folders = self._folders
            checked_variant_pair(
                self._root, folders,
                self.choices[0].currentData(), self.choices[1].currentData())
            content = safe_animation_inventory(self._root, name)
            qa = load_local_quality_review(self._root, name, full_audit=False)
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self._inventories[i] = {}
            self._motion[i] = {}
            self._frames[i] = []
            self.action_choices[i].clear()
            self.identity_labels[i].setText("无法确认素材所属角色")
            self.motion_labels[i].setText("动作检查不可用")
            self.qa[i].setText("素材无法核查：" + str(exc)[:110])
            self.viewports[i].setText("素材无效或不可打开")
            self._stop()
            self._shared_refresh()
            return
        self._inventories[i] = content
        self.qa[i].setText("当前版本人审：" + str(qa["status"]) +
                            "（无需视为官方Q版认证）")
        # Per-source identity checklist is never a likeness approval. It
        # cannot borrow another character's frames or silently relabel art.
        try:
            cues = cues_for_local_role(self._root, name)
            self.identity_labels[i].setText(cue_text(cues))
        except (OSError, ValueError, KeyError, TypeError):
            self.identity_labels[i].setText(cue_text(None))
        # Full pose analysis is independent from structural playability.
        # On an error retain the source preview but mark the motion audit
        # unknown, NEVER call it a natural or quality-verified animation.
        try:
            audit = analyze_creator_actions(self._root, name)
            self._motion[i] = {row["action"]: row for row in audit["actions"]}
        except (OSError, ValueError, KeyError, TypeError):
            self._motion[i] = {}
        self.motion_labels[i].setText("请选择真实动作，查看整套PNG姿态风险")
        choice = self.action_choices[i]
        choice.blockSignals(True)
        choice.clear()
        for action in content:
            choice.addItem(action, action)
        choice.blockSignals(False)
        self._tick = 0
        self._set_action(i)
        self._shared_refresh()

    def _set_action(self, i):
        self._stop()
        action = self.action_choices[i].currentData()
        self._frames[i] = list(self._inventories[i].get(action, []))
        self._tick = 0
        self._refresh_motion_note(i)
        self._render_both()
        self._shared_refresh()

    def _refresh_motion_note(self, i):
        action = self.action_choices[i].currentData()
        record = self._motion[i].get(action)
        if record is None:
            self.motion_labels[i].setText("本动作暂无完整逐帧姿态证据；不能当作自然动态合格")
            return
        problems = record["risk_indicators"]
        detail = ("⚠ " + "、".join(problems) if problems
                  else "未发现重复姿态风险（仍需人工检查动作自然性）")
        self.motion_labels[i].setText(
            f"原画动作 {action}：{record['frame_count']}帧 / "
            f"{record['unique_visible_poses']}种不同可见姿态；{detail}")

    def _shared_refresh(self):
        shared = shared_native_interactions(
            self._inventories[0].keys(), self._inventories[1].keys())
        self.shared.blockSignals(True)
        self.shared.clear()
        for x in shared:
            left = self._motion[0].get(x["left_native_action"])
            right = self._motion[1].get(x["right_native_action"])
            # Unknown audit means unknown, not automatically safe.
            risks = (left is None or right is None or
                     bool(left.get("risk_indicators")) or
                     bool(right.get("risk_indicators")))
            self.shared.addItem(x["label"] + (" ⚠待核对" if risks else ""), x)
        self.shared.blockSignals(False)
        self.apply_shared.setEnabled(bool(shared) and
                                     all(self._inventories) and
                                     self.choices[0].currentData() !=
                                     self.choices[1].currentData())
        if not shared:
            self.shared.setToolTip("两个版本没有同类别的原生动作；可分别选择动作比较")
        else:
            self.shared.setToolTip("只映射双方真实存在的动作类别，绝不补动作")
        self._refresh_recommendation()

    def _refresh_recommendation(self, *_):
        self._recommendation_index = None
        item = self.shared.currentData()
        if not isinstance(item, dict) or not all(self._inventories):
            note = "尚无双方都已安装的同一类别原画动作可供逐帧对比"
        elif self.choices[0].currentData() == self.choices[1].currentData():
            note = "请选择不同作者素材版本，不能比较同一目录"
        else:
            record = compare_motion_evidence(
                self._motion[0].get(item["left_native_action"]),
                self._motion[1].get(item["right_native_action"]))
            note = record["text"]
            self._recommendation_index = record["candidate_index"]
            if self._recommendation_index is not None:
                folder = self.choices[self._recommendation_index].currentData()
                note += " 候选来源目录：" + str(folder)
        self.motion_recommendation.setText(note)
        self.review_recommended.setEnabled(self._recommendation_index is not None)

    def _review_recommended(self):
        index = self._recommendation_index
        if index not in (0, 1):
            return
        item = self.shared.currentData()
        if not isinstance(item, dict):
            return
        current = compare_motion_evidence(
            self._motion[0].get(item["left_native_action"]),
            self._motion[1].get(item["right_native_action"]))
        if current["candidate_index"] != index:
            self._refresh_recommendation()
            return
        # Only a preview of the exact original creator version. No switching,
        # downloading, file copying or persistent user choice is performed.
        original_action = (item["left_native_action"] if index == 0
                           else item["right_native_action"])
        self._review(index, native_action=original_action)

    def _choose_shared(self):
        selected = self.shared.currentData()
        if not isinstance(selected, dict):
            return
        actions = (selected["left_native_action"], selected["right_native_action"])
        if any(name not in self._inventories[i] for i, name in enumerate(actions)):
            return
        self._stop()
        for i, action in enumerate(actions):
            self.action_choices[i].blockSignals(True)
            self.action_choices[i].setCurrentIndex(
                self.action_choices[i].findData(action))
            self.action_choices[i].blockSignals(False)
            self._frames[i] = list(self._inventories[i][action])
        self._tick = 0
        for i in range(2):
            self._refresh_motion_note(i)
        self._refresh_recommendation()
        self._render_both()

    def _render_both(self):
        for i in range(2):
            frames = self._frames[i]
            if not frames or self.choices[0].currentData() == self.choices[1].currentData():
                self.viewports[i].clear()
                self.viewports[i].setText("当前版本没有可比对的真实原画帧")
                self.frame_counts[i].setText("帧 0 / 0")
                continue
            pos = self._tick % len(frames)
            try:
                pix = display_pixmap_for_comparison(
                    frames[pos], trim_transparent=bool(self.crop_mode.currentData()))
            except (OSError, ValueError):
                pix = QPixmap()
            if pix.isNull():
                self._stop()
                self.viewports[i].setText("当前原画帧已损坏")
                self.frame_counts[i].setText("无法读取")
                continue
            self.viewports[i].setPixmap(pix.scaled(
                390, 330, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
            self.frame_counts[i].setText(
                f"帧 {pos+1} / {len(frames)} · 原图 {pix.width()}×{pix.height()}")
        self.counter.setText(f"同步时间帧 {self._tick}")
        self.slider.blockSignals(True)
        self.slider.setValue(min(self._tick, 99))
        self.slider.blockSignals(False)

    def _seek(self, n):
        self._tick = max(0, min(99, n))
        self._render_both()

    def _slider_seek(self, n):
        self._stop()
        self._seek(n)

    def _advance(self):
        # User can scrub 0..99; playback loops at the end without cross-role
        # interpolation or cross-variant merging.
        self._tick = (self._tick + 1) % 100
        self._render_both()

    def _stop(self):
        self._clock.stop()
        self._playing = False
        self.play.setText("同步播放")

    def _toggle(self):
        if self._clock.isActive():
            self._stop()
            return
        if not all(self._frames) or self.choices[0].currentData() == self.choices[1].currentData():
            return
        self._clock.start()
        self._playing = True
        self.play.setText("暂停")

    def _review(self, i, *, native_action=None):
        folder = self.choices[i].currentData()
        if not folder or not self._frames[i]:
            return
        was_playing = self._clock.isActive()
        self._stop()
        try:
            viewer = NativeFramePreviewDialog(self._root, [folder], self)
            # Focus the exact native movement whose evidence was compared;
            # do not make users hunt through other actions or versions.
            if native_action is not None:
                index = viewer.action.findData(native_action)
                if index < 0:
                    raise ValueError("该原画版本已不包含所选动作，无法直接复核")
                viewer.action.setCurrentIndex(index)
            viewer.exec()
        except (OSError, ValueError, TypeError, KeyError) as exc:
            QMessageBox.warning(self, "逐帧复核失败", str(exc))
            return
        self._load(i)
        # Playback deliberately stays stopped; no implicit re-approval.

    def closeEvent(self, event):
        self._stop()
        super().closeEvent(event)
