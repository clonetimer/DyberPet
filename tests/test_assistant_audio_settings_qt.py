"""Audio choices through actual Qt workers and local preference storage."""
import builtins
import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtCore import QCoreApplication, QEvent, QTimer, Qt
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt CI")
class AudioSettingsQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        from DyberPet.assistant.preferences import defaults
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.gates = []
        self.dialogs = []
        self.addCleanup(self.dispose)
        with patch("DyberPet.assistant.ui.load_preferences", new=defaults):
            self.dialog = PetAssistantDialog(
                "Doro", self.root / "files", store_path=self.root / "history.sqlite3")
        self.dialogs.append(self.dialog)
        self.dialog.show()
        self.app.processEvents()
        self.assertTrue(hasattr(self.dialog, "audio_settings"),
                        "Users need shared microphone, voice and rate controls")
        self.panel = self.dialog.audio_settings

    def dispose(self):
        for gate in self.gates:
            gate.set()
        for dialog in self.dialogs:
            dialog.close()
            if dialog._job is not None:
                self.assertTrue(dialog._job.wait(3000))
                self.app.processEvents()
            dialog.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    def gate(self):
        event = threading.Event()
        self.gates.append(event)
        return event

    def wait_for(self, predicate, timeout=3):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.app.processEvents()
            if predicate():
                return
            time.sleep(.005)
        self.fail("Qt operation did not reach the expected state: " + self.dialog.status.text())

    @staticmethod
    def catalog():
        from DyberPet.assistant.voice_devices import AudioOptions, MicrophoneInfo, SystemVoiceInfo
        return AudioOptions(
            (MicrophoneInfo("USB 麦克风", "WASAPI", 2),
             MicrophoneInfo("USB 麦克风", "MME", 7)),
            (SystemVoiceInfo("voice-zh", "中文系统声音", ("zh-CN",)),
             SystemVoiceInfo("voice-en", "English voice", ("en-US",))),
            "发现两个输入设备", "发现两个系统音色")

    def choose(self, voice="voice-zh", rate=145):
        self.panel.apply_catalog(self.catalog())
        self.panel.device_selector.setCurrentIndex(1)
        self.panel.voice_selector.setCurrentIndex(
            self.panel.voice_selector.findData(voice))
        self.panel.rate_spin.setValue(rate)

    def test_opening_and_expanding_settings_never_imports_audio_drivers(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        from DyberPet.assistant.preferences import defaults
        original = builtins.__import__
        def guarded(name, *args, **kwargs):
            if name.split(".")[0] in {"sounddevice", "vosk", "pyttsx3"}:
                raise AssertionError("Opening settings must remain passive: " + name)
            return original(name, *args, **kwargs)
        with patch("builtins.__import__", new=guarded), \
                patch("DyberPet.assistant.ui.load_preferences", new=defaults):
            other = PetAssistantDialog("Kitty", self.root / "other",
                                       store_path=self.root / "other.sqlite3")
            self.dialogs.append(other)
            other.show()
            other.audio_settings.toggle_button.click()
            self.app.processEvents()
        self.assertIsNone(other._job)
        self.assertIsNone(other.audio_settings.microphone())
        self.assertEqual(other.audio_settings.voice_id(), "")
        self.assertEqual(other.audio_settings.rate(), 170)

    def test_explicit_refresh_runs_on_worker_and_preserves_selected_identity(self):
        self.choose()
        main_thread = threading.get_ident()
        threads = []
        release, entered = self.gate(), threading.Event()
        def inspect(stop_event=None):
            threads.append(threading.get_ident())
            entered.set()
            release.wait(2)
            return self.catalog()
        with patch("DyberPet.assistant.ui.inspect_audio_options", new=inspect):
            self.panel.refresh_button.click()
            self.wait_for(entered.is_set)
            self.assertFalse(self.panel.refresh_button.isEnabled())
            self.assertFalse(self.panel.preview_button.isEnabled())
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertTrue(threads and all(thread != main_thread for thread in threads))
        self.assertEqual(self.panel.microphone(), {"name": "USB 麦克风", "host_api": "WASAPI"})
        self.assertEqual((self.panel.voice_id(), self.panel.rate()), ("voice-zh", 145))
        self.assertEqual(self.panel.voice_selector.count(), 3)
        self.assertTrue(self.panel.refresh_button.isEnabled())
        report = json.dumps(self.dialog._trial_recorder.snapshot(), ensure_ascii=False)
        self.assertNotIn("USB 麦克风", report)
        self.assertNotIn("voice-zh", report)

    def test_unavailable_saved_choices_are_retained_instead_of_replaced_with_default(self):
        self.panel.set_values({"name": "Missing microphone", "host_api": "API"},
                              "missing-voice", 180)
        self.panel.apply_catalog(self.catalog())
        self.assertEqual(self.panel.microphone(), {"name": "Missing microphone", "host_api": "API"})
        self.assertEqual(self.panel.voice_id(), "missing-voice")
        self.assertIn("不可用", self.panel.device_selector.currentText())
        self.assertIn("不可用", self.panel.voice_selector.currentText())

    def test_role_voice_profiles_and_global_microphone_survive_save_and_reopen(self):
        from DyberPet.assistant.preferences import load, save
        from DyberPet.assistant.ui import PetAssistantDialog
        self.choose()
        self.dialog.set_character("Kitty")
        self.assertEqual((self.panel.voice_id(), self.panel.rate()), ("", 170))
        self.panel.voice_selector.setCurrentIndex(self.panel.voice_selector.findData("voice-en"))
        self.panel.rate_spin.setValue(210)
        self.dialog.set_character("Doro")
        self.assertEqual((self.panel.voice_id(), self.panel.rate()), ("voice-zh", 145))
        destination = self.root / "assistant.json"
        with patch("DyberPet.assistant.ui.save_preferences", new=lambda data: save(data, destination)):
            self.dialog.save_preferences()
        with patch("DyberPet.assistant.ui.load_preferences", new=lambda: load(destination)):
            other = PetAssistantDialog("Kitty", self.root / "other",
                                       store_path=self.root / "other.sqlite3")
        self.dialogs.append(other)
        self.assertEqual((other.audio_settings.voice_id(), other.audio_settings.rate()),
                         ("voice-en", 210))
        self.assertEqual(other.audio_settings.microphone(),
                         {"name": "USB 麦克风", "host_api": "WASAPI"})

    def test_manual_trial_and_auto_reading_share_selected_voice_and_rate(self):
        self.choose()
        self.dialog.message.setText("保留的草稿")
        self.dialog._last_reply = "完整回复" * 150
        spoken = []
        def speak(text, stop_event, *, rate, voice_id, on_ready, on_progress, **kwargs):
            spoken.append((text, rate, voice_id))
            on_ready()
            on_progress(1, 2)
            on_progress(2, 2)
            return True
        with patch("DyberPet.assistant.ui.speak_interruptible", new=speak):
            self.dialog.read_reply()
            self.wait_for(lambda: self.dialog._job is None)
            self.panel.preview_button.click()
            self.wait_for(lambda: self.dialog._job is None)
            self.dialog.auto_speak.setChecked(True)
            self.dialog._auto_read_reply()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(len(spoken), 3)
        self.assertEqual(spoken[0], ("完整回复" * 150, 145, "voice-zh"))
        self.assertEqual(spoken[1][1:], (145, "voice-zh"))
        self.assertEqual(spoken[2], spoken[0])
        self.assertEqual(self.dialog.message.text(), "保留的草稿")
        self.assertEqual(self.dialog._last_reply, "完整回复" * 150)

    def test_manual_dictation_uses_selected_microphone_and_preserves_final_text(self):
        self.choose()
        self.dialog.voice_model.setText("/model")
        selections = []
        def capture(model, stop_event, *, microphone, on_ready, **kwargs):
            selections.append(microphone)
            on_ready()
            return "检查这段识别文字"
        with patch("DyberPet.assistant.ui.recognize_until_stopped", new=capture):
            self.dialog.listen_continuously()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(selections, [{"name": "USB 麦克风", "host_api": "WASAPI"}])
        self.assertEqual(self.dialog.message.text(), "检查这段识别文字")

    def test_audio_change_and_revert_revokes_pending_auto_read_but_allows_manual_read(self):
        self.choose()
        self.dialog.auto_speak.setChecked(True)
        spoken = []
        def speak(text, stop_event, *, rate, voice_id, on_ready, **kwargs):
            spoken.append((text, rate, voice_id))
            on_ready()
            return True
        with patch("DyberPet.assistant.ui.speak_interruptible", new=speak):
            self.dialog._message_reply("这条回复仍可手动朗读")
            self.panel.rate_spin.setValue(200)
            self.panel.rate_spin.setValue(145)
            elapsed = threading.Event()
            QTimer.singleShot(180, elapsed.set)
            self.wait_for(elapsed.is_set)
            self.assertEqual(spoken, [])
            self.assertEqual(self.dialog._last_reply, "这条回复仍可手动朗读")
            self.dialog.read_reply()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(spoken, [("这条回复仍可手动朗读", 145, "voice-zh")])

    def test_unchanged_settings_auto_read_reply_with_current_voice_once(self):
        self.choose()
        self.dialog.auto_speak.setChecked(True)
        spoken = []
        def speak(text, stop_event, *, rate, voice_id, on_ready, **kwargs):
            spoken.append((text, rate, voice_id))
            on_ready()
            return True
        with patch("DyberPet.assistant.ui.speak_interruptible", new=speak):
            self.dialog._message_reply("设置未变，自动朗读")
            self.wait_for(lambda: len(spoken) == 1 and self.dialog._job is None)
        self.assertEqual(spoken, [("设置未变，自动朗读", 145, "voice-zh")])

    def test_changing_audio_settings_cancels_old_speech_and_rejects_late_progress(self):
        self.choose()
        release, entered = self.gate(), threading.Event()
        old_events = []
        def speak(text, stop_event, *, on_ready, on_progress, **kwargs):
            old_events.append(stop_event)
            on_ready()
            on_progress(0, 3)
            entered.set()
            release.wait(2)
            on_progress(2, 3)
            return not stop_event.is_set()
        with patch("DyberPet.assistant.ui.speak_interruptible", new=speak):
            self.dialog.try_speech()
            self.wait_for(lambda: entered.is_set() and self.dialog._speech_has_started)
            self.panel.rate_spin.setValue(200)
            self.panel.rate_spin.setValue(145)
            self.assertTrue(old_events[0].is_set())
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(self.dialog._activity_outcome, "cancelled")
        self.assertNotIn("2/3", self.dialog.status.text())
        self.assertTrue(self.panel.preview_button.isEnabled())

    def test_changing_microphone_discards_previous_devices_pending_transcript(self):
        self.choose()
        self.dialog.voice_model.setText("/model")
        self.dialog.message.setText("保留的草稿")
        entered, release = threading.Event(), self.gate()
        stopped = []
        def capture(model, stop_event, *, on_ready, **kwargs):
            on_ready()
            entered.set()
            release.wait(2)
            stopped.append(stop_event.is_set())
            return "旧设备的迟到结果"
        with patch("DyberPet.assistant.ui.recognize_until_stopped", new=capture):
            self.dialog.listen_continuously()
            self.wait_for(entered.is_set)
            self.panel.device_selector.setCurrentIndex(2)
            release.set()
            self.wait_for(lambda: self.dialog._job is None)
        self.assertEqual(stopped, [True])
        self.assertEqual(self.dialog.message.text(), "保留的草稿")

    def test_close_during_catalog_refresh_cancels_and_discards_returned_catalog(self):
        release, entered = self.gate(), threading.Event()
        cancelled = []
        def inspect(stop_event=None):
            entered.set()
            release.wait(2)
            cancelled.append(stop_event.is_set())
            return self.catalog()
        with patch("DyberPet.assistant.ui.inspect_audio_options", new=inspect):
            self.panel.refresh_button.click()
            self.wait_for(entered.is_set)
            self.dialog.close()
            release.set()
            self.wait_for(lambda: self.dialog._job is None and not self.dialog.isVisible())
        self.assertEqual(cancelled, [True])
        self.assertEqual(self.panel.voice_selector.count(), 1)

    def test_catalog_refresh_preserves_voice_session_identity_without_signal_churn(self):
        self.choose()
        changes = []
        self.panel.settings_changed.connect(lambda: changes.append(True))
        before = self.panel.snapshot()
        self.panel.apply_catalog(self.catalog())
        self.assertEqual(self.panel.snapshot(), before)
        self.assertEqual(changes, [])

    def test_expanded_audio_settings_fit_small_window_and_fixed_voice_controls_remain_visible(self):
        self.dialog.resize(800, 600)
        self.panel.toggle_button.click()
        self.app.processEvents()
        self.dialog.content_scroll.verticalScrollBar().setValue(
            self.dialog.content_scroll.verticalScrollBar().maximum())
        self.app.processEvents()
        self.assertEqual(self.dialog.content_scroll.horizontalScrollBar().maximum(), 0)
        for button in (self.dialog.voice_chat_button, self.dialog.voice_interrupt_button,
                       self.dialog.voice_end_button):
            location = button.mapTo(self.dialog, button.rect().center())
            self.assertTrue(self.dialog.rect().contains(location))
        self.assertTrue(self.panel.details.isVisible())


if __name__ == "__main__":
    unittest.main()
