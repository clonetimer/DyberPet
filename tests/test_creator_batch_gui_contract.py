"""R13: GUI bulk imports real author sprites only after affirmative consent.

The source/role import code is tested separately by test_personal_source_batch.
These AST contracts are intentionally runnable on importer-only Python 3.9,
where PySide6 / qfluentwidgets may not be installed.
"""
from __future__ import annotations

import ast
from pathlib import Path
import unittest


PATH = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberSettings" / "CharCardUI.py"


class BulkArtistGuiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ast = ast.parse(PATH.read_text(encoding="utf-8"))
        cls.methods = {n.name: ast.unparse(n) for n in ast.walk(cls.ast)
                       if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
        cls.classes = {n.name: n for n in ast.walk(cls.ast)
                       if isinstance(n, ast.ClassDef)}

    def test_all_art_or_two_trial_and_individual_choice(self):
        handler = self.methods["_chooseCreatorInstallMode"]
        self.assertIn("尚未安装", handler)
        self.assertIn("先试装 2 位", handler)
        self.assertIn("只安装一位", handler)
        self.assertIn("if not accepted:", handler)
        self.assertIn("self._startCreatorBulkImport(", handler)
        self.assertIn("self._installArtistGenshin()", handler)

    def test_no_remote_download_before_explicit_user_confirmation(self):
        source = self.methods["_startCreatorBulkImport"]
        pos_consent = source.index("if not self.__showMessageBox(")
        pos_thread = source.index("CreatorBatchImportThread(")
        self.assertLess(pos_consent, pos_thread)
        self.assertIn("不会上传或重新分发", source)
        self.assertIn("QProgressDialog(", source)
        self.assertIn("progress.canceled.connect(self.chibiThread.request_stop)", source)
        self.assertIn("self.chibiThread.progress.connect(", source)
        self.assertIn("self.chibiThread.start()", source)

    def test_off_thread_exact_inventory_and_no_background_ui_updates(self):
        worker = self.classes["CreatorBatchImportThread"]
        self.assertIn("QThread", ast.unparse(worker.bases))
        func = next(n for n in worker.body if isinstance(n, ast.FunctionDef)
                    and n.name == "run")
        body = ast.unparse(func)
        self.assertIn("plan_personal_sources(", body)
        self.assertIn("install_personal_plan(", body)
        self.assertIn("confirmed=True", body)
        self.assertIn("should_stop=self._stop_requested.is_set", body)
        self.assertIn("self.progress.emit", body)
        self.assertIn("self.done.emit", body)
        self.assertNotIn("QMessageBox", body)

    def test_local_receipt_and_no_false_quality_gate(self):
        body = self.methods["_onCreatorBatchDone"]
        self.assertIn("personal65-batch-", body)
        self.assertIn("json.dumps(", body)
        self.assertIn("installed_unreviewed", body)
        self.assertIn("不代表原设/动作人工验收合格", body)
        self.assertIn("重启 DyberPet", body)


if __name__ == "__main__":
    unittest.main()
