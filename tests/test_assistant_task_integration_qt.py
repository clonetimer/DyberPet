"""Assistant/task scope integration using the real Qt widgets and filesystem."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
try:
    from PySide6.QtWidgets import QApplication, QMessageBox
except ImportError:
    QApplication = QMessageBox = None


@unittest.skipIf(QApplication is None, "PySide6 optional; runs in Qt smoke CI")
class TaskIntegrationQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dialog = PetAssistantDialog(
            "咕嘎", Path(self.tmp.name) / "files",
            store_path=Path(self.tmp.name) / "companion.sqlite3")
        self.addCleanup(self.dialog.close)
        self.dialog.llm_model.setText("local-model")

    def plan(self):
        from DyberPet.assistant.task_plan import parse_task_plan
        return parse_task_plan(
            '{"version":1,"title":"两份便签","steps":['
            '{"action":"create_note","name":"a.md","content":"第一份"},'
            '{"action":"create_note","name":"b.md","content":"第二份"}]}')

    def generate(self):
        self.dialog.message.setText("创建两份便签")

        def run(task, success, *args, **kwargs):
            success(task(*args, **kwargs))

        with patch("DyberPet.assistant.ui.generate_task_plan", return_value=self.plan()):
            with patch.object(self.dialog, "_submit", side_effect=run):
                self.dialog.propose_task()
        return self.dialog._task_session

    def test_generated_plan_only_opens_preview_and_requires_each_click(self):
        session = self.generate()
        self.assertEqual(self.dialog.workspace.list_files(), [])
        review = self.dialog._task_review_dialog
        self.assertEqual(review.content_view.toPlainText(), "第一份")
        review.approve_button.click()
        review.approve_button.click()
        self.assertEqual(self.dialog.workspace.list_files(), ["a.md"])
        self.assertEqual(len(session.completed), 1)
        self.assertIn("1/2", self.dialog.status.text())
        review.next_button.click()
        review.approve_button.click()
        self.assertEqual(self.dialog.workspace.list_files(), ["a.md", "b.md"])
        self.assertEqual(session.state, "completed")

    def test_busy_generate_and_send_preserve_input_and_existing_plan(self):
        session = self.generate()
        self.dialog.message.setText("保留这条输入")
        self.dialog._job = object()
        try:
            self.dialog.propose_task()
            self.dialog.send_message()
            self.assertEqual(self.dialog.message.text(), "保留这条输入")
            self.assertIs(self.dialog._task_session, session)
            self.assertFalse(self.dialog._stream_reply_open)
        finally:
            self.dialog._job = None

    def test_role_persona_workspace_and_history_changes_cancel_old_proposal(self):
        changes = [lambda: self.dialog.set_character("Doro"),
                   lambda: self.dialog.persona.setCurrentIndex(
                       self.dialog.persona.findData("klee")),
                   self.dialog.reset_workspace,
                   self.dialog.clear_character_history]
        for change in changes:
            with self.subTest(change=change):
                session = self.generate()
                review = self.dialog._task_review_dialog
                with patch("PySide6.QtWidgets.QMessageBox.question",
                           return_value=QMessageBox.StandardButton.Yes):
                    change()
                review.approve_current()
                self.assertEqual(session.state, "cancelled")
                self.assertEqual(self.dialog.workspace.list_files(), [])

    def test_late_plan_from_old_workspace_is_ignored(self):
        callbacks = []

        def capture(task, success, *args, **kwargs):
            callbacks.append((task, success, args, kwargs))

        self.dialog.message.setText("生成文件")
        with patch("DyberPet.assistant.ui.generate_task_plan", return_value=self.plan()):
            with patch.object(self.dialog, "_submit", side_effect=capture):
                self.dialog.propose_task()
            task, success, args, kwargs = callbacks[0]
            result = task(*args, **kwargs)
        self.dialog.reset_workspace()
        success(result)
        self.assertIsNone(self.dialog._task_session)
        self.assertEqual(self.dialog.workspace.list_files(), [])

    def test_attach_is_consumed_on_success_but_kept_on_model_failure(self):
        source = {"name": "source.md", "content": "唯一资料"}
        self.dialog._pending_file_context = source.copy()
        self.generate()
        self.assertIsNone(self.dialog._pending_file_context)
        self.dialog._pending_file_context = source.copy()
        self.dialog.message.setText("创建文件")

        def fail(task, success, *args, **kwargs):
            try:
                task(*args, **kwargs)
            except Exception as exc:
                self.dialog._job_error(str(exc))

        with patch("DyberPet.assistant.ui.generate_task_plan", side_effect=ValueError("model failed")):
            with patch.object(self.dialog, "_submit", side_effect=fail):
                self.dialog.propose_task()
        self.assertEqual(self.dialog._pending_file_context, source)
        self.assertIsNone(self.dialog._task_session)

    def test_close_during_worker_immediately_invalidates_old_preview(self):
        session = self.generate()
        generation = self.dialog._session_generation
        self.dialog._job = object()

        class Event:
            ignored = False
            def ignore(self):
                self.ignored = True

        event = Event()
        try:
            self.dialog.closeEvent(event)
            self.assertTrue(event.ignored)
            self.assertGreater(self.dialog._session_generation, generation)
            self.assertEqual(session.state, "cancelled")
            self.assertEqual(self.dialog.workspace.list_files(), [])
        finally:
            self.dialog._job = None
            self.dialog._closing_after_worker = False

    def test_late_chat_and_failure_after_context_reset_do_not_repopulate_session(self):
        generation = self.dialog._session_generation
        self.dialog.reset_workspace()
        self.dialog._message_reply(("咕嘎", generation, "old user", "late answer", None))
        self.dialog._scoped_job_error("late error", generation)
        self.assertNotIn("late", self.dialog.chat_log.toPlainText())
        self.assertEqual(self.dialog._conversation_store.recent_messages("咕嘎"), [])

    def test_manual_approval_cannot_survive_character_change_inside_confirmation(self):
        def change_then_yes(*args):
            self.dialog.set_character("Doro")
            return QMessageBox.StandardButton.Yes

        with patch("PySide6.QtWidgets.QMessageBox.question", side_effect=change_then_yes):
            result = self.dialog._execute_user_approved_action(
                "create_note", {"name": "stale.md", "content": "old"}, title="确认")
        self.assertIsNone(result)
        self.assertEqual(self.dialog.workspace.list_files(), [])

    def test_normal_chat_json_never_creates_executable_plan(self):
        self.dialog._message_reply(("咕嘎", '{"version":1,"title":"x","steps":[]}'))
        self.assertIsNone(self.dialog._task_session)
        self.assertEqual(self.dialog.workspace.list_files(), [])

    def test_real_worker_discards_late_success_and_failure_after_scope_changes(self):
        import threading
        import time
        from PySide6.QtTest import QTest

        received = []
        for fails in (False, True):
            with self.subTest(fails=fails):
                gate = threading.Event()

                def work():
                    if not gate.wait(timeout=2):
                        raise RuntimeError("test worker gate timeout")
                    if fails:
                        raise RuntimeError("late worker error")
                    return "late worker success"

                self.dialog._submit(work, received.append)
                self.assertFalse(self.dialog.plan_button.isEnabled())
                self.dialog.reset_workspace()
                gate.set()
                deadline = time.monotonic() + 3
                while self.dialog._job is not None and time.monotonic() < deadline:
                    QTest.qWait(10)
                self.assertIsNone(self.dialog._job)
                self.assertTrue(self.dialog.plan_button.isEnabled())
                self.assertEqual(received, [])
                self.assertNotIn("late worker", self.dialog.chat_log.toPlainText())

    def test_escape_closes_parent_and_revokes_review_before_any_write(self):
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        self.dialog.show()
        session = self.generate()
        review = self.dialog._task_review_dialog
        QTest.keyClick(self.dialog, Qt.Key.Key_Escape)
        self.assertFalse(self.dialog.isVisible())
        self.assertFalse(review.isVisible())
        self.assertEqual(session.state, "cancelled")
        review.approve_current()
        self.assertEqual(self.dialog.workspace.list_files(), [])

    def test_replacing_plans_releases_previous_child_dialogs(self):
        from DyberPet.assistant.task_review import TaskReviewDialog
        for _ in range(4):
            self.generate()
        self.assertEqual(len(self.dialog.findChildren(TaskReviewDialog)), 1)

    def test_context_invalidation_discards_pending_microphone_partial(self):
        import threading
        self.dialog._listening = True
        self.dialog._listen_stop_event = threading.Event()
        self.dialog.reset_workspace()
        self.dialog._heard_partial("旧目录中的私密话语")
        self.assertNotIn("私密话语", self.dialog.status.text())
        self.assertTrue(self.dialog._listen_stop_event.is_set())

    def test_escape_during_real_planner_worker_discards_result_and_waits_for_exit(self):
        import threading
        import time
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        gate = threading.Event()
        plan = self.plan()

        def delayed_plan(*args, **kwargs):
            if not gate.wait(timeout=2):
                raise RuntimeError("test planner gate timeout")
            return plan

        self.dialog.show()
        self.dialog.message.setText("创建便签")
        with patch("DyberPet.assistant.ui.generate_task_plan", side_effect=delayed_plan):
            self.dialog.propose_task()
            QTest.keyClick(self.dialog, Qt.Key.Key_Escape)
            self.assertTrue(self.dialog._closing_after_worker)
            gate.set()
            deadline = time.monotonic() + 3
            while (self.dialog._job is not None or self.dialog.isVisible()) and time.monotonic() < deadline:
                QTest.qWait(10)
        self.assertIsNone(self.dialog._job)
        self.assertFalse(self.dialog.isVisible())
        self.assertIsNone(self.dialog._task_session)
        self.assertEqual(self.dialog.workspace.list_files(), [])


if __name__ == "__main__":
    unittest.main()
