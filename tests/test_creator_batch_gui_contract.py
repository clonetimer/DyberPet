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

    def test_resume_last_run_read_only_and_reconfirm_before_download(self):
        menu = self.methods["_chooseCreatorInstallMode"]
        self.assertIn("查看上次进度", menu)
        self.assertIn("self._resumeCreatorBulkImport()", menu)
        resume = self.methods["_resumeCreatorBulkImport"]
        self.assertIn("latest_install_journal(", resume)
        self.assertIn("plan_personal_sources(", resume)
        self.assertIn("restartable_profiles(", resume)
        self.assertIn("if not targets:", resume)
        self.assertIn("self._startCreatorBulkImport(only_profiles=targets)", resume)
        worker = self.classes["CreatorBatchImportThread"]
        start = next(x for x in worker.body
                     if isinstance(x, ast.FunctionDef) and x.name == "run")
        self.assertIn("only_profiles=self.only_profiles", ast.unparse(start))
        spawn = self.methods["_startCreatorBulkImport"]
        self.assertIn("only_profiles=only_profiles", spawn)
        self.assertIn("if not self.__showMessageBox(", spawn)
        self.assertLess(spawn.index("if not self.__showMessageBox("),
                        spawn.index("CreatorBatchImportThread("))

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

    def test_new_roles_do_not_dispatch_immediate_change_pet(self):
        launch = self.methods["__onLaunchClicked"]
        self.assertIn("self._restart_required_roles", launch)
        self.assertIn("stage_default_pet(", launch)
        self.assertLess(launch.index("self._restart_required_roles"),
                        launch.index("self.change_pet.emit("))
        register = self.methods["__onAddClickedContinue"]
        self.assertIn("self._restart_required_roles.add(petFolder)", register)
        batch = self.methods["_onCreatorBatchDone"]
        self.assertIn("verified_new_artist_folders(", batch)
        self.assertIn("stage_default_pet(", batch)
        self.assertIn("scan_genshin_library(", batch)
        self.assertIn("self._previewJustInstalledCreatorArt(", batch)

    def test_off_thread_exact_inventory_and_no_background_ui_updates(self):
        worker = self.classes["CreatorBatchImportThread"]
        self.assertTrue(any(isinstance(base, ast.Name) and base.id == "QThread"
                            for base in worker.bases))
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

    def test_checkpoint_saving_on_worker_thread_and_failure_receipt(self):
        # Find the batch worker's own run and verify no Qt widgets are touched.
        klass = self.classes["CreatorBatchImportThread"]
        method = next(n for n in klass.body if isinstance(n, ast.FunctionDef)
                      and n.name == "run")
        run = ast.unparse(method)
        self.assertIn("PersonalInstallJournal(", run)
        self.assertIn("checkpoint=save_checkpoint", run)
        self.assertIn("journal.record_character(", run)
        self.assertIn("planned_profiles=planned_profiles", run)
        self.assertIn("ready_profiles[:self.max_roles]", run)
        self.assertIn("journal.finalize(result)", run)
        self.assertIn("journal_error", run)
        self.assertNotIn("QMessageBox", run)

    def test_immediate_preview_only_of_inventory_verified_new_art(self):
        body = self.methods["_onCreatorBatchDone"]
        self.assertIn("journal_path", body)
        self.assertIn("installed_unreviewed", body)
        self.assertIn("verified_native_folders", body)
        self.assertIn("QInputDialog.getItem(", body)
        self.assertIn("self._previewJustInstalledCreatorArt(", body)
        self.assertIn("不代表原设形象", body)
        self.assertIn("重启 DyberPet", body)
        self.assertNotIn("settings.pets.append(", body)


if __name__ == "__main__":
    unittest.main()
