"""R5 creator alternate installation never overwrites original 65 role receipts."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from tools.install_r5_q_review_alternates import stage_r5_original_alternatives


class StageTwoVerifiedChibiAlternatesTests(unittest.TestCase):
    def _fixtures(self, base, *, risky=False, wrong_identity=False):
        root = base / "res" / "role"
        root.mkdir(parents=True)
        (root / "OriginalPersonalArtist").mkdir()
        (root / "OriginalPersonalArtist" / "source.txt").write_text("ORIGINAL")
        record = {}

        def install(kind, staging, *, confirmed):
            self.assertTrue(confirmed)
            name = "SourceShimeji" + kind.title()
            dest = staging / name
            dest.mkdir(parents=True)
            (dest / "PERSONAL_IMPORT.json").write_text(json.dumps({
                "selected_profile": "genshin_" + kind}), encoding="utf-8")
            record[name] = kind
            return {"folder": name, "profile": (
                "genshin_wrong" if wrong_identity else "genshin_" + kind)}

        def inspect(staging, folder):
            return {
                "silhouette_width_height_ratio": 0.71,
                "risk_indicators": ["narrow_tall_silhouette_needs_human_review"] if risky else [],
                "weak_movement_action_evidence": [],
            }

        def scan(root_to_check):
            if root_to_check == root:
                return {"summary": {"personal_art_profile_count": 63},
                        "characters": []}
            return {"summary": {"personal_art_profile_count": len(record)},
                    "characters": [{
                        "profile": "genshin_" + key, "status": "structurally_installed",
                        "installed_folders": [{"folder": "SourceShimeji"+key.title(),
                                               "is_original_demo": False}],
                    } for key in record.values()]}

        def mascot(_):
            return {"summary": {"imported_creator_art_count": 2}}

        return root, install, inspect, scan, mascot

    def test_adds_two_candidate_versions_without_changing_original_art(self):
        with TemporaryDirectory() as d:
            root, install, inspect, scan, mascot = self._fixtures(Path(d))
            with patch("tools.install_r5_q_review_alternates.scan_genshin_library",
                       side_effect=scan), patch(
                       "tools.install_r5_q_review_alternates.scan_mascot_library",
                       side_effect=mascot):
                result = stage_r5_original_alternatives(
                    root, confirmed=True, install=install, measure=inspect,
                    full_audit=lambda role: {"summary": {"animation_structure_passed": True}})
            self.assertEqual(result["additional_original_author_versions"], 2)
            self.assertEqual(result["unchanged_distinct_genshin_profiles"], 63)
            self.assertEqual(result["user_q_approved"], 0)
            self.assertFalse(result["overwrote_existing_source_art"])
            self.assertEqual((root/"OriginalPersonalArtist"/"source.txt").read_text(), "ORIGINAL")
            self.assertTrue((root/"SourceShimejiAyaka").is_dir())
            self.assertTrue((root/"SourceShimejiVenti").is_dir())

    def test_bad_shape_aborts_before_modifying_existing_install(self):
        with TemporaryDirectory() as d:
            root, install, inspect, scan, mascot = self._fixtures(Path(d), risky=True)
            with patch("tools.install_r5_q_review_alternates.scan_genshin_library",
                       side_effect=scan), patch(
                       "tools.install_r5_q_review_alternates.scan_mascot_library",
                       side_effect=mascot):
                with self.assertRaisesRegex(ValueError, "standee"):
                    stage_r5_original_alternatives(
                        root, confirmed=True, install=install, measure=inspect)
            self.assertEqual(sorted(x.name for x in root.iterdir()), ["OriginalPersonalArtist"])

    def test_consent_identity_and_no_overwrite(self):
        with TemporaryDirectory() as d:
            root, install, inspect, scan, mascot = self._fixtures(Path(d), wrong_identity=True)
            with self.assertRaisesRegex(ValueError, "consent"):
                stage_r5_original_alternatives(root)
            with patch("tools.install_r5_q_review_alternates.scan_genshin_library",
                       side_effect=scan), patch(
                       "tools.install_r5_q_review_alternates.scan_mascot_library",
                       side_effect=mascot):
                with self.assertRaisesRegex(ValueError, "identity"):
                    stage_r5_original_alternatives(
                        root, confirmed=True, install=install, measure=inspect)
                (root / "SourceShimejiAyaka").mkdir()
                with self.assertRaisesRegex(ValueError, "overwrite"):
                    stage_r5_original_alternatives(
                        root, confirmed=True, install=install, measure=inspect)


if __name__ == "__main__":
    unittest.main()
