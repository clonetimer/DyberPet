"""Q版桌宠 assistant dialog: explicit file tools, local voice and PPL persona.

Each operation is started by a direct user click. AI text never grants file
permissions or triggers filesystem actions. No network calls on the Qt thread.
"""
from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QVBoxLayout,
)

from .files import PetWorkspace, WorkspaceError, validate_session_folder
from .persona import (
    DEFAULT_CHAT_URL, DEFAULT_PPL_URL, PERSONAS, PPLCharacterClient,
    chat_local, list_local_models, AssistantServiceError,
)
from .voice import recognize_once, speak_once, VoiceUnavailable
from .guga_audio import record_local_clip, play_local_clip, load_local_clip
from .character_fidelity import inspect_guga_role, inspect_character_role, FidelityError
from .character_profiles import resolve_profile
from .character_audio import (
    register as register_character_audio, read as read_character_audio,
    play as play_character_audio,
)
from .preferences import load as load_preferences, save as save_preferences, defaults as default_preferences


class _AssistantJob(QThread):
    success = Signal(object)
    failed = Signal(str)

    def __init__(self, task, *args, **kwargs):
        super().__init__()
        self._task, self._args, self._kwargs = task, args, kwargs

    def run(self):
        try:
            self.success.emit(self._task(*self._args, **self._kwargs))
        except Exception as exc:
            self.failed.emit(str(exc))


