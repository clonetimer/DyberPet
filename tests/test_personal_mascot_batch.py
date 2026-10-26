"""Offline Guga/Doro local source entry regression; no downloads."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.personal_mascot_batch import plan_mascot_sources, install_mascot_plan


class MascotPersonalBatchTests(unittest.TestCase):
    def _inventory(self):
        return {"mascots": [
            {"key": "guga", "display_name": "咕嘎", "imported_creator_art": [],
             "original_demos": [{"folder": "DemoMascotGuga"}]},
            {"key": "doro", "display_name": "Doro", "imported_creator_art": [
                {"folder": "SourceDoro"}], "original_demos": []}],
            "invalid_local": []}

    def test_dry_run_demo_is_not_creator_art(self):
        with TemporaryDirectory() as temp:
            dest = Path(temp) / "not_created"
            report = plan_mascot_sources(dest, inventory=self._inventory())
            self.assertFalse(dest.exists())
            self.assertEqual(report["summary"]["mascot_templates"], 2)
            self.assertEqual([r["status"] for r in report["mascots"]],
                             ["ready_for_opt_in", "already_installed"])
            self.assertTrue(all(not x["original_voice_included"] for x in report["mascots"]))
            self.assertTrue(all(not x["original_likeness_verified"] for x in report["mascots"]))

    def test_consent_install_and_source_identity(self):
        with TemporaryDirectory() as temp:
            report = plan_mascot_sources(temp, inventory=self._inventory())
            seen = []
            def fake(kind, dest, *, confirmed):
                seen.append((kind, confirmed))
                return {"kind": kind, "actions": 9, "frames": 57}
            with self.assertRaisesRegex(ValueError, "Confirm"):
                install_mascot_plan(report, temp, installer=fake)
            self.assertFalse(seen)
            outcome = install_mascot_plan(report, temp, confirmed=True, installer=fake)
            self.assertEqual(seen, [("guga", True)])
            self.assertEqual(outcome["installed_unreviewed"], 1)
            self.assertTrue(outcome["no_art_uploaded"])

    def test_bad_or_failed_install_is_reported(self):
        with TemporaryDirectory() as temp:
            report = plan_mascot_sources(temp, inventory=self._inventory())
            result = install_mascot_plan(
                report, temp, confirmed=True,
                installer=lambda *_a, **_k: {"kind": "wrong"})
            self.assertEqual(result["failed"], 1)
            self.assertEqual(result["installed_unreviewed"], 0)

if __name__ == "__main__":
    unittest.main()
