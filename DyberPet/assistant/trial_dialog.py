"""Non-modal local trial controls and explicit, frozen diagnostic exports.

The provider returns TrialRecorder.snapshot(). This view never starts a model,
audio device or parent task: the owner connects its request signals instead.
"""
import json
import math

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFileDialog, QFrame, QGridLayout, QGroupBox,
    QHBoxLayout, QLabel, QPlainTextEdit, QPushButton, QScrollArea,
    QSizePolicy, QVBoxLayout, QWidget,
)


_PROBE_CHAR_LIMIT = 4000
_REPORT_BYTE_LIMIT = 64 * 1024
_KIND_LABELS = {
    "chat": "普通聊天", "model_probe": "模型试聊", "plan": "任务规划",
    "listen": "连续监听", "speech": "朗读", "models": "检查可用模型",
    "voice_check": "检查语音配置", "other": "其他操作",
}
_OUTCOME_LABELS = {
    "running": "进行中", "completed": "程序已完成", "cancelled": "已停止",
    "failed": "失败", "interrupted": "意外中断",
}
_STOP_LABELS = {
    "user": "用户停止", "scope_changed": "角色或工作范围已切换",
    "window_closed": "主助手窗口已关闭", "configuration_changed": "配置已更改",
}
_ERROR_LABELS = {
    "invalid_endpoint": "服务地址配置不可用，请检查对应服务的地址设置。",
    "connection": "连接失败，请检查本机服务是否正在运行。",
    "timeout": "等待服务超时，可以停止后重试。",
    "http": "服务返回失败状态，请检查服务运行情况。",
    "redirect": "服务地址发生重定向，请检查对应服务配置。",
    "response": "服务返回的内容无法读取。",
    "no_models": "没有找到可用模型，请先在模型服务中加载模型。",
    "service": "所需服务暂时不可用。",
    "voice_unavailable": "语音设备、识别模型或朗读驱动暂时不可用。",
    "internal_error": "操作失败，请检查设置后重试。",
    "invalid_result": "没有得到可用的结果。",
}
_FEEDBACK_FIELDS = (
    ("model_reply", "模型回复"),
    ("recognition", "识别文字"),
    ("speech", "是否听到朗读"),
)
_FEEDBACK_OPTIONS = (
    ("not_checked", "未检查"), ("satisfied", "符合预期"), ("problem", "发现问题"),
)


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def _duration(value, missing="未记录"):
    value = _number(value)
    if value is None:
        return missing
    if value < 1000:
        return f"{value:.0f} 毫秒"
    return f"{value / 1000:.2f} 秒"


def _observation_text(observation):
    kind = _KIND_LABELS.get(observation.get("kind"), "其他操作")
    outcome = observation.get("outcome")
    result = _OUTCOME_LABELS.get(outcome, "状态未知")
    reason = _STOP_LABELS.get(observation.get("stop_reason"))
    if reason:
        result += f"（{reason}）"
    number = _number(observation.get("id"))
    prefix = f"#{int(number)} · " if number is not None else ""
    lines = [prefix + kind + " · " + result + " · 用时 "
             + _duration(observation.get("elapsed_ms"))]
    timing = ["就绪：" + _duration(observation.get("ready_ms"), "未观察到就绪"),
              "首段文字：" + _duration(observation.get("first_text_ms"), "未观察到")]
    if observation.get("stop_requested_ms") is not None:
        timing.append("请求停止：" + _duration(observation.get("stop_requested_ms")))
        timing.append("停止等待：" + _duration(observation.get("stop_settled_ms"), "尚未结束"))
    lines.append("；".join(timing))

    details = []
    displayed = _number(observation.get("displayed_chars"))
    if displayed is not None:
        details.append(f"已显示 {int(displayed)} 字")
    chars = _number(observation.get("result_chars"))
    if chars is not None:
        details.append(f"返回文字 {int(chars)} 字")
        if observation.get("kind") == "listen" and chars > 0 and outcome == "cancelled":
            details.append("停止后仍得到识别文字，请在主助手输入框检查")
    count = _number(observation.get("model_count"))
    if count is not None:
        details.append(f"找到 {int(count)} 个模型")
    for field, label in (("recognition_ready", "识别配置"), ("tts_ready", "朗读配置")):
        value = observation.get(field)
        if isinstance(value, bool):
            details.append(label + ("初检通过" if value else "初检未通过"))
    completed = observation.get("engine_completed")
    if completed is True:
        details.append("朗读驱动报告完成；是否实际听到请人工核对")
    elif completed is False:
        details.append("朗读驱动未报告完成")
    if details:
        lines.append("；".join(details))
    error = observation.get("error_code")
    if error is not None:
        lines.append("提示：" + _ERROR_LABELS.get(error, _ERROR_LABELS["internal_error"]))

    percent = _number(observation.get("cpu_percent_one_core"))
    cpu = _number(observation.get("cpu_seconds"))
    rss = _number(observation.get("rss_max_bytes"))
    samples = _number(observation.get("sample_count"))
    resources = ["CPU " + (f"{percent:.1f}%" if percent is not None else "未采样"),
                 "CPU 时间 " + (f"{cpu:.3f} 秒" if cpu is not None else "未采样"),
                 "内存采样最大值 " + (f"{rss / (1024 * 1024):.1f} MiB"
                                    if rss is not None else "未采样")]
    if samples is not None:
        resources.append(f"采样 {int(samples)} 次")
    lines.append("；".join(resources))
    return "\n".join(lines)


