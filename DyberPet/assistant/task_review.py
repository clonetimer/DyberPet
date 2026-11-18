"""Non-modal review for one explicitly approved file action at a time."""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from .task_plan import TaskSession


_TERMINAL_STATES = {"completed", "cancelled", "failed"}
_ACTION_NAMES = {"create_file": "新建文件", "create_note": "新建便签"}
_STATE_MESSAGES = {
    "ready": "请查看下一步。",
    "awaiting_approval": "请确认当前文件的目标路径和完整内容。",
    "completed": "任务已完成。",
    "cancelled": "已取消剩余步骤。",
    "failed": "任务已停止，请重新生成任务草案。",
}


def _plain_label(text=""):
    label = QLabel()
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    label.setWordWrap(True)
    label.setText(text)
    return label


class TaskReviewDialog(QDialog):
    progress_changed = Signal(object)

    def __init__(self, session: TaskSession, parent=None, *, scope_is_current=None):
        super().__init__(parent)
        self.session = session
        self._scope_is_current = scope_is_current
        self._current = None
        self._busy = False
        self._reason = ""
        self._error = ""

        self.setWindowTitle("审核任务草案")
        self.setModal(False)
        self.resize(680, 480)

        self.title_label = _plain_label(session.plan.title)
        self.workspace_label = _plain_label(str(session.workspace.root))
        self.action_label = _plain_label()
        self.target_label = _plain_label()
        self.status_label = _plain_label()

        self.steps_view = QPlainTextEdit(readOnly=True)
        line_height = self.steps_view.fontMetrics().lineSpacing()
        self.steps_view.setMaximumHeight((len(session.plan.steps) + 1) * line_height + 12)
        self.content_view = QPlainTextEdit(readOnly=True)
        self.escape_content = QCheckBox("显示原始字符的转义形式")
        self.escape_content.toggled.connect(self._render_content)

        self.approve_button = QPushButton("批准并执行此步")
        self.next_button = QPushButton("查看下一步")
        self.cancel_button = QPushButton("取消剩余步骤")
        for button in (self.approve_button, self.next_button, self.cancel_button):
            button.setAutoDefault(False)
        self.approve_button.clicked.connect(self.approve_current)
        self.next_button.clicked.connect(self.show_next_step)
        self.cancel_button.clicked.connect(self._cancel_or_close)

        details = QFormLayout()
        details.addRow("工作区", self.workspace_label)
        details.addRow("当前操作", self.action_label)
        details.addRow("目标路径", self.target_label)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(self.approve_button)
        buttons.addWidget(self.next_button)
        buttons.addWidget(self.cancel_button)
        layout = QVBoxLayout(self)
        layout.addWidget(self.title_label)
        layout.addLayout(details)
        layout.addWidget(self.steps_view)
        layout.addWidget(self.content_view, 1)
        layout.addWidget(self.escape_content)
        layout.addWidget(self.status_label)
        layout.addLayout(buttons)

        self._set_preview(None)
        self._refresh()
        self.show_next_step()
        self.content_view.setFocus()

    def _set_preview(self, preview):
        self._current = preview
        self.action_label.setText(_ACTION_NAMES[preview["action"]] if preview else "")
        self.target_label.setText(preview["target"] if preview else "")
        self.escape_content.setChecked(False)
        self._render_content()
        # Qt normalizes some characters for display, including carriage returns
        # and Unicode paragraph separators. Offer a lossless representation.
        content = preview["content"] if preview else ""
        self.escape_content.setVisible(any(
            not char.isprintable() and char not in "\n\t" for char in content
        ))

    def _render_content(self):
        content = self._current["content"] if self._current else ""
        self.content_view.setPlainText(repr(content) if self.escape_content.isChecked() else content)

    def _refresh(self):
        state = self.session.state
        completed = self.session.completed
        count = len(completed)
        pending = self._current is not None
        rows = []
        for index, step in enumerate(self.session.plan.steps):
            if index < count:
                status = "已完成"
            elif state == "cancelled":
                status = "已取消"
            elif state == "failed":
                status = "失败" if index == count else "未执行"
            elif pending and index == self._current["index"]:
                status = "待审批"
            else:
                status = "待执行"
            rows.append(f"{index + 1}. {step.name}  ·  {status}")
        self.steps_view.setPlainText("\n".join(rows))

        message = self._reason or _STATE_MESSAGES[state]
        error = self.session.error or self._error
        if error:
            message += f"\n{error}"
        for result in completed:
            if result.get("audit_warning"):
                message += f"\n审计警告（{result['result']['name']}） {result['audit_warning']}"
        self.status_label.setText(f"已完成 {count}/{len(rows)} 步。\n{message}")

        self.approve_button.setEnabled(not self._busy and state == "awaiting_approval" and pending)
        self.next_button.setEnabled(not self._busy and state == "ready" and not pending)
        self.cancel_button.setText("关闭" if state in _TERMINAL_STATES else "取消剩余步骤")

    def _check_scope(self):
        if self._scope_is_current is None:
            return True
        try:
            if self._scope_is_current():
                return True
        except Exception as exc:
            self.invalidate(f"无法确认当前会话，任务草案已失效。\n{exc}")
            return False
        self.invalidate("会话或工作区已变更，任务草案已失效。")
        return False

    def show_next_step(self):
        if self._busy or self._current is not None or self.session.state != "ready":
            return
        self._busy = True
        self.next_button.setEnabled(False)
        try:
            if self._check_scope() and self.session.state == "ready":
                self._set_preview(self.session.prepare_next())
        except Exception as exc:
            self._error = str(exc)
        finally:
            self._busy = False
            self._refresh()
        if self.session.state in ("awaiting_approval", "failed"):
            self.progress_changed.emit(self.session)

    def approve_current(self):
        preview = self._current
        if self._busy or preview is None or self.session.state != "awaiting_approval":
            return
        self._busy = True
        self.approve_button.setEnabled(False)
        action_attempted = False
        try:
            if self._check_scope() and self.session.state == "awaiting_approval":
                action_attempted = True
                self.session.decide(preview["request_id"], True)
        except Exception as exc:
            self._error = str(exc)
        finally:
            if action_attempted:
                self._set_preview(None)
            self._busy = False
            self._refresh()
        if action_attempted:
            self.progress_changed.emit(self.session)

    def invalidate(self, reason):
        if self.session.state in _TERMINAL_STATES:
            return
        self._reason = reason
        self.session.cancel()
        self._set_preview(None)
        self._refresh()
        self.progress_changed.emit(self.session)

    def _cancel_or_close(self):
        if self.session.state in _TERMINAL_STATES:
            self.close()
        else:
            self.invalidate(_STATE_MESSAGES["cancelled"])

    def done(self, result):
        self.invalidate("任务草案已关闭，已取消剩余步骤。")
        super().done(result)
