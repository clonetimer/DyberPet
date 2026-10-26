"""Integrated 123+2 gap reporting must never confuse provenance with readiness."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.creator_assistant_gap_report import make_gap_report, save_gap_report


def reports():
    src = {"characters": [
        {"id": "genshin_a", "source_found": True, "source_candidate_count": 2},
        {"id": "genshin_b", "source_found": False, "source_candidate_count": 0},
    ]}
    def role(identity, *, family="genshin", folders=0, usable=0, actions=()):
        return {
            "id": identity, "name": identity, "family": family,
            "imported_creator_role_count": folders,
            "playable_creator_role_count": usable,
            "original_creator_art_present": bool(usable),
            "actual_action_names": list(actions),
            "action_categories_present_in_art": ["greet"] if actions else [],
            "action_categories_missing_in_art": ["jump", "sleep"] if actions else ["greet", "jump", "sleep"],
            "errors": [],
        }
    installed = {"characters": [
        role("genshin_a"),
        role("genshin_b", folders=1, usable=1, actions=("wave",)),
        role("mascot_guga", family="mascot", folders=1, usable=0),
        role("mascot_doro", family="mascot"),
    ]}
    return src, installed


class CreatorAssistantIntegrationTests(unittest.TestCase):
    def test_stages_are_independent_and_mascots_not_in_123_denominator(self):
        source, installed = reports()
        out = make_gap_report(".", pinned_report=source, installed_report=installed)
        rows = {x["id"]: x for x in out["roles"]}
        self.assertEqual(out["summary"]["genshin_template_count"], 2)
        self.assertEqual(out["summary"]["mascot_template_count"], 2)
        self.assertEqual(out["summary"]["pinned_genshin_source_count"], 1)
        self.assertEqual(rows["genshin_a"]["stage"], "pinned_source_not_installed")
        self.assertEqual(rows["genshin_b"]["stage"], "local_creator_first_frame_decodable")
        self.assertEqual(rows["mascot_guga"]["stage"], "local_creator_files_unplayable")
        self.assertEqual(rows["mascot_doro"]["stage"], "missing_pinned_source")
        self.assertEqual(rows["genshin_b"]["available_action_categories_in_art"], ["greet"])
        for row in rows.values():
            self.assertFalse(row["human_original_likeness_verified"])
            self.assertFalse(row["complete_motion_sequence_verified"])
            self.assertFalse(row["physical_desktop_playback_verified"])
            self.assertFalse(row["voice_fidelity_verified"])

    def test_cross_character_identity_mismatch_is_a_hard_failure(self):
        source, installed = reports()
        installed["characters"][0]["id"] = "genshin_b"
        with self.assertRaises(ValueError):
            make_gap_report(".", pinned_report=source, installed_report=installed)
        source, installed = reports()
        installed["characters"][0]["id"] = "genshin_wrong"
        with self.assertRaises(ValueError):
            make_gap_report(".", pinned_report=source, installed_report=installed)

    def test_invalid_counts_do_not_inflate_coverage(self):
        source, installed = reports()
        installed["characters"][1]["playable_creator_role_count"] = 2
        with self.assertRaises(ValueError):
            make_gap_report(".", pinned_report=source, installed_report=installed)
        source, installed = reports()
        source["characters"][0]["source_found"] = False
        with self.assertRaises(ValueError):
            make_gap_report(".", pinned_report=source, installed_report=installed)

    def test_output_is_only_written_after_explicit_export(self):
        source, installed = reports()
        with tempfile.TemporaryDirectory() as td:
            target = Path(td) / "report.json"
            output = make_gap_report(td, pinned_report=source, installed_report=installed)
            self.assertFalse(target.exists())
            save_gap_report(target, output)
            self.assertEqual(json.loads(target.read_text(encoding="utf-8")), output)
            with self.assertRaises(ValueError):
                save_gap_report(Path(td) / "not-json.txt", output)

    def test_real_empty_install_tree_does_not_fake_available_roles(self):
        with tempfile.TemporaryDirectory() as td:
            report = make_gap_report(Path(td))
        s = report["summary"]
        self.assertGreaterEqual(s["genshin_template_count"], 100)
        self.assertEqual(s["mascot_template_count"], 2)
        self.assertEqual(s["genshin_with_decodable_creator_first_frame"], 0)
        self.assertEqual(s["mascots_with_decodable_creator_first_frame"], 0)
        self.assertEqual(
            s["pinned_genshin_source_count"] + s["genshin_without_pinned_source"],
            s["genshin_template_count"])


if __name__ == "__main__":
    unittest.main()
