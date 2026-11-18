"""First-use setup through real Qt workers without model or audio hardware."""
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = QTest = None


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt smoke CI")
class AssistantSetupQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.preferences import defaults
        from DyberPet.assistant.ui import PetAssistantDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.gates = []
        self.preference_patch = patch("DyberPet.assistant.ui.load_preferences",
                                      side_effect=defaults)
        self.preference_patch.start()
        # The pre-change discovery used a modal picker. Keep RED runs from
        # waiting for human input; assertions exercise the new inline choices.
        self.legacy_picker = patch("PySide6.QtWidgets.QInputDialog.getItem",
                                   return_value=("", False))
        self.legacy_picker.start()
        self.dialog = PetAssistantDialog(
            "Doro", Path(self.tmp.name) / "files",
            store_path=Path(self.tmp.name) / "companion.sqlite3")

    def tearDown(self):
        for gate in self.gates:
            gate.set()
        if self.dialog._job is not None:
            self.dialog.close()
            self.dialog._job.wait(2500)
            QTest.qWait(30)
        self.dialog.close()
        self.preference_patch.stop()
        self.legacy_picker.stop()
        self.tmp.cleanup()

    def wait_for(self, predicate):
        deadline = time.monotonic() + 3
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate(), "Qt worker did not reach expected state")

    def gate(self):
        gate = threading.Event()
        self.gates.append(gate)
        return gate

    def test_open_shows_next_steps_without_starting_services_or_audio(self):
        self.assertIsNone(self.dialog._job)
        self.assertIn("检查", self.dialog.model_status.text())
        self.assertIn("模型", self.dialog.voice_status.text())
        self.assertIn("检查", self.dialog.tts_status.text())
        self.assertEqual(self.dialog.model_selector.count(), 0)
        self.assertIsNone(self.dialog._listen_stop_event)
        self.assertIsNone(self.dialog._speech_stop_event)

    def test_discovery_populates_editable_choices_without_overwriting_manual_id(self):
        self.dialog.llm_model.setText("my-manual-id")
        with patch("DyberPet.assistant.ui.list_local_models",
                   return_value=["chat-a", "chat-b"]):
            self.dialog.detect_models()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.llm_model.text(), "my-manual-id")
        self.assertEqual([self.dialog.model_selector.itemText(i) for i in range(2)],
                         ["chat-a", "chat-b"])
        self.dialog.model_selector.setCurrentIndex(1)
        self.assertEqual(self.dialog.llm_model.text(), "chat-b")
        self.assertIn("尚未", self.dialog.model_status.text())
        self.assertEqual(self.dialog._conversation_store.recent_messages("Doro"), [])

    def test_one_model_fills_empty_selection_but_multiple_models_do_not(self):
        with patch("DyberPet.assistant.ui.list_local_models", return_value=["only-model"]):
            self.dialog.detect_models()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.llm_model.text(), "only-model")
        self.dialog.llm_model.clear()
        with patch("DyberPet.assistant.ui.list_local_models", return_value=["one", "two"]):
            self.dialog.detect_models()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.llm_model.text(), "")

    def test_model_typed_during_check_is_preserved(self):
        release, entered = self.gate(), threading.Event()
        def discover(*args, **kwargs):
            entered.set()
            release.wait(2)
            return ["server-model"]
        with patch("DyberPet.assistant.ui.list_local_models", side_effect=discover):
            self.dialog.detect_models()
            self.wait_for(entered.is_set)
            self.dialog.llm_model.setText("new-user-choice")
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.llm_model.text(), "new-user-choice")

    def test_old_address_result_is_discarded_even_after_editing_back(self):
        release, entered = self.gate(), threading.Event()
        captured = {}
        def discover(url, *, cancel_token=None):
            captured["token"] = cancel_token
            entered.set()
            release.wait(2)
            return ["old-address-model"]
        original = self.dialog.llm_endpoint.text()
        with patch("DyberPet.assistant.ui.list_local_models", side_effect=discover):
            self.dialog.detect_models()
            self.wait_for(entered.is_set)
            self.dialog.llm_endpoint.setText("http://127.0.0.1:2345")
            self.dialog.llm_endpoint.setText(original)
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.model_selector.count(), 0)
        self.assertEqual(self.dialog.llm_model.text(), "")
        self.assertIn("重新检查", self.dialog.model_status.text())
        from DyberPet.assistant.request_control import RequestCancelled
        with self.assertRaises(RequestCancelled):
            captured["token"].raise_if_cancelled()

    def test_old_address_error_does_not_replace_new_setup_hint(self):
        release, entered = self.gate(), threading.Event()
        def discover(*args, **kwargs):
            entered.set()
            release.wait(2)
            raise RuntimeError("obsolete endpoint failure")
        with patch("DyberPet.assistant.ui.list_local_models", side_effect=discover):
            self.dialog.detect_models()
            self.wait_for(entered.is_set)
            self.dialog.llm_endpoint.setText("http://127.0.0.1:2345")
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertNotIn("obsolete", self.dialog.status.text())
        self.assertNotIn("obsolete", self.dialog.chat_log.toPlainText())

    def test_cancel_check_keeps_question_attachment_and_allows_retry(self):
        from DyberPet.assistant.request_control import RequestCancelled
        release, entered = self.gate(), threading.Event()
        self.dialog.message.setText("我的问题")
        self.dialog._pending_file_context = {"name": "a.md", "content": "资料"}
        def discover(*args, cancel_token=None, **kwargs):
            entered.set()
            release.wait(2)
            cancel_token.raise_if_cancelled()
            return ["obsolete"]
        with patch("DyberPet.assistant.ui.list_local_models", side_effect=discover):
            self.dialog.detect_models()
            self.wait_for(entered.is_set)
            self.dialog.stop_generation_button.click()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.message.text(), "我的问题")
        self.assertEqual(self.dialog._pending_file_context["content"], "资料")
        self.assertTrue(self.dialog.detect_button.isEnabled())
        self.assertIn("停止", self.dialog.model_status.text())
        with patch("DyberPet.assistant.ui.list_local_models", return_value=["retry-model"]):
            self.dialog.detect_models()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.llm_model.text(), "retry-model")

    def test_second_check_does_not_replace_running_worker(self):
        release, entered = self.gate(), threading.Event()
        requests = []
        def discover(url, **kwargs):
            requests.append(url)
            entered.set()
            release.wait(2)
            return ["one"]
        with patch("DyberPet.assistant.ui.list_local_models", side_effect=discover):
            self.dialog.detect_models()
            self.wait_for(entered.is_set)
            job = self.dialog._job
            self.assertFalse(self.dialog.detect_button.isEnabled())
            self.dialog.detect_models()
            self.assertIs(self.dialog._job, job)
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(len(requests), 1)
        self.assertTrue(self.dialog.detect_button.isEnabled())

    def test_missing_model_keeps_input_and_attachment_for_both_entries(self):
        self.dialog.message.setText("保留我的请求")
        source = {"name": "ref.md", "content": "资料"}
        self.dialog._pending_file_context = source.copy()
        self.dialog.send_message()
        self.assertIsNone(self.dialog._job)
        self.assertEqual(self.dialog.message.text(), "保留我的请求")
        self.assertEqual(self.dialog._pending_file_context, source)
        self.dialog.propose_task()
        self.assertIsNone(self.dialog._job)
        self.assertEqual(self.dialog.message.text(), "保留我的请求")
        self.assertIn("模型", self.dialog.model_status.text())

    def test_invalid_endpoint_never_consumes_question(self):
        self.dialog.llm_model.setText("manual-model")
        self.dialog.llm_endpoint.setText("https://example.com:1234")
        self.dialog.message.setText("保留")
        self.dialog.send_message()
        self.assertIsNone(self.dialog._job)
        self.assertEqual(self.dialog.message.text(), "保留")
        self.assertIn("127.0.0.1", self.dialog.model_status.text())

    def test_failed_chat_restores_original_question_but_preserves_new_input(self):
        self.dialog.llm_model.setText("manual-model")
        self.dialog.message.setText("原问题")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=RuntimeError("offline")):
            self.dialog.send_message()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.message.text(), "原问题")
        release, entered = self.gate(), threading.Event()
        def stream(*args, **kwargs):
            entered.set()
            release.wait(2)
            raise RuntimeError("offline again")
        with patch("DyberPet.assistant.ui.stream_local_chat", side_effect=stream):
            self.dialog.send_message()
            self.wait_for(entered.is_set)
            self.dialog.message.setText("新问题")
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog.message.text(), "新问题")

    def test_voice_check_reports_tts_separately_and_never_starts_audio(self):
        self.dialog.voice_check_button.click()
        self.wait_for(lambda: self.dialog._job is None)
        self.assertTrue(self.dialog.voice_status.text())
        self.assertTrue(self.dialog.tts_status.text())
        self.assertIsNone(self.dialog._listen_stop_event)
        self.assertIsNone(self.dialog._speech_stop_event)
        self.assertFalse(self.dialog.stop_listen_button.isEnabled())
        self.assertFalse(self.dialog.stop_speak_button.isEnabled())

    def test_voice_result_for_old_path_cannot_mark_new_path_ready(self):
        from DyberPet.assistant.voice_readiness import VoiceReadiness
        release, entered = self.gate(), threading.Event()
        def inspect(path):
            entered.set()
            release.wait(2)
            return VoiceReadiness(True, "obsolete ready", True, "old tts")
        with patch("DyberPet.assistant.ui.inspect_voice_readiness", side_effect=inspect):
            self.dialog.check_voice_setup()
            self.wait_for(entered.is_set)
            self.dialog.voice_model.setText(str(Path(self.tmp.name) / "new-model"))
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertNotIn("obsolete", self.dialog.voice_status.text())
        self.assertIn("检查", self.dialog.voice_status.text())

    def test_settings_persist_selected_model_as_original_string_schema(self):
        from DyberPet.assistant.preferences import load, save
        prefs_path = Path(self.tmp.name) / "prefs.json"
        with patch("DyberPet.assistant.ui.list_local_models", return_value=["one", "two"]):
            self.dialog.detect_models()
            self.wait_for(lambda: self.dialog._job is None)
        self.dialog.model_selector.setCurrentIndex(1)
        with patch("DyberPet.assistant.ui.save_preferences",
                   side_effect=lambda data: save(data, prefs_path)):
            self.dialog.save_preferences()
        self.assertEqual(load(prefs_path)["llm_model"], "two")

    def test_close_during_discovery_cancels_and_discards_pending_result(self):
        release, entered = self.gate(), threading.Event()
        def discover(*args, **kwargs):
            entered.set()
            release.wait(2)
            return ["late"]
        self.dialog.show()
        with patch("DyberPet.assistant.ui.list_local_models", side_effect=discover):
            self.dialog.detect_models()
            self.wait_for(entered.is_set)
            self.dialog.close()
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
            QTest.qWait(30)
        self.assertFalse(self.dialog.isVisible())
        self.assertEqual(self.dialog.llm_model.text(), "")

    def test_reopen_after_cancelled_setup_never_shows_a_running_check(self):
        from DyberPet.assistant.voice_readiness import VoiceReadiness
        for kind in ("models", "voice"):
            with self.subTest(kind=kind):
                release, entered = self.gate(), threading.Event()
                def check(*args, **kwargs):
                    entered.set()
                    release.wait(2)
                    return (["late"] if kind == "models" else
                            VoiceReadiness(True, "late", True, "late"))
                target = ("list_local_models" if kind == "models"
                          else "inspect_voice_readiness")
                self.dialog.show()
                with patch("DyberPet.assistant.ui." + target, side_effect=check):
                    if kind == "models":
                        self.dialog.detect_models()
                    else:
                        self.dialog.check_voice_setup()
                    self.wait_for(entered.is_set)
                    self.dialog.close()
                    release.set()
                    self.wait_for(lambda: self.dialog._job is None)
                    QTest.qWait(30)
                self.dialog.show()
                labels = ([self.dialog.model_status] if kind == "models" else
                          [self.dialog.voice_status, self.dialog.tts_status])
                for label in labels:
                    self.assertNotIn("正在", label.text())
                    self.assertIn("重新检查", label.text())

    def test_character_switch_ends_inflight_setup_status(self):
        release, entered = self.gate(), threading.Event()
        def discover(*args, **kwargs):
            entered.set()
            release.wait(2)
            return ["late"]
        with patch("DyberPet.assistant.ui.list_local_models", side_effect=discover):
            self.dialog.detect_models()
            self.wait_for(entered.is_set)
            self.dialog.set_character("咕嘎")
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertNotIn("正在", self.dialog.model_status.text())
        self.assertIn("重新检查", self.dialog.model_status.text())

    def test_ppl_connection_failure_does_not_direct_user_to_model_service(self):
        from DyberPet.assistant.persona import AssistantServiceError
        self.dialog.ppl_enabled.setChecked(True)
        self.dialog.llm_model.setText("manual-model")
        for error in (AssistantServiceError("PPL unavailable", code="connection"),
                      AssistantServiceError("PPL route missing", code="http", status_code=404)):
            with self.subTest(error=error.code):
                self.dialog.message.setText("保留这个问题")
                with patch("DyberPet.assistant.ui.PPLCharacterClient.state", side_effect=error):
                    self.dialog.send_message()
                    self.wait_for(lambda: self.dialog._job is None)
                self.assertNotIn("LM Studio", self.dialog.status.text())
                self.assertNotIn("OpenAI", self.dialog.status.text())
                self.assertEqual(self.dialog.message.text(), "保留这个问题")


if __name__ == "__main__":
    unittest.main()
