"""Q版桌宠 assistant dialog: explicit file tools, local voice and PPL persona.

Network/audio sessions start with a direct user action; an explicitly opened
voice conversation can continue its own turns. AI text never grants file
permissions or triggers filesystem actions. No network calls on the Qt thread.
"""
from __future__ import annotations

import threading
import uuid
import sqlite3
import weakref
from functools import partial
from pathlib import Path
from time import monotonic

from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QInputDialog,
    QGroupBox, QLabel, QLineEdit, QMessageBox, QPlainTextEdit, QPushButton, QScrollArea,
    QVBoxLayout, QWidget,
)

from .files import PetWorkspace, WorkspaceError, validate_session_folder
from .action_runtime import ActionRuntime, ActionDenied
from .persona import (
    DEFAULT_CHAT_URL, DEFAULT_PPL_URL, PERSONAS, PPLCharacterClient,
    chat_local, stream_local_chat, list_local_models, AssistantServiceError, _local_base,
)
from .voice import (
    recognize_once, recognize_until_stopped, speak_interruptible, speak_once,
    VoiceUnavailable,
)
from .guga_audio import record_local_clip, play_local_clip, load_local_clip
from .character_fidelity import (
    inspect_guga_role, inspect_character_role, inspect_mini_character_role,
    FidelityError,
)
from .character_profiles import resolve_profile
from .character_audio import (
    register as register_character_audio, read as read_character_audio,
    play as play_character_audio,
)
from .preferences import load as load_preferences, save as save_preferences, defaults as default_preferences
from .conversation_store import CompanionStore
from .task_plan import TaskSession
from .task_planner import generate_task_plan
from .task_review import TaskReviewDialog
from .request_control import CancellationToken, RequestCancelled
from .service_diagnostics import service_error_hint
from .voice_readiness import inspect_voice_readiness
from .trial_records import TrialRecorder
from .trial_dialog import TrialDialog
from .voice_session import VoiceConversation
from .audio_settings import AudioSettingsWidget
from .voice_devices import inspect_audio_options


def _weak_ready_callback(owner, signal_name, *args):
    """A retained device callback must not own the dialog's Qt object tree."""
    reference = weakref.ref(owner)

    def ready():
        receiver = reference()
        if receiver is not None:
            getattr(receiver, signal_name).emit(*args)

    return ready


class _AssistantJob(QThread):
    success = Signal(object)
    failed = Signal(str)
    progress = Signal(str)
    cancelled = Signal()

    def __init__(self, task, *args, stream=False, **kwargs):
        super().__init__()
        self._task, self._args, self._kwargs = task, args, kwargs
        self._stream = stream
        self.error_code = "internal_error"
        self.engine_completed = None

    def run(self):
        try:
            if self._stream:
                result = self._task(*self._args, on_delta=self.progress.emit,
                                    **self._kwargs)
            else:
                result = self._task(*self._args, **self._kwargs)
            self.success.emit(result)
        except RequestCancelled:
            self.cancelled.emit()
        except AssistantServiceError as exc:
            self.error_code = exc.code
            self.failed.emit(service_error_hint(exc))
        except VoiceUnavailable as exc:
            self.error_code = "voice_unavailable"
            observed = getattr(exc, "engine_completed", None)
            self.engine_completed = observed if type(observed) is bool else None
            self.failed.emit(str(exc))
        except Exception as exc:
            self.failed.emit(str(exc))


