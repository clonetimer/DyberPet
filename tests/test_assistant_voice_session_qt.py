"""Real Qt workers and HTTP turns, with only physical audio replaced."""
import json
import os
import queue
import tempfile
import threading
import time
import sys
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None

from DyberPet.assistant.voice import VoiceUnavailable
from DyberPet.assistant.voice_readiness import VoiceReadiness


class AudioBoundary:
    def __init__(self):
        self.inputs = queue.Queue()
        self.listen_count = 0
        self.model_count = 0
        self.speeches = []
        self.events = []
        self.active = 0
        self.overlap = False
        self.lock = threading.Lock()
        self.hold_speech = threading.Event()
        self.hold_speech.set()
        self.fail_speech = False
        self.listen_stop_returns_text = False
        self.partials = []
        self.microphones = []
        self.speech_settings = []

    def enter(self, kind):
        with self.lock:
            self.overlap |= self.active != 0
            self.active += 1
            self.events.append(kind + ":open")

    def leave(self, kind):
        with self.lock:
            self.events.append(kind + ":closed")
            self.active -= 1

    def recognizer(self, model_dir):
        self.model_count += 1
        driver = self

        class Recognizer:
            def listen(self, stop_event, *, on_partial=None, on_ready=None, **kwargs):
                driver.microphones.append(kwargs.get("microphone"))
                driver.listen_count += 1
                driver.enter("microphone")
                try:
                    if on_ready:
                        on_ready()
                    while not stop_event.is_set():
                        try:
                            value = driver.inputs.get(timeout=0.02)
                        except queue.Empty:
                            continue
                        if isinstance(value, Exception):
                            raise value
                        if isinstance(value, tuple):
                            on_partial(value[1])
                            driver.partials.append(value[1])
                            continue
                        return value
                    return "不应发送的迟到识别" if driver.listen_stop_returns_text else ""
                finally:
                    driver.leave("microphone")

        return Recognizer()

    def speak(self, text, stop_event, *, on_ready=None, **kwargs):
        self.speeches.append(text)
        self.speech_settings.append((kwargs.get("voice_id"), kwargs.get("rate")))
        self.enter("speaker")
        try:
            if self.fail_speech:
                raise VoiceUnavailable("测试声音驱动不可用")
            if on_ready:
                on_ready()
            while not stop_event.is_set() and not self.hold_speech.wait(0.02):
                pass
            return not stop_event.is_set()
        finally:
            self.leave("speaker")


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt CI")
class VoiceConversationQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        from DyberPet.assistant.preferences import defaults

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        with patch("DyberPet.assistant.ui.load_preferences", new=defaults):
            self.dialog = PetAssistantDialog(
                "咕嘎", self.root / "files", store_path=self.root / "history.sqlite3")
        self.addCleanup(self.dispose_dialog)
        self.assertTrue(hasattr(self.dialog, "voice_chat_button"),
                        "The assistant needs explicit voice-conversation controls")
        self.audio = AudioBoundary()
        self.requests = []
        self.reply_gate = threading.Event()
        self.reply_gate.set()
        self.partial_sent = threading.Event()
        self.empty_reply = False
        self.reply_override = None
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                owner.requests.append(body)
                reply = (owner.reply_override if owner.reply_override is not None else
                         "" if owner.empty_reply else "本地回复" + str(len(owner.requests)))
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                try:
                    part = {"choices": [{"delta": {"content": reply}}]}
                    self.wfile.write(("data: " + json.dumps(part, ensure_ascii=False)
                                      + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                    owner.partial_sent.set()
                    # Deliberately held replies stay held until the test or
                    # unconditional server cleanup releases them.
                    owner.reply_gate.wait()
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass

            def log_message(self, *_args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server_thread = threading.Thread(
            target=lambda: self.server.serve_forever(poll_interval=0.01), daemon=True)
        self.server_thread.start()
        self.addCleanup(self.shutdown_server)
        self.dialog.llm_endpoint.setText("http://127.0.0.1:" + str(self.server.server_port))
        self.dialog.llm_model.setText("voice-contract")
        self.dialog.voice_model.setText(str(self.root / "vosk-model"))
        ready = VoiceReadiness(True, "识别初检通过", True, "朗读初检通过")
        for target, replacement in (
                ("DyberPet.assistant.voice_session.VoiceTurnRecognizer", self.audio.recognizer),
                ("DyberPet.assistant.voice_session.inspect_voice_readiness", lambda _path: ready),
                ("DyberPet.assistant.ui.speak_interruptible", self.audio.speak)):
            patcher = patch(target, new=replacement)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.dialog.show()
        self.app.processEvents()

    def shutdown_server(self):
        self.reply_gate.set()
        self.server.shutdown()
        self.server.server_close()
        self.server_thread.join(2)

    def dispose_dialog(self):
        if hasattr(self, "audio"):
            self.audio.hold_speech.set()
            self.reply_gate.set()
        self.dialog.close()
        if self.dialog._job is not None:
            self.assertTrue(self.dialog._job.wait(3000))
            self.app.processEvents()
        self.dialog.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def wait_for(self, predicate, *, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            # qWait can hold the GIL in these Qt bindings. Python HTTP
            # and audio workers need a real scheduling opportunity as well.
            time.sleep(0.005)
        self.app.processEvents()
        self.assertTrue(predicate(), "Voice turn did not reach the expected state: "
                        + repr(self.operation_state()))

    def operation_state(self):
        job = self.dialog._job
        return {"kind": self.dialog._activity_kind,
                "outcome": self.dialog._activity_outcome,
                "worker_running": job.isRunning() if job is not None else False,
                "voice_active": self.dialog.voice_conversation.active,
                "phase": self.dialog.voice_chat_status.text(),
                "listen_count": self.audio.listen_count,
                "speech_count": len(self.audio.speeches),
                "request_count": len(self.requests)}

    def pump_events(self, milliseconds):
        deadline = time.monotonic() + milliseconds / 1000
        while time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.app.processEvents()

    def start(self):
        previous = self.audio.listen_count
        self.dialog.voice_chat_button.click()
        self.wait_for(lambda: self.audio.listen_count == previous + 1)
        self.wait_for(lambda: "正在听" in self.dialog.voice_chat_status.text())

    def end(self):
        self.dialog.voice_end_button.click()
        self.wait_for(lambda: self.dialog._job is None)
        self.assertFalse(self.dialog.voice_conversation.active)

    def test_two_turns_reuse_context_preserve_draft_and_attachment_and_never_overlap(self):
        phases = []
        self.dialog.interaction_changed.connect(
            lambda character, phase: phases.append((character, phase)))
        draft = "尚未发送的键盘草稿"
        attachment = {"name": "private.md", "content": "未授权给语音的附件内容"}
        self.dialog.message.setText(draft)
        self.dialog._pending_file_context = attachment.copy()
        self.dialog.auto_speak.setChecked(True)
        self.dialog._conversation_store.append_turn("咕嘎", "以前的问题", "以前的回复")
        self.start()
        self.audio.inputs.put("第一句")
        self.wait_for(lambda: self.audio.listen_count == 2)
        self.audio.inputs.put("第二句")
        self.wait_for(lambda: self.audio.listen_count == 3)
        self.wait_for(lambda: phases.count(("咕嘎", "listening")) == 3)
        # Give the existing 100 ms automatic-read window time to run too.
        self.pump_events(130)
        self.end()

        self.assertEqual(self.audio.speeches, ["本地回复1", "本地回复2"])
        self.assertEqual(self.audio.model_count, 1)
        self.assertFalse(self.audio.overlap)
        self.assertEqual(self.audio.active, 0)
        self.assertEqual(self.dialog.message.text(), draft)
        self.assertEqual(self.dialog._pending_file_context, attachment)
        self.assertEqual(len(self.requests), 2)
        self.assertIn("以前的回复", json.dumps(self.requests[0], ensure_ascii=False))
        self.assertIn("本地回复1", json.dumps(self.requests[1], ensure_ascii=False))
        self.assertNotIn("未授权给语音", json.dumps(self.requests, ensure_ascii=False))
        history = self.dialog._conversation_store.recent_messages("咕嘎", limit=12)
        self.assertEqual([item["content"] for item in history],
                         ["以前的问题", "以前的回复", "第一句", "本地回复1", "第二句", "本地回复2"])
        self.assertEqual(self.dialog.workspace.list_files(), [])
        self.assertEqual([phase for character, phase in phases
                          if character == "咕嘎" and phase not in ("idle", "stopping")],
                         ["listening", "thinking", "speaking",
                          "listening", "thinking", "speaking", "listening"])
        self.assertEqual(phases[-1], ("咕嘎", "idle"))

    def test_partial_recognition_never_sends_or_replaces_keyboard_draft(self):
        self.dialog.message.setText("保留草稿")
        self.start()
        self.audio.inputs.put(("partial", "还没说完"))
        self.wait_for(lambda: "还没说完" in self.dialog.voice_chat_status.text())
        self.assertEqual(self.requests, [])
        self.assertEqual(self.dialog.message.text(), "保留草稿")
        self.end()

    def test_voice_controls_remain_visible_when_scrolling_to_read_replies(self):
        self.dialog.resize(800, 600)
        self.start()
        scroll = self.dialog.content_scroll.verticalScrollBar()
        self.assertGreater(scroll.maximum(), 0)
        scroll.setValue(scroll.maximum())
        self.app.processEvents()
        for control in (self.dialog.voice_chat_button, self.dialog.voice_interrupt_button,
                        self.dialog.voice_end_button, self.dialog.voice_chat_status):
            rect = QRect(control.mapTo(self.dialog, QPoint()), control.size())
            self.assertTrue(self.dialog.rect().contains(rect), control.text())
        self.end()

    def test_stop_wins_over_already_queued_recognition_success(self):
        self.start()
        job = self.dialog._job
        self.audio.inputs.put("排队但不能发送")
        self.assertTrue(job.wait(1000))
        self.dialog.voice_end_button.click()
        self.wait_for(lambda: self.dialog._job is None)
        self.pump_events(30)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.audio.listen_count, 1)
        self.assertFalse(self.dialog.voice_conversation.active)

    def test_end_between_finished_and_next_stage_prevents_queued_model_request(self):
        self.dialog.show_trial_dialog()
        self.start()
        self.dialog._job.finished.connect(self.dialog.end_voice_conversation)
        self.audio.inputs.put("完成监听后马上结束")
        self.wait_for(lambda: self.dialog._job is None)
        self.pump_events(30)
        self.assertEqual(self.requests, [])
        self.assertFalse(self.dialog.voice_conversation.active)
        for button in (self.dialog.send_button, self.dialog.plan_button,
                       self.dialog.listen_button, self.dialog.speak_button,
                       self.dialog.ppl_button, self.dialog.detect_button,
                       self.dialog.voice_check_button):
            self.assertTrue(button.isEnabled(), button.text())
        self.assertTrue(self.dialog._trial_dialog.model_test_button.isEnabled())
        self.assertFalse(self.dialog._trial_dialog.stop_button.isEnabled())

    def test_interrupt_generation_waits_for_old_worker_and_keeps_partial_out_of_history(self):
        self.reply_gate.clear()
        self.start()
        self.audio.inputs.put("取消这一问")
        self.wait_for(lambda: self.partial_sent.is_set())
        # The HTTP thread flushing a chunk does not mean Qt has displayed it.
        self.wait_for(lambda: "本地回复1" in self.dialog.chat_log.toPlainText())
        self.dialog.voice_interrupt_button.click()
        self.wait_for(lambda: self.audio.listen_count == 2)
        self.assertFalse(self.reply_gate.is_set())
        self.assertTrue(self.dialog.voice_conversation.active)
        self.assertEqual(self.audio.speeches, [])
        self.assertEqual(self.dialog.message.text(), "")
        self.assertEqual(self.dialog._conversation_store.recent_messages("咕嘎"), [])
        self.assertIn("本地回复1", self.dialog.chat_log.toPlainText())
        self.assertFalse(self.audio.overlap)
        self.end()

    def test_interrupt_speech_and_end_take_precedence_over_resuming(self):
        self.audio.hold_speech.clear()
        self.start()
        self.audio.inputs.put("朗读时打断")
        self.wait_for(lambda: len(self.audio.speeches) == 1)
        self.dialog.voice_interrupt_button.click()
        self.dialog.voice_end_button.click()
        self.wait_for(lambda: self.dialog._job is None)
        self.pump_events(30)
        self.assertEqual(self.audio.listen_count, 1)
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertFalse(self.audio.overlap)
        self.assertEqual(self.audio.events[-1], "speaker:closed")

    def test_selected_audio_settings_reach_listening_and_reply_playback(self):
        self.dialog.audio_settings.set_values(
            {"name": "USB microphone", "host_api": "WASAPI"}, "voice-a", 155)
        self.start()
        self.audio.inputs.put("用选定的设备和声音回答")
        self.wait_for(lambda: self.audio.listen_count == 2)
        self.assertEqual(self.audio.microphones, [
            {"name": "USB microphone", "host_api": "WASAPI"},
            {"name": "USB microphone", "host_api": "WASAPI"}])
        self.assertEqual(self.audio.speech_settings, [("voice-a", 155)])
        self.end()

    def _production_speech_engine(self, *, failure=False):
        from test_assistant_speech_output import QueuedSpeechEngine
        engine = QueuedSpeechEngine()
        second_entered, release = threading.Event(), threading.Event()
        # Successful GUI/audio cleanup is always available even if an assertion fails.
        self.addCleanup(release.set)
        def on_event(_engine, event):
            if event[0] == "init":
                self.audio.enter("speaker")
            elif event[0] == "end":
                self.audio.leave("speaker")
        def iterate(current):
            if len(current.started) == 2:
                second_entered.set()
                if not release.is_set():
                    return
                if failure:
                    current.notify("error", name=current.current[1],
                                   exception=RuntimeError("测试第二段驱动失败"))
                    return
            current.finish(True)
        engine.on_event = on_event
        engine.on_iteration = iterate
        module = types.ModuleType("pyttsx3")
        module.init = engine.initialize
        self.dialog.audio_settings.set_values(None, "voice-a", 155)
        self.reply_override = "甲" * 500 + "乙" * 500 + "丙" * 200
        return engine, module, second_entered, release

    def test_production_chunked_reply_reopens_microphone_only_after_final_chunk_and_cleanup(self):
        from DyberPet.assistant.voice import speak_interruptible
        engine, module, second, release = self._production_speech_engine()
        ready = []
        self.dialog.speech_started.connect(lambda character, _text: ready.append(character))
        with patch.dict(sys.modules, {"pyttsx3": module}), \
                patch("DyberPet.assistant.speech.sys.platform", "win32"), \
                patch("DyberPet.assistant.ui.speak_interruptible", new=speak_interruptible):
            self.start()
            self.audio.inputs.put("请完整读出这段长回复")
            self.wait_for(lambda: second.is_set() and "1/3" in self.dialog.voice_chat_status.text())
            self.assertEqual(self.audio.listen_count, 1)
            self.assertEqual(engine.completed, ["甲" * 500])
            self.assertTrue(self.dialog.voice_conversation.active)
            release.set()
            self.wait_for(lambda: self.audio.listen_count == 2)
            self.assertEqual(engine.completed, ["甲" * 500, "乙" * 500, "丙" * 200])
            self.assertEqual(ready, ["咕嘎"])
            self.assertEqual([part[2]["voice"] for part in engine.started], ["voice-a"] * 3)
            self.assertEqual([part[2]["rate"] for part in engine.started], [155] * 3)
            self.assertFalse(self.audio.overlap)
            self.assertLess(self.audio.events.index("speaker:closed"),
                            len(self.audio.events) - 1)
            self.assertEqual(self.audio.events[-1], "microphone:open")
            self.assertEqual(self.dialog._last_reply, self.reply_override)
            self.end()

    def test_end_during_second_production_chunk_discards_remaining_audio_and_never_reopens(self):
        from DyberPet.assistant.voice import speak_interruptible
        engine, module, second, release = self._production_speech_engine()
        with patch.dict(sys.modules, {"pyttsx3": module}), \
                patch("DyberPet.assistant.speech.sys.platform", "win32"), \
                patch("DyberPet.assistant.ui.speak_interruptible", new=speak_interruptible):
            self.start()
            self.audio.inputs.put("在第二段结束对话")
            self.wait_for(second.is_set)
            self.dialog.voice_end_button.click()
            self.wait_for(lambda: self.dialog._job is None)
            self.pump_events(30)
        self.assertFalse(release.is_set())
        self.assertEqual(len(engine.started), 2)
        self.assertEqual(engine.completed, ["甲" * 500])
        self.assertEqual(self.audio.listen_count, 1)
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertEqual(self.audio.active, 0)
        self.assertEqual(self.dialog._last_reply, self.reply_override)

    def test_second_production_chunk_error_retains_answer_but_ends_voice_session(self):
        from DyberPet.assistant.voice import speak_interruptible
        engine, module, second, release = self._production_speech_engine(failure=True)
        with patch.dict(sys.modules, {"pyttsx3": module}), \
                patch("DyberPet.assistant.speech.sys.platform", "win32"), \
                patch("DyberPet.assistant.ui.speak_interruptible", new=speak_interruptible):
            self.start()
            self.audio.inputs.put("第二段音频驱动失败")
            self.wait_for(second.is_set)
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
            self.pump_events(30)
        self.assertEqual(len(engine.started), 2)
        self.assertEqual(engine.completed, ["甲" * 500])
        self.assertEqual(self.audio.listen_count, 1)
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertEqual(self.audio.active, 0)
        self.assertEqual(self.dialog._last_reply, self.reply_override)
        self.assertIn("失败", self.dialog.voice_chat_status.text())

    def test_standard_stop_listening_ends_session_and_discards_late_transcript(self):
        self.audio.listen_stop_returns_text = True
        self.start()
        self.dialog.stop_listen_button.click()
        self.wait_for(lambda: self.dialog._job is None)
        self.pump_events(30)
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertEqual(self.requests, [])
        self.assertEqual(self.dialog.message.text(), "")

    def test_configuration_changes_and_role_change_end_session_without_restart(self):
        changes = [
            lambda: self.dialog.llm_model.setText("another-model"),
            lambda: self.dialog.llm_endpoint.setText("http://127.0.0.1:1234"),
            lambda: self.dialog.voice_model.setText(str(self.root / "another-vosk")),
            lambda: self.dialog.ppl_enabled.setChecked(True),
            lambda: self.dialog.ppl_endpoint.setText("http://127.0.0.1:4001"),
            lambda: self.dialog.persona.setCurrentIndex(
                (self.dialog.persona.currentIndex() + 1) % self.dialog.persona.count()),
            lambda: self.dialog.set_character("Doro"),
            lambda: self.dialog.audio_settings.rate_spin.setValue(200),
        ]
        for change in changes:
            with self.subTest(change=change):
                self.start()
                count = self.audio.listen_count
                change()
                self.wait_for(lambda: self.dialog._job is None)
                self.pump_events(20)
                self.assertFalse(self.dialog.voice_conversation.active)
                self.assertEqual(self.audio.listen_count, count)
        self.assertEqual(self.requests, [])

    def test_close_waits_for_audio_and_does_not_reopen_on_queued_ready(self):
        self.start()
        stop = self.dialog._listen_stop_event
        generation = self.dialog._session_generation
        self.dialog.close()
        self.wait_for(lambda: self.dialog._job is None and not self.dialog.isVisible())
        self.dialog.microphone_ready.emit("咕嘎", generation, stop)
        self.pump_events(20)
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertEqual(self.audio.listen_count, 1)

    def test_empty_or_failed_audio_ends_once_without_model_request(self):
        for value in ("", VoiceUnavailable("没有听到有效语音")):
            with self.subTest(value=value):
                self.start()
                count = self.audio.listen_count
                self.audio.inputs.put(value)
                self.wait_for(lambda: self.dialog._job is None)
                self.pump_events(30)
                self.assertFalse(self.dialog.voice_conversation.active)
                self.assertEqual(self.audio.listen_count, count)
        self.assertEqual(self.requests, [])

    def test_speech_failure_preserves_reply_and_ends_without_new_microphone(self):
        self.audio.fail_speech = True
        self.start()
        self.audio.inputs.put("声音驱动故障")
        self.wait_for(lambda: self.dialog._job is None and bool(self.audio.speeches))
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertEqual(self.dialog._last_reply, "本地回复1")
        self.assertEqual(self.audio.listen_count, 1)
        self.assertIn("声音驱动", self.dialog.voice_chat_status.text())

    def test_twenty_completed_turns_end_session_without_opening_next_microphone(self):
        self.start()
        for index in range(20):
            self.audio.inputs.put("第{}句".format(index + 1))
        self.wait_for(lambda: self.dialog._job is None
                      and not self.dialog.voice_conversation.active, timeout=5)
        self.assertEqual(len(self.requests), 20)
        self.assertEqual(len(self.audio.speeches), 20)
        self.assertEqual(self.audio.listen_count, 20)
        self.assertEqual(self.audio.model_count, 1)
        self.assertEqual(self.audio.active, 0)
        self.assertFalse(self.audio.overlap)
        self.assertIn("20 轮", self.dialog.voice_chat_status.text())
        self.assertTrue(self.dialog.send_button.isEnabled())

    def test_session_timer_expiry_stops_microphone_without_rearming(self):
        self.start()
        self.dialog.voice_conversation._limit_timer.start(1)
        self.wait_for(lambda: self.dialog._job is None
                      and not self.dialog.voice_conversation.active)
        self.assertEqual(self.audio.listen_count, 1)
        self.assertEqual(self.audio.active, 0)
        self.assertEqual(self.requests, [])
        self.assertIn("10 分钟", self.dialog.voice_chat_status.text())
        self.assertTrue(self.dialog.voice_chat_button.isEnabled())

    def test_missing_preconditions_never_open_microphone_and_start_is_not_persistent(self):
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertEqual(self.audio.listen_count, 0)
        self.dialog.llm_model.clear()
        self.dialog.voice_chat_button.click()
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertEqual(self.audio.listen_count, 0)
        self.dialog.llm_model.setText("model")
        with patch("DyberPet.assistant.voice_session.inspect_voice_readiness",
                   new=lambda _p: VoiceReadiness(False, "缺少识别组件", True, "TTS")):
            self.dialog.voice_chat_button.click()
        self.assertFalse(self.dialog.voice_conversation.active)
        self.assertIn("缺少识别", self.dialog.voice_chat_status.text())
        self.assertEqual(self.audio.listen_count, 0)


if __name__ == "__main__":
    unittest.main()