class TrialDialog(QDialog):
    """Display bounded observations while keeping task ownership in the caller."""

    model_test_requested = Signal()
    speech_test_requested = Signal()
    listen_requested = Signal()
    stop_requested = Signal()
    clear_requested = Signal()
    feedback_changed = Signal(str, str)

    def __init__(self, provider, parent=None):
        super().__init__(parent)
        self._provider = provider
        self._frozen_report = None
        self._provider_failed = False
        self.setWindowTitle("DyberPet · 试用与诊断")
        self.setModal(False)
        self.setMinimumSize(360, 280)
        self.setSizeGripEnabled(True)
        available = self.screen().availableGeometry()
        self.resize(min(720, max(360, available.width() - 48)),
                    min(760, max(280, available.height() - 48)))

        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 14, 14, 12)
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget(self.scroll_area)
        content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(2, 2, 8, 8)
        layout.setSpacing(12)
        self.scroll_area.setWidget(content)
        outer.addWidget(self.scroll_area)

        heading = self._label("试用当前配置，看看实际效果", content)
        font = heading.font()
        font.setBold(True)
        font.setPointSize(font.pointSize() + 2)
        heading.setFont(font)
        layout.addWidget(heading)
        layout.addWidget(self._label(
            "打开本窗口不会启动模型或音频。选择下方操作开始试用，"
            "再按实际看到、听到的结果填写反馈。", content))

        actions = QGroupBox("本机试用", content)
        action_layout = QGridLayout(actions)
        self.model_test_button = self._button("试聊当前模型", actions)
        self.speech_test_button = self._button("试听示例", actions)
        self.listen_button = self._button("开始连续监听", actions)
        self.stop_button = self._button("停止当前操作", actions)
        self.model_test_button.clicked.connect(lambda: self.model_test_requested.emit())
        self.speech_test_button.clicked.connect(lambda: self.speech_test_requested.emit())
        self.listen_button.clicked.connect(lambda: self.listen_requested.emit())
        self.stop_button.clicked.connect(lambda: self.stop_requested.emit())
        action_layout.addWidget(self.model_test_button, 0, 0)
        action_layout.addWidget(self.speech_test_button, 0, 1)
        action_layout.addWidget(self.listen_button, 1, 0)
        action_layout.addWidget(self.stop_button, 1, 1)
        action_layout.setColumnStretch(0, 1)
        action_layout.setColumnStretch(1, 1)
        self.activity_label = self._label("", actions)
        action_layout.addWidget(self.activity_label, 2, 0, 1, 2)
        action_layout.addWidget(self._label(
            "识别文字会回到主助手输入框，检查后再发送。"
            "关闭本窗口不会停止正在执行的操作。", actions), 3, 0, 1, 2)
        layout.addWidget(actions)

        probe = QGroupBox("模型试聊回复", content)
        probe_layout = QVBoxLayout(probe)
        self.probe_preview = self._text_view(probe, 100, 150)
        self.probe_preview.setPlaceholderText("点击“试聊当前模型”后，在这里查看回复。")
        probe_layout.addWidget(self.probe_preview)
        probe_layout.addWidget(self._label(
            "仅在本窗口显示前 4000 字符，不进入聊天历史或诊断报告。", probe))
        layout.addWidget(probe)

        observations = QGroupBox("最近操作 · 最多 30 条", content)
        observations_layout = QVBoxLayout(observations)
        self.observations_view = self._text_view(observations, 170, 220)
        self.observations_view.setPlaceholderText("还没有运行记录。可以先试聊、试听或开始监听。")
        observations_layout.addWidget(self.observations_view)
        self.resource_note = self._label(
            "CPU 只统计桌宠进程，不包括独立模型服务；100% 表示一个逻辑核心，"
            "可以超过 100%。内存为采样最大值，可能漏过瞬时峰值。"
            "GPU、画面帧率和长期稳定性未测量。", observations)
        observations_layout.addWidget(self.resource_note)
        self.clear_button = self._button("清空观察记录", observations)
        self.clear_button.clicked.connect(self._request_clear)
        observations_layout.addWidget(self.clear_button, 0, Qt.AlignmentFlag.AlignRight)
        layout.addWidget(observations)

        feedback = QGroupBox("人工反馈", content)
        feedback_layout = QGridLayout(feedback)
        feedback_layout.addWidget(self._label(
            "程序完成不代表效果符合预期；请亲自检查后选择。", feedback), 0, 0, 1, 2)
        self.feedback_combos = {}
        for row, (key, label) in enumerate(_FEEDBACK_FIELDS, 1):
            combo = QComboBox(feedback)
            combo.setAccessibleName(label)
            for value, caption in _FEEDBACK_OPTIONS:
                combo.addItem(caption, value)
            combo.currentIndexChanged.connect(
                lambda _index, field=key, control=combo:
                self.feedback_changed.emit(field, control.currentData()))
            feedback_layout.addWidget(self._label(label, feedback), row, 0)
            feedback_layout.addWidget(combo, row, 1)
            self.feedback_combos[key] = combo
        feedback_layout.setColumnStretch(1, 1)
        layout.addWidget(feedback)

        report = QGroupBox("诊断报告", content)
        report_layout = QVBoxLayout(report)
        report_layout.addWidget(self._label(
            "报告只包含运行环境、操作状态、时序、资源采样和人工反馈；"
            "不包含提示词、回复或识别文字。记录默认只保存在内存中。", report))
        report_actions = QHBoxLayout()
        self.preview_report_button = self._button("预览报告", report)
        self.preview_report_button.clicked.connect(self.preview_report)
        self.export_button = self._button("保存预览报告…", report)
        self.export_button.setEnabled(False)
        self.export_button.setToolTip("先预览报告，再选择一个新文件名保存。")
        self.export_button.clicked.connect(self.export_preview)
        report_actions.addWidget(self.preview_report_button)
        report_actions.addWidget(self.export_button)
        report_layout.addLayout(report_actions)
        self.report_section = QWidget(report)
        preview_layout = QVBoxLayout(self.report_section)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.addWidget(self._label(
            "以下快照已经固定，后台刷新不会改变它。"
            "需要最新内容时，请点击“更新报告预览”。", self.report_section))
        self.report_preview = self._text_view(self.report_section, 180, 270)
        self.report_preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        preview_layout.addWidget(self.report_preview)
        self.report_section.hide()
        report_layout.addWidget(self.report_section)
        layout.addWidget(report)
        layout.addStretch(1)

        self.status_label = self._label("", self)
        outer.addWidget(self.status_label)
        footer = QHBoxLayout()
        footer.addStretch(1)
        self.close_button = self._button("关闭", self)
        self.close_button.clicked.connect(self.close)
        footer.addWidget(self.close_button)
        outer.addLayout(footer)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.setInterval(1000)
        self.refresh_timer.timeout.connect(self.refresh_report)
        self.set_busy(False)

    @staticmethod
    def _label(text, parent):
        label = QLabel(text, parent)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.setWordWrap(True)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    @staticmethod
    def _button(text, parent):
        button = QPushButton(text, parent)
        button.setAutoDefault(False)
        button.setMinimumHeight(30)
        return button

    @staticmethod
    def _text_view(parent, minimum, maximum):
        view = QPlainTextEdit(parent)
        view.setReadOnly(True)
        view.setMinimumHeight(minimum)
        view.setMaximumHeight(maximum)
        return view

    def set_busy(self, busy, can_stop=False):
        for button in (self.model_test_button, self.speech_test_button, self.listen_button):
            button.setEnabled(not busy)
        self.clear_button.setEnabled(not busy)
        self.stop_button.setEnabled(bool(busy and can_stop))
        self.activity_label.setText(
            "操作进行中，可以在这里停止。" if busy and can_stop else
            "正在等待当前操作结束。" if busy else "准备好后，选择一项开始试用。")

    def set_probe_text(self, text):
        text = text[:_PROBE_CHAR_LIMIT] if isinstance(text, str) else ""
        if self.probe_preview.toPlainText() != text:
            scrollbar = self.probe_preview.verticalScrollBar()
            following = scrollbar.value() == scrollbar.maximum()
            previous = scrollbar.value()
            self.probe_preview.setPlainText(text)
            scrollbar.setValue(scrollbar.maximum() if following else previous)

    def clear_probe(self):
        self.probe_preview.clear()

    def _snapshot(self):
        report = self._provider()
        if not isinstance(report, dict) or report.get("schema_version") != 1:
            raise ValueError("Unsupported diagnostic snapshot")
        if not isinstance(report.get("observations"), list):
            raise ValueError("Invalid observation collection")
        if not isinstance(report.get("feedback"), dict):
            raise ValueError("Invalid feedback collection")
        return report

    def refresh_report(self):
        """Refresh visible summaries without changing an explicitly reviewed report."""
        if not self.isVisible():
            return
        try:
            report = self._snapshot()
            observations = [entry for entry in report["observations"][-30:]
                            if isinstance(entry, dict)]
            summary = "\n\n".join(_observation_text(entry) for entry in reversed(observations))
            if self.observations_view.toPlainText() != summary:
                scrollbar = self.observations_view.verticalScrollBar()
                previous = scrollbar.value()
                self.observations_view.setPlainText(summary)
                scrollbar.setValue(previous)
            for key, combo in self.feedback_combos.items():
                index = combo.findData(report["feedback"].get(key, "not_checked"))
                blocker = QSignalBlocker(combo)
                combo.setCurrentIndex(max(0, index))
                del blocker
        except Exception:
            self._provider_failed = True
            self.status_label.setText("暂时无法读取运行观察，当前操作不受影响。")
            return
        if self._provider_failed:
            self.status_label.setText("运行观察已恢复更新。")
            self._provider_failed = False

    def _forget_preview(self):
        self._frozen_report = None
        self.report_preview.clear()
        self.report_section.hide()
        self.export_button.setEnabled(False)
        self.preview_report_button.setText("预览报告")

    def preview_report(self):
        """Freeze one bounded snapshot; no file is written during preview."""
        self._forget_preview()
        try:
            encoded = json.dumps(self._snapshot(), ensure_ascii=False, allow_nan=False,
                                 indent=2)
            if len(encoded.encode("utf-8")) > _REPORT_BYTE_LIMIT:
                raise ValueError("Diagnostic report exceeds size limit")
            frozen = json.loads(encoded)
        except Exception:
            self.status_label.setText("报告预览不可用或超过 64 KiB，请清空记录后重试。")
            return
        self._frozen_report = frozen
        self.report_preview.setPlainText(encoded)
        self.report_section.show()
        self.export_button.setEnabled(True)
        self.preview_report_button.setText("更新报告预览")
        self.status_label.setText("报告已预览。保存时会使用此快照，并拒绝覆盖已有文件。")

    def export_preview(self):
        """Save only the reviewed snapshot, with export failures local to this view."""
        if self._frozen_report is None:
            self.preview_report()
        if self._frozen_report is None:
            return
        path, _selected_filter = QFileDialog.getSaveFileName(
            self, "保存诊断报告", "DyberPet-诊断报告.json", "JSON 报告 (*.json)",
            options=QFileDialog.Option.DontConfirmOverwrite)
        if not path:
            return
        try:
            from .trial_records import export_report
            export_report(path, self._frozen_report)
        except FileExistsError:
            self.status_label.setText("未覆盖已有文件，请使用新文件名保存。")
        except Exception:
            self.status_label.setText("报告保存失败，请检查文件夹和写入权限后重试。")
        else:
            self.status_label.setText("报告已保存，内容与当前预览一致。")

    def _request_clear(self):
        self._forget_preview()
        self.status_label.clear()
        self.clear_requested.emit()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh_report()
        self.refresh_timer.start()

    def hideEvent(self, event):
        self.refresh_timer.stop()
        super().hideEvent(event)

    def closeEvent(self, event):
        self.refresh_timer.stop()
        super().closeEvent(event)
