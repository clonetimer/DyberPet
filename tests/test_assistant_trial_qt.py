"""Trial actions and privacy-safe evidence through actual assistant workers."""
import json
import os
import sys
import tempfile
import threading
import time
import types
import unittest
from contextlib import contextmanager
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
class AssistantTrialQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.preferences import defaults
        from DyberPet.assistant.ui import PetAssistantDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.preference_patch = patch("DyberPet.assistant.ui.load_preferences",
                                      side_effect=defaults)
        self.preference_patch.start()
        self.dialog = PetAssistantDialog(
            "角色秘密", Path(self.tmp.name) / "private-files",
            store_path=Path(self.tmp.name) / "history.sqlite3")
        self.dialog.llm_model.setText("private-model-id")
        self.dialog.auto_speak.setChecked(False)
        self.gates = []

    def tearDown(self):
        for gate in self.gates:
            gate.set()
        if self.dialog._job is not None:
            self.dialog.close()
            self.dialog._job.wait(2500)
            QTest.qWait(30)
        self.dialog.close()
        self.preference_patch.stop()
        self.tmp.cleanup()

    def gate(self):
        gate = threading.Event()
        self.gates.append(gate)
        return gate

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate(), "Qt worker did not reach expected state")

    def records(self):
        return self.dialog._trial_recorder.snapshot()["observations"]

    @contextmanager
    def model_server(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_POST(self):
                requests.append((self.path, json.loads(self.rfile.read(
                    int(self.headers["Content-Length"])).decode())))
                chunks = [
                    {"choices": [{"delta": {"content": "你好，"}, "finish_reason": None}]},
                    {"choices": [{"delta": {"content": "试聊成功。"}, "finish_reason": None}]},
                    {"choices": [{"delta": {}, "finish_reason": "stop"}]},
                ]
                body = "".join("data: " + json.dumps(item, ensure_ascii=False) + "\n\n"
                               for item in chunks) + "data: [DONE]\n\n"
                encoded = body.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(encoded)))
                self.end_headers()
                self.wfile.write(encoded)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01),
                                  daemon=True)
        thread.start()
        try:
            yield "http://127.0.0.1:" + str(server.server_port), requests
        finally:
            server.shutdown()
            server.server_close()
            thread.join(1)

    def test_opening_trial_is_passive_and_reuses_one_nonmodal_window(self):
        self.assertTrue(hasattr(self.dialog, "trial_button"), "Trial entry is missing")
        with patch("DyberPet.assistant.ui.stream_local_chat",
                   side_effect=AssertionError("must not infer")), patch(
                       "DyberPet.assistant.ui.recognize_until_stopped",
                       side_effect=AssertionError("must not listen")), patch(
                           "DyberPet.assistant.ui.speak_interruptible",
                           side_effect=AssertionError("must not speak")):
            self.dialog.trial_button.click()
            trial = self.dialog._trial_dialog
            self.dialog.trial_button.click()
            QTest.qWait(20)
            self.assertIs(self.dialog._trial_dialog, trial)
            self.assertFalse(trial.isModal())
            self.assertIsNone(self.dialog._job)
            self.assertEqual(self.records(), [])

    def test_actual_trial_request_excludes_private_context_and_preserves_chat(self):
        self.dialog.message.setText("PRIVATE_DRAFT")
        self.dialog._last_reply = "PRIVATE_PREVIOUS_REPLY"
        self.dialog._pending_file_context = {"name": "PRIVATE_FILE", "content": "PRIVATE_BODY"}
        self.dialog._ppl_snapshot = "PRIVATE_PPL"
        self.dialog.ppl_enabled.setChecked(True)
        self.dialog._conversation_store.append_turn("角色秘密", "PRIVATE_HISTORY", "OLD_REPLY")
        self.dialog._conversation_store.add_memory("角色秘密", "PRIVATE_MEMORY")
        before = self.dialog._conversation_store.recent_messages("角色秘密")
        with self.model_server() as (endpoint, requests), patch(
                "DyberPet.assistant.ui.PPLCharacterClient",
                side_effect=AssertionError("Trial must not fetch PPL")):
            self.dialog.llm_endpoint.setText(endpoint)
            self.dialog.try_model()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(len(requests), 1)
        path, payload = requests[0]
        self.assertEqual(path, "/v1/chat/completions")
        self.assertEqual([item["role"] for item in payload["messages"]], ["system", "user"])
        self.assertNotIn("PRIVATE_", json.dumps(payload))
        self.assertTrue(payload["stream"])
        self.assertEqual(payload["model"], "private-model-id")
        self.assertIn("试聊成功", self.dialog._trial_dialog.probe_preview.toPlainText())
        self.assertEqual(self.dialog.message.text(), "PRIVATE_DRAFT")
        self.assertEqual(self.dialog._last_reply, "PRIVATE_PREVIOUS_REPLY")
        self.assertEqual(self.dialog._pending_file_context["content"], "PRIVATE_BODY")
        self.assertEqual(self.dialog._conversation_store.recent_messages("角色秘密"), before)
        self.assertIsNone(self.dialog._speech_stop_event)
        record = self.records()[-1]
        self.assertEqual((record["kind"], record["outcome"]), ("model_probe", "completed"))
        self.assertEqual(record["displayed_chars"], 8)
        self.assertIsNotNone(record["first_text_ms"])
        report = json.dumps(self.dialog._trial_recorder.snapshot(), ensure_ascii=False)
        for private in ("PRIVATE_", "private-model-id", "角色秘密", endpoint, self.tmp.name, "试聊成功"):
            self.assertNotIn(private, report)

    def test_stop_wins_over_queued_trial_success_and_retry_is_independent(self):
        self.dialog.message.setText("尚未发送的问题")
        self.dialog._last_reply = "保留上一回复"
        with patch("DyberPet.assistant.ui.stream_local_chat", return_value="迟到试聊回复"):
            self.dialog.try_model()
            self.assertTrue(self.dialog._job.wait(1000))
            self.dialog.stop_generation()
            self.wait_for(lambda: self.dialog._job is None)
        first = self.records()[-1]
        self.assertEqual(first["outcome"], "cancelled")
        self.assertEqual(first["stop_reason"], "user")
        self.assertIsNotNone(first["stop_settled_ms"])
        self.assertNotIn("迟到试聊回复", self.dialog._trial_dialog.probe_preview.toPlainText())
        self.assertEqual(self.dialog.message.text(), "尚未发送的问题")
        self.assertEqual(self.dialog._last_reply, "保留上一回复")
        with patch("DyberPet.assistant.ui.stream_local_chat", return_value="本次完成"):
            self.dialog.try_model()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual([r["outcome"] for r in self.records()], ["cancelled", "completed"])
        self.assertNotEqual(self.records()[0]["id"], self.records()[1]["id"])

    def test_trial_endpoint_or_model_edits_discard_stale_success_even_after_revert(self):
        for field_name in ("llm_endpoint", "llm_model"):
            with self.subTest(field=field_name):
                release, entered = self.gate(), threading.Event()
                def stream(text, *, on_delta, **kwargs):
                    entered.set()
                    release.wait(2)
                    on_delta("旧配置正文")
                    return "旧配置正文"
                with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
                    self.dialog.try_model()
                    self.wait_for(entered.is_set)
                    field = getattr(self.dialog, field_name)
                    original = field.text()
                    field.setText("http://localhost:9998" if field_name == "llm_endpoint" else "new-model")
                    field.setText(original)
                    release.set()
                    self.wait_for(lambda: self.dialog._job is None)
                record = self.records()[-1]
                self.assertEqual(record["outcome"], "cancelled")
                self.assertEqual(record["stop_reason"], "configuration_changed")
                self.assertEqual(record["displayed_chars"], 0)
                self.assertNotIn("旧配置正文", self.dialog._trial_dialog.probe_preview.toPlainText())

    def test_chat_and_speech_records_retain_only_counts_and_observed_stages(self):
        def stream(text, *, on_delta, **kwargs):
            on_delta("SECRET_ANSWER")
            return "SECRET_ANSWER"
        self.dialog.message.setText("SECRET_QUESTION")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(lambda: self.dialog._job is None)
        release, entered = self.gate(), threading.Event()
        def speak(text, stop_event, *, on_ready):
            self.assertEqual(text, "SECRET_ANSWER")
            on_ready()
            entered.set()
            release.wait(2)
            return True
        with patch("DyberPet.assistant.ui.speak_interruptible", side_effect=speak):
            self.dialog.read_reply()
            self.wait_for(lambda: entered.is_set() and self.records()[-1]["ready_ms"] is not None)
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        records = self.records()
        self.assertEqual([r["kind"] for r in records], ["chat", "speech"])
        self.assertEqual([r["outcome"] for r in records], ["completed", "completed"])
        self.assertEqual(records[0]["result_chars"], 13)
        self.assertTrue(records[1]["engine_completed"])
        report = self.dialog._trial_recorder.snapshot()
        self.assertEqual(report["feedback"]["speech"], "not_checked")
        self.assertNotIn("SECRET_", json.dumps(report))

    def test_stopped_microphone_preserves_final_transcript_evidence(self):
        self.dialog.voice_model.setText("/PRIVATE_MODEL_PATH")
        entered = threading.Event()
        def recognize(model, stop_event, *, on_partial, max_seconds, on_ready):
            on_ready()
            entered.set()
            stop_event.wait(2)
            return "私密转写文字"
        with patch("DyberPet.assistant.ui.recognize_until_stopped", side_effect=recognize):
            self.dialog.listen_continuously()
            self.wait_for(lambda: entered.is_set() and self.records()[-1]["ready_ms"] is not None)
            self.dialog.stop_listening()
            self.wait_for(lambda: self.dialog._job is None)
        record = self.records()[-1]
        self.assertEqual(record["outcome"], "cancelled")
        self.assertEqual(record["result_chars"], 6)
        self.assertIsNotNone(record["ready_ms"])
        self.assertIsNotNone(record["stop_requested_ms"])
        self.assertEqual(self.dialog.message.text(), "私密转写文字")
        encoded = json.dumps(self.dialog._trial_recorder.snapshot(), ensure_ascii=False)
        self.assertNotIn("私密转写文字", encoded)
        self.assertNotIn("PRIVATE_MODEL_PATH", encoded)

    def test_failure_report_uses_stable_category_without_exception_text(self):
        from DyberPet.assistant.persona import AssistantServiceError
        self.dialog.message.setText("SECRET_QUESTION")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=
                   AssistantServiceError("SECRET_ERROR /private/user", code="timeout")):
            self.dialog.send_message()
            self.wait_for(lambda: self.dialog._job is None)
        record = self.records()[-1]
        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(record["error_code"], "timeout")
        self.assertEqual(self.dialog.message.text(), "SECRET_QUESTION")
        self.assertNotIn("SECRET_", json.dumps(self.dialog._trial_recorder.snapshot()))

    def test_sample_speech_preserves_reply_and_draft(self):
        self.dialog.message.setText("MY_DRAFT")
        self.dialog._last_reply = "MY_REPLY"
        spoken = []
        def speak(text, stop_event, *, on_ready):
            spoken.append(text)
            on_ready()
            return True
        with patch("DyberPet.assistant.ui.speak_interruptible", side_effect=speak):
            self.dialog.try_speech()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(spoken, ["你好，我是你的桌宠助手。这是一段语音试听。"])
        self.assertEqual(self.dialog.message.text(), "MY_DRAFT")
        self.assertEqual(self.dialog._last_reply, "MY_REPLY")
        self.assertTrue(self.records()[-1]["engine_completed"])

    def test_closing_trial_or_failed_export_does_not_stop_live_microphone(self):
        self.dialog.voice_model.setText("/model")
        release, entered = self.gate(), threading.Event()
        def recognize(model, stop_event, **kwargs):
            kwargs["on_ready"]()
            entered.set()
            release.wait(2)
            return ""
        with patch("DyberPet.assistant.ui.recognize_until_stopped", side_effect=recognize):
            self.dialog.listen_continuously()
            self.wait_for(entered.is_set)
            self.dialog.show_trial_dialog()
            trial = self.dialog._trial_dialog
            existing = Path(self.tmp.name) / "existing.json"
            existing.write_text("keep me")
            with patch("DyberPet.assistant.trial_dialog.QFileDialog.getSaveFileName",
                       return_value=(str(existing), "JSON (*.json)")):
                trial.export_preview()
            self.assertEqual(existing.read_text(), "keep me")
            self.assertTrue(self.dialog.stop_listen_button.isEnabled())
            self.assertFalse(self.dialog._listen_stop_event.is_set())
            trial.close()
            self.assertFalse(self.dialog._listen_stop_event.is_set())
            self.dialog.stop_listening()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.records()[-1]["outcome"], "cancelled")

    def test_scope_change_cancels_trial_and_drops_late_ready_or_text(self):
        release, entered = self.gate(), threading.Event()
        def stream(text, *, on_delta, **kwargs):
            entered.set()
            release.wait(2)
            on_delta("旧角色结果")
            return "旧角色结果"
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.try_model()
            self.wait_for(entered.is_set)
            self.dialog.set_character("新角色")
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        record = self.records()[-1]
        self.assertEqual(record["outcome"], "cancelled")
        self.assertEqual(record["stop_reason"], "scope_changed")
        self.assertEqual(record["displayed_chars"], 0)
        self.assertNotIn("旧角色结果", self.dialog._trial_dialog.probe_preview.toPlainText())

    def test_closing_assistant_records_window_stop_and_closes_trial(self):
        release, entered = self.gate(), threading.Event()
        def stream(text, *, on_delta, **kwargs):
            entered.set()
            release.wait(2)
            return "迟到结果"
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.show()
            self.dialog.try_model()
            self.wait_for(entered.is_set)
            trial = self.dialog._trial_dialog
            self.dialog.close()
            release.set()
            self.wait_for(lambda: self.dialog._job is None and not self.dialog.isVisible())
        self.assertFalse(trial.isVisible())
        self.assertEqual(self.records()[-1]["stop_reason"], "window_closed")
        self.assertEqual(self.records()[-1]["outcome"], "cancelled")

    def test_passive_checks_do_not_claim_generation_or_device_completion(self):
        from DyberPet.assistant.voice_readiness import VoiceReadiness
        with patch("DyberPet.assistant.ui.list_local_models", return_value=["a", "b"]):
            self.dialog.detect_models()
            self.wait_for(lambda: self.dialog._job is None)
        with patch("DyberPet.assistant.ui.inspect_voice_readiness", return_value=
                   VoiceReadiness(True, "组件存在", True, "组件存在")):
            self.dialog.check_voice_setup()
            self.wait_for(lambda: self.dialog._job is None)
        records = self.records()
        self.assertEqual([r["kind"] for r in records], ["models", "voice_check"])
        self.assertEqual(records[0]["model_count"], 2)
        self.assertTrue(records[1]["recognition_ready"])
        self.assertTrue(records[1]["tts_ready"])
        self.assertTrue(all(r["ready_ms"] is None and r["engine_completed"] is None for r in records))

    def test_queued_speech_success_cannot_undo_a_user_stop_in_main_ui(self):
        with patch("DyberPet.assistant.ui.speak_interruptible", return_value=True):
            self.dialog.try_speech()
            self.assertTrue(self.dialog._job.wait(1000))
            self.dialog.stop_speaking()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog._activity_outcome, "cancelled")
        self.assertIn("停止", self.dialog.activity_status.text())
        self.assertIn("停止", self.dialog.status.text())
        record = self.records()[-1]
        self.assertEqual(record["outcome"], "cancelled")
        self.assertTrue(record["engine_completed"])

    def test_stopping_real_tts_during_init_does_not_invent_engine_completion(self):
        release, entered = self.gate(), threading.Event()
        cleanup = []
        engine = types.SimpleNamespace(stop=lambda: cleanup.append("stop"))
        def initialize():
            entered.set()
            release.wait(2)
            return engine
        module = types.ModuleType("pyttsx3")
        module.init = initialize
        with patch.dict(sys.modules, {"pyttsx3": module}):
            self.dialog.try_speech()
            self.wait_for(entered.is_set)
            self.dialog.stop_speaking()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        record = self.records()[-1]
        self.assertEqual(record["outcome"], "cancelled")
        self.assertIsNone(record["ready_ms"])
        self.assertIsNone(record["engine_completed"])
        self.assertEqual(cleanup, ["stop"])

    def test_missing_trial_prerequisites_are_explained_in_foreground_window(self):
        self.dialog.show_trial_dialog()
        trial = self.dialog._trial_dialog
        self.dialog.llm_model.clear()
        trial.model_test_button.click()
        self.assertIn("模型", trial.status_label.text())
        self.assertIsNone(self.dialog._job)
        self.dialog.voice_model.clear()
        trial.listen_button.click()
        self.assertIn("目录", trial.status_label.text())
        self.assertIsNone(self.dialog._job)
        self.assertEqual(self.records(), [])

    def test_structured_voice_failure_retains_observed_negative_completion(self):
        from DyberPet.assistant.voice import VoiceUnavailable
        failure = VoiceUnavailable("PRIVATE_DRIVER_ERROR")
        failure.engine_completed = False
        with patch("DyberPet.assistant.ui.speak_interruptible", side_effect=failure):
            self.dialog.try_speech()
            self.wait_for(lambda: self.dialog._job is None)
        record = self.records()[-1]
        self.assertEqual(record["outcome"], "failed")
        self.assertEqual(record["error_code"], "voice_unavailable")
        self.assertIs(record["engine_completed"], False)
        self.assertNotIn("PRIVATE_DRIVER_ERROR", json.dumps(self.dialog._trial_recorder.snapshot()))


if __name__ == "__main__":
    unittest.main()