class PetAssistantDialog(QDialog):
    reply_ready = Signal(str)
    action_notice = Signal(str)
    action_requested = Signal(str)
    motion_toggled = Signal(bool)
    speech_started = Signal(str, str)
    speech_finished = Signal(str)
    voice_engine_ready = Signal(str, str, object)
    microphone_ready = Signal(str, int, object)
    speech_progress = Signal(str, int, object, int, int)
    interaction_changed = Signal(str, str)

    def __init__(self, character_name: str, workspace: Path, parent=None,
                 role_root: Path | None = None, store_path: Path | None = None):
        super().__init__(parent)
        self.character_name = character_name
        self._interaction_state = (character_name, "idle")
        self.role_root = Path(role_root) if role_root is not None else Path.cwd() / "res" / "role"
        self._default_workspace = Path(workspace)
        self.workspace = PetWorkspace(self._default_workspace)
        self._action_runtime_error = ""
        self._pending_file_context = None
        try:
            action_audit_path = (
                Path(store_path).parent / "assistant-actions.sqlite3"
                if store_path is not None else None)
            self._action_runtime = ActionRuntime(
                self.workspace, audit_path=action_audit_path)
        except (OSError, ValueError) as exc:
            self._action_runtime = None
            self._action_runtime_error = str(exc)
        self._job = None
        self._job_generation = None
        self._job_success_handler = None
        self._job_progress_handler = None
        self._request_token = None
        self._setup_job = None
        self._model_check_revision = 0
        self._voice_check_revision = 0
        self._model_catalog_endpoint = None
        self._model_catalog = ()
        self._request_text = ""
        self._job_cancel_requested = False
        self._activity_kind = None
        self._activity_phase = "就绪"
        self._activity_started = None
        self._activity_ended = None
        self._activity_first_text = None
        self._activity_chars = 0
        self._activity_outcome = ""
        self._trial_recorder = TrialRecorder()
        self._trial_run_id = None
        self._trial_dialog = None
        self._trial_probe_text = ""
        self._task_generation = 0
        self._task_session = None
        self._task_review_dialog = None
        self._last_reply = ""
        self._stream_reply_open = False
        self._listen_stop_event = None
        self._listening = False
        self._speech_stop_event = None
        self._audio_options_stop = None
        self._closing_after_worker = False
        self._speaking_session = None
        self._speech_has_started = False
        self._speech_is_sample = False
        self.voice_engine_ready.connect(self._on_voice_engine_ready)
        self.microphone_ready.connect(self._on_microphone_ready)
        self.speech_progress.connect(self._on_speech_progress)
        self._ppl_snapshot = ""
        self._session_generation = 0
        self._store_error = ""
        try:
            self._conversation_store = CompanionStore(store_path)
        except (OSError, ValueError) as exc:
            self._conversation_store = None
            self._store_error = str(exc)
        try:
            self._prefs = load_preferences()
            self._prefs_error = ""
        except (OSError, ValueError, KeyError) as exc:
            self._prefs = default_preferences()
            self._prefs_error = str(exc)
        self._build_ui()
        self.voice_conversation = VoiceConversation(self)
        self._activity_timer = QTimer(self)
        self._activity_timer.setInterval(250)
        self._activity_timer.timeout.connect(self._refresh_activity)
        self._auto_read_timer = QTimer(self)
        self._auto_read_timer.setSingleShot(True)
        self._auto_read_timer.setInterval(100)
        self._auto_read_timer.timeout.connect(self._auto_read_reply)
        self._apply_preferences()
        self.auto_speak.toggled.connect(self._auto_read_timer.stop)
        self.llm_endpoint.textChanged.connect(self._model_endpoint_changed)
        self.llm_model.textChanged.connect(self._model_choice_changed)
        self.voice_model.textChanged.connect(self._voice_path_changed)
        for editor in (self.llm_endpoint, self.llm_model, self.voice_model, self.ppl_endpoint):
            editor.textChanged.connect(self.voice_conversation.configuration_changed)
        self.ppl_enabled.toggled.connect(self.voice_conversation.configuration_changed)
        self.audio_settings.settings_changed.connect(self._audio_settings_changed)
        self.persona.currentIndexChanged.connect(self._persona_changed)
        self._sync_guga_controls()
        self._restore_character_history()
        if self._store_error:
            self.status.setText("本地记忆暂不可用：" + self._store_error)
        if self._prefs_error:
            self.status.setText("旧配置未加载（未覆盖原文件）：" + self._prefs_error)

    def _build_ui(self):
        self.setWindowTitle("桌宠助手 · " + self.character_name)
        available = self.screen().availableGeometry()
        self.resize(min(900, available.width() - 40), min(820, available.height() - 60))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        self.content_scroll = QScrollArea(self)
        self.content_scroll.setWidgetResizable(True)
        content = QWidget()
        body = QVBoxLayout(content)
        self.content_scroll.setWidget(content)
        outer.addWidget(self.content_scroll)
        title = QLabel("人设、语音与受控文件操作（本地优先）")
        body.addWidget(title)

        voice_chat = QGroupBox("语音对话 · 轮流说话")
        voice_chat_layout = QVBoxLayout(voice_chat)
        explanation = QLabel(
            "开启后，说完一句会自动发给当前本地模型并朗读回复，然后继续听。"
            "键盘草稿和待发送附件保留；随时可以结束。")
        explanation.setWordWrap(True)
        explanation.setTextFormat(Qt.TextFormat.PlainText)
        voice_chat_layout.addWidget(explanation)
        voice_chat_buttons = QHBoxLayout()
        self.voice_chat_button = QPushButton("开始语音对话")
        self.voice_interrupt_button = QPushButton("打断，继续听")
        self.voice_end_button = QPushButton("结束语音对话")
        self.voice_interrupt_button.setEnabled(False)
        self.voice_end_button.setEnabled(False)
        for button in (self.voice_chat_button, self.voice_interrupt_button, self.voice_end_button):
            button.setAutoDefault(False)
            voice_chat_buttons.addWidget(button)
        self.voice_chat_button.clicked.connect(self.start_voice_conversation)
        self.voice_interrupt_button.clicked.connect(self.interrupt_voice_conversation)
        self.voice_end_button.clicked.connect(self.end_voice_conversation)
        voice_chat_layout.addLayout(voice_chat_buttons)
        self.voice_chat_status = QLabel("未开启；麦克风和朗读按轮次交替工作。")
        self.voice_chat_status.setWordWrap(True)
        self.voice_chat_status.setTextFormat(Qt.TextFormat.PlainText)
        voice_chat_layout.addWidget(self.voice_chat_status)
        # Keep interrupt/end reachable while the user scrolls through replies.
        outer.insertWidget(0, voice_chat)

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
        self.model_selector = QComboBox()
        self.model_selector.setEditable(True)
        self.model_selector.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.model_selector.setMinimumContentsLength(18)
        self.model_selector.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.llm_model = self.model_selector.lineEdit()
        self.llm_model.setPlaceholderText("检查连接后选择模型，也可手动输入 ID")
        form.addRow("本地模型地址", self.llm_endpoint)
        model_row = QHBoxLayout()
        model_row.addWidget(self.model_selector, 1)
        self.detect_button = QPushButton("检查连接 / 刷新模型")
        self.detect_button.setAutoDefault(False)
        self.detect_button.clicked.connect(self.detect_models)
        model_row.addWidget(self.detect_button)
        form.addRow("聊天模型", model_row)
        self.model_status = QLabel(
            "尚未检查连接；启动 LM Studio 本地服务后，点击“检查连接 / 刷新模型”。")
        self.model_status.setWordWrap(True)
        self.model_status.setTextFormat(Qt.TextFormat.PlainText)
        form.addRow(self.model_status)
        self.audio_settings = AudioSettingsWidget()
        self.audio_settings.refresh_requested.connect(self.refresh_audio_options)
        self.audio_settings.preview_requested.connect(self.try_speech)
        self.audio_settings.stop_requested.connect(self.stop_audio_operation)
        form.addRow(self.audio_settings)
        voice_form = self.audio_settings.form_layout
        self.voice_model = QLineEdit()
        self.voice_model.setPlaceholderText("Vosk 已下载的本地模型文件夹路径")
        voice_model_row = QHBoxLayout()
        voice_model_row.addWidget(self.voice_model, 1)
        browse_button = QPushButton("浏览")
        browse_button.clicked.connect(self.browse_voice_model)
        voice_model_row.addWidget(browse_button)
        voice_form.insertRow(0, "离线识别模型", voice_model_row)
        self.voice_check_button = QPushButton("检查语音条件（不录音、不发声）")
        self.voice_check_button.setAutoDefault(False)
        self.voice_check_button.clicked.connect(self.check_voice_setup)
        voice_form.addRow(self.voice_check_button)
        self.voice_status = QLabel("识别：请选择已解压的 Vosk 模型目录，再检查语音条件。")
        self.tts_status = QLabel("朗读：尚未检查；系统 TTS 与识别模型独立。")
        for label in (self.voice_status, self.tts_status):
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.PlainText)
            voice_form.addRow(label)
        self.bubble_enabled = QCheckBox("对话回复/文件操作时显示桌宠气泡")
        self.auto_speak = QCheckBox("自动朗读模型回复（本机离线 TTS）")
        self.motion_enabled = QCheckBox("角色运动增强（Doro步速／派蒙悬浮）")
        self.motion_enabled.toggled.connect(self.motion_toggled.emit)
        self.action_menu = QComboBox()
        self.action_menu.addItem("无额外动作", "")
        form.addRow(self.bubble_enabled)
        voice_form.addRow(self.auto_speak)
        form.addRow(self.motion_enabled)
        form.addRow("交互成功时播放已解锁动作", self.action_menu)
        self.save_pref_button = QPushButton("保存助手设置（聊天历史独立保存）")
        self.save_pref_button.clicked.connect(self.save_preferences)
        form.addRow(self.save_pref_button)
        body.addLayout(form)

        activity_row = QHBoxLayout()
        self.activity_status = QLabel("就绪")
        self.activity_status.setTextFormat(Qt.TextFormat.PlainText)
        self.activity_status.setStyleSheet("font-weight: 600;")
        self.activity_metrics = QLabel("")
        self.activity_metrics.setTextFormat(Qt.TextFormat.PlainText)
        self.activity_metrics.setToolTip(
            "本次活动的本机观察时间；首段指第一段显示文字。"
            "不代表模型吞吐量或 CPU/GPU 性能。")
        self.stop_generation_button = QPushButton("停止生成")
        self.stop_generation_button.setEnabled(False)
        self.stop_generation_button.setAutoDefault(False)
        self.stop_generation_button.clicked.connect(self.stop_generation)
        activity_row.addWidget(self.activity_status)
        activity_row.addStretch(1)
        activity_row.addWidget(self.stop_generation_button)
        body.addLayout(activity_row)
        body.addWidget(self.activity_metrics)

        self.trial_button = QPushButton("试用与诊断")
        self.trial_button.clicked.connect(self.show_trial_dialog)
        body.addWidget(self.trial_button)

        self.chat_log = QPlainTextEdit()
        self.chat_log.setReadOnly(True)
        self.chat_log.appendPlainText(
            "桌宠助手已打开。聊天需要本地模型服务和正确的模型 ID；"
            "PPL 只管理关系状态，不直接生成回复。")
        body.addWidget(self.chat_log, 1)

        memory_row = QHBoxLayout()
        self.remember_button = QPushButton("记住这件事")
        self.remember_button.clicked.connect(self.remember_fact)
        self.memory_manage_button = QPushButton("管理本角色记忆")
        self.memory_manage_button.clicked.connect(self.manage_memories)
        self.clear_history_button = QPushButton("清空本角色聊天")
        self.clear_history_button.clicked.connect(self.clear_character_history)
        self.action_audit_button = QPushButton("查看操作记录")
        self.action_audit_button.clicked.connect(self.show_action_audit)
        memory_row.addWidget(self.remember_button)
        memory_row.addWidget(self.memory_manage_button)
        memory_row.addWidget(self.clear_history_button)
        memory_row.addWidget(self.action_audit_button)
        body.addLayout(memory_row)

        message_row = QHBoxLayout()
        self.message = QLineEdit()
        self.message.setPlaceholderText("输入文字，或开始连续监听后检查识别结果")
        self.message.returnPressed.connect(self.send_message)
        self.send_button = QPushButton("发送")
        self.send_button.clicked.connect(self.send_message)
        self.plan_button = QPushButton("生成任务草案")
        self.plan_button.clicked.connect(self.propose_task)
        message_row.addWidget(self.message, 1)
        message_row.addWidget(self.send_button)
        message_row.addWidget(self.plan_button)
        body.addLayout(message_row)

        voice_row = QHBoxLayout()
        self.listen_button = QPushButton("开始连续监听")
        self.listen_button.clicked.connect(self.listen_continuously)
        self.stop_listen_button = QPushButton("停止监听")
        self.stop_listen_button.setEnabled(False)
        self.stop_listen_button.clicked.connect(self.stop_listening)
        self.speak_button = QPushButton("朗读上一条回复")
        self.speak_button.clicked.connect(self.read_reply)
        self.stop_speak_button = QPushButton("停止朗读")
        self.stop_speak_button.setEnabled(False)
        self.stop_speak_button.clicked.connect(self.stop_speaking)
        self.ppl_button = QPushButton("向 PPL 发送安慰事件")
        self.ppl_button.clicked.connect(self.comfort)
        voice_row.addWidget(self.listen_button)
        voice_row.addWidget(self.stop_listen_button)
        voice_row.addWidget(self.speak_button)
        voice_row.addWidget(self.stop_speak_button)
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
        self.mini_audit = QPushButton("检查派蒙迷你宠物（res/pet）")
        self.mini_audit.clicked.connect(self.audit_mini_paimon)
        body.addWidget(self.mini_audit)

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
        self.save_reply_button = QPushButton("将 AI 回复保存为便签")
        self.save_reply_button.clicked.connect(self.save_reply_as_note)
        self.attach_file_button = QPushButton("选择文件供 AI 分析")
        self.attach_file_button.clicked.connect(self.attach_workspace_file)
        create_button.clicked.connect(self.create_file)
        delete_button.clicked.connect(self.delete_file)
        restore_button.clicked.connect(self.restore_file)
        for widget in (create_button, delete_button, restore_button,
                       self.save_reply_button, self.attach_file_button):
            file_row.addWidget(widget)
        body.addLayout(file_row)
        self.status = QLabel("麦克风默认关闭；所有文件动作均须用户亲自选择。")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        body.addWidget(self.status)

    def set_character(self, name: str):
        if self.character_name == name:
            return
        self._invalidate_assistant_scope("角色已切换，旧任务草案已取消。")
        if self._listen_stop_event is not None:
            self._listen_stop_event.set()
            self._listening = False
            self.stop_listen_button.setEnabled(False)
        if self._speech_stop_event is not None:
            self._speech_stop_event.set()
            self.stop_speak_button.setEnabled(False)
        self._finish_speech_visuals()
        self._stream_reply_open = False
        self.character_name = name
        self._apply_character_audio()
        self.setWindowTitle("桌宠助手 · " + name)
        self._sync_guga_controls()
        profile = resolve_profile(name)
        persona = profile.key if profile and profile.key in PERSONAS else "companion"
        saved = self._prefs["personas"].get(name)
        if saved in PERSONAS:
            persona = saved
        blocked = self.persona.blockSignals(True)
        try:
            self.persona.setCurrentIndex(max(0, self.persona.findData(persona)))
        finally:
            self.persona.blockSignals(blocked)
        self.chat_log.appendPlainText("已切换当前桌宠：" + name)
        self._last_reply = ""
        self._pending_file_context = None
        self._ppl_snapshot = ""  # Persona snapshots belong to the previous character
        self._restore_character_history()

    def _restore_character_history(self):
        self.chat_log.clear()
        self.chat_log.appendPlainText("桌宠助手 · " + self.character_name)
        if not self._conversation_store:
            self.chat_log.appendPlainText("本地历史/记忆数据库不可用。")
            return
        try:
            for item in self._conversation_store.recent_messages(
                    self.character_name, limit=40):
                prefix = "你：" if item["role"] == "user" else self.character_name + "："
                self.chat_log.appendPlainText(prefix + item["content"])
        except (OSError, ValueError) as exc:
            self.chat_log.appendPlainText("历史读取失败：" + str(exc))

    def clear_character_history(self):
        if not self._conversation_store:
            self._job_error("本地历史数据库不可用")
            return
        character, generation = self.character_name, self._session_generation
        if QMessageBox.question(
                self, "清空当前角色聊天记录",
                "只删除“" + self.character_name + "”的本地聊天记录；已保存的角色记忆不会删除。\n确认继续？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        if character != self.character_name or generation != self._session_generation:
            return
        try:
            count = self._conversation_store.clear_history(self.character_name)
            self._invalidate_assistant_scope("会话已清空，旧任务草案已取消。")
            self._restore_character_history()
            self.status.setText("已清空当前角色聊天记录（" + str(count) + " 条）。角色记忆保留。")
        except (OSError, ValueError) as exc:
            self._job_error("清空聊天记录失败：" + str(exc))

    def remember_fact(self):
        if not self._conversation_store:
            self._job_error("本地记忆数据库不可用")
            return
        content, ok = QInputDialog.getMultiLineText(
            self, "保存本角色记忆", "输入你明确希望这个角色记住的事实：")
        if not ok or not content.strip():
            return
        content = content.strip()
        if QMessageBox.question(
                self, "确认保存记忆",
                "仅保存到本机，并且只对当前角色可见：\n" + content,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._conversation_store.add_memory(self.character_name, content, importance=2)
            self.status.setText("已保存到当前角色的本地记忆。")
        except (OSError, ValueError) as exc:
            self._job_error("记忆保存失败：" + str(exc))

    def manage_memories(self):
        if not self._conversation_store:
            self._job_error("本地记忆数据库不可用")
            return
        try:
            memories = self._conversation_store.list_memories(self.character_name)
        except (OSError, ValueError) as exc:
            self._job_error("记忆读取失败：" + str(exc))
            return
        if not memories:
            QMessageBox.information(self, "角色记忆", "当前角色还没有保存的记忆。")
            return
        labels = [item["content"] for item in memories]
        selected, ok = QInputDialog.getItem(
            self, "管理本角色记忆", "选择一条记忆（删除需要再次确认）：",
            labels, 0, False)
        if not ok:
            return
        item = memories[labels.index(selected)]
        if QMessageBox.question(
                self, "删除记忆",
                "确认从本机删除这条当前角色记忆？\n" + selected,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._conversation_store.delete_memory(self.character_name, item["id"])
            self.status.setText("已删除所选角色记忆。")
        except (OSError, ValueError) as exc:
            self._job_error("记忆删除失败：" + str(exc))

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

    def audit_mini_paimon(self):
        """Inspect independently installed SubPet roles, not main PetWidget."""
        root = self.role_root.expanduser().resolve().parent / "pet"
        try:
            matches = (sorted(
                p for p in root.iterdir()
                if p.is_dir() and not p.is_symlink()
                and resolve_profile(p.name) is not None
                and resolve_profile(p.name).key == "paimon")
                if root.is_dir() else [])
            if not matches:
                raise FidelityError(
                    "没有检测到派蒙迷你宠物。请检查安装目录 res/pet/Paimon "
                    "或 res/pet/派蒙；主角色包不等于迷你宠物包。")
            selected = matches[0]
            if len(matches) > 1:
                choice, ok = QInputDialog.getItem(
                    self, "选择已安装的派蒙迷你宠物",
                    "选择一个 res/pet 子目录：",
                    [p.name for p in matches], 0, False)
                if not ok:
                    return
                selected = next(p for p in matches if p.name == choice)
            report = inspect_mini_character_role(selected, selected.name)
            flags = report["mini_follow"]
            lines = [
                "本机迷你宠物：" + str(selected),
                "跟随主宠物 X：" + ("是" if flags["follow_main_x"] else "否"),
                "跟随主宠物 Y：" + ("是" if flags["follow_main_y"] else "否"),
                "可选附加悬浮：" + (
                    "可用（受全局设置与迷你宠物菜单开关控制）"
                    if flags["optional_hover_supported"] else "不启用"),
                "工程原因：" + flags["reason"],
                "静态缺口：" + (
                    "；".join(report["issues"]) if report["issues"] else "无"),
                "形象及声音：尚未与具体作品人工验证。"
            ]
            QMessageBox.information(
                self, "派蒙迷你宠物独立检查", "\n".join(lines))
        except (FidelityError, OSError, ValueError) as exc:
            self._job_error("迷你宠物检查失败：" + str(exc))

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
        self._voice_profiles = {name: dict(profile)
                                for name, profile in prefs.get("voice_profiles", {}).items()}
        profile = self._voice_profiles.get(self.character_name, {})
        self.audio_settings.set_values(prefs.get("microphone"),
                                       profile.get("voice_id", ""), profile.get("rate", 170))
        self.llm_endpoint.setText(prefs["llm_url"])
        self.llm_model.setText(prefs["llm_model"])
        self.ppl_endpoint.setText(prefs["ppl_url"])
        self.voice_model.setText(prefs["voice_model"])
        self.ppl_enabled.setChecked(prefs["ppl_enabled"])
        self.bubble_enabled.setChecked(prefs["bubble_enabled"])
        self.auto_speak.setChecked(prefs["auto_speak"])
        self.motion_enabled.setChecked(prefs["motion_enabled"])
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
            "microphone": self.audio_settings.microphone(),
            "voice_profiles": {name: dict(profile) for name, profile in self._voice_profiles.items()},
            "ppl_enabled": self.ppl_enabled.isChecked(),
            "bubble_enabled": self.bubble_enabled.isChecked(),
            "auto_speak": self.auto_speak.isChecked(),
            "motion_enabled": self.motion_enabled.isChecked(),
        })
        prefs["personas"] = dict(prefs["personas"])
        prefs["personas"][self.character_name] = self.persona.currentData()
        try:
            save_preferences(prefs)
            self._prefs = prefs
            self.status.setText("配置已保存；聊天历史独立保存在本机，PPL 快照仅本次会话有效。")
        except (OSError, ValueError) as exc:
            self._job_error("配置保存失败：" + str(exc))

    def _apply_character_audio(self):
        profile = self._voice_profiles.get(self.character_name, {})
        self.audio_settings.set_values(self.audio_settings.microphone(),
                                       profile.get("voice_id", ""), profile.get("rate", 170))

    def _audio_settings_changed(self):
        self._auto_read_timer.stop()
        self._voice_profiles[self.character_name] = {
            "voice_id": self.audio_settings.voice_id(), "rate": self.audio_settings.rate()}
        self._trial_recorder.reset_feedback()
        self.voice_conversation.configuration_changed()
        if self._job is not None and self._activity_kind in ("listen", "speech"):
            self._job_cancel_requested = True
            self._activity_outcome = "cancelled"
            for event in (self._listen_stop_event, self._speech_stop_event):
                if event is not None:
                    event.set()
            self._trial_recorder.request_stop(self._trial_run_id, "configuration_changed")
            self._activity_phase = "正在停止旧语音设置的任务"
            self.status.setText("语音设置已改变；旧任务停止后使用新设置。")
            self._refresh_activity()
        self._sync_audio_controls()

    def _sync_audio_controls(self):
        busy = (self._job is not None or self.voice_conversation.active
                or self._closing_after_worker)
        can_stop = self.voice_conversation.active or any(
            event is not None and not event.is_set()
            for event in (self._listen_stop_event, self._speech_stop_event,
                          self._audio_options_stop))
        self.audio_settings.set_busy(busy, can_stop=can_stop)
        self.audio_settings.stop_button.setText(
            "停止刷新" if self._audio_options_stop is not None else "停止当前语音")

    def refresh_audio_options(self):
        if self._job is not None or self.voice_conversation.active:
            self.status.setText("请先结束当前操作，再刷新设备与音色。")
            return
        self._audio_options_stop = threading.Event()
        self._begin_activity("voice_options")
        self.audio_settings.status_label.setText(
            "正在读取本机输入设备与系统音色；不会录音或发声。")
        self._submit(inspect_audio_options, self._audio_options_ready,
                     stop_event=self._audio_options_stop)

    def _audio_options_ready(self, catalog):
        if catalog is not None and self._audio_options_stop is not None \
                and not self._audio_options_stop.is_set():
            self.audio_settings.apply_catalog(catalog)
            self.status.setText("设备与音色目录已刷新；选择后可试听，并保存助手设置。")

    def stop_audio_operation(self):
        if self.voice_conversation.active:
            self.end_voice_conversation()
        elif self._audio_options_stop is not None:
            self._audio_options_stop.set()
            self._job_cancel_requested = True
            self._activity_outcome = "cancelled"
            self._activity_phase = "正在停止读取设备与音色"
            self._trial_recorder.request_stop(self._trial_run_id, "user")
            self.audio_settings.status_label.setText("已请求停止；等待当前系统查询返回。")
            self._refresh_activity()
        elif self._speech_stop_event is not None:
            self.stop_speaking()
        elif self._listen_stop_event is not None:
            self.stop_listening()
        self._sync_audio_controls()

    def _notice(self, text: str):
        # Tell PetWidget to use the *existing* notification bubble pipeline.
        # This signal has no filesystem write capability.
        if self.bubble_enabled.isChecked():
            self.action_notice.emit(text[:120])
        self._emit_selected_animation()

    def _append_stream_delta(self, piece, character, generation):
        if (generation != self._session_generation or character != self.character_name
                or self._job_cancel_requested):
            return
        self.chat_log.insertPlainText(piece)
        self.chat_log.verticalScrollBar().setValue(
            self.chat_log.verticalScrollBar().maximum())
        self._trial_recorder.text(self._trial_run_id, len(piece))
        if self._activity_kind == "chat" and self._activity_ended is None and piece:
            if self._activity_first_text is None:
                self._activity_first_text = monotonic()
            self._activity_chars += len(piece)
            self._activity_phase = "正在生成回复"
            self._refresh_activity()

    def _begin_activity(self, kind):
        # New explicit work supersedes an ordinary reply waiting to auto-read.
        self._auto_read_timer.stop()
        self._activity_kind = kind
        self._activity_started = monotonic()
        self._activity_ended = None
        self._activity_first_text = None
        self._activity_chars = 0
        self._activity_outcome = ""
        self._job_cancel_requested = False
        self._activity_phase = {
            "chat": "正在等待模型回复", "plan": "正在生成任务草案",
            "model_probe": "正在试聊当前模型",
            "listen": "正在准备麦克风", "speech": "正在准备朗读",
            "models": "正在检查模型连接", "voice_check": "正在检查语音条件",
            "voice_options": "正在读取设备与音色",
            "other": "正在执行本地任务",
        }[kind]
        self.stop_generation_button.setText({
            "models": "停止检查", "model_probe": "停止试聊",
        }.get(kind, "停止生成"))
        self._activity_timer.start()
        if kind in ("chat", "plan", "model_probe"):
            self._set_interaction_phase("thinking")
        self._refresh_activity()

    def _set_interaction_phase(self, phase):
        state = (self.character_name, phase)
        if state != self._interaction_state:
            self._interaction_state = state
            self.interaction_changed.emit(*state)

    def start_voice_conversation(self):
        self.voice_conversation.start()

    def interrupt_voice_conversation(self):
        self.voice_conversation.interrupt()

    def end_voice_conversation(self):
        self.voice_conversation.stop()

    def _refresh_activity(self):
        self._trial_recorder.sample(self._trial_run_id)
        self._sync_trial_window()
        self.activity_status.setText(self._activity_phase)
        if self._activity_started is None:
            self.activity_metrics.setText("")
            return
        end = monotonic() if self._activity_ended is None else self._activity_ended
        parts = ["耗时 {:.1f} 秒".format(max(0.0, end - self._activity_started))]
        if self._activity_kind in ("chat", "model_probe"):
            if self._activity_first_text is not None:
                parts.append("首段 {:.1f} 秒".format(
                    max(0.0, self._activity_first_text - self._activity_started)))
            else:
                parts.append("首段等待中" if self._activity_ended is None else "未收到正文")
            parts.append("已显示 {} 字符".format(self._activity_chars))
        self.activity_metrics.setText(" · ".join(parts))

    def _finish_activity(self):
        if self._activity_started is None:
            return
        self._activity_ended = monotonic()
        if self._activity_outcome == "failed":
            self._activity_phase = "操作未完成"
        elif self._job_cancel_requested or self._activity_outcome == "cancelled":
            self._activity_phase = "已停止"
        else:
            self._activity_phase = {
                "chat": "回复已完成", "plan": "任务草案已生成",
                "model_probe": "试聊已完成",
                "listen": "识别已完成", "speech": "朗读已完成",
                "models": "连接检查已完成", "voice_check": "语音条件已检查",
                "voice_options": "设备与音色读取已完成",
                "other": "本地任务已完成",
            }.get(self._activity_kind, "就绪")
        self._activity_timer.stop()
        self._refresh_activity()

    def stop_generation(self, *, reason="user"):
        voice = self.voice_conversation
        if voice.active and voice.owns_job and not voice.controlling_stop:
            voice.stop(stop_reason=reason)
            return
        if (self._job is None or self._request_token is None
                or self._job_cancel_requested or self._activity_outcome):
            return
        self._job_cancel_requested = True
        self._trial_recorder.request_stop(self._trial_run_id, reason)
        self._request_token.cancel()
        self.stop_generation_button.setEnabled(False)
        self._activity_phase = ("正在停止检查" if self._activity_kind == "models"
                                else "正在停止生成")
        self._refresh_activity()
        if self._stream_reply_open:
            self.chat_log.appendPlainText("（用户停止；以上为未完成的回复）")
            self._stream_reply_open = False
        if self._activity_kind == "chat":
            self._last_reply = ""
            if not self.message.text().strip():
                self.message.setText(self._request_text)
        if self._activity_kind == "models":
            self.model_status.setText("连接检查已请求停止；可在检查结束后重试。")
            self.status.setText("正在停止连接检查；输入和附件已保留。")
        else:
            self.status.setText("正在停止本次生成；已显示文字和待重试附件保留。")

    def _submit(self, task, on_success, *args, stream=False,
                on_progress=None, **kwargs):
        if self.voice_conversation.active and not self.voice_conversation.dispatching:
            self.status.setText("语音对话进行中；请先结束，再开始其他操作。")
            return False
        if self._job is not None:
            self.status.setText("上一项语音/对话任务仍在执行")
            return
        if self._activity_started is None or self._activity_ended is not None:
            self._begin_activity("other")
        self.send_button.setEnabled(False)
        self.plan_button.setEnabled(False)
        self.listen_button.setEnabled(False)
        self.ppl_button.setEnabled(False)
        self.speak_button.setEnabled(False)
        self.detect_button.setEnabled(False)
        self.voice_check_button.setEnabled(False)
        job = _AssistantJob(task, *args, stream=stream, **kwargs)
        self._job = job
        self._job_generation = self._session_generation
        self._job_success_handler = on_success
        self._job_progress_handler = on_progress
        self._trial_run_id = self._trial_recorder.begin(self._activity_kind or "other")
        self._trial_notice("")
        job.success.connect(self._job_succeeded)
        job.failed.connect(self._job_failed)
        job.cancelled.connect(self._job_cancelled)
        if stream and on_progress is not None:
            job.progress.connect(self._job_progress)
        job.finished.connect(self._job_finished)
        job.start()
        self._sync_trial_window(refresh=True)
        self.voice_conversation.sync_controls()
        return True

    def _job_succeeded(self, result):
        if (self._job_generation == self._session_generation
                and not self._closing_after_worker
                and not self._job_cancel_requested
                and self._setup_job_is_current()
                and self._job_success_handler is not None):
            if not self._activity_outcome:
                self._activity_outcome = "completed"
            self.stop_generation_button.setEnabled(False)
            self._job_success_handler(result)

    def _job_progress(self, piece):
        if (self._job_generation == self._session_generation
                and not self._closing_after_worker
                and not self._job_cancel_requested
                and self._job_progress_handler is not None):
            self._job_progress_handler(piece)

    def _scoped_job_error(self, detail, generation):
        if generation == self._session_generation and not self._closing_after_worker:
            self._job_error(detail, worker_failed=True)

    def _job_failed(self, detail):
        if self._job_cancel_requested or not self._setup_job_is_current():
            return
        if self._job_generation == self._session_generation and not self._closing_after_worker:
            self._activity_outcome = "failed"
            self._trial_recorder.fail(
                self._trial_run_id, getattr(self._job, "error_code", "internal_error"))
            if self._activity_kind == "speech":
                self._trial_recorder.observe(
                    self._trial_run_id,
                    engine_completed=getattr(self._job, "engine_completed", None))
            self._trial_notice("本次操作未完成，请查看最近操作中的提示。")
            self.voice_conversation.failed(detail)
            if self._activity_kind == "models":
                self._model_catalog_endpoint = None
                self._replace_model_choices(())
                self.model_status.setText(detail)
            elif self._activity_kind == "voice_check":
                self.voice_status.setText("识别检查未完成：" + detail)
                self.tts_status.setText("朗读：本次检查未完成，请重试。")
            elif self._activity_kind == "voice_options":
                self.audio_settings.status_label.setText("设备与音色读取未完成：" + detail)
            elif self._activity_kind == "chat" and not self.message.text().strip():
                self.message.setText(self._request_text)
        self._scoped_job_error(detail, self._job_generation)

    def _job_cancelled(self):
        self._job_cancel_requested = True
        self._trial_recorder.request_stop(self._trial_run_id, "user")

    def _job_finished(self):
        outcome = ("cancelled" if self._job_cancel_requested else
                   self._activity_outcome or "interrupted")
        self._trial_recorder.finish(self._trial_run_id, outcome)
        self._trial_run_id = None
        self._finish_speech_visuals()
        self._finish_activity()
        self._set_interaction_phase("idle")
        if self._job_cancel_requested:
            self._finish_setup_cancel()
        if (self._job_cancel_requested and self._request_token is not None
                and self._job_generation == self._session_generation
                and not self._closing_after_worker and self._setup_job_is_current()):
            self.status.setText("连接检查已停止；可再次检查。" if self._activity_kind == "models"
                                else "本次生成已停止；可修改输入后重新发送。")
        job = self._job
        self._job = None
        self._job_generation = None
        self._job_success_handler = None
        self._job_progress_handler = None
        self._request_token = None
        self._setup_job = None
        self._request_text = ""
        self.stop_generation_button.setEnabled(False)
        self._listening = False
        self._listen_stop_event = None
        self._speech_stop_event = None
        self._audio_options_stop = None
        self.stop_listen_button.setEnabled(False)
        self.stop_speak_button.setEnabled(False)
        for button in (self.send_button, self.plan_button, self.listen_button,
                       self.ppl_button, self.speak_button, self.detect_button,
                       self.voice_check_button):
            button.setEnabled(True)
        if job is not None:
            job.deleteLater()
        self._sync_trial_window(refresh=True)
        if self._closing_after_worker:
            self._closing_after_worker = False
            QTimer.singleShot(0, self.close)
        self.voice_conversation.job_finished(outcome)

    def _on_voice_engine_ready(self, character, text, stop_event=None):
        if (self._speaking_session is None
                or self._speaking_session !=
                (character, self._session_generation)
                or self._speech_stop_event is None or self._speech_stop_event.is_set()
                or (stop_event is not None and stop_event is not self._speech_stop_event)
                or self._closing_after_worker):
            return
        self._speech_has_started = True
        self._trial_recorder.ready(self._trial_run_id)
        self._activity_phase = "正在朗读"
        self._refresh_activity()
        self._set_interaction_phase("speaking")
        self.voice_conversation.speech_ready()
        self.speech_started.emit(character, text[:120])

    def _on_microphone_ready(self, character, generation, stop_event):
        if (character != self.character_name or generation != self._session_generation
                or stop_event is not self._listen_stop_event or stop_event.is_set()
                or not self._listening or self._closing_after_worker):
            return
        self._activity_phase = "正在监听"
        self._set_interaction_phase("listening")
        self.voice_conversation.microphone_ready()
        self._trial_recorder.ready(self._trial_run_id)
        self._refresh_activity()
        self.status.setText("麦克风已打开；音频只在内存中处理，点击“停止监听”结束。")

    def _on_speech_progress(self, character, generation, stop_event, completed, total):
        if (self._speaking_session != (character, generation)
                or character != self.character_name or generation != self._session_generation
                or stop_event is not self._speech_stop_event or stop_event.is_set()
                or self._job_cancel_requested or self._closing_after_worker
                or not self._speech_has_started or self._job is None
                or not 0 <= completed <= total or total <= 0):
            return
        self._activity_phase = "正在朗读（" + str(completed) + "/" + str(total) + " 段完成）"
        self.status.setText("朗读进度：" + str(completed) + "/" + str(total) + " 段完成")
        self.voice_conversation.speech_progress(completed, total)
        self._refresh_activity()

    def _finish_speech_visuals(self):
        session = self._speaking_session
        self._speaking_session = None
        self._speech_has_started = False
        if session is not None:
            self.speech_finished.emit(session[0])

    def _job_error(self, detail: str, *, worker_failed=False):
        # A separate file/settings action may fail while audio is still live.
        # Only the worker's own failure may revoke its controls and ownership.
        if self._job is None or worker_failed:
            self._listening = False
            self._listen_stop_event = None
            self._speech_stop_event = None
            self.stop_listen_button.setEnabled(False)
            self.stop_speak_button.setEnabled(False)
            if self._stream_reply_open:
                self.chat_log.appendPlainText("（回复中断）")
                self._stream_reply_open = False
            # Preserve text feedback if an automatic speech engine cannot start.
            if (self._speaking_session is not None and not self._speech_has_started
                    and not self._speech_is_sample
                    and self.bubble_enabled.isChecked() and self._last_reply):
                self.reply_ready.emit(self._last_reply[:120])
            self._finish_speech_visuals()
        self.status.setText("操作失败：" + detail)
        self.chat_log.appendPlainText("[错误] " + detail)

    def show_trial_dialog(self):
        if self._trial_dialog is None:
            dialog = TrialDialog(self._trial_recorder.snapshot, self)
            dialog.model_test_requested.connect(self.try_model)
            dialog.speech_test_requested.connect(self.try_speech)
            dialog.listen_requested.connect(self.listen_continuously)
            dialog.stop_requested.connect(self._stop_trial_operation)
            dialog.clear_requested.connect(self._clear_trial_records)
            dialog.feedback_changed.connect(self._trial_recorder.set_feedback)
            self._trial_dialog = dialog
        self._trial_dialog.set_probe_text(self._trial_probe_text)
        self._sync_trial_window(refresh=True)
        self._trial_dialog.show()
        self._trial_dialog.raise_()
        self._trial_dialog.activateWindow()

    def _sync_trial_window(self, *, refresh=False):
        if self._trial_dialog is None:
            return
        can_stop = (
            (self._request_token is not None and not self._job_cancel_requested
             and not self._activity_outcome)
            or (self._listen_stop_event is not None and self._listening
                and not self._listen_stop_event.is_set())
            or (self._speech_stop_event is not None and self._speaking_session is not None
                and not self._speech_stop_event.is_set()))
        voice_active = self.voice_conversation.active
        self._trial_dialog.set_busy(self._job is not None or voice_active,
                                    can_stop=bool(can_stop or voice_active))
        if refresh:
            self._trial_dialog.refresh_report()

    def _clear_trial_records(self):
        if self._job is None:
            self._trial_recorder.clear()
            self._sync_trial_window(refresh=True)

    def _trial_notice(self, text):
        if self._trial_dialog is not None and self._trial_dialog.isVisible():
            self._trial_dialog.status_label.setText(text)

    def _clear_trial_probe(self):
        self._trial_probe_text = ""
        if self._trial_dialog is not None:
            self._trial_dialog.clear_probe()

    def _trial_configuration_changed(self):
        self._trial_recorder.reset_feedback()
        self._clear_trial_probe()
        if self._job is not None and self._activity_kind == "model_probe":
            self.stop_generation(reason="configuration_changed")

    def _stop_trial_operation(self):
        if self.voice_conversation.active:
            self.end_voice_conversation()
            return
        if self._activity_kind == "listen":
            self.stop_listening()
        elif self._activity_kind == "speech":
            self.stop_speaking()
        else:
            self.stop_generation()

    def try_model(self):
        if self._job is not None:
            self.status.setText("请先结束当前操作，再试聊模型。")
            return
        if not self._chat_configuration_ready():
            self._trial_notice(self.status.text())
            return
        self.show_trial_dialog()
        self._clear_trial_probe()
        token = CancellationToken()
        endpoint, model = self.llm_endpoint.text(), self.llm_model.text()
        self._request_token = token
        self._begin_activity("model_probe")
        self.stop_generation_button.setEnabled(True)
        self.status.setText("正在试聊当前模型，回复显示在试用窗口。")

        def task(on_delta):
            answer = stream_local_chat(
                "请用一句简短中文向我打招呼。", on_delta=on_delta,
                persona_key="companion", base_url=endpoint, model=model,
                cancel_token=token)
            token.raise_if_cancelled()
            return answer

        self._submit(task, self._trial_model_reply, stream=True,
                     on_progress=self._trial_model_delta)

    def _trial_model_delta(self, piece):
        # _job_progress has already accepted this worker's scope and stop state.
        displayed = piece[:max(0, 4000 - len(self._trial_probe_text))]
        if not displayed:
            return
        self._trial_probe_text += displayed
        self._trial_recorder.text(self._trial_run_id, len(displayed))
        if self._activity_first_text is None:
            self._activity_first_text = monotonic()
        self._activity_chars += len(displayed)
        self._activity_phase = "正在显示试聊回复"
        if self._trial_dialog is not None:
            self._trial_dialog.set_probe_text(self._trial_probe_text)
        self._refresh_activity()

    def _trial_model_reply(self, answer):
        self._trial_recorder.observe(self._trial_run_id, result_chars=len(answer))
        if not self._trial_probe_text:
            self._trial_model_delta(answer)
        self.status.setText("已收到完整试聊回复；可在试用窗口查看并记录效果。")

    def try_speech(self):
        if self._job is not None:
            self.status.setText("请先结束当前操作，再试听示例。")
            return
        self._start_speech("你好，我是你的桌宠助手。这是一段语音试听。", sample=True)

    def _relationship_state(self):
        if not self.ppl_enabled.isChecked():
            return None
        return PPLCharacterClient(self.ppl_endpoint.text()).state(
            self.character_name)

    def detect_models(self):
        if self._job is not None:
            self.status.setText("上一项任务仍在执行；结束后可检查连接。")
            return
        endpoint = self.llm_endpoint.text().strip()
        self._model_catalog_endpoint = None
        self._replace_model_choices(())
        self._setup_job = ("models", self._model_check_revision, endpoint)
        token = CancellationToken()
        self._request_token = token
        self._begin_activity("models")
        self.stop_generation_button.setEnabled(True)
        self.model_status.setText("正在读取本地服务列出的模型；本次检查不会发送聊天内容。")
        self.status.setText("正在检查连接；可点击“停止检查”。")
        self._submit(list_local_models, self._choose_model,
                     endpoint, cancel_token=token)

    def _choose_model(self, names):
        self._trial_recorder.observe(self._trial_run_id, model_count=len(names))
        self._model_catalog_endpoint = self.llm_endpoint.text().strip()
        self._replace_model_choices(names, select_single=True)
        self._model_choice_changed()
        self.status.setText("已读取本地模型列表；选择聊天模型后发送消息即可验证回复。")

    def _replace_model_choices(self, names, *, select_single=False):
        current = self.llm_model.text()
        self._model_catalog = tuple(names)
        selector_blocked = self.model_selector.blockSignals(True)
        editor_blocked = self.llm_model.blockSignals(True)
        try:
            self.model_selector.clear()
            self.model_selector.addItems(list(names))
            chosen = (names[0] if select_single and len(names) == 1
                      and not current.strip() else current)
            self.model_selector.setCurrentIndex(self.model_selector.findText(chosen))
            self.model_selector.setEditText(chosen)
        finally:
            self.llm_model.blockSignals(editor_blocked)
            self.model_selector.blockSignals(selector_blocked)

    def _model_choice_changed(self, _text=None):
        self._trial_configuration_changed()
        if self._model_catalog_endpoint != self.llm_endpoint.text().strip():
            return
        model = self.llm_model.text().strip()
        if not model:
            note = "请从下拉框选择聊天模型，或手动输入 ID。"
        elif model not in self._model_catalog:
            note = "当前手填 ID 未在本次列表中，请核对或重新选择。"
        else:
            note = "已选择模型：" + model + "。"
        self.model_status.setText("服务可连接。" + note + "尚未验证生成，列表不代表已加载。")

    def _model_endpoint_changed(self, _text):
        self._trial_configuration_changed()
        self._model_check_revision += 1
        self._model_catalog_endpoint = None
        self._replace_model_choices(())
        self.model_status.setText("地址已更改，请重新检查连接；已保留手填模型 ID。")
        if self._setup_job is not None and self._setup_job[0] == "models":
            self._trial_recorder.request_stop(self._trial_run_id, "configuration_changed")
            if self._request_token is not None:
                self._request_token.cancel()
            self._job_cancel_requested = True
            self.stop_generation_button.setEnabled(False)
            self._activity_phase = "正在停止旧地址检查"
            self._refresh_activity()
            self.status.setText("地址已更改；旧检查结束后可重新检查。")

    def _voice_path_changed(self, _text):
        self._trial_recorder.reset_feedback()
        self._voice_check_revision += 1
        self.voice_status.setText("识别：模型目录已更改，请重新检查语音条件。")
        if self._setup_job is not None and self._setup_job[0] == "voice":
            self._trial_recorder.request_stop(self._trial_run_id, "configuration_changed")
            self._activity_outcome = "cancelled"
            self.tts_status.setText("朗读：请等待旧检查结束后重新检查。")

    def _setup_job_is_current(self):
        if self._setup_job is None:
            return True
        kind, revision, value = self._setup_job
        if kind == "models":
            return (revision == self._model_check_revision
                    and value == self.llm_endpoint.text().strip())
        return (revision == self._voice_check_revision
                and value == self.voice_model.text().strip())

    def _finish_setup_cancel(self):
        if (self._setup_job is None or not self._setup_job_is_current()
                or self._activity_outcome in ("completed", "failed")):
            return
        if self._setup_job[0] == "models":
            self.model_status.setText("连接检查已停止，请重新检查。")
        else:
            self.voice_status.setText("识别：检查已停止，请重新检查语音条件。")
            self.tts_status.setText("朗读：检查已停止，请重新检查语音条件。")

    def check_voice_setup(self):
        if self._job is not None:
            self.status.setText("上一项任务仍在执行；结束后可检查语音条件。")
            return
        path = self.voice_model.text().strip()
        self._setup_job = ("voice", self._voice_check_revision, path)
        self._begin_activity("voice_check")
        self.voice_status.setText("识别：正在检查组件与模型目录，不会打开麦克风。")
        self.tts_status.setText("朗读：正在检查组件，不会发声。")
        self._submit(inspect_voice_readiness, self._voice_setup_checked, path)

    def _voice_setup_checked(self, result):
        self._trial_recorder.observe(
            self._trial_run_id, recognition_ready=result.recognition_ready,
            tts_ready=result.tts_ready)
        self.voice_status.setText("识别：" + result.recognition_message)
        self.tts_status.setText("朗读：" + result.tts_message)
        self.status.setText("语音条件已检查；实际录音和朗读仍须由你点击启动。")

    def _chat_configuration_ready(self):
        try:
            _local_base(self.llm_endpoint.text())
        except AssistantServiceError as exc:
            detail = service_error_hint(exc)
            self.model_status.setText(detail)
            self.status.setText(detail + " 输入与附件已保留。")
            self.llm_endpoint.setFocus()
            return False
        model = self.llm_model.text().strip()
        if not model or len(model) > 120 or any(ord(ch) < 32 or ord(ch) == 127 for ch in model):
            detail = "请选择或填写聊天模型 ID；可先点击“检查连接 / 刷新模型”。"
            self.model_status.setText(detail)
            self.status.setText(detail + " 输入与附件已保留。")
            self.llm_model.setFocus()
            return False
        return True

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
            self.voice_conversation.configuration_changed()
            self.status.setText("PPL 渲染快照已加载：" + file.name)
        except (OSError, UnicodeError, ValueError) as exc:
            self._job_error(str(exc))

    def send_message(self):
        if self.voice_conversation.active:
            self.status.setText("语音对话进行中，键盘草稿已保留；结束后可发送。")
            return
        self._send_chat(self.message.text().strip())

    def _send_chat(self, text, *, voice_turn=False, on_reply=None):
        if self._job is not None:
            self.status.setText("上一项语音/对话任务仍在执行，输入已保留。")
            return False
        if not text:
            return False
        if not self._chat_configuration_ready():
            return False
        # The assistant only replies as text; the output is never passed to
        # PetWorkspace and cannot mutate user files.
        endpoint, model = self.llm_endpoint.text(), self.llm_model.text()
        character, persona = self.character_name, self.persona.currentData()
        snapshot = self._ppl_snapshot
        generation = self._session_generation
        ppl = (self.ppl_endpoint.text() if self.ppl_enabled.isChecked()
               else None)
        file_context = None if voice_turn else self._pending_file_context
        try:
            history = (self._conversation_store.recent_messages(character, limit=12)
                       if self._conversation_store else [])
            memory_context = (self._conversation_store.memory_context(
                character, text, limit=5) if self._conversation_store else "")
        except (OSError, ValueError, sqlite3.Error) as exc:
            self._job_error("本地历史读取失败，输入与附件已保留：" + str(exc))
            return
        token = CancellationToken()
        self._request_token = token
        self._request_text = "" if voice_turn else text
        self._last_reply = ""
        self._begin_activity("chat")
        self.stop_generation_button.setEnabled(True)
        if not voice_turn:
            self.message.clear()
        self.chat_log.appendPlainText("你：" + text)
        if file_context:
            self.chat_log.appendPlainText("本轮已附加用户确认的文件：" + file_context["name"])
        self.status.setText("正在请求本地模型…")
        self.chat_log.appendPlainText(character + "：")
        self._stream_reply_open = True

        def task(on_delta):
            state = (PPLCharacterClient(ppl).state(character, cancel_token=token)
                     if ppl else None)
            answer = stream_local_chat(
                text, on_delta=on_delta, persona_key=persona, state=state,
                ppl_prompt=snapshot, history=history, memory_context=memory_context,
                file_context=file_context, base_url=endpoint, model=model,
                cancel_token=token)
            token.raise_if_cancelled()
            return character, generation, text, answer, file_context

        return self._submit(
            task, on_reply or self._message_reply, stream=True,
            on_progress=lambda piece: self._append_stream_delta(
                piece, character, generation))

    def _message_reply(self, result, *, voice_turn=False):
        if isinstance(result, tuple):
            if len(result) == 5:
                character, generation, user_text, reply, file_context = result
                if generation != self._session_generation:
                    return
                if not voice_turn and self._pending_file_context == file_context:
                    self._pending_file_context = None
            elif len(result) == 4:
                character, generation, user_text, reply = result
                if generation != self._session_generation:
                    return
            elif len(result) == 3:
                character, generation, reply = result
                user_text = None
                if generation != self._session_generation:
                    return
            else:
                character, reply = result
                user_text = None
            if character != self.character_name:
                self.chat_log.appendPlainText(
                    "[旧角色回复已丢弃] 切换角色后不展示之前的人设内容")
                return
        else:
            reply = result
        self._trial_recorder.observe(self._trial_run_id, result_chars=len(reply))
        self._last_reply = reply
        history_warning = ""
        if isinstance(result, tuple) and len(result) in (4, 5) and self._conversation_store:
            try:
                self._conversation_store.append_turn(character, user_text, reply)
            except (OSError, ValueError, sqlite3.Error) as exc:
                history_warning = "回复已生成，但本地历史保存失败：" + str(exc)
        if not self._stream_reply_open:
            self.chat_log.appendPlainText(self.character_name + "：" + reply)
        self._stream_reply_open = False
        # When auto-read is enabled, the native bubble appears when TTS
        # starts, not seconds earlier during model response handling.
        will_speak = (voice_turn or self.auto_speak.isChecked()) and self.isVisible()
        if self.bubble_enabled.isChecked() and not will_speak:
            self.reply_ready.emit(reply[:120])
        if not will_speak:
            self._emit_selected_animation()
        self.status.setText(history_warning or "回复已生成；点击朗读按钮可使用离线语音播报。")
        if not voice_turn and self.auto_speak.isChecked() and self.isVisible():
            self._auto_read_timer.start()

    def _auto_read_reply(self):
        if (self._job is None and not self.voice_conversation.active
                and self.auto_speak.isChecked() and self.isVisible()):
            self.read_reply()

    def _cancel_task_plan(self, reason):
        self._task_generation += 1
        session, review = self._task_session, self._task_review_dialog
        # Detach first so cancellation callbacks cannot rewrite the new scope.
        self._task_session = None
        self._task_review_dialog = None
        if review is not None:
            review.invalidate(reason)
            review.close()
            review.progress_changed.disconnect(self._task_progress)
            # Release the hidden child without queuing deletion against a parent
            # that may itself be closing. Python now owns its remaining lifetime.
            review.setParent(None)
        elif session is not None:
            session.cancel()

    def _invalidate_assistant_scope(self, reason, *, stop_reason="scope_changed"):
        self._auto_read_timer.stop()
        self.voice_conversation.stop(reason, stop_reason=stop_reason, cancel_job=False)
        if self._audio_options_stop is not None:
            self._audio_options_stop.set()
        if self._job is not None:
            self._trial_recorder.request_stop(self._trial_run_id, stop_reason)
        self._trial_recorder.reset_feedback()
        self._clear_trial_probe()
        self._finish_setup_cancel()
        if self._request_token is not None:
            self._request_token.cancel()
        if self._job is not None:
            self._job_cancel_requested = True
            self.stop_generation_button.setEnabled(False)
            self._activity_phase = "正在停止旧会话任务"
            self._refresh_activity()
        else:
            self._activity_timer.stop()
            self._activity_started = None
            self._activity_ended = None
            self._activity_kind = None
            self._activity_phase = "就绪"
            self._refresh_activity()
        if self._stream_reply_open:
            self.chat_log.appendPlainText("（会话已变更，回复停止）")
        self._session_generation += 1
        self._cancel_task_plan(reason)
        if self._action_runtime is not None:
            self._action_runtime.invalidate_pending()
        self._pending_file_context = None
        self._last_reply = ""
        self._stream_reply_open = False
        self.stop_listening()
        self._listening = False
        self.stop_speaking()
        self._finish_speech_visuals()
        if self._job is None:
            self._set_interaction_phase("idle")

    def _persona_changed(self, _index):
        self._invalidate_assistant_scope("人设已切换，旧任务草案已取消。")
        self._ppl_snapshot = ""
        self.status.setText("人设已切换；旧回复、附件和任务草案已失效。")

    def propose_task(self):
        if self._job is not None:
            self.status.setText("上一项语音/对话任务仍在执行，输入已保留。")
            return
        text = self.message.text().strip()
        if not text:
            self.status.setText("先输入要创建的文件和内容要求，再生成任务草案。")
            return
        if not self._chat_configuration_ready():
            return
        if self._action_runtime is None:
            self._job_error("安全操作中心不可用：" + self._action_runtime_error)
            return
        self._cancel_task_plan("已请求新草案，先前未完成的步骤已取消。")
        task_generation = self._task_generation
        generation, character = self._session_generation, self.character_name
        workspace = self.workspace
        endpoint, model = self.llm_endpoint.text(), self.llm_model.text()
        file_context = (dict(self._pending_file_context)
                        if self._pending_file_context is not None else None)
        token = CancellationToken()
        self._request_token = token
        self._request_text = text
        self._begin_activity("plan")
        self.stop_generation_button.setEnabled(True)
        self.status.setText("正在生成文件任务草案；生成后逐步查看和批准。")

        def task():
            plan = generate_task_plan(text, base_url=endpoint, model=model,
                                      file_context=file_context, cancel_token=token)
            token.raise_if_cancelled()
            return task_generation, generation, character, workspace, text, file_context, plan

        self._submit(task, self._task_plan_reply)

    def _task_plan_reply(self, result):
        task_generation, generation, character, workspace, text, file_context, plan = result
        if (task_generation != self._task_generation
                or generation != self._session_generation
                or character != self.character_name or workspace is not self.workspace
                or self._closing_after_worker):
            return
        if self._pending_file_context == file_context:
            self._pending_file_context = None
        if self.message.text().strip() == text:
            self.message.clear()
        session = TaskSession(plan, self._action_runtime)
        self._task_session = session

        def current():
            return (self._task_session is session and task_generation == self._task_generation
                    and generation == self._session_generation
                    and character == self.character_name and workspace is self.workspace
                    and not self._closing_after_worker)

        review = TaskReviewDialog(session, self, scope_is_current=current)
        self._task_review_dialog = review
        review.progress_changed.connect(self._task_progress)
        self.chat_log.appendPlainText(
            "[任务草案] " + plan.title + "（" + str(len(plan.steps)) + " 步；尚未执行）")
        self._task_progress(session)
        review.show()

    def _task_progress(self, session):
        if session is not self._task_session:
            return
        count, total = len(session.completed), len(session.plan.steps)
        states = {"ready": "等待查看下一步", "awaiting_approval": "等待本步批准",
                  "completed": "全部完成", "cancelled": "剩余步骤已取消", "failed": "已停止"}
        message = "任务 " + str(count) + "/" + str(total) + "：" + states[session.state]
        if count:
            message += "；已创建：" + "、".join(
                item["result"]["name"] for item in session.completed)
        if session.error:
            message += "；" + str(session.error)
        warnings = [item.get("audit_warning", "") for item in session.completed
                    if item.get("audit_warning")]
        if warnings:
            message += "；" + "；".join(warnings)
        self.status.setText(message)

    def listen_once(self):
        """Compatibility entry point for the existing bounded four-second mode."""
        if self._job is not None:
            self.status.setText("上一项语音/对话任务仍在执行")
            return
        model = self.voice_model.text().strip()
        if not model:
            self._job_error("请先设置已安装的 Vosk 离线识别模型目录")
            return
        self.status.setText("正在录音 4 秒；只在这次点击后开启麦克风…")
        self._begin_activity("listen")
        self._submit(recognize_once, self._heard, model, seconds=4,
                     microphone=self.audio_settings.microphone())

    def listen_continuously(self):
        if self._job is not None:
            self.status.setText("上一项语音/对话任务仍在执行")
            return
        model = self.voice_model.text().strip()
        if not model:
            self._job_error("请先设置已安装的 Vosk 离线识别模型目录")
            self._trial_notice("请先在主助手中选择已解压的 Vosk 模型目录，再开始监听。")
            return
        self._listen_stop_event = threading.Event()
        stop_event = self._listen_stop_event
        character = self.character_name
        generation = self._session_generation
        microphone = self.audio_settings.microphone()
        self._listening = True
        self._begin_activity("listen")
        self.listen_button.setEnabled(False)
        self.stop_listen_button.setEnabled(True)
        self.status.setText("正在加载离线识别模型并准备麦克风；可点击“停止监听”取消。")
        on_ready = _weak_ready_callback(
            self, "microphone_ready", character, generation, stop_event)

        def task(on_delta):
            text = recognize_until_stopped(
                model, stop_event, on_partial=on_delta, max_seconds=120,
                on_ready=on_ready, microphone=microphone)
            return character, generation, text

        self._submit(task, self._heard_continuous, stream=True,
                     on_progress=self._heard_partial)

    def stop_listening(self):
        voice = self.voice_conversation
        if voice.active and voice.owns_job and not voice.controlling_stop:
            voice.stop()
            return
        if self._listen_stop_event is not None and self._listening:
            self._trial_recorder.request_stop(self._trial_run_id, "user")
            self._listen_stop_event.set()
            self.stop_listen_button.setEnabled(False)
            self._activity_outcome = "cancelled"
            self._activity_phase = "正在停止监听"
            self._refresh_activity()
            self.status.setText("正在停止麦克风并完成最后一段识别…")

    def _heard_partial(self, text):
        if (self._listening and self._listen_stop_event is not None
                and not self._listen_stop_event.is_set()):
            self.status.setText("正在识别：" + text[:100])

    def _heard_continuous(self, result):
        self._listening = False
        self._listen_stop_event = None
        if not isinstance(result, tuple) or len(result) != 3:
            self._activity_outcome = "failed"
            self._trial_recorder.fail(self._trial_run_id, "invalid_result")
            self._job_error("连续语音识别返回了无效结果")
            return
        character, generation, text = result
        if character != self.character_name or generation != self._session_generation:
            self.status.setText("角色已切换，已丢弃旧角色的语音识别结果。")
            return
        self._trial_recorder.observe(self._trial_run_id, result_chars=len(text))
        if text:
            self.message.setText(text)
            self.status.setText("语音识别完成；请检查文字后点击“发送”。")
        else:
            self._activity_outcome = "cancelled"
            self.status.setText("监听已停止，未产生识别文字。")

    def _heard(self, text):
        self._trial_recorder.observe(self._trial_run_id, result_chars=len(text))
        self.message.setText(text)
        self.status.setText("语音已转为文字；请检查后点击“发送”。")

    def read_reply(self):
        if not self._last_reply.strip():
            self._job_error("还没有可朗读的回复")
            return
        if self._job is not None:
            self.status.setText("上一项语音/对话任务仍在执行")
            return
        self._start_speech(self._last_reply)

    def _start_speech(self, text, *, sample=False):
        character = self.character_name
        self._speech_is_sample = sample
        self._begin_activity("speech")
        self.status.setText("正在使用本机语音合成…")
        self._speaking_session = (character, self._session_generation)
        self._speech_has_started = False
        self._speech_stop_event = threading.Event()
        stop_event = self._speech_stop_event
        self.stop_speak_button.setEnabled(True)
        generation = self._session_generation
        reference = weakref.ref(self)

        def progress(completed, total):
            owner = reference()
            if owner is not None:
                owner.speech_progress.emit(character, generation, stop_event, completed, total)

        self._submit(
            partial(speak_interruptible, rate=self.audio_settings.rate(),
                    voice_id=self.audio_settings.voice_id(), on_progress=progress),
            self._speech_completed,
            text, stop_event, on_ready=_weak_ready_callback(
                self, "voice_engine_ready", character, text[:120], stop_event))

    def _speech_completed(self, completed):
        # False is the operation's stop result, not a negative driver callback.
        # A completed engine can also have returned before a queued UI stop.
        if completed is True:
            self._trial_recorder.observe(self._trial_run_id, engine_completed=True)
        stopped = (self._activity_outcome == "cancelled" or self._job_cancel_requested
                   or (self._speech_stop_event is not None
                       and self._speech_stop_event.is_set()))
        finished = completed is True and not stopped
        self._activity_outcome = "completed" if finished else "cancelled"
        self.status.setText("朗读结束" if finished else "朗读已停止")

    def stop_speaking(self):
        voice = self.voice_conversation
        if voice.active and voice.owns_job and not voice.controlling_stop:
            voice.stop()
            return
        if self._speech_stop_event is not None and self._speaking_session is not None:
            self._trial_recorder.request_stop(self._trial_run_id, "user")
            self._speech_stop_event.set()
            self.stop_speak_button.setEnabled(False)
            self._activity_outcome = "cancelled"
            self._activity_phase = "正在停止朗读"
            self._refresh_activity()
            self.status.setText("正在停止本机语音合成…")

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
            workspace = PetWorkspace(approved)
            self._invalidate_assistant_scope("文件夹已切换，旧任务草案已取消。")
            self.workspace = workspace
            self._pending_file_context = None
            if self._action_runtime is not None:
                self._action_runtime.set_workspace(self.workspace)
            self.folder_label.setText("当前文件操作目录：" + str(self.workspace.root))
            self.status.setText("此目录仅在当前窗口会话中获得授权。")
        except (WorkspaceError, OSError) as exc:
            self._job_error(str(exc))

    def reject(self):
        # QDialog's default Escape route hides it without calling closeEvent.
        self.close()

    def closeEvent(self, event):
        if self._trial_dialog is not None:
            self._trial_dialog.close()
        if self._job is not None:
            if not self._closing_after_worker:
                self._invalidate_assistant_scope(
                    "助手正在关闭，旧任务草案已取消。", stop_reason="window_closed")
            self._closing_after_worker = True
            self.stop_listening()
            self.stop_speaking()
            event.ignore()
            return
        self._finish_speech_visuals()
        # QDialog.close() does not necessarily destroy the dialog; release
        # any user-granted folder even when the widget is reopened later.
        self._invalidate_assistant_scope("助手已关闭，未完成任务已取消。")
        self._ppl_snapshot = ""
        self._last_reply = ""
        self._stream_reply_open = False
        self._pending_file_context = None
        self.workspace = PetWorkspace(self._default_workspace)
        if self._action_runtime is not None:
            self._action_runtime.set_workspace(self.workspace)
        self.folder_label.setText("当前文件操作目录：" + str(self.workspace.root))
        # Calling QDialog.closeEvent here would invoke our reject() again.
        QDialog.done(self, QDialog.DialogCode.Rejected)
        event.accept()

    def reset_workspace(self):
        workspace = PetWorkspace(self._default_workspace)
        self._invalidate_assistant_scope("目录授权已撤销，旧任务草案已取消。")
        self.workspace = workspace
        self._pending_file_context = None
        if self._action_runtime is not None:
            self._action_runtime.set_workspace(self.workspace)
        self.folder_label.setText("当前文件操作目录：" + str(self.workspace.root))
        self.status.setText("已回到默认专属文件目录；临时授权已撤销。")

    def attach_workspace_file(self):
        entries = self.workspace.list_files()
        if not entries:
            self._job_error("当前工作区没有可供 AI 分析的文本文件")
            return
        name, ok = QInputDialog.getItem(
            self, "选择文件供 AI 分析", "选择一个 UTF-8 文本文件：", entries, 0, False)
        if not ok:
            return
        result = self._execute_user_approved_action(
            "read_file", {"name": name}, title="确认将文件内容发送给本地 AI")
        if result is None:
            return
        payload = result["result"]
        self._pending_file_context = {"name": payload["name"], "content": payload["content"]}
        self.status.setText(
            "已附加 " + payload["name"] + "（" + str(payload["characters"])
            + " 字符）；仅用于下一轮本地模型请求。")
        self.chat_log.appendPlainText(
            "[已选择文件：" + payload["name"] + "；发送问题后只使用一次]")

    def save_reply_as_note(self):
        if not self._last_reply.strip():
            self._job_error("还没有可保存的 AI 回复")
            return
        name, ok = QInputDialog.getText(
            self, "保存 AI 回复为便签", "便签文件名（.md/.txt）：",
            QLineEdit.EchoMode.Normal, "AI回复便签.md")
        if not ok:
            return
        try:
            validated = self.workspace.validate_name(name)
            if Path(validated).suffix.lower() not in (".md", ".txt"):
                raise WorkspaceError("AI 回复便签只允许 .md 或 .txt 格式")
        except WorkspaceError as exc:
            self._job_error(str(exc))
            return
        result = self._execute_user_approved_action(
            "create_note", {"name": validated, "content": self._last_reply},
            title="确认保存 AI 回复")
        if result is not None:
            self.status.setText("AI 回复已保存为便签：" + result["result"]["path"])
            self._notice("已保存便签：" + result["result"]["name"])

    def _execute_user_approved_action(self, action, arguments, *, title):
        if self._action_runtime is None:
            self._job_error("安全操作中心不可用：" + self._action_runtime_error)
            return None
        try:
            plan = self._action_runtime.prepare(action, arguments)
        except (ActionDenied, WorkspaceError, OSError, ValueError) as exc:
            self._job_error(str(exc))
            return None
        generation = self._session_generation
        answer = QMessageBox.question(
            self, title,
            plan["preview"] + "\n\n此操作需要本次明确授权；授权 60 秒内有效且只能使用一次。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if generation != self._session_generation or self._closing_after_worker:
            self.status.setText("角色、目录或会话已改变，旧操作授权已失效。")
            return None
        try:
            if answer != QMessageBox.StandardButton.Yes:
                self._action_runtime.approve(plan["request_id"], False)
                self.status.setText("已取消操作，未修改文件。")
                return None
            self._action_runtime.approve(plan["request_id"], True)
            return self._action_runtime.execute(plan["request_id"])
        except (ActionDenied, WorkspaceError, OSError, ValueError) as exc:
            self._job_error("安全操作未完成：" + str(exc))
            return None

    def show_action_audit(self):
        if self._action_runtime is None:
            self._job_error("安全操作中心不可用：" + self._action_runtime_error)
            return
        from datetime import datetime
        dialog = QDialog(self)
        dialog.setWindowTitle("桌宠助手 · 安全操作记录")
        dialog.resize(680, 420)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        rows = self._action_runtime.audit_log(limit=100)
        if not rows:
            view.setPlainText("暂无操作记录。")
        else:
            lines = []
            for row in rows:
                stamp = datetime.fromtimestamp(row["created_at"]).strftime("%Y-%m-%d %H:%M:%S")
                lines.append(
                    f'{stamp}  [{row["status"]}]  {row["action"]}\n'
                    f'目标：{row["target"]}\n说明：{row["detail"]}')
            view.setPlainText("\n\n".join(lines))
        layout.addWidget(view)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        self._action_audit_dialog = dialog
        dialog.finished.connect(lambda _: setattr(self, "_action_audit_dialog", None))
        dialog.open()

    def create_file(self):
        name, ok = QInputDialog.getText(
            self, "创建文本文件", "新文件名（支持 .txt/.md/.json/.csv）：")
        if not ok:
            return
        content, ok = QInputDialog.getMultiLineText(
            self, "文件内容", "输入 UTF-8 文本：")
        if not ok:
            return
        result = self._execute_user_approved_action(
            "create_file", {"name": name, "content": content},
            title="确认创建文件")
        if result is not None:
            self.status.setText("已创建：" + result["result"]["path"])
            self._notice("文件已创建：" + result["result"]["name"])

    def delete_file(self):
        entries = self.workspace.list_files()
        if not entries:
            self._job_error("工作区没有可删除的文件")
            return
        name, ok = QInputDialog.getItem(
            self, "选择文件", "删除到桌宠可恢复区：", entries, 0, False)
        if not ok:
            return
        result = self._execute_user_approved_action(
            "trash_file", {"name": name}, title="确认移入可恢复区")
        if result is not None:
            key = result["result"]["trash_key"]
            self.status.setText("文件已移入可恢复区：" + key)
            self._notice("已移入可恢复区：" + name)

    def restore_file(self):
        entries = self.workspace.deleted_files()
        if not entries:
            self._job_error("没有可恢复的文件")
            return
        key, ok = QInputDialog.getItem(
            self, "恢复文件", "选择需要恢复的记录：", entries, 0, False)
        if not ok:
            return
        result = self._execute_user_approved_action(
            "restore_file", {"key": key}, title="确认恢复文件")
        if result is not None:
            self.status.setText("已恢复：" + result["result"]["path"])
            self._notice("文件已恢复：" + result["result"]["name"])
