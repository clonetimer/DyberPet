"""Integrated 123+2 gap reporting must never confuse provenance with readiness."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

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

    def test_opt_in_full_frame_audit_catches_corrupt_later_frame(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            role = root / "RealSayu"
            art = role / "action"
            art.mkdir(parents=True)
            (role / "pet_conf.json").write_text(
                json.dumps({"default": "walk"}), encoding="utf-8")
            (role / "act_conf.json").write_text(
                json.dumps({"walk": {"images": "walk", "need_move": True}}),
                encoding="utf-8")
            Image.new("RGBA", (4, 4), (255, 0, 0, 255)).save(art / "walk_0.png")
            (art / "walk_1.png").write_bytes(b"not-a-png-second-frame")
            src, installed = reports()
            installed["characters"][1]["playable_creator_role_folders"] = ["RealSayu"]
            ordinary = make_gap_report(root, pinned_report=src, installed_report=installed)
            self.assertEqual(
                next(x for x in ordinary["roles"] if x["id"] == "genshin_b")
                ["full_frame_structure_audit"]["status"], "not_requested")
            checked = make_gap_report(root, pinned_report=src, installed_report=installed,
                                      deep_frame_audit=True)
            row = next(x for x in checked["roles"] if x["id"] == "genshin_b")
            self.assertEqual(row["stage"], "local_creator_first_frame_decodable")
            self.assertEqual(row["full_frame_structure_audit"]["status"], "has_structure_issues")
            self.assertFalse(row["complete_motion_sequence_verified"])
            self.assertEqual(checked["summary"]["roles_with_full_frame_structure_issues"], 1)
            self.assertEqual(checked["summary"]["roles_with_full_frame_structure_checked"], 1)
            Image.new("RGBA", (4, 4), (0, 0, 255, 255)).save(art / "walk_1.png")
            good = make_gap_report(root, pinned_report=src, installed_report=installed,
                                   deep_frame_audit=True)
            good_role = next(x for x in good["roles"] if x["id"] == "genshin_b")
            self.assertEqual(good_role["full_frame_structure_audit"]["status"],
                             "passed_structure")
            self.assertEqual(good_role["full_frame_structure_audit"]["folders"][0]
                             ["frame_count"], 2)
            self.assertFalse(good_role["physical_desktop_playback_verified"])

    def test_full_frame_audit_rejects_untrusted_folder_names(self):
        with tempfile.TemporaryDirectory() as td:
            src, installed = reports()
            art = installed["characters"][1]
            art["playable_creator_role_folders"] = ["../Outside"]
            output = make_gap_report(td, pinned_report=src, installed_report=installed,
                                     deep_frame_audit=True)
            row = next(x for x in output["roles"] if x["id"] == "genshin_b")
            self.assertEqual(row["full_frame_structure_audit"]["status"], "has_structure_issues")
            self.assertIn("unreadable_or_incomplete_sequence",
                          row["full_frame_structure_audit"]["folders"][0]["issue_categories"])
            art["playable_creator_role_folders"] = []
            with self.assertRaises(ValueError):
                make_gap_report(td, pinned_report=src, installed_report=installed,
                                deep_frame_audit=True)

    def test_integrated_per_version_audit_never_claims_combined_actions_available(self):
        source, installed = reports()
        row = installed["characters"][1]
        row["imported_creator_role_count"] = 2
        row["playable_creator_role_count"] = 2
        row["creator_role_variants"] = [
            {"folder": "Source1", "status": "has_decodable_first_frames",
             "available_category_ids": ["greet"], "installed_action_names": ["wave"]},
            {"folder": "Source2", "status": "has_decodable_first_frames",
             "available_category_ids": ["jump"], "installed_action_names": ["jump"]},
        ]
        row["action_categories_present_in_art"] = ["greet", "jump"]
        row["action_categories_missing_in_art"] = ["sleep"]
        row["action_categories_in_every_usable_version"] = []
        row["action_categories_only_in_some_versions"] = ["greet", "jump"]
        result = make_gap_report(".", pinned_report=source, installed_report=installed)
        by_id = {x["id"]: x for x in result["roles"]}
        entry = by_id["genshin_b"]
        self.assertEqual(entry["interaction_scope"],
                         "union_of_installed_versions_not_runtime_role")
        self.assertEqual(entry["categories_shared_by_every_usable_version"], [])
        self.assertEqual(entry["categories_missing_from_at_least_one_usable_version"],
                         ["greet", "jump"])
        self.assertEqual(len(entry["per_installed_creator_version"]), 2)
        self.assertEqual(result["summary"]["roles_with_version_specific_action_gaps"], 1)
        self.assertEqual(result["summary"]["roles_with_multiple_imported_creator_versions"], 1)
        self.assertFalse(entry["physical_desktop_playback_verified"])

    def test_variant_receipts_reject_double_counting_the_same_folder(self):
        source, installed = reports()
        art = installed["characters"][1]
        art["creator_role_variants"] = [
            {"folder": "Shared", "status": "has_decodable_first_frames"},
            {"folder": "Shared", "status": "has_decodable_first_frames"},
        ]
        art["imported_creator_role_count"] = 2
        art["playable_creator_role_count"] = 2
        with self.assertRaises(ValueError):
            make_gap_report(".", pinned_report=source, installed_report=installed)

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
