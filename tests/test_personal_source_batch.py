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
            result = install_personal_plan(
                report, temp, confirmed=True, max_roles=1, dispatch=fake)
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
