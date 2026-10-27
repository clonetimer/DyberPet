"""Offline coverage: installed character != pinned source, and no implicit download."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from tools.personal_source_batch import plan_personal_sources, install_personal_plan


def fake_coverage():
    return {"characters": [
        {"id": "genshin_a", "name": "A", "source_candidates": [
            {"provider": "unverified_lfs", "source_key": "manual", "url": "https://example.org/manual"},
            {"provider": "codexpetdb_zip", "source_key": "a", "url": "https://example.org/a"}]},
        {"id": "genshin_b", "name": "B", "source_candidates": [
            {"provider": "unverified_lfs", "source_key": "b", "url": "https://example.org/b"}]},
        {"id": "genshin_c", "name": "C", "source_candidates": []},
        {"id": "genshin_d", "name": "D", "source_candidates": [
            {"provider": "native", "source_key": "d", "url": "https://example.org/d"}]},
    ]}


def fake_inventory():
    return {"characters": [
        {"profile": "genshin_a", "installed_folders": [
            {"folder": "DemoG_a", "is_original_demo": True}]},
        {"profile": "genshin_d", "installed_folders": [
            {"folder": "UserD", "is_original_demo": False}]},
    ], "invalid_local": [{"folder": "broken"}]}


class PersonalSourceBatchTests(unittest.TestCase):
    def test_dry_run_distinguishes_source_from_install_and_demo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "no-role-dir"
            report = plan_personal_sources(root, coverage=fake_coverage(),
                                           inventory=fake_inventory())
            self.assertFalse(root.exists())
            self.assertEqual(
                {r["profile"]: r["status"] for r in report["characters"]},
                {"genshin_a": "ready_for_opt_in",
                 "genshin_b": "manual_import_only",
                 "genshin_c": "missing_source",
                 "genshin_d": "already_installed"})
            self.assertEqual(report["summary"]["local_invalid_folders"], 1)
            self.assertEqual(report["characters"][0]["provider"], "codexpetdb_zip")
            self.assertFalse(report["characters"][0]["original_likeness_verified"])

    def test_explicit_consent_and_bounded_calls(self):
        with tempfile.TemporaryDirectory() as temp:
            report = plan_personal_sources(temp, coverage=fake_coverage(),
                                           inventory=fake_inventory())
            calls = []
            def fake(provider, key, root):
                calls.append((provider, key, root))
            with self.assertRaisesRegex(ValueError, "Explicit"):
                install_personal_plan(report, temp, dispatch=fake)
            self.assertEqual(calls, [])
            progress = []
            result = install_personal_plan(
                report, temp, confirmed=True, max_roles=1, dispatch=fake,
                inventory_reader=lambda _: {"characters": [
                    {"profile": "genshin_a", "installed_folders": [
                        {"is_original_demo": False}]}], "invalid_local": []},
                progress=progress.append)
            self.assertTrue(result["post_install_inventory_checked"])
            self.assertTrue(result["results"][0]["post_install_validation_passed"])
            self.assertEqual(progress[-1]["status"], "installed_unreviewed")
            self.assertEqual(result["attempted"], 1)
            self.assertEqual(result["installed_unreviewed"], 1)
            self.assertEqual(calls[0][1], "a")
            self.assertTrue(result["no_artwork_uploaded"])

    def test_unknown_roles_and_individual_install_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ValueError, "Unknown role"):
                plan_personal_sources(
                    temp, only_profiles=["genshin_absent"],
                    coverage=fake_coverage(), inventory=fake_inventory())
            report = plan_personal_sources(
                temp, coverage=fake_coverage(), inventory=fake_inventory())
            def fail(provider, key, root):
                raise RuntimeError("network offline")
            outcome = install_personal_plan(
                report, temp, confirmed=True, dispatch=fail)
            self.assertEqual(outcome["failed"], 1)
            self.assertIn("network offline", outcome["results"][0]["reason"])

    def test_successful_import_return_is_not_a_valid_installed_character(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = plan_personal_sources(
                temp, coverage=fake_coverage(), inventory=fake_inventory())
            progress = []
            outcome = install_personal_plan(
                plan, temp, confirmed=True, max_roles=1,
                dispatch=lambda *_: None, progress=progress.append)
            self.assertEqual(outcome["installed_unreviewed"], 0)
            self.assertEqual(outcome["failed"], 1)
            self.assertTrue(outcome["results"][0]["post_install_validation_failed"])
            self.assertTrue(outcome["post_install_inventory_checked"])
            self.assertEqual(progress[-1]["status"], "failed")

    def test_inventory_scan_failure_must_not_claim_installed(self):
        with tempfile.TemporaryDirectory() as temp:
            plan = plan_personal_sources(
                temp, coverage=fake_coverage(), inventory=fake_inventory())
            def fail_scan(_root):
                raise ValueError("broken binding metadata")
            outcome = install_personal_plan(
                plan, temp, confirmed=True, max_roles=1,
                dispatch=lambda *_: None, inventory_reader=fail_scan)
            self.assertEqual(outcome["installed_unreviewed"], 0)
            self.assertEqual(outcome["failed"], 1)
            self.assertFalse(outcome["post_install_inventory_checked"])
            self.assertIn("broken binding", outcome["post_install_inventory_error"])

    def test_symlink_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            link = root / "linked"
            try:
                link.symlink_to(root, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks cannot be created on this runner")
            with self.assertRaisesRegex(ValueError, "symlink"):
                plan_personal_sources(link, coverage=fake_coverage(),
                                      inventory=fake_inventory())


if __name__ == "__main__":
    unittest.main()
