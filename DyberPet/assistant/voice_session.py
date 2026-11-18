"""User-started, turn-taking speech on the assistant's existing single worker."""
from __future__ import annotations

import threading
import weakref

from PySide6.QtCore import QObject, QTimer

from .voice_readiness import inspect_voice_readiness
from .voice_turn import VoiceTurnRecognizer


class VoiceConversation(QObject):
    """Queue the next stage only after the old worker has been released.

    The owner remains responsible for HTTP, history, TTS and operation records.
    This object holds no strong Python reference back to its parent widget.
    """

    def __init__(self, owner):
        super().__init__(owner)
        self._owner = weakref.ref(owner)
        self.active = False
        self.owns_job = False
        self.controlling_stop = False
        self.dispatching = False
        self._epoch = 0
        self._scope = None
        self._recognizer = None
        self._stage = None
        self._pending = None
        self._queued = None
        self._restart_requested = False
        self._turns = 0
        self._advance_timer = QTimer(self)
        self._advance_timer.setSingleShot(True)
        self._advance_timer.timeout.connect(self._advance)
        self._limit_timer = QTimer(self)
        self._limit_timer.setSingleShot(True)
        self._limit_timer.timeout.connect(self._time_limit)

    @staticmethod
    def _configuration(owner):
        return (owner.character_name, owner._session_generation,
                owner.persona.currentData(), owner.llm_endpoint.text(),
                owner.llm_model.text(), owner.voice_model.text(),
                owner.ppl_enabled.isChecked(), owner.ppl_endpoint.text(),
                owner._ppl_snapshot)

    def _current(self, epoch=None):
        owner = self._owner()
        return bool(owner is not None and self.active
                    and (epoch is None or epoch == self._epoch)
                    and not owner._closing_after_worker and owner.isVisible()
                    and self._scope == self._configuration(owner))

    def _notice(self, message):
        owner = self._owner()
        if owner is not None:
            owner.voice_chat_status.setText(message)

    def sync_controls(self):
        owner = self._owner()
        if owner is None:
            return
        owner.voice_chat_button.setEnabled(
            not self.active and owner._job is None and not owner._closing_after_worker)
        owner.voice_end_button.setEnabled(self.active)
        owner.voice_interrupt_button.setEnabled(self.active and not self._restart_requested)
        busy = self.active or owner._job is not None or owner._closing_after_worker
        for button in (owner.send_button, owner.plan_button, owner.listen_button,
                       owner.speak_button, owner.ppl_button, owner.detect_button,
                       owner.voice_check_button):
            button.setEnabled(not busy)
        owner._sync_trial_window()

    def start(self):
        owner = self._owner()
        if owner is None or self.active:
            return
        if owner._job is not None or owner._closing_after_worker:
            self._notice("请先结束当前操作，再开始语音对话。")
            return
        if not owner.isVisible():
            return
        if not owner._chat_configuration_ready():
            self._notice(owner.status.text())
            return
        ready = inspect_voice_readiness(owner.voice_model.text().strip())
        if not ready.recognition_ready or not ready.tts_ready:
            self._notice("语音对话尚未就绪：" + (
                ready.recognition_message if not ready.recognition_ready else ready.tts_message))
            return
        self._epoch += 1
        self._scope = self._configuration(owner)
        self._recognizer = VoiceTurnRecognizer(owner.voice_model.text().strip())
        self.active = True
        self._turns = 0
        self._restart_requested = False
        self._pending = None
        self._limit_timer.start(10 * 60 * 1000)
        self._queue("listen")
        self.sync_controls()

    def configuration_changed(self, *_args):
        if self.active:
            self.stop("设置已改变，语音对话已结束；重新开启后使用新设置。",
                      stop_reason="configuration_changed")

    def stop(self, message="语音对话已结束；麦克风关闭后可重新开启。", *,
             stop_reason="user", cancel_job=True):
        if not self.active and not self.owns_job:
            return
        self.active = False
        self._epoch += 1
        self._advance_timer.stop()
        self._limit_timer.stop()
        self._pending = self._queued = None
        self._restart_requested = False
        self._recognizer = None
        self._notice(message)
        owner = self._owner()
        if cancel_job and self.owns_job:
            self._cancel_worker(stop_reason)
        if owner is not None:
            owner._set_interaction_phase("stopping" if self.owns_job else "idle")
        self.sync_controls()

    def interrupt(self):
        if not self._current() or self._restart_requested:
            return
        self._epoch += 1
        self._advance_timer.stop()
        self._pending = self._queued = None
        self._restart_requested = True
        self._notice("正在打断本轮；旧任务结束后继续听。")
        owner = self._owner()
        owner._set_interaction_phase("stopping")
        if self.owns_job:
            self._cancel_worker("user")
        else:
            self._restart_requested = False
            self._queue("listen")
        self.sync_controls()

    def _cancel_worker(self, reason):
        owner = self._owner()
        if owner is None or owner._job is None:
            return
        # A consumed successful result needs no retroactive cancellation; its
        # successor has already been revoked by stop/interrupt above.
        if owner._activity_outcome in ("completed", "failed"):
            for event in (owner._listen_stop_event, owner._speech_stop_event):
                if event is not None:
                    event.set()
            return
        self.controlling_stop = True
        try:
            if owner._request_token is not None:
                owner.stop_generation(reason=reason)
            elif owner._listen_stop_event is not None:
                owner.stop_listening()
            elif owner._speech_stop_event is not None:
                owner.stop_speaking()
            owner._job_cancel_requested = True
            owner._trial_recorder.request_stop(owner._trial_run_id, reason)
        finally:
            self.controlling_stop = False

    def _queue(self, stage, payload=None):
        self._queued = (self._epoch, stage, payload)
        self._advance_timer.start(0)

    def _advance(self):
        queued, self._queued = self._queued, None
        if queued is None:
            return
        epoch, stage, payload = queued
        if not self._current(epoch):
            if self.active:
                self.stop("会话已变更，语音对话已结束。")
            return
        owner = self._owner()
        if owner._job is not None:
            self.stop("另一项操作已开始，语音对话已结束。", cancel_job=False)
            return
        self._stage = stage
        self._pending = None
        self.owns_job = True
        self.dispatching = True
        try:
            if stage == "listen":
                self._listen(owner, epoch)
            elif stage == "chat":
                self._notice("正在思考你的话…")
                owner._send_chat(payload, voice_turn=True,
                                 on_reply=lambda result: self._chat_ready(epoch, result))
            elif stage == "speech":
                self._notice("正在准备朗读…")
                owner._start_speech(payload)
        finally:
            self.dispatching = False
        if owner._job is None:
            self.owns_job = False
            self.stop("语音对话未能继续：" + owner.status.text(), cancel_job=False)
        self.sync_controls()

    def _listen(self, owner, epoch):
        stop = threading.Event()
        owner._listen_stop_event = stop
        owner._listening = True
        owner._begin_activity("listen")
        owner.stop_listen_button.setEnabled(True)
        self._notice("正在准备麦克风…")
        character, generation = owner.character_name, owner._session_generation
        reference = self._owner
        recognizer = self._recognizer

        def ready():
            current = reference()
            if current is not None:
                current.microphone_ready.emit(character, generation, stop)

        def task(on_delta):
            return recognizer.listen(stop, on_partial=on_delta, on_ready=ready,
                                     max_seconds=30.0)

        owner._submit(task, lambda text: self._heard(epoch, text), stream=True,
                      on_progress=lambda text: self._partial(epoch, text))

    def _partial(self, epoch, text):
        if self._current(epoch) and not self._restart_requested and isinstance(text, str):
            self._notice("正在听：" + text[:100])

    def microphone_ready(self):
        if self._current() and self.owns_job and self._stage == "listen":
            self._notice("正在听，请说一句话；说完后会自动回复。")

    def speech_ready(self):
        if self._current() and self.owns_job and self._stage == "speech":
            self._notice("正在朗读；可以打断并继续说。")

    def _heard(self, epoch, text):
        if not self._current(epoch) or self._restart_requested:
            return
        owner = self._owner()
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            self.stop("未听到有效的一句话，语音对话已结束；可重新开启。", cancel_job=False)
            return
        owner._trial_recorder.observe(owner._trial_run_id, result_chars=len(text))
        self._pending = ("chat", text.strip())

    def _chat_ready(self, epoch, result):
        if not self._current(epoch) or self._restart_requested:
            return
        owner = self._owner()
        if (not isinstance(result, tuple) or len(result) != 5
                or result[0] != owner.character_name or result[1] != owner._session_generation
                or not isinstance(result[3], str) or not result[3].strip()):
            self.stop("本轮没有得到有效回复，语音对话已结束。", cancel_job=False)
            return
        owner._message_reply(result, voice_turn=True)
        self._pending = ("speech", result[3])

    def failed(self, detail):
        if self.owns_job and self.active:
            self.stop("语音对话已结束：" + detail, cancel_job=False)

    def job_finished(self, outcome):
        if not self.owns_job:
            self.sync_controls()
            return
        stage = self._stage
        self.owns_job = False
        self._stage = None
        if not self.active:
            self.sync_controls()
            return
        if not self._current():
            self.stop("会话已变更，语音对话已结束。", cancel_job=False)
        elif self._restart_requested:
            self._restart_requested = False
            self._queue("listen")
        elif outcome != "completed":
            self.stop("本轮已停止，语音对话结束。", cancel_job=False)
        elif stage == "speech":
            self._turns += 1
            if self._turns >= 20:
                self.stop("已完成 20 轮语音对话；需要继续时可重新开启。", cancel_job=False)
            else:
                self._queue("listen")
        elif self._pending is not None:
            next_stage, payload = self._pending
            self._pending = None
            self._queue(next_stage, payload)
        else:
            self.stop("本轮没有可继续的内容，语音对话已结束。", cancel_job=False)
        self.sync_controls()

    def _time_limit(self):
        if self.active:
            self.stop("本次语音对话已达到 10 分钟；需要继续时可重新开启。")
