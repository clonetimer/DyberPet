"""Headless Qt smoke of actual assistant dialog, with no microphone or model."""
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
class AssistantQtTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from DyberPet.assistant.ui import PetAssistantDialog
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dialog = PetAssistantDialog("咕嘎", Path(self.tmp.name) / "files")
        self.addCleanup(self.dialog.close)

    def test_dialog_persona_and_file_actions_exist(self):
        self.assertEqual(self.dialog.persona.currentData(), "guga")
        self.assertFalse(self.dialog.ppl_enabled.isChecked())
        self.assertTrue(self.dialog.workspace.root.is_dir())
        self.dialog.set_character("Doro")
        self.assertEqual(self.dialog.persona.currentData(), "doro")

    def test_bubble_signals_and_stale_character_responses(self):
        replies, notices = [], []
        self.dialog.reply_ready.connect(replies.append)
        self.dialog.action_notice.connect(notices.append)
        self.dialog._message_reply(("咕嘎", "好耶，文件准备好了！"))
        self.assertEqual(replies, ["好耶，文件准备好了！"])
        self.dialog._notice("已创建文件")
        self.assertEqual(notices, ["已创建文件"])
        self.dialog.set_character("Doro")
        self.dialog._message_reply(("咕嘎", "old persona text"))
        self.assertEqual(len(replies), 1)
        self.assertNotIn("old persona text", self.dialog.chat_log.toPlainText())

    def test_save_preferences_without_transcript(self):
        self.dialog.message.setText("private chat")
        self.dialog.llm_model.setText("local-model")
        with patch("DyberPet.assistant.ui.save_preferences") as saved:
            self.dialog.save_preferences()
        sent = saved.call_args.args[0]
        self.assertEqual(sent["llm_model"], "local-model")
        self.assertEqual(sent["personas"]["咕嘎"], "guga")
        self.assertNotIn("private chat", str(sent))

    def test_user_authorized_folder_session_only_and_reset(self):
        with tempfile.TemporaryDirectory(dir=Path.home()) as staging:
            specific = Path(staging) / "MyPetNotes"
            specific.mkdir()
            with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                       return_value=str(specific)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.No):
                self.dialog.grant_session_folder()
            self.assertNotEqual(self.dialog.workspace.root, specific)
            with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                       return_value=str(specific)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Yes):
                self.dialog.grant_session_folder()
            self.assertEqual(self.dialog.workspace.root, specific.resolve())
            self.dialog.workspace.create("pet.txt", "local")
            self.dialog.reset_workspace()
            self.assertNotEqual(self.dialog.workspace.root, specific.resolve())
            self.assertEqual((specific / "pet.txt").read_text(), "local")

    def test_unlocked_animation_signal_and_dialog_close_revokes_grant(self):
        chosen = []
        self.dialog.action_requested.connect(chosen.append)
        self.dialog.set_actions(["游戏互动", "挥手", "挥手"])
        self.assertEqual(self.dialog.action_menu.count(), 3)
        self.dialog.action_menu.setCurrentIndex(
            self.dialog.action_menu.findData("挥手"))
        self.dialog._notice("已恢复文件")
        self.assertEqual(chosen, ["挥手"])
        self.dialog._ppl_snapshot = "private PPL snapshot"
        self.dialog._last_reply = "private reply"
        with tempfile.TemporaryDirectory(dir=Path.home()) as home_temp:
            specific = Path(home_temp) / "Files"
            specific.mkdir()
            with patch("PySide6.QtWidgets.QFileDialog.getExistingDirectory",
                       return_value=str(specific)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Yes):
                self.dialog.grant_session_folder()
            self.assertEqual(self.dialog.workspace.root, specific.resolve())
            self.dialog.close()
            self.assertNotEqual(self.dialog.workspace.root, specific.resolve())
            self.assertEqual(self.dialog._last_reply, "")
            self.assertEqual(self.dialog._ppl_snapshot, "")

    def test_create_requires_confirmation(self):
        with patch("PySide6.QtWidgets.QInputDialog.getText",
                   return_value=("note.txt", True)), patch(
                       "PySide6.QtWidgets.QInputDialog.getMultiLineText",
                       return_value=("hello", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.question",
                       return_value=QMessageBox.StandardButton.No):
            self.dialog.create_file()
        self.assertEqual(self.dialog.workspace.list_files(), [])
        with patch("PySide6.QtWidgets.QInputDialog.getText",
                   return_value=("note.txt", True)), patch(
                       "PySide6.QtWidgets.QInputDialog.getMultiLineText",
                       return_value=("hello", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.question",
                       return_value=QMessageBox.StandardButton.Yes):
            self.dialog.create_file()
        self.assertEqual(self.dialog.workspace.list_files(), ["note.txt"])

    def test_delete_requires_confirmation_and_supports_restore(self):
        self.dialog.workspace.create("pet.md", "hello")
        with patch("PySide6.QtWidgets.QInputDialog.getItem",
                   return_value=("pet.md", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.No):
            self.dialog.delete_file()
        self.assertEqual(self.dialog.workspace.list_files(), ["pet.md"])
        with patch("PySide6.QtWidgets.QInputDialog.getItem",
                   return_value=("pet.md", True)), patch(
                       "PySide6.QtWidgets.QMessageBox.warning",
                       return_value=QMessageBox.StandardButton.Yes):
            self.dialog.delete_file()
        self.assertEqual(self.dialog.workspace.list_files(), [])
        record = self.dialog.workspace.deleted_files()[0]
        with patch("PySide6.QtWidgets.QInputDialog.getItem",
                   return_value=(record, True)):
            self.dialog.restore_file()
        self.assertEqual(self.dialog.workspace.list_files(), ["pet.md"])


if __name__ == "__main__":
    unittest.main()
