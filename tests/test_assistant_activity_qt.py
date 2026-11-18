"""User-visible cancellation and activity lifecycle on real Qt workers."""
import os
import gc
import tempfile
import threading
import time
import unittest
import weakref
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = QTest = None


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt smoke CI")
class AssistantActivityQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.dialog = PetAssistantDialog(
            "咕嘎", Path(self.tmp.name) / "files",
            store_path=Path(self.tmp.name) / "companion.sqlite3")
        self.dialog.llm_model.setText("local-model")
        self.dialog.auto_speak.setChecked(False)
        self.gates = []

    def tearDown(self):
        for gate in self.gates:
            gate.set()
        if self.dialog._job is not None:
            self.dialog._job.wait(2500)
            QTest.qWait(20)
        self.dialog.close()
        self.tmp.cleanup()

    def gate(self):
        gate = threading.Event()
        self.gates.append(gate)
        return gate

    def wait_for(self, predicate):
        deadline = time.monotonic() + 2
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate(), "Qt worker did not reach the expected state")

    def test_stop_keeps_partial_and_attachment_but_never_commits_late_answer(self):
        release = self.gate()
        source = {"name": "reference.md", "content": "参考资料"}
        self.dialog._pending_file_context = source.copy()
        self.dialog.message.setText("总结这份资料")
        self.dialog._last_reply = "上一轮旧回复"
        bubbles = []
        self.dialog.reply_ready.connect(bubbles.append)

        def stream(text, *, on_delta, **kwargs):
            on_delta("已收到的片段")
            release.wait(2)
            on_delta("不应显示的后续")
            return "不应保存的完整答案"

        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(lambda: "已收到的片段" in self.dialog.chat_log.toPlainText())
            self.dialog.stop_generation_button.click()
            self.assertIn("停止", self.dialog.activity_status.text())
            self.assertFalse(self.dialog.send_button.isEnabled())
            self.assertFalse(self.dialog.stop_generation_button.isEnabled())
            self.assertEqual(self.dialog.message.text(), "总结这份资料")
            release.set()
            self.wait_for(lambda: self.dialog._job is None)

        transcript = self.dialog.chat_log.toPlainText()
        self.assertIn("已收到的片段", transcript)
        self.assertIn("用户停止", transcript)
        self.assertNotIn("不应显示", transcript)
        self.assertNotIn("不应保存", transcript)
        self.assertEqual(self.dialog._conversation_store.recent_messages("咕嘎"), [])
        self.assertEqual(self.dialog._pending_file_context, source)
        self.assertEqual(self.dialog._last_reply, "")
        self.assertEqual(bubbles, [])
        self.assertTrue(self.dialog.send_button.isEnabled())

    def test_stop_preserves_newly_typed_question_and_allows_clean_retry(self):
        release = self.gate()
        entered = threading.Event()

        def stream(text, *, on_delta, **kwargs):
            entered.set()
            release.wait(2)
            return "旧答案"

        self.dialog.message.setText("原问题")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(entered.is_set)
            self.dialog.message.setText("新问题")
            self.dialog.stop_generation()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.message.text(), "新问题")
        with patch("DyberPet.assistant.ui.stream_local_chat", return_value="新答案"):
            self.dialog.send_message()
            self.wait_for(lambda: self.dialog._job is None)
        messages = self.dialog._conversation_store.recent_messages("咕嘎")
        self.assertEqual([(item["role"], item["content"]) for item in messages],
                         [("user", "新问题"), ("assistant", "新答案")])
        self.assertEqual(self.dialog._last_reply, "新答案")

    def test_stop_wins_over_success_already_queued_to_qt(self):
        self.dialog.message.setText("停止前已返回")
        self.dialog.auto_speak.setChecked(True)
        self.dialog.show()
        with patch("DyberPet.assistant.ui.stream_local_chat", return_value="迟到成功"):
            self.dialog.send_message()
            self.assertTrue(self.dialog._job.wait(1000))
            # The worker ended, but the GUI has not consumed its queued success.
            self.dialog.stop_generation()
            self.wait_for(lambda: self.dialog._job is None)
            QTest.qWait(130)
        self.assertEqual(self.dialog._conversation_store.recent_messages("咕嘎"), [])
        self.assertEqual(self.dialog._last_reply, "")
        self.assertIsNone(self.dialog._speaking_session)

    def test_cancelled_plan_never_opens_review_or_consumes_attachment(self):
        from DyberPet.assistant.task_plan import parse_task_plan
        plan = parse_task_plan('{"version":1,"title":"便签","steps":['
                               '{"action":"create_note","name":"a.md","content":"正文"}]}')
        release, entered = self.gate(), threading.Event()
        source = {"name": "source.md", "content": "资料"}
        self.dialog._pending_file_context = source.copy()
        self.dialog.message.setText("生成便签")

        def planner(*args, **kwargs):
            entered.set()
            release.wait(2)
            return plan

        with patch("DyberPet.assistant.ui.generate_task_plan", side_effect=planner):
            self.dialog.propose_task()
            self.wait_for(entered.is_set)
            self.dialog.stop_generation_button.click()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertIsNone(self.dialog._task_review_dialog)
        self.assertIsNone(self.dialog._task_session)
        self.assertEqual(self.dialog.workspace.list_files(), [])
        self.assertEqual(self.dialog._pending_file_context, source)
        self.assertEqual(self.dialog.message.text(), "生成便签")

    def test_late_error_after_stop_does_not_replace_cancel_status(self):
        release, entered = self.gate(), threading.Event()

        def stream(*args, **kwargs):
            entered.set()
            release.wait(2)
            raise RuntimeError("late transport error")

        self.dialog.message.setText("问题")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(entered.is_set)
            self.dialog.stop_generation()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertNotIn("late transport", self.dialog.chat_log.toPlainText())
        self.assertIn("已停止", self.dialog.activity_status.text())

    def test_scope_change_cancels_transport_and_discards_old_output(self):
        release, entered = self.gate(), threading.Event()
        tokens = []

        def stream(*args, **kwargs):
            tokens.append(kwargs.get("cancel_token"))
            entered.set()
            release.wait(2)
            return "旧角色答案"

        self.dialog.message.setText("问题")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(entered.is_set)
            self.dialog.set_character("Doro")
            self.assertIsNotNone(tokens[0])
            self.assertTrue(tokens[0].cancelled)
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertNotIn("旧角色答案", self.dialog.chat_log.toPlainText())
        self.assertEqual(self.dialog._conversation_store.recent_messages("Doro"), [])

    def test_close_cancels_request_then_waits_for_worker_before_hiding(self):
        from DyberPet.assistant.request_control import RequestCancelled
        entered = threading.Event()

        def stream(*args, **kwargs):
            token = kwargs["cancel_token"]
            entered.set()
            deadline = time.monotonic() + 2
            while not token.cancelled and time.monotonic() < deadline:
                threading.Event().wait(0.01)
            if token.cancelled:
                raise RequestCancelled("cancelled")
            raise RuntimeError("UI never cancelled the transport")

        self.dialog.show()
        self.dialog.message.setText("问题")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(entered.is_set)
            self.dialog.close()
            self.wait_for(lambda: self.dialog._job is None and not self.dialog.isVisible())
        self.assertEqual(self.dialog._conversation_store.recent_messages("咕嘎"), [])

    def test_activity_timer_records_first_text_and_freezes_at_completion(self):
        release, entered = self.gate(), threading.Event()
        clock = [100.0]

        def stream(*args, on_delta, **kwargs):
            entered.set()
            release.wait(2)
            return "两字"

        self.dialog.message.setText("问题")
        with patch("DyberPet.assistant.ui.monotonic", side_effect=lambda: clock[0]):
            with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
                self.dialog.send_message()
                self.wait_for(entered.is_set)
                clock[0] = 101.5
                self.dialog._job_progress("两字")
                self.assertIn("首段 1.5 秒", self.dialog.activity_metrics.text())
                self.assertIn("2 字符", self.dialog.activity_metrics.text())
                clock[0] = 103.0
                release.set()
                self.wait_for(lambda: self.dialog._job is None)
                frozen = self.dialog.activity_metrics.text()
                self.assertIn("3.0 秒", frozen)
                clock[0] = 900.0
                QTest.qWait(300)
                self.assertEqual(self.dialog.activity_metrics.text(), frozen)

    def test_listening_becomes_active_only_after_ready_and_stop_ignores_partial(self):
        ready_gate, finish_gate = self.gate(), self.gate()
        entered = threading.Event()

        def recognize(model, stop, *, on_ready, on_partial, **kwargs):
            entered.set()
            ready_gate.wait(2)
            on_ready()
            finish_gate.wait(2)
            on_partial("停止后不应覆盖状态")
            return "最终识别"

        self.dialog.voice_model.setText(self.tmp.name)
        with patch("DyberPet.assistant.ui.recognize_until_stopped", side_effect=recognize):
            self.dialog.listen_continuously()
            self.wait_for(entered.is_set)
            self.assertIn("准备", self.dialog.activity_status.text())
            ready_gate.set()
            self.wait_for(lambda: "正在监听" in self.dialog.activity_status.text())
            self.dialog.stop_listening()
            self.assertIn("停止", self.dialog.activity_status.text())
            finish_gate.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.message.text(), "最终识别")
        self.assertNotIn("停止后不应", self.dialog.status.text())
        self.assertIn("已停止", self.dialog.activity_status.text())

    def test_late_voice_ready_after_stop_never_starts_native_feedback(self):
        entered, release = threading.Event(), self.gate()
        started = []
        self.dialog.speech_started.connect(lambda *args: started.append(args))
        self.dialog._last_reply = "朗读内容"

        def speak(text, stop, *, on_ready, **kwargs):
            entered.set()
            release.wait(2)
            on_ready()
            return False

        with patch("DyberPet.assistant.ui.speak_interruptible", side_effect=speak):
            self.dialog.read_reply()
            self.wait_for(entered.is_set)
            self.dialog.stop_speaking()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(started, [])
        self.assertIn("已停止", self.dialog.activity_status.text())

    def test_unrelated_action_error_does_not_remove_live_microphone_stop_control(self):
        entered, release = threading.Event(), self.gate()
        events = []

        def recognize(model, stop, *, on_ready, **kwargs):
            events.append(stop)
            entered.set()
            on_ready()
            release.wait(2)
            return "完成识别"

        self.dialog.voice_model.setText(self.tmp.name)
        with patch("DyberPet.assistant.ui.recognize_until_stopped", side_effect=recognize):
            self.dialog.listen_continuously()
            self.wait_for(entered.is_set)
            self.dialog._job_error("另一项文件操作失败")
            self.assertTrue(self.dialog.stop_listen_button.isEnabled())
            self.dialog.stop_listen_button.click()
            self.assertTrue(events[0].is_set())
            release.set()
            self.wait_for(lambda: self.dialog._job is None)

    def test_unreadable_history_preserves_input_and_never_starts_generation(self):
        self.dialog.message.setText("保留尚未发出的原问题")
        source = {"name": "input.md", "content": "还未使用的附件"}
        self.dialog._pending_file_context = source.copy()
        self.dialog._conversation_store.path.write_bytes(b"not a sqlite database")
        self.dialog.send_message()
        self.assertEqual(self.dialog.message.text(), "保留尚未发出的原问题")
        self.assertEqual(self.dialog._pending_file_context, source)
        self.assertIsNone(self.dialog._job)
        self.assertFalse(self.dialog._activity_timer.isActive())
        self.assertFalse(self.dialog.stop_generation_button.isEnabled())
        self.assertTrue(self.dialog.send_button.isEnabled())
        self.assertIn("历史", self.dialog.status.text())

    def test_history_write_failure_keeps_reply_and_visible_warning(self):
        release, entered = self.gate(), threading.Event()

        def stream(*args, **kwargs):
            entered.set()
            release.wait(2)
            return "已生成的完整回复"

        self.dialog.message.setText("请求")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(entered.is_set)
            self.dialog._conversation_store.path.write_bytes(b"broken while generating")
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog._last_reply, "已生成的完整回复")
        self.assertIn("历史保存失败", self.dialog.status.text())
        self.assertFalse(self.dialog._activity_timer.isActive())

    def test_real_http_generation_stop_releases_chat_and_plan_connections(self):
        # Actual Qt -> persona/planner -> socket shutdown, without patching any
        # production transport, signal or history component.
        for is_plan in (False, True):
            with self.subTest(plan=is_plan):
                arrived, disconnected = threading.Event(), threading.Event()

                class Handler(BaseHTTPRequestHandler):
                    def do_POST(self):
                        self.rfile.read(int(self.headers["Content-Length"]))
                        self.send_response(200)
                        self.send_header("Connection", "close")
                        self.end_headers()
                        payload = (b'{"choices":[' if is_plan else
                                   b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n')
                        self.wfile.write(payload)
                        self.wfile.flush()
                        arrived.set()
                        self.connection.settimeout(2)
                        try:
                            if self.connection.recv(1) == b"":
                                disconnected.set()
                        except ConnectionResetError:
                            disconnected.set()
                        except OSError:
                            pass

                    def log_message(self, *args):
                        pass

                server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
                serving = threading.Thread(
                    target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
                serving.start()
                self.dialog.llm_endpoint.setText("http://127.0.0.1:" + str(server.server_port))
                self.dialog.message.setText("实际请求")
                try:
                    if is_plan:
                        self.dialog.propose_task()
                    else:
                        self.dialog.send_message()
                    self.wait_for(arrived.is_set)
                    if not is_plan:
                        self.wait_for(lambda: "hello" in self.dialog.chat_log.toPlainText())
                    self.dialog.stop_generation_button.click()
                    self.wait_for(lambda: self.dialog._job is None and disconnected.is_set())
                    self.assertIsNone(self.dialog._task_review_dialog)
                    self.assertEqual(self.dialog._conversation_store.recent_messages("咕嘎"), [])
                    self.assertTrue(self.dialog.send_button.isEnabled())
                finally:
                    if self.dialog._request_token is not None:
                        self.dialog._request_token.cancel()
                    server.shutdown()
                    server.server_close()
                    serving.join(timeout=2)

    def test_previous_voice_ready_cannot_start_a_new_same_character_utterance(self):
        started = []
        self.dialog.speech_started.connect(lambda *args: started.append(args))
        self.dialog._last_reply = "当前回复"
        with patch.object(self.dialog, "_submit"):
            self.dialog.read_reply()
            old_stop = self.dialog._speech_stop_event
            self.dialog._job_finished()
            self.dialog.read_reply()
            self.dialog.voice_engine_ready.emit("咕嘎", "旧回复", old_stop)
            QTest.qWait(10)
            self.assertEqual(started, [])
            self.dialog.voice_engine_ready.emit(
                "咕嘎", "当前回复", self.dialog._speech_stop_event)
            QTest.qWait(10)
        self.assertEqual(started, [("咕嘎", "当前回复")])

    def test_retained_audio_callback_does_not_keep_a_closed_window_alive(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        for listening in (False, True):
            with self.subTest(listening=listening):
                callbacks = []
                extra = PetAssistantDialog(
                    "Doro", Path(self.tmp.name) / "extra-files",
                    store_path=Path(self.tmp.name) / "extra.sqlite3")
                extra.voice_model.setText(self.tmp.name)
                extra._last_reply = "临时朗读"

                def capture(task, on_success, *args, **kwargs):
                    if listening:
                        # Retain the microphone task exactly as a worker can.
                        callbacks.append(task)
                    else:
                        callbacks.append(kwargs["on_ready"])

                with patch.object(extra, "_submit", new=capture):
                    if listening:
                        extra.listen_continuously()
                    else:
                        extra.read_reply()
                window = weakref.ref(extra)
                extra.close()
                del extra
                gc.collect()
                self.assertIsNone(window(), "A worker callback retained the closed window")
                if listening:
                    def recognize(*args, on_ready, **kwargs):
                        on_ready()
                        return ""
                    with patch("DyberPet.assistant.ui.recognize_until_stopped",
                               side_effect=recognize):
                        callbacks[0](lambda _: None)
                else:
                    callbacks[0]()


if __name__ == "__main__":
    unittest.main()
