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
            progress = []
            def after(_):
                return {"mascots": [
                    {"key": "guga", "imported_creator_art": [{"folder": "SourceGuga"}]},
                    {"key": "doro", "imported_creator_art": [{"folder": "SourceDoro"}]}]}
            outcome = install_mascot_plan(
                report, temp, confirmed=True, installer=fake,
                inventory_reader=after, progress=progress.append)
            self.assertTrue(outcome["post_install_inventory_checked"])
            self.assertEqual(progress[-1]["status"], "installed_unreviewed")
            self.assertEqual(seen, [("guga", True)])
            self.assertEqual(outcome["installed_unreviewed"], 1)
            self.assertTrue(outcome["no_art_uploaded"])

    def test_doro_v2_is_a_separate_source_not_replaced_by_existing_classic(self):
        with TemporaryDirectory() as temp:
            plan = plan_mascot_sources(
                temp, inventory=self._inventory(), doro_variant="handdrawn_v2")
            guga, doro = plan["mascots"]
            self.assertEqual(guga["status"], "ready_for_opt_in")
            self.assertEqual(doro["status"], "ready_for_opt_in")
            self.assertEqual(doro["source_variant"], "handdrawn_v2")
            self.assertEqual(doro["source_id"], "doro--godxxy1229")
            requests = []
            def fake(kind, root, *, confirmed, variant="classic"):
                requests.append((kind, confirmed, variant))
                return {"kind": kind, "actions": 9, "frames": 70}
            def after(_):
                return {"mascots": [
                    {"key": "guga", "imported_creator_art": [
                        {"source_id": "guga--circus"}]},
                    {"key": "doro", "imported_creator_art": [
                        {"source_id": "doro--lingxiaotian"},
                        {"source_id": "doro--godxxy1229"}]},
                ]}
            outcome = install_mascot_plan(
                plan, temp, confirmed=True,
                installer=fake, inventory_reader=after)
            self.assertEqual(outcome["installed_unreviewed"], 2)
            self.assertEqual(outcome["post_install_recognized_source_variants"], 3)
            self.assertEqual(requests,
                             [("guga", True, "classic"),
                              ("doro", True, "handdrawn_v2")])

    def test_doro_v2_must_not_count_old_classic_installed_as_success(self):
        with TemporaryDirectory() as temp:
            plan = plan_mascot_sources(
                temp, inventory=self._inventory(), doro_variant="handdrawn_v2")
            def fake(kind, root, *, confirmed, variant="classic"):
                return {"kind": kind, "actions": 9, "frames": 70}
            def only_classic(_):
                return {"mascots": [
                    {"key": "guga", "imported_creator_art": [
                        {"source_id": "guga--circus"}]},
                    {"key": "doro", "imported_creator_art": [
                        {"source_id": "doro--lingxiaotian"}]},
                ]}
            outcome = install_mascot_plan(
                plan, temp, confirmed=True, installer=fake,
                inventory_reader=only_classic)
            self.assertEqual(outcome["installed_unreviewed"], 1)
            self.assertEqual(outcome["failed"], 1)
            doro = next(x for x in outcome["results"] if x["key"] == "doro")
            self.assertEqual(doro["status"], "failed")
            self.assertTrue(doro["post_install_validation_failed"])

    def test_noop_mascot_installer_must_not_count_as_real_art(self):
        with TemporaryDirectory() as temp:
            report = plan_mascot_sources(temp, inventory=self._inventory())
            outcome = install_mascot_plan(
                report, temp, confirmed=True,
                installer=lambda kind, *_a, **_kw: {
                    "kind": kind, "actions": 10, "frames": 70})
            self.assertEqual(outcome["installed_unreviewed"], 0)
            self.assertEqual(outcome["failed"], 1)
            self.assertTrue(outcome["results"][0]["post_install_validation_failed"])

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
