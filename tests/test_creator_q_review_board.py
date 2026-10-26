"""R5 per-version original PNG comparison, no fake Q approvals or sources."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image
from tools.creator_q_review_board import make_review_board


SCOPE = "read_only_original_art_automated_review_priorities_not_likeness_grade"


def artist(root, name, *, with_image=True):
    role = root / name
    action = role / "action"
    action.mkdir(parents=True, exist_ok=True)
    (role / "pet_conf.json").write_text('{"default":"idle"}', encoding="utf-8")
    (role / "act_conf.json").write_text('{"idle":{"images":"idle"}}', encoding="utf-8")
    if with_image:
        Image.new("RGBA", (22, 60), (190, 80, 90, 255)).save(
            action / "idle_0.png")
    return role


def evidence(folders):
    return {
        "scope": SCOPE,
        "versions": [{
            "id": ident, "folder": name, "status": "review_priority",
            "silhouette_width_height_ratio": .366,
            "risk_indicators": ["extremely_thin_tall_silhouette_needs_human_review"],
            "weak_movement_action_evidence": [{"action": "left_walk", "evidence": "single_frame_motion"}],
        } for ident, name in folders]
    }


def pinned():
    return {"characters": [{
        "id": "genshin_amber", "name": "安柏",
        "source_candidates": [
            {"provider": "react_lfs", "source_key": "amber",
             "url": "https://github.com/example/pinned", "visual_verified": False},
            {"provider": "native", "source_key": "new_amber",
             "url": "https://github.com/example/native", "visual_verified": False},
        ]}, {
        "id": "genshin_ayaka", "name": "神里绫华",
        "source_candidates": []
    }]}


def quality():
    return {"profiles": {
        "genshin_amber": {
            "variants": [{"folder": "SourceAmber", "status": "user_q_standard_eligible"}]
        },
        "genshin_ayaka": {
            "variants": [{"folder": "SourceAyaka", "status": "rejected_standee"}]
        },
    }}


class CreatorComparisonDataTests(unittest.TestCase):
    def test_actual_frame_with_source_alternatives_and_no_injected_approval(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "res" / "role"
            artist(root, "SourceAmber")
            artist(root, "SourceAyaka")
            board = make_review_board(
                root,
                measured=evidence([
                    ("genshin_amber", "SourceAmber"),
                    ("genshin_ayaka", "SourceAyaka"),
                ]),
                sources=pinned(), quality=quality())
            self.assertEqual(board["summary"]["installed_artist_variants"], 2)
            self.assertEqual(board["summary"]["thin_risk_versions"], 2)
            self.assertEqual(board["summary"]["personally_q_approved_versions"], 0)
            by_id = {r["id"]: r for r in board["rows"]}
            self.assertEqual(by_id["genshin_amber"]["name"], "安柏")
            self.assertEqual(by_id["genshin_amber"]["available_source_option_count"], 2)
            self.assertTrue(Path(by_id["genshin_amber"]["first_png"]).is_file())
            self.assertEqual(by_id["genshin_amber"]["human_q_status"], "unreviewed_candidate")
            self.assertEqual(by_id["genshin_ayaka"]["human_q_status"], "rejected_standee")
            self.assertTrue(all(x["risk_is_not_a_q_style_verdict"] for x in board["rows"]))
            self.assertFalse(any(x["source_options"][0]["visual_verified"]
                                 for x in board["rows"] if x["source_options"]))

    def test_missing_png_never_becomes_synthetic_picture(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "res" / "role"
            artist(root, "SourceAmber", with_image=False)
            board = make_review_board(root, measured=evidence([
                ("genshin_amber", "SourceAmber"),
            ]), sources=pinned(), quality=quality())
            self.assertIsNone(board["rows"][0]["first_png"])

    def test_repeated_and_out_of_root_folders_rejected(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "res" / "role"
            artist(root, "SourceAmber")
            with self.assertRaisesRegex(ValueError, "same imported"):
                make_review_board(root, measured=evidence([
                    ("genshin_amber", "SourceAmber"), ("genshin_ayaka", "SourceAmber")]),
                    sources=pinned(), quality=quality())
            with self.assertRaisesRegex(ValueError, "Invalid"):
                make_review_board(root, measured=evidence([
                    ("genshin_amber", "../outside")]), sources=pinned(), quality=quality())


if __name__ == "__main__":
    unittest.main()
