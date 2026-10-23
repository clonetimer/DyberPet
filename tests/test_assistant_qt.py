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
