"""Regression tests for the *installed-asset* Q版三视图 evidence gate."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

from tools.qchibi_threeview_audit import audit_role, audit_role_root, main


class QChibiPackagedEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "res" / "role"
        self.role = self.root / "QChibiTest"
        action = self.role / "threeview"
        action.mkdir(parents=True)
        (self.role / "pet_conf.json").write_text("{}", encoding="utf-8")
        (self.role / "act_conf.json").write_text("{}", encoding="utf-8")
        self.files = {}
        for name, box in [
            ("front", (7, 7, 27, 47)),
            ("side", (11, 9, 28, 46)),
            ("back", (8, 8, 29, 48)),
        ]:
            image = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
            ImageDraw.Draw(image).rectangle(box, fill=(80, 115, 220, 255))
            # An asymmetric accessory ensures mirror tests are meaningful.
            ImageDraw.Draw(image).rectangle(
                (box[0] + 1, box[1] + 2, box[0] + 3, box[1] + 5),
                fill=(240, 80, 30, 255))
            path = action / (name + ".png")
            image.save(path)
            self.files[name] = path

    def _manifest(self):
        content = {
            "schema_version": 1,
            "source_url": "https://example.org/art-source",
            "artist": "same artist",
            "variant": "one costume version",
            "views": {},
        }
        for name, path in self.files.items():
            content["views"][name] = {
                "file": "threeview/" + path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        (self.role / "Q_CHIBI_3VIEW.json").write_text(
            json.dumps(content), encoding="utf-8")

    def test_missing_sources_do_not_become_completed_threeviews(self):
        report = audit_role_root(self.root)
        self.assertEqual(report["summary"]["installed_role_folders"], 1)
        self.assertEqual(report["summary"]["source_threeview_candidates"], 0)
        self.assertEqual(report["summary"]["missing_source_threeviews"], 1)
        self.assertFalse(report["roles"][0]["character_likeness_verified"])
        self.assertEqual(report["roles"][0]["views"], {})

    def test_declared_independent_views_still_require_human_review(self):
        self._manifest()
        before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in self.files.values()}
        result = audit_role(self.role)
        self.assertEqual(result["status"],
                         "threeview_source_candidate_manual_review_required")
        self.assertTrue(result["source_threeview_complete"])
        self.assertEqual(set(result["views"]), {"front", "side", "back"})
        self.assertFalse(result["threeview_human_approved"])
        self.assertFalse(result["character_likeness_verified"])
        self.assertEqual(before, {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in self.files.values()})

    def test_mirror_cannot_count_as_independent_back_reference(self):
        with Image.open(self.files["front"]) as front:
            ImageOps.mirror(front).save(self.files["back"])
        self._manifest()
        row = audit_role(self.role)
        self.assertEqual(row["status"], "threeview_requires_source_correction")
        self.assertFalse(row["source_threeview_complete"])
        self.assertIn("front_back:exact_horizontal_mirror", row["issues"])

    def test_distinct_png_bytes_with_identical_pixels_rejected(self):
        with Image.open(self.files["front"]) as front:
            front.save(self.files["back"], compress_level=1)
        self.assertNotEqual(self.files["front"].read_bytes(),
                            self.files["back"].read_bytes())
        self._manifest()
        row = audit_role(self.role)
        self.assertIn("front_back:identical_visible_pixels", row["issues"])

    def test_bad_hash_is_not_a_valid_threeview(self):
        self._manifest()
        path = self.role / "Q_CHIBI_3VIEW.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["views"]["back"]["sha256"] = "0" * 64
        path.write_text(json.dumps(data), encoding="utf-8")
        report = audit_role_root(self.root)
        self.assertEqual(report["summary"]["invalid_or_suspicious_evidence"], 1)
        self.assertEqual(report["roles"][0]["status"],
                         "invalid_threeview_evidence")

    def test_shared_system_action_directory_is_not_a_playable_role(self):
        sysdir = self.root / "sys"
        sysdir.mkdir()
        (sysdir / "act_conf.json").write_text("{}", encoding="utf-8")
        report = audit_role_root(self.root)
        self.assertEqual(report["summary"]["installed_role_folders"], 1)
        self.assertEqual(report["summary"]["invalid_or_suspicious_evidence"], 0)

    def test_generated_ci_demo_art_is_not_counted_as_real_source_character(self):
        demo = self.root / "DemoG_fixture"
        demo.mkdir()
        (demo / "BUILTIN_CHIBI_DEMO.json").write_text(json.dumps({
            "generator": "DyberPet-first-party-abstract-chibi-v1",
            "profile": "genshin_fixture",
            "official_character_art": False,
            "original_illustration": True,
        }), encoding="utf-8")
        report = audit_role_root(self.root)
        self.assertEqual(report["summary"]["installed_role_folders"], 1)
        self.assertEqual(report["summary"]["excluded_generated_test_demos"], 1)
        self.assertEqual(report["summary"]["source_threeview_candidates"], 0)

    def test_cli_writes_report_but_never_changes_role_art(self):
        self._manifest()
        dest = self.root.parent.parent / "audit.json"
        self.assertEqual(main(["--role-root", str(self.root),
                               "--out", str(dest),
                               "--fail-on-invalid"]), 0)
        self.assertEqual(json.loads(dest.read_text(encoding="utf-8"))[
            "summary"]["source_threeview_candidates"], 1)


if __name__ == "__main__":
    unittest.main()
