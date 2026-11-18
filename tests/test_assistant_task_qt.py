"""Offscreen task confirmation with real workspace writes and audit records."""
import os
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt smoke CI")
class AssistantTaskReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.task_review import TaskReviewDialog
        from DyberPet.assistant.action_runtime import ActionRuntime
        from DyberPet.assistant.files import PetWorkspace

        self.dialog_type = TaskReviewDialog
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.workspace = PetWorkspace(root / "工作区")
        self.audit_path = root / "audit.sqlite3"
        self.runtime = ActionRuntime(self.workspace, self.audit_path)
        self.first = self.workspace.root / "第一份.md"
        self.second = self.workspace.root / "第二份.txt"
        self.content = "  中文和 Markdown\n\n<em>逐字审核</em>\n" + "全文" * 900 + "\n"

    def open_review(self, *, scope_is_current=None, content=None):
        from DyberPet.assistant.task_plan import TaskPlan, TaskSession, TaskStep

        plan = TaskPlan("<b>文件任务</b>", (
            TaskStep("create_note", self.first.name, self.content if content is None else content),
            TaskStep("create_file", self.second.name, "单独批准第二份"),
        ))
        self.session = TaskSession(plan, self.runtime)
        self.dialog = self.dialog_type(self.session, scope_is_current=scope_is_current)
        self.addCleanup(self.dialog.close)
        self.dialog.show()
        self.app.processEvents()

    def test_preview_shows_full_plain_text_and_prepares_only_the_first_step(self):
        self.open_review()

        self.assertFalse(self.dialog.isModal())
        self.assertEqual(self.dialog.title_label.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(self.dialog.title_label.text(), "<b>文件任务</b>")
        self.assertEqual(self.dialog.workspace_label.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(self.dialog.workspace_label.text(), str(self.workspace.root))
        self.assertEqual(self.dialog.target_label.textFormat(), Qt.TextFormat.PlainText)
        self.assertEqual(self.dialog.target_label.text(), str(self.first))
        self.assertEqual(self.dialog.content_view.toPlainText(), self.content)
        self.assertTrue(self.dialog.content_view.isReadOnly())
        self.assertIn(self.first.name, self.dialog.steps_view.toPlainText())
        self.assertIn(self.second.name, self.dialog.steps_view.toPlainText())
        self.assertEqual(self.session.state, "awaiting_approval")
        self.assertEqual(self.workspace.list_files(), [])
        audit = self.runtime.audit_log()
        self.assertEqual([(row["status"], row["target"]) for row in audit],
                         [("prepared", str(self.first))])

    def test_double_click_approves_only_the_step_on_screen(self):
        self.open_review()
        updates = []
        self.dialog.progress_changed.connect(
            lambda session: updates.append((session.state, len(session.completed))))

        QTest.mouseClick(self.dialog.approve_button, Qt.MouseButton.LeftButton)
        QTest.mouseDClick(self.dialog.approve_button, Qt.MouseButton.LeftButton)
        self.dialog.approve_current()

        self.assertEqual(self.first.read_bytes(), self.content.encode("utf-8"))
        self.assertFalse(self.second.exists())
        self.assertEqual(self.session.state, "ready")
        self.assertEqual(updates, [("ready", 1)])
        self.assertFalse(self.dialog.approve_button.isEnabled())
        self.assertTrue(self.dialog.next_button.isEnabled())
        self.assertIn("1/2", self.dialog.status_label.text())
        self.assertEqual({row["target"] for row in self.runtime.audit_log()}, {str(self.first)})

        self.dialog.next_button.click()
        self.assertEqual(self.dialog.target_label.text(), str(self.second))
        self.assertEqual(self.dialog.content_view.toPlainText(), "单独批准第二份")
        self.assertFalse(self.second.exists())
        self.dialog.approve_button.click()

        self.assertEqual(self.second.read_text(encoding="utf-8"), "单独批准第二份")
        self.assertEqual(self.session.state, "completed")
        self.assertEqual(updates, [("ready", 1), ("awaiting_approval", 1), ("completed", 2)])
        self.assertIn("2/2", self.dialog.status_label.text())
        self.assertFalse(self.dialog.approve_button.isEnabled())
        self.assertFalse(self.dialog.next_button.isEnabled())
        self.dialog.close()
        self.assertEqual(self.session.state, "completed")

    def test_cancel_after_one_write_preserves_file_and_stops_remainder(self):
        self.open_review()
        updates = []
        self.dialog.progress_changed.connect(
            lambda session: updates.append((session.state, len(session.completed))))
        self.dialog.approve_button.click()
        self.dialog.next_button.click()
        self.dialog.cancel_button.click()

        self.assertEqual(self.session.state, "cancelled")
        self.assertEqual(updates, [("ready", 1), ("awaiting_approval", 1), ("cancelled", 1)])
        self.assertEqual(self.first.read_bytes(), self.content.encode("utf-8"))
        self.assertFalse(self.second.exists())
        self.assertIn("1/2", self.dialog.status_label.text())
        self.assertIn("取消", self.dialog.status_label.text())
        self.assertFalse(self.dialog.approve_button.isEnabled())
        self.assertFalse(self.dialog.next_button.isEnabled())

    def test_collision_found_preparing_second_step_keeps_the_original(self):
        self.open_review()
        self.dialog.approve_button.click()
        self.workspace.create(self.second.name, "原来的文件")

        self.dialog.next_button.click()

        self.assertEqual(self.session.state, "failed")
        self.assertEqual(self.first.read_bytes(), self.content.encode("utf-8"))
        self.assertEqual(self.second.read_text(encoding="utf-8"), "原来的文件")
        self.assertIn("1/2", self.dialog.status_label.text())
        self.assertIn("already exists", self.dialog.status_label.text())
        self.assertFalse(self.dialog.approve_button.isEnabled())
        self.assertFalse(self.dialog.next_button.isEnabled())

    def test_collision_after_second_preview_stops_at_one_completed_file(self):
        self.open_review()
        self.dialog.approve_button.click()
        self.dialog.next_button.click()
        self.workspace.create(self.second.name, "后来创建的文件")

        self.dialog.approve_button.click()

        self.assertEqual(self.session.state, "failed")
        self.assertEqual(self.first.read_bytes(), self.content.encode("utf-8"))
        self.assertEqual(self.second.read_text(encoding="utf-8"), "后来创建的文件")
        self.assertIn("1/2", self.dialog.status_label.text())
        self.assertIn("already exists", self.dialog.status_label.text())
        self.assertFalse(self.dialog.next_button.isEnabled())

    def test_scope_is_revalidated_at_approval(self):
        active = True
        self.open_review(scope_is_current=lambda: active)
        active = False

        self.dialog.approve_button.click()

        self.assertEqual(self.session.state, "cancelled")
        self.assertEqual(self.workspace.list_files(), [])
        self.assertIn("0/2", self.dialog.status_label.text())
        self.assertIn("已失效", self.dialog.status_label.text())
        self.assertFalse(self.dialog.approve_button.isEnabled())

    def test_invalidate_cancels_prepared_action_and_removes_preview(self):
        from DyberPet.assistant.action_runtime import ActionDenied

        self.open_review()
        request_id = self.runtime.audit_log()[0]["request_id"]
        updates = []
        self.dialog.progress_changed.connect(updates.append)

        self.dialog.invalidate("角色已切换，任务草案已失效。")
        self.dialog.approve_current()
        self.dialog.show_next_step()

        self.assertEqual(self.session.state, "cancelled")
        self.assertEqual(updates, [self.session])
        self.assertEqual(self.workspace.list_files(), [])
        self.assertEqual(self.dialog.target_label.text(), "")
        self.assertEqual(self.dialog.content_view.toPlainText(), "")
        self.assertIn("角色已切换", self.dialog.status_label.text())
        with self.assertRaises(ActionDenied):
            self.runtime.approve(request_id, True)

    def test_reject_and_close_cancel_pending_approval(self):
        for dismiss in ("reject", "close"):
            with self.subTest(dismiss=dismiss):
                self.open_review()
                updates = []
                self.dialog.progress_changed.connect(updates.append)

                getattr(self.dialog, dismiss)()

                self.assertEqual(self.session.state, "cancelled")
                self.assertEqual(updates, [self.session])
                self.assertEqual(self.workspace.list_files(), [])
                self.assertFalse(self.dialog.isVisible())

    def test_expired_approval_reports_zero_completed_and_stops(self):
        with patch("DyberPet.assistant.action_runtime.time.monotonic", return_value=10):
            self.open_review()
        with patch("DyberPet.assistant.action_runtime.time.monotonic", return_value=71):
            self.dialog.approve_button.click()

        self.assertEqual(self.session.state, "failed")
        self.assertIn("0/2", self.dialog.status_label.text())
        self.assertIn("expired", self.dialog.status_label.text())
        self.assertFalse(self.dialog.next_button.isEnabled())
        self.assertEqual(self.workspace.list_files(), [])

    def test_post_write_audit_warning_counts_the_write_as_completed(self):
        with closing(sqlite3.connect(self.audit_path)) as database, database:
            database.execute("""
                CREATE TRIGGER reject_executed_audit BEFORE INSERT ON action_audit
                WHEN NEW.status = 'executed' BEGIN
                    SELECT RAISE(ABORT, 'test audit volume failure');
                END
            """)
        self.open_review()

        self.dialog.approve_button.click()

        self.assertEqual(self.session.state, "ready")
        self.assertEqual(self.first.read_bytes(), self.content.encode("utf-8"))
        self.assertIn("1/2", self.dialog.status_label.text())
        self.assertIn("test audit volume failure", self.dialog.status_label.text())
        self.assertFalse(self.dialog.approve_button.isEnabled())
        self.assertFalse(self.second.exists())
        self.dialog.next_button.click()
        self.assertIn("test audit volume failure", self.dialog.status_label.text())

    def test_normalized_qt_characters_can_be_reviewed_in_escaped_form(self):
        content = "甲\r\n乙\xa0丙\u2028丁\\n"
        self.open_review(content=content)

        self.assertTrue(self.dialog.escape_content.isVisible())
        self.dialog.escape_content.click()
        self.assertEqual(self.dialog.content_view.toPlainText(), "'甲\\r\\n乙\\xa0丙\\u2028丁\\\\n'")
        self.dialog.approve_button.click()

        self.assertEqual(self.first.read_bytes(), content.encode("utf-8"))


if __name__ == "__main__":
    unittest.main()
