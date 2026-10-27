"""R14 local-only crash-tolerant character checkpoint acceptance."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tools.personal_install_journal import PersonalInstallJournal


class DurableJournalTests(unittest.TestCase):
    def test_each_role_checkpoint_is_valid_json_and_unapproved(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "portable" / "data"
            journal = PersonalInstallJournal(folder, {"ready_for_opt_in": 2})
            self.assertTrue(journal.path.is_file())
            before = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertFalse(before["finished"])
            self.assertIsNone(before["final_installation"])
            self.assertFalse(before["likeness_approved"])
            journal.record_character({
                "profile": "genshin_nahida", "index": 1,
                "status": "pending_inventory_validation",
                "source_attempts": [{"provider": "native",
                                     "status": "installed_unreviewed"}]})
            midway = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertFalse(midway["finished"])
            self.assertEqual(len(midway["completed_character_attempts"]), 1)
            self.assertEqual(midway["completed_character_attempts"][0]["status"],
                             "pending_inventory_validation")
            journal.record_character({
                "profile": "genshin_klee", "index": 2,
                "status": "failed", "source_attempts": [
                    {"provider": "codex", "reason": "HTTP 404"}]})
            interrupted = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertEqual(len(interrupted["completed_character_attempts"]), 2)
            self.assertFalse(interrupted["finished"])
            self.assertEqual(list(folder.glob("*.tmp")), [])
            result = {"attempted": 2, "installed_unreviewed": 1, "failed": 1,
                      "results": [{"profile": "genshin_nahida",
                                   "verified_native_folders": ["SourceNahida"]}]}
            journal.finalize(result)
            end = json.loads(journal.path.read_text(encoding="utf-8"))
            self.assertTrue(end["finished"])
            self.assertEqual(end["final_installation"], result)
            self.assertFalse(end["rights_approved"])
            with self.assertRaisesRegex(ValueError, "finalized"):
                journal.record_character({"profile": "genshin_xiao",
                                          "status": "failed"})

    def test_refuse_linked_report_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            linked = root / "link"
            try:
                linked.symlink_to(root, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation unavailable")
            with self.assertRaisesRegex(ValueError, "real directory"):
                PersonalInstallJournal(linked, {})

    def test_invalid_checkpoint_never_written(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = PersonalInstallJournal(Path(tmp) / "data", {})
            for record in ({}, {"profile": "genshin_nahida", "status": "passed"},
                           {"profile": 14, "status": "failed"}):
                with self.assertRaises(ValueError):
                    journal.record_character(record)
            self.assertEqual(json.loads(journal.path.read_text(
                encoding="utf-8"))["completed_character_attempts"], [])


if __name__ == "__main__":
    unittest.main()
