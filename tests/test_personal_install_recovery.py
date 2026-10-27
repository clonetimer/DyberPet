"""R15 read-only recovery of a persisted, bounded source-art journal."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.personal_install_journal import (
    PersonalInstallJournal, latest_install_journal, restartable_profiles)


def current_plan():
    return {"characters": [
        {"profile": "genshin_klee", "status": "ready_for_opt_in"},
        {"profile": "genshin_noelle", "status": "missing_source"},
        {"profile": "genshin_nahida", "status": "already_installed"},
        {"profile": "genshin_xiao", "status": "ready_for_opt_in"},
    ]}


class JournalRecoveryTests(unittest.TestCase):
    def test_incomplete_work_recovers_remaining_native_source_candidates(self):
        with TemporaryDirectory() as temp:
            j = PersonalInstallJournal(
                Path(temp) / "data", {"ready_for_opt_in": 4},
                planned_profiles=["genshin_nahida", "genshin_klee",
                                  "genshin_xiao"])
            j.record_character({"profile": "genshin_nahida", "index": 1,
                                "status": "pending_inventory_validation"})
            found = latest_install_journal(Path(temp) / "data")
            self.assertFalse(found["finished"])
            self.assertEqual(found["attempts"], 1)
            self.assertEqual(restartable_profiles(found, current_plan()),
                             ["genshin_klee", "genshin_xiao"])
            # Fresh planning is authoritative: the previously downloaded
            # Nahida and a no-source Noelle are never re-attempted.

    def test_interrupted_two_role_trial_never_expands_to_all_candidates(self):
        with TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            j = PersonalInstallJournal(
                data, {"ready_for_opt_in": 3},
                planned_profiles=["genshin_klee", "genshin_nahida"])
            j.record_character({"profile": "genshin_klee", "index": 1,
                                "status": "failed"})
            candidate_plan = {"characters": [
                {"profile": "genshin_klee", "status": "ready_for_opt_in"},
                {"profile": "genshin_nahida", "status": "ready_for_opt_in"},
                {"profile": "genshin_xiao", "status": "ready_for_opt_in"},
            ]}
            found = latest_install_journal(data)
            self.assertEqual(found["planned_profiles"],
                             ["genshin_klee", "genshin_nahida"])
            self.assertEqual(restartable_profiles(found, candidate_plan),
                             ["genshin_klee", "genshin_nahida"])
            # A role never selected in the original trial cannot be added
            # merely because the original process was interrupted.

    def test_legacy_interruption_only_retries_recorded_attempts(self):
        with TemporaryDirectory() as temp:
            j = PersonalInstallJournal(Path(temp) / "data", {})
            j.record_character({"profile": "genshin_klee", "status": "failed"})
            found = latest_install_journal(Path(temp) / "data")
            self.assertIsNone(found["planned_profiles"])
            self.assertEqual(restartable_profiles(found, current_plan()),
                             ["genshin_klee"])
            # Older reports cannot prove whether user selected 2 or 65.
            # Not-yet-attempted Xiaos must not be silently included.

    def test_finished_batch_retries_only_failed_and_not_already_installed(self):
        with TemporaryDirectory() as temp:
            j = PersonalInstallJournal(Path(temp) / "data", {})
            j.record_character({"profile": "genshin_klee", "index": 1,
                                "status": "failed"})
            j.finalize({"results": [
                {"profile": "genshin_klee", "status": "failed"},
                {"profile": "genshin_nahida", "status": "failed"},
                {"profile": "genshin_xiao", "status": "installed_unreviewed"},
                {"profile": "genshin_noelle", "status": "failed"},
            ], "failed": 3})
            found = latest_install_journal(Path(temp) / "data")
            self.assertTrue(found["finished"])
            self.assertEqual(restartable_profiles(found, current_plan()),
                             ["genshin_klee"])

    def test_missing_or_invalid_journal_never_executes_downloads(self):
        with TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            self.assertIsNone(latest_install_journal(data))
            data.mkdir()
            (data / "old-partial.tmp").write_text("{}", encoding="utf-8")
            (data / "personal65-batch-20261027-120000-deadbeef.json").write_text(
                "{bad", encoding="utf-8")
            (data / "personal65-batch-20261027-120001-feedface.json").write_bytes(
                b"x" * (4*1024*1024 + 1))
            self.assertIsNone(latest_install_journal(data))

    def test_reject_forged_scope_and_keep_older_valid_report(self):
        with TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            good = PersonalInstallJournal(
                data, {}, planned_profiles=["genshin_klee"])
            bad = data / "personal65-batch-20990101-010101-deadbeef.json"
            payload = json.loads(good.path.read_text(encoding="utf-8"))
            payload["planned_profiles"] = ["genshin_klee", "genshin_klee"]
            bad.write_text(json.dumps(payload), encoding="utf-8")
            found = latest_install_journal(data)
            self.assertEqual(found["path"], str(good.path))
            with self.assertRaisesRegex(ValueError, "scope"):
                PersonalInstallJournal(data, {}, planned_profiles=["a", "a"])

    def test_invalid_newest_skips_to_older_valid_report(self):
        with TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            data.mkdir()
            valid = {
                "schema": 1, "scope": "local_only_unverified_progress",
                "plan_summary": {}, "completed_character_attempts": [],
                "finished": False, "final_installation": None,
            }
            older = data / "personal65-batch-20261027-080000-1234abcd.json"
            older.write_text(json.dumps(valid), encoding="utf-8")
            (data / "personal65-batch-20261027-090000-1234abcd.json").write_text(
                '{"schema":2}', encoding="utf-8")
            self.assertEqual(latest_install_journal(data)["path"], str(older))

    def test_invalid_and_symlink_source_never_authorizes_profiles(self):
        with TemporaryDirectory() as temp:
            data = Path(temp) / "data"
            data.mkdir()
            report = data / "personal65-batch-20261027-080000-1234abcd.json"
            doc = {
                "schema": 1, "plan_summary": {}, "finished": True,
                "completed_character_attempts": [],
                "final_installation": {"results": [
                    {"profile": "genshin_fake", "status": "failed"},
                    {"profile": "genshin_klee", "status": "failed"},
                    {"profile": "genshin_xiao", "status": "installed_unreviewed"},
                ]},
            }
            report.write_text(json.dumps(doc), encoding="utf-8")
            found = latest_install_journal(data)
            self.assertEqual(restartable_profiles(found, current_plan()),
                             ["genshin_klee"])
            with self.assertRaisesRegex(ValueError, "validated"):
                restartable_profiles(None, current_plan())
            alias = Path(temp) / "alias"
            try:
                alias.symlink_to(data, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink unsupported")
            with self.assertRaisesRegex(ValueError, "not be linked"):
                latest_install_journal(alias)


if __name__ == "__main__":
    unittest.main()
