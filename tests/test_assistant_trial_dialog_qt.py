"""Trial controls, transient text and frozen exports on actual Qt widgets."""
import copy
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QScrollArea
except ImportError:
    QApplication = QTest = None


def report_fixture():
    return {
        "schema_version": 1,
        "environment": {
            "system": "Linux", "architecture": "x86_64",
            "python_version": "3.12.9", "qt_version": "6.8.3",
            "pyside_version": "6.8.3", "mode": "source",
            "build_info_status": "missing", "checkout_commit": None,
            "candidate": None,
        },
        "observations": [{
            "id": 1, "kind": "listen", "outcome": "cancelled",
            "elapsed_ms": 1500, "first_text_ms": None, "ready_ms": 125,
            "stop_requested_ms": 1200, "stop_settled_ms": 300,
            "stop_reason": "user", "displayed_chars": 0,
            "result_chars": 8, "model_count": None,
            "recognition_ready": True, "tts_ready": None,
            "engine_completed": None, "error_code": None,
            "cpu_seconds": 0.25, "cpu_percent_one_core": 16.7,
            "rss_max_bytes": 33554432, "sample_count": 3,
        }],
        "feedback": {
            "model_reply": "not_checked", "recognition": "not_checked",
            "speech": "not_checked",
        },
        "limitations": [],
    }


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt smoke CI")
class AssistantTrialDialogQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.assertIsNotNone(
            importlib.util.find_spec("DyberPet.assistant.trial_dialog"),
            "The independent trial dialog is not implemented yet")
        from DyberPet.assistant.trial_dialog import TrialDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.report = report_fixture()
        self.provider_reads = 0
        self.provider_error = None

        def provider():
            self.provider_reads += 1
            if self.provider_error is not None:
                raise self.provider_error
            return self.report

        self.dialog = TrialDialog(provider)
        self.addCleanup(self.dialog.deleteLater)
        self.addCleanup(self.dialog.close)
        self.events = []
        for name in ("model_test_requested", "speech_test_requested",
                     "listen_requested", "stop_requested", "clear_requested"):
            getattr(self.dialog, name).connect(
                lambda name=name: self.events.append(name))
        self.dialog.feedback_changed.connect(
            lambda key, value: self.events.append((key, value)))

    def show_dialog(self):
        self.dialog.show()
        self.app.processEvents()

    def preview_real_report(self):
        from DyberPet.assistant.trial_records import TrialRecorder
        recorder = TrialRecorder(environment=self.report["environment"])
        run_id = recorder.begin("model_probe")
        recorder.text(run_id, 6)
        recorder.finish(run_id, "completed")
        self.report = recorder.snapshot()
        self.show_dialog()
        self.dialog.preview_report_button.click()
        return json.loads(self.dialog.report_preview.toPlainText())

    def test_open_and_refresh_only_read_snapshot_without_requesting_work(self):
        self.assertEqual(self.provider_reads, 0)
        self.show_dialog()
        self.dialog.refresh_report()
        self.assertGreaterEqual(self.provider_reads, 2)
        self.assertEqual(self.events, [])
        self.assertFalse(self.dialog.isModal())
        self.assertFalse(self.dialog.report_preview.isVisible())
        self.assertFalse(self.dialog.export_button.isEnabled())
        self.assertEqual(self.dialog.probe_preview.toPlainText(), "")

    def test_action_controls_only_emit_their_matching_requests(self):
        self.show_dialog()
        for button in (self.dialog.model_test_button,
                       self.dialog.speech_test_button, self.dialog.listen_button):
            button.click()
        self.dialog.set_busy(True, can_stop=True)
        self.dialog.stop_button.click()
        self.dialog.set_busy(False)
        self.dialog.clear_button.click()
        self.assertEqual(self.events, [
            "model_test_requested", "speech_test_requested", "listen_requested",
            "stop_requested", "clear_requested"])

    def test_busy_controls_prevent_new_requests_until_worker_settles(self):
        self.show_dialog()
        self.dialog.set_busy(True, can_stop=True)
        for button in (self.dialog.model_test_button,
                       self.dialog.speech_test_button, self.dialog.listen_button):
            self.assertFalse(button.isEnabled())
            button.click()
        self.assertEqual(self.events, [])
        self.assertTrue(self.dialog.stop_button.isEnabled())
        self.dialog.set_busy(True, can_stop=False)
        self.dialog.stop_button.click()
        self.assertEqual(self.events, [])
        self.dialog.set_busy(False, can_stop=True)
        self.assertFalse(self.dialog.stop_button.isEnabled())
        self.assertTrue(self.dialog.model_test_button.isEnabled())
        self.assertTrue(self.dialog.speech_test_button.isEnabled())
        self.assertTrue(self.dialog.listen_button.isEnabled())

    def test_running_operation_cannot_clear_its_own_observations(self):
        self.show_dialog()
        self.dialog.set_busy(True, can_stop=True)
        self.dialog.clear_button.click()
        self.assertEqual(self.events, [])
        self.dialog.set_busy(False)
        self.dialog.clear_button.click()
        self.assertEqual(self.events, ["clear_requested"])

    def test_only_user_feedback_changes_emit_and_success_never_means_satisfied(self):
        self.report["observations"][0]["outcome"] = "completed"
        self.report["observations"][0]["engine_completed"] = True
        self.show_dialog()
        for combo in self.dialog.feedback_combos.values():
            self.assertEqual(combo.currentData(), "not_checked")
        combo = self.dialog.feedback_combos["speech"]
        combo.setCurrentIndex(combo.findData("problem"))
        self.assertEqual(self.events, [("speech", "problem")])
        self.report["feedback"]["model_reply"] = "satisfied"
        self.dialog.refresh_report()
        self.assertEqual(self.dialog.feedback_combos["model_reply"].currentData(),
                         "satisfied")
        self.assertEqual(self.events, [("speech", "problem")])

    def test_probe_is_plain_text_bounded_and_excluded_from_report(self):
        self.show_dialog()
        text = "<b>私密试聊</b>" + "字" * 4100
        self.dialog.set_probe_text(text)
        self.assertTrue(self.dialog.probe_preview.isReadOnly())
        self.assertEqual(self.dialog.probe_preview.toPlainText(), text[:4000])
        self.dialog.preview_report_button.click()
        self.assertNotIn("私密试聊", self.dialog.report_preview.toPlainText())
        self.assertTrue(self.dialog.report_preview.isReadOnly())
        self.dialog.clear_probe()
        self.assertEqual(self.dialog.probe_preview.toPlainText(), "")

    def test_stopped_recognition_keeps_text_and_explains_resource_scope(self):
        self.show_dialog()
        text = self.dialog.observations_view.toPlainText()
        self.assertIn("连续监听", text)
        self.assertIn("已停止", text)
        self.assertIn("8 字", text)
        self.assertNotIn("失败", text)
        self.assertIn("32.0 MiB", text)
        self.assertIn("16.7%", text)
        self.assertNotIn("cancelled", text)
        self.assertNotIn("listen", text)
        scope = self.dialog.resource_note.text()
        self.assertIn("桌宠进程", scope)
        self.assertIn("独立模型服务", scope)
        self.assertIn("采样最大值", scope)
        self.assertIn("未测量", scope)

    def test_unknown_metrics_and_missing_ready_are_not_reported_as_zero(self):
        observation = self.report["observations"][0]
        for name in ("ready_ms", "cpu_seconds", "cpu_percent_one_core", "rss_max_bytes"):
            observation[name] = None
        self.show_dialog()
        text = self.dialog.observations_view.toPlainText()
        self.assertIn("未观察到就绪", text)
        self.assertIn("未采样", text)
        self.assertNotIn("0.0 MiB", text)
        self.assertNotIn("0.0%", text)

    def test_statuses_use_fixed_explanations_and_never_show_raw_error_strings(self):
        self.report["observations"][0].update(
            outcome="failed", error_code="connection", result_chars=None)
        self.show_dialog()
        self.assertIn("连接", self.dialog.observations_view.toPlainText())
        self.report["observations"][0]["error_code"] = "<b>SECRET host/path</b>"
        self.dialog.refresh_report()
        self.assertNotIn("SECRET", self.dialog.observations_view.toPlainText())
        self.assertIn("失败", self.dialog.observations_view.toPlainText())

    def test_refresh_timer_runs_only_while_visible_and_close_requests_no_stop(self):
        self.dialog.refresh_timer.setInterval(10)
        QTest.qWait(30)
        self.assertEqual(self.provider_reads, 0)
        self.show_dialog()
        before = self.provider_reads
        QTest.qWait(35)
        self.assertGreater(self.provider_reads, before)
        self.dialog.hide()
        before = self.provider_reads
        QTest.qWait(35)
        self.assertEqual(self.provider_reads, before)
        self.assertFalse(self.dialog.refresh_timer.isActive())
        self.dialog.show()
        self.assertTrue(self.dialog.refresh_timer.isActive())
        self.dialog.set_busy(True, can_stop=True)
        self.dialog.close()
        before = self.provider_reads
        QTest.qWait(35)
        self.assertEqual(self.provider_reads, before)
        self.assertFalse(self.dialog.refresh_timer.isActive())
        self.assertEqual(self.events, [])

    def test_provider_failure_stays_inside_dialog_and_keeps_stop_available(self):
        self.show_dialog()
        self.dialog.set_busy(True, can_stop=True)
        self.provider_error = RuntimeError("SECRET device path")
        self.dialog.refresh_report()
        self.assertTrue(self.dialog.isVisible())
        self.assertTrue(self.dialog.stop_button.isEnabled())
        self.assertNotIn("SECRET", self.dialog.status_label.text())
        self.assertTrue(self.dialog.status_label.text())
        self.assertEqual(self.events, [])

    def test_small_window_keeps_controls_reachable_by_scrolling(self):
        self.show_dialog()
        self.dialog.resize(360, 300)
        self.app.processEvents()
        scroll = self.dialog.findChild(QScrollArea)
        self.assertIsNotNone(scroll)
        self.assertLessEqual(self.dialog.minimumHeight(), 300)
        self.assertLessEqual(self.dialog.minimumWidth(), 360)
        self.assertGreater(scroll.verticalScrollBar().maximum(), 0)
        scroll.ensureWidgetVisible(self.dialog.preview_report_button)
        self.app.processEvents()
        point = self.dialog.preview_report_button.mapTo(scroll.viewport(),
                                                        self.dialog.preview_report_button.rect().center())
        self.assertTrue(scroll.viewport().rect().contains(point))

    def test_export_uses_frozen_reviewed_snapshot_despite_live_changes(self):
        reviewed = self.preview_real_report()
        self.report["feedback"]["speech"] = "problem"
        self.report["observations"][0]["displayed_chars"] = 999
        self.dialog.refresh_report()
        self.assertEqual(json.loads(self.dialog.report_preview.toPlainText()), reviewed)
        target = Path(self.tmp.name) / "reviewed.json"
        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                   return_value=(str(target), "JSON 报告 (*.json)")):
            self.dialog.export_button.click()
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), reviewed)
        self.assertIn("已保存", self.dialog.status_label.text())
        self.assertEqual(self.events, [])

    def test_explicit_preview_refresh_replaces_frozen_snapshot(self):
        self.preview_real_report()
        self.report["feedback"]["recognition"] = "problem"
        self.dialog.preview_report_button.click()
        reviewed = json.loads(self.dialog.report_preview.toPlainText())
        self.assertEqual(reviewed["feedback"]["recognition"], "problem")

    def test_cancel_export_leaves_preview_and_writes_nothing(self):
        reviewed = self.preview_real_report()
        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("", "")):
            self.dialog.export_button.click()
        self.assertEqual(list(Path(self.tmp.name).iterdir()), [])
        self.assertEqual(json.loads(self.dialog.report_preview.toPlainText()), reviewed)
        self.assertTrue(self.dialog.export_button.isEnabled())
        self.assertEqual(self.events, [])

    def test_existing_file_is_never_overwritten_or_forwarded_to_parent_errors(self):
        self.preview_real_report()
        self.dialog.set_busy(True, can_stop=True)
        target = Path(self.tmp.name) / "exists.json"
        target.write_bytes(b"keep this existing file")
        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                   return_value=(str(target), "")):
            self.dialog.export_button.click()
        self.assertEqual(target.read_bytes(), b"keep this existing file")
        self.assertIn("已有", self.dialog.status_label.text())
        self.assertTrue(self.dialog.stop_button.isEnabled())
        self.assertTrue(self.dialog.export_button.isEnabled())
        self.assertEqual(self.events, [])

    def test_failed_export_can_be_retried_without_changing_operation_state(self):
        reviewed = self.preview_real_report()
        self.dialog.set_busy(True, can_stop=True)
        missing = Path(self.tmp.name) / "SECRET-missing" / "report.json"
        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                   return_value=(str(missing), "")):
            self.dialog.export_button.click()
        self.assertIn("失败", self.dialog.status_label.text())
        self.assertNotIn("SECRET", self.dialog.status_label.text())
        self.assertTrue(self.dialog.stop_button.isEnabled())
        target = Path(self.tmp.name) / "retry.json"
        with patch("PySide6.QtWidgets.QFileDialog.getSaveFileName",
                   return_value=(str(target), "")):
            self.dialog.export_button.click()
        self.assertEqual(json.loads(target.read_text(encoding="utf-8")), reviewed)
        self.assertEqual(self.events, [])

    def test_preview_rejects_oversize_or_nonfinite_data_without_enabling_save(self):
        self.show_dialog()
        for bad_report in (
                dict(copy.deepcopy(self.report), limitations=["字" * 24000]),
                dict(copy.deepcopy(self.report), schema_version=float("nan"))):
            with self.subTest(report_type=type(bad_report["schema_version"]).__name__):
                self.report = bad_report
                self.dialog.preview_report_button.click()
                self.assertFalse(self.dialog.export_button.isEnabled())
                self.assertEqual(self.dialog.report_preview.toPlainText(), "")
                self.assertTrue(self.dialog.status_label.text())

    def test_clear_removes_frozen_report_before_requesting_new_records(self):
        self.preview_real_report()
        self.dialog.clear_button.click()
        self.assertEqual(self.dialog.report_preview.toPlainText(), "")
        self.assertFalse(self.dialog.export_button.isEnabled())
        self.assertEqual(self.events, ["clear_requested"])


if __name__ == "__main__":
    unittest.main()