class PetAssistantDialog(QDialog):
    reply_ready = Signal(str)
    action_notice = Signal(str)
    action_requested = Signal(str)

    def __init__(self, character_name: str, workspace: Path, parent=None,
                 role_root: Path | None = None):
        super().__init__(parent)
        self.character_name = character_name
        self.role_root = Path(role_root) if role_root is not None else Path.cwd() / "res" / "role"
        self._default_workspace = Path(workspace)
        self.workspace = PetWorkspace(self._default_workspace)
        self._job = None
        self._last_reply = ""
        self._ppl_snapshot = ""
        self._session_generation = 0
        try:
            self._prefs = load_preferences()
            self._prefs_error = ""
        except (OSError, ValueError, KeyError) as exc:
            self._prefs = default_preferences()
            self._prefs_error = str(exc)
        self._build_ui()
        self._apply_preferences()
        self._sync_guga_controls()
        if self._prefs_error:
            self.status.setText("旧配置未加载（未覆盖原文件）：" + self._prefs_error)

    def _build_ui(self):
        self.setWindowTitle("桌宠助手 · " + self.character_name)
        self.resize(560, 580)
        body = QVBoxLayout(self)
        title = QLabel("人设、语音与受控文件操作（本地优先）")
        body.addWidget(title)

        form = QFormLayout()
        self.persona = QComboBox()
        for key, item in PERSONAS.items():
            self.persona.addItem(item.name, key)
        initial = resolve_profile(self.character_name)
        if initial and initial.key in PERSONAS:
            self.persona.setCurrentIndex(self.persona.findData(initial.key))
        form.addRow("当前人设", self.persona)

        self.ppl_enabled = QCheckBox("读取 PPL 关系状态（需单独启动 PPL）")
        self.ppl_endpoint = QLineEdit(DEFAULT_PPL_URL)
        form.addRow(self.ppl_enabled)
        form.addRow("PPL 地址", self.ppl_endpoint)
        self.ppl_snapshot_button = QPushButton("导入 PPL Persona DSL 渲染快照（文本）")
        self.ppl_snapshot_button.clicked.connect(self.load_ppl_snapshot)
        form.addRow(self.ppl_snapshot_button)

        self.llm_endpoint = QLineEdit(DEFAULT_CHAT_URL)
        self.llm_model = QLineEdit()
        self.llm_model.setPlaceholderText("例如：本地 LM Studio 已加载模型的 ID")
        form.addRow("本地模型地址", self.llm_endpoint)
        model_row = QHBoxLayout()
        model_row.addWidget(self.llm_model, 1)
        detect_button = QPushButton("检测")
        detect_button.clicked.connect(self.detect_models)
        model_row.addWidget(detect_button)
        form.addRow("模型 ID", model_row)
        self.voice_model = QLineEdit()
        self.voice_model.setPlaceholderText("Vosk 已下载的本地模型文件夹路径")
        voice_model_row = QHBoxLayout()
        voice_model_row.addWidget(self.voice_model, 1)
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(self.browse_voice_model)
        voice_model_row.addWidget(browse_button)
        form.addRow("离线识别模型", voice_model_row)
        self.bubble_enabled = QCheckBox("对话回复/文件操作时显示桌宠气泡")
        self.auto_speak = QCheckBox("自动朗读模型回复（本机离线 TTS）")
        self.action_menu = QComboBox()
        self.action_menu.addItem("无额外动作", "")
        form.addRow(self.bubble_enabled)
        form.addRow(self.auto_speak)
        form.addRow("交互成功时播放已解锁动作", self.action_menu)
        self.save_pref_button = QPushButton("保存助手设置（不保存聊天记录与人设快照）")
        self.save_pref_button.clicked.connect(self.save_preferences)
        form.addRow(self.save_pref_button)
        body.addLayout(form)

        self.chat_log = QPlainTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.appendPlainText(
            "桌宠助手已打开。聊天需要本地模型服务和正确的模型 ID；"
            "PPL 只管理关系状态，不直接生成回复。")
        body.addWidget(self.chat_log, 1)

        message_row = QHBoxLayout()
        self.message = QLineEdit()
        self.message.setPlaceholderText("输入文字，或点击“录音识别”获取一句语音文字")
        self.message.returnPressed.connect(self.send_message)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.send_message)
        message_row.addWidget(self.message, 1)
        message_row.addWidget(self.send_button)
        body.addLayout(message_row)

        voice_row = QHBoxLayout()
        self.listen_button = QPushButton("录音识别（4秒）")
        self.listen_button.clicked.connect(self.listen_once)
        self.speak_button = QPushButton("朗读上一条回复")
        self.speak_button.clicked.connect(self.read_reply)
        self.ppl_button = QPushButton("向 PPL 发送安慰事件")
        self.ppl_button.clicked.connect(self.comfort)
        voice_row.addWidget(self.listen_button)
        voice_row.addWidget(self.speak_button)
        voice_row.addWidget(self.ppl_button)
        body.addLayout(voice_row)

        # The signature sample is independent from speech synthesis / TTS.
        sample_row = QHBoxLayout()
        self.guga_sample_label = QLabel("咕嘎标志音效（非系统 TTS）")
        self.guga_select = QPushButton("登记本地授权 WAV")
        self.guga_select.clicked.connect(self.select_character_sample)
        self.guga_preview = QPushButton("试听咕嘎音效")
        self.guga_preview.clicked.connect(self.preview_character_sample)
        sample_row.addWidget(self.guga_sample_label)
        sample_row.addStretch(1)
        body.addLayout(sample_row)
        sample_actions = QHBoxLayout()
        sample_actions.addWidget(self.guga_select)
        sample_actions.addWidget(self.guga_preview)
        self.guga_audit = QPushButton("核查当前咕嘎形象")
        self.guga_audit.clicked.connect(self.audit_character)
        sample_actions.addWidget(self.guga_audit)
        body.addLayout(sample_actions)

        self.folder_label = QLabel("当前文件操作目录：" + str(self.workspace.root))
        self.folder_label.setWordWrap(True)
        body.addWidget(self.folder_label)
        folder_row = QHBoxLayout()
        grant_button = QPushButton("本次授权其他文件夹")
        grant_button.clicked.connect(self.grant_session_folder)
        reset_button = QPushButton("恢复默认目录")
        reset_button.clicked.connect(self.reset_workspace)
        folder_row.addWidget(grant_button)
        folder_row.addWidget(reset_button)
        body.addLayout(folder_row)
        file_row = QHBoxLayout()
        create_button = QPushButton("创建文件")
        delete_button = QPushButton("删除到可恢复区")
        restore_button = QPushButton("恢复文件")
        create_button.clicked.connect(self.create_file)
        delete_button.clicked.connect(self.delete_file)
        restore_button.clicked.connect(self.restore_file)
        for widget in (create_button, delete_button, restore_button):
            file_row.addWidget(widget)
        body.addLayout(file_row)
        self.status = QLabel("麦克风默认关闭；所有文件动作均须用户亲自选择。")
        self.status.setWordWrap(True)
        body.addWidget(self.status)

    def set_character(self, name: str):
        if self.character_name == name:
            return
        self.character_name = name
        self.setWindowTitle("桌宠助手 · " + name)
        self._sync_guga_controls()
        profile = resolve_profile(name)
        persona = profile.key if profile and profile.key in PERSONAS else "companion"
        self.persona.setCurrentIndex(max(0, self.persona.findData(persona)))
        self.chat_log.appendPlainText("已切换当前桌宠：" + name)
        saved = self._prefs["personas"].get(name)
        if saved in PERSONAS:
            self.persona.setCurrentIndex(self.persona.findData(saved))
        self._last_reply = ""
        self._ppl_snapshot = ""  # Persona snapshots belong to the previous character

    def set_actions(self, names):
        """Only accept actual currently-unlocked animations from PetWidget."""
        previous = self.action_menu.currentData()
        self.action_menu.clear()
        self.action_menu.addItem("无额外动作", "")
        for name in sorted(set(n for n in names if isinstance(n, str) and n)):
            self.action_menu.addItem(name, name)
        matched = self.action_menu.findData(previous)
        self.action_menu.setCurrentIndex(max(0, matched))

    def _emit_selected_animation(self):
        action = self.action_menu.currentData()
        if action:
            self.action_requested.emit(action)

    def _is_guga(self):
        text = self.character_name.casefold()
        return any(label in text for label in ("咕嘎", "咕咕嘎嘎", "guga", "gugugaga"))

    def _sync_guga_controls(self):
        profile = resolve_profile(self.character_name)
        show = profile is not None
        if profile:
            self.guga_sample_label.setText(profile.title + "：角色短音效（不是 TTS）")
            self.guga_preview.setText("试听已登记音效")
            self.guga_audit.setText("核查当前角色")
        for widget in (self.guga_sample_label, self.guga_select,
                       self.guga_preview, self.guga_audit):
            widget.setVisible(show)

    def _role_path(self):
        root = self.role_root.expanduser().resolve()
        name = self.character_name
        if (not name or name in (".", "..") or
                any(x in name for x in ("/", "\\", "\x00"))):
            raise FidelityError("Invalid installed character folder name")
        path = root / name
        if path.parent.resolve() != root:
            raise FidelityError("Character folder escapes the role directory")
        return path

    def select_character_sample(self):
        profile = resolve_profile(self.character_name)
        if profile is None:
            self._job_error("当前角色没有已登记的原设档案")
            return
        if profile.key == "guga":
            self.select_guga_sample()
            return
        wav, _ = QFileDialog.getOpenFileName(
            self, "选择该角色许可允许的本地短音效", str(Path.home()), "WAV (*.wav)")
        if not wav:
            return
        creator, ok = QInputDialog.getText(
            self, "作者署名", "实际声音/音效作者或发布者：")
        if not ok or not creator.strip():
            return
        link, ok = QInputDialog.getText(
            self, "作品来源", "具体作品 HTTPS 来源链接：")
        if not ok or not link.strip():
            return
        if QMessageBox.warning(
                self, "确认本地音效权限",
                "仅登记本地试听用途，不能据此宣称为官方原声。\n"
                "确认你已核实该具体素材允许个人桌宠使用？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            record = register_character_audio(
                self.character_name, wav, creator, link,
                acknowledged_local_rights=True)
            self.status.setText("已登记 " + profile.title +
                                " 本地音效；尚未认证原声：" + record["creator"])
        except (OSError, ValueError) as exc:
            self._job_error(str(exc))

    def preview_character_sample(self):
        profile = resolve_profile(self.character_name)
        if profile is None:
            self._job_error("当前角色没有已登记的原设档案")
            return
        if profile.key == "guga":
            self.preview_guga_sample()
            return
        key = self.character_name
        self.status.setText("本地试听中；不是角色对话 TTS。")
        self._submit(play_character_audio, self._guga_sample_finished, key)

    def audit_character(self):
        profile = resolve_profile(self.character_name)
        if profile is None:
            self._job_error("当前角色没有已登记的原设档案")
            return
        if profile.key == "guga":
            self.audit_guga()
            return
        try:
            folder = self._role_path()
            clip = read_character_audio(self.character_name)
            result = inspect_character_role(folder, self.character_name,
                                            clip["clip"] if clip else None)
            coverage = result["action_coverage"]
            lines = [
                "当前角色：" + profile.title,
                "安装目录：" + str(folder),
                "已有动作：" + "、".join(
                    name + ("✓" if val["available"] else "×")
                    for name, val in coverage.items()),
                "视觉对照：" + "；".join(profile.visual_checks),
                "动作对照：" + "；".join(profile.motion_checks),
                "实际移动策略：" + result["runtime_motion_policy"]["kind"]
                + "（仅运行时轻量补偿，不代表原作动作图已齐备）",
                "声音注意：" + "；".join(profile.audio_checks),
                "问题：" + ("；".join(result["issues"]) if result["issues"] else "无静态问题"),
                "结论：未核实原作形象、声音及素材使用权；必须人工比对具体版本。",
            ]
            QMessageBox.information(self, "角色原设核查", "\n".join(lines))
        except (FidelityError, OSError, ValueError) as exc:
            self._job_error("角色检查失败：" + str(exc))

    def select_guga_sample(self):
        if not self._is_guga():
            self._job_error("当前角色不是咕嘎")
            return
        wav, _ = QFileDialog.getOpenFileName(
            self, "选择有权在本地使用的咕嘎音效", str(Path.home()), "WAV (*.wav)")
        if not wav:
            return
        author, ok = QInputDialog.getText(
            self, "音效来源署名", "实际音频作者或发布者：")
        if not ok or not author.strip():
            return
        source, ok = QInputDialog.getText(
            self, "具体作品来源", "原音效的 HTTPS 作品链接：")
        if not ok or not source.strip():
            return
        if QMessageBox.warning(
                self, "确认音效本地使用权限",
                "请确认已核查此音频的具体使用规则，允许在个人桌宠本地使用。\n"
                "音效不会提交到仓库，也不会被用于声线克隆或模型训练。\n"
                "此操作只记录用户声明，不代表作品身份及授权已被独立核实。",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            result = record_local_clip(
                wav, author, source, acknowledged_local_rights=True)
            self.status.setText(
                "已登记本地音效（尚未认证原声）：" + result["creator"])
        except (OSError, ValueError) as exc:
            self._job_error(str(exc))

    def audit_guga(self):
        if not self._is_guga():
            self._job_error("只能检查当前选择的咕嘎角色")
            return
        # Use the actual current role folder, not a reference screenshot.
        folder = self._role_path()
        try:
            wav = None
            try:
                clip = load_local_clip()
                if clip:
                    wav = clip["clip"]
            except FidelityError as exc:
                self.status.setText("音效校验异常：" + str(exc))
            result = inspect_guga_role(folder, wav)
            coverage = result["action_coverage"]
            lines = [
                "本机角色目录：" + str(folder),
                "动作覆盖：" + "、".join(
                    name + ("：有" if value["available"] else "：缺")
                    for name, value in coverage.items()
                ),
                "问题：" + ("；".join(result["issues"]) if result["issues"] else "未检测到静态问题"),
                "真实性：尚未核实（必须与具体作者作品的图像和音频人工对比）。"
            ]
            QMessageBox.information(
                self, "咕嘎本地角色工程验收", "\n".join(lines))
        except (FidelityError, OSError, ValueError) as exc:
            self._job_error("角色检查失败：" + str(exc))

    def preview_guga_sample(self):
        if not self._is_guga():
            self._job_error("当前角色不是咕嘎")
            return
        self.status.setText("正在试听用户选定的本地音效（不是 TTS）。")
        self._submit(play_local_clip, self._guga_sample_finished)

    def _guga_sample_finished(self, creator):
        self.status.setText("试听完成，登记来源：" + creator + "；尚未认证为原声。")

    def _apply_preferences(self):
        prefs = self._prefs
        self.llm_endpoint.setText(prefs["llm_url"])
        self.llm_model.setText(prefs["llm_model"])
        self.ppl_endpoint.setText(prefs["ppl_url"])
        self.voice_model.setText(prefs["voice_model"])
        self.ppl_enabled.setChecked(prefs["ppl_enabled"])
        self.bubble_enabled.setChecked(prefs["bubble_enabled"])
        self.auto_speak.setChecked(prefs["auto_speak"])
        saved = prefs["personas"].get(self.character_name)
        if saved in PERSONAS:
            self.persona.setCurrentIndex(self.persona.findData(saved))

    def save_preferences(self):
        prefs = dict(self._prefs)
        prefs.update({
            "llm_url": self.llm_endpoint.text().strip(),
            "llm_model": self.llm_model.text().strip(),
            "ppl_url": self.ppl_endpoint.text().strip(),
            "voice_model": self.voice_model.text().strip(),
            "ppl_enabled": self.ppl_enabled.isChecked(),
            "bubble_enabled": self.bubble_enabled.isChecked(),
            "auto_speak": self.auto_speak.isChecked(),
        })
        prefs["personas"] = dict(prefs["personas"])
        prefs["personas"][self.character_name] = self.persona.currentData()
        try:
            save_preferences(prefs)
            self._prefs = prefs
            self.status.setText("配置已保存；聊天记录和 PPL 文本快照不会落盘。")
        except (OSError, ValueError) as exc:
            self._job_error("配置保存失败：" + str(exc))

    def _notice(self, text: str):
        # Tell PetWidget to use the *existing* notification bubble pipeline.
        # This signal has no filesystem write capability.
        if self.bubble_enabled.isChecked():
            self.action_notice.emit(text[:120])
        self._emit_selected_animation()

    def _submit(self, task, on_success, *args, **kwargs):
        if self._job is not None:
            self.status.setText("上一项语音/对话任务仍在执行")
            return
        self.send_button.setEnabled(False)
        self.listen_button.setEnabled(False)
        self.ppl_button.setEnabled(False)
        self.speak_button.setEnabled(False)
        job = _AssistantJob(task, *args, **kwargs)
        self._job = job
        job.success.connect(on_success)
        job.failed.connect(self._job_error)
        job.finished.connect(self._job_finished)
        job.start()

    def _job_finished(self):
        job = self._job
        self._job = None
        for button in (self.send_button, self.listen_button,
                       self.ppl_button, self.speak_button):
            button.setEnabled(True)
        if job is not None:
            job.deleteLater()

    def _job_error(self, detail: str):
        self.status.setText("操作失败：" + detail)
        self.chat_log.appendPlainText("[错误] " + detail)

    def _relationship_state(self):
        if not self.ppl_enabled.isChecked():
            return None
        return PPLCharacterClient(self.ppl_endpoint.text()).state(
            self.character_name)

    def detect_models(self):
        self.status.setText("正在读取本地 LM Studio 模型列表…")
        self._submit(list_local_models, self._choose_model,
                     self.llm_endpoint.text())

    def _choose_model(self, names):
        name, ok = QInputDialog.getItem(
            self, "本地模型", "选择已加载的模型：", names, 0, False)
        if ok:
            self.llm_model.setText(name)
            self.status.setText("已选择本地模型：" + name)

    def browse_voice_model(self):
        folder = QFileDialog.getExistingDirectory(
            self, "请选择已下载并解压的 Vosk 模型文件夹",
            str(Path.home()))
        if folder:
            self.voice_model.setText(folder)

    def load_ppl_snapshot(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "导入 PPL 命令行渲染快照", str(Path.home()),
            "Text (*.txt);;All Files (*)")
        if not path:
            return
        try:
            file = Path(path)
            if file.stat().st_size > 64000:
                raise ValueError("人设快照文件过大（上限 64 KB）")
            content = file.read_text(encoding="utf-8")
            if not content.strip() or len(content) > 16000:
                raise ValueError("PPL 人设快照为空或过长（上限 16000 字符）")
            if QMessageBox.question(
                    self, "确认导入",
                    "这份文本将作为本地模型的人设上下文。\n"
                    "请选择你自己从 PPL CLI 导出的可信文件，确认继续？",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                    ) != QMessageBox.StandardButton.Yes:
                return
            self._ppl_snapshot = content
            self.status.setText("PPL 渲染快照已加载：" + file.name)
        except (OSError, UnicodeError, ValueError) as exc:
            self._job_error(str(exc))

    def send_message(self):
        text = self.message.text().strip()
        if not text:
            return
        # The assistant only replies as text; the output is never passed to
        # PetWorkspace and cannot mutate user files.
        endpoint, model = self.llm_endpoint.text(), self.llm_model.text()
        character, persona = self.character_name, self.persona.currentData()
        snapshot = self._ppl_snapshot
        generation = self._session_generation
        ppl = (self.ppl_endpoint.text() if self.ppl_enabled.isChecked()
               else None)
        self.message.clear()
        self.chat_log.appendPlainText("你：" + text)
        self.status.setText("正在请求本地模型…")
        def task():
            state = PPLCharacterClient(ppl).state(character) if ppl else None
            answer = chat_local(text, persona_key=persona, state=state,
                                ppl_prompt=snapshot, base_url=endpoint, model=model)
            return character, generation, answer
        self._submit(task, self._message_reply)

    def _message_reply(self, result):
        if isinstance(result, tuple):
            if len(result) == 3:
                character, generation, reply = result
                if generation != self._session_generation:
                    return
            else:
                character, reply = result
            if character != self.character_name:
                self.chat_log.appendPlainText(
                    "[旧角色回复已丢弃] 切换角色后不展示之前的人设内容")
                return
        else:
            reply = result
        self._last_reply = reply
        self.chat_log.appendPlainText(self.character_name + "：" + reply)
        if self.bubble_enabled.isChecked():
            self.reply_ready.emit(reply[:120])
        self._emit_selected_animation()
        self.status.setText("回复已生成；点击朗读按钮可使用离线语音播报。")
        if self.auto_speak.isChecked() and self.isVisible():
            QTimer.singleShot(100, self._auto_read_reply)

    def _auto_read_reply(self):
        if self._job is None and self.auto_speak.isChecked() and self.isVisible():
            self.read_reply()

    def listen_once(self):
        model = self.voice_model.text().strip()
        if not model:
            self._job_error("请先设置已安装的 Vosk 离线识别模型目录")
            return
        self.status.setText("正在录音 4 秒；只在这次点击后开启麦克风…")
        self._submit(recognize_once, self._heard, model, seconds=4)

    def _heard(self, text):
        self.message.setText(text)
        self.status.setText("语音已转为文字；请检查后点击“发送”。")

    def read_reply(self):
        if not self._last_reply:
            self._job_error("还没有可朗读的回复")
            return
        self.status.setText("正在使用本机语音合成…")
        self._submit(speak_once, lambda _: self.status.setText("朗读结束"),
                     self._last_reply)

    def comfort(self):
        if not self.ppl_enabled.isChecked():
            self._job_error("请先勾选 PPL 连接，并启动独立的 Character Governance 服务")
            return
        character, endpoint = self.character_name, self.ppl_endpoint.text()
        event_id = str(uuid.uuid4())
        self.status.setText("正在通知本地 PPL Character Governance…")
        self._submit(
            lambda: PPLCharacterClient(endpoint).event(
                character, "COMFORT", event_id),
            lambda state: self.chat_log.appendPlainText(
                "[PPL] 关系状态：" + str(state)))

    def grant_session_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "授权一个具体的个人子文件夹（本次会话有效）",
            str(Path.home()))
        if not folder:
            return
        try:
            approved = validate_session_folder(Path(folder))
        except WorkspaceError as exc:
            self._job_error(str(exc))
            return
        if QMessageBox.warning(
                self, "确认文件夹授权",
                "此操作允许桌宠的手动按钮在下列目录创建、移入可恢复区和恢复文本文件："
                + "\n" + str(approved)
                + "\n仅本次窗口会话有效；不递归操作、不授予模型自动工具权限。"
                + "\n确认授权？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.workspace = PetWorkspace(approved)
            self.folder_label.setText("当前文件操作目录：" + str(self.workspace.root))
            self.status.setText("此目录仅在当前窗口会话中获得授权。")
        except (WorkspaceError, OSError) as exc:
            self._job_error(str(exc))

    def closeEvent(self, event):
        # QDialog.close() does not necessarily destroy the dialog; release
        # any user-granted folder even when the widget is reopened later.
        self._session_generation += 1
        self._ppl_snapshot = ""
        self._last_reply = ""
        self.workspace = PetWorkspace(self._default_workspace)
        self.folder_label.setText("当前文件操作目录：" + str(self.workspace.root))
        super().closeEvent(event)

    def reset_workspace(self):
        self.workspace = PetWorkspace(self._default_workspace)
        self.folder_label.setText("当前文件操作目录：" + str(self.workspace.root))
        self.status.setText("已回到默认专属文件目录；临时授权已撤销。")

    def create_file(self):
        name, ok = QInputDialog.getText(
            self, "创建文本文件", "新文件名（支持 .txt/.md/.json/.csv）：")
        if not ok:
            return
        content, ok = QInputDialog.getMultiLineText(
            self, "文件内容", "输入 UTF-8 文本：")
        if not ok:
            return
        if QMessageBox.question(
                self, "确认创建文件",
                f"仅在当前授权目录内创建：{name}\n{self.workspace.root}\n不覆盖任何已有文件。"
                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            path = self.workspace.create(name, content)
            self.status.setText("已创建：" + str(path))
            self._notice("文件已创建：" + path.name)
        except (WorkspaceError, OSError) as exc:
            self._job_error(str(exc))

    def delete_file(self):
        entries = self.workspace.list_files()
        if not entries:
            self._job_error("工作区没有可删除的文件")
            return
        name, ok = QInputDialog.getItem(
            self, "选择文件", "删除到桌宠可恢复区：", entries, 0, False)
        if not ok:
            return
        if QMessageBox.warning(
                self, "确认移入可恢复区",
                "仅移动当前授权目录内的文件，不会永久删除。\n"
                + str(self.workspace.root) + "\n确认移动：" + name,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
                ) != QMessageBox.StandardButton.Yes:
            return
        try:
            key = self.workspace.soft_delete(name)
            self.status.setText("文件已移入可恢复区：" + key)
            self._notice("已移入可恢复区：" + name)
        except (WorkspaceError, OSError) as exc:
            self._job_error(str(exc))

    def restore_file(self):
        entries = self.workspace.deleted_files()
        if not entries:
            self._job_error("没有可恢复的文件")
            return
        key, ok = QInputDialog.getItem(
            self, "恢复文件", "选择需要恢复的记录：", entries, 0, False)
        if not ok:
            return
        try:
            target = self.workspace.restore(key)
            self.status.setText("已恢复：" + str(target))
            self._notice("文件已恢复：" + target.name)
        except (WorkspaceError, OSError) as exc:
            self._job_error(str(exc))
