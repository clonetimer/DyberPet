"""R4 Q-style/standee gates: no creator can be approved by file presence alone."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image
from tools.creator_art_manual_review import create_manual_review_receipt
from tools.creator_chibi_quality import (
    evaluate_quality_receipt, load_local_quality_review, save_local_quality_review,
    summarize_local_quality)


def maker(root, *, same_walk=False):
    role = root / "SourceArtistQ"
    action = role / "action"
    action.mkdir(parents=True)
    pet = {"default": "default", "left": "left_walk"}
    acts = {"default": {"images": "idle"},
            "left_walk": {"images": "walk", "need_move": True}}
    (role / "pet_conf.json").write_text(json.dumps(pet), encoding="utf-8")
    (role / "act_conf.json").write_text(json.dumps(acts), encoding="utf-8")
    Image.new("RGBA", (24, 32), (255, 10, 30, 255)).save(action / "idle_0.png")
    for i in range(2):
        Image.new("RGBA", (24, 32), (30 + (0 if same_walk else 20*i), 50, 200, 255)).save(
            action / f"walk_{i}.png")
    return role, {"default": [action / "idle_0.png"],
                  "left_walk": [action / "walk_0.png", action / "walk_1.png"]}


def review(root, inventory, **overrides):
    values = {
        "grade": "A 原设较吻合", "compared_to_reference": True,
        "motion_checked": True, "notes": "personally reviewed",
        "chibi_form": "圆润Q版", "desktop_checked": True,
    }
    values.update(overrides)
    seen = {k: set(range(len(v))) for k, v in inventory.items()}
    return create_manual_review_receipt(
        root, "SourceArtistQ", inventory, seen, **values)


class CreatorQGateTests(unittest.TestCase):
    def test_no_review_is_unreviewed_and_never_standard(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            maker(root)
            self.assertEqual(
                load_local_quality_review(root, "SourceArtistQ")["status"],
                "unreviewed_candidate")
            summary = summarize_local_quality(root, {
                "genshin_amber": ["SourceArtistQ"]})
            self.assertEqual(summary["summary"]["user_q_standard_eligible"], 0)
            self.assertEqual(summary["summary"]["pending_or_unreviewed"], 1)

    def test_personal_q_a_grade_and_all_frames_desktop_checked_all_required(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            maker(root)
            _role, frames = maker_already(root)
            record = review(root, frames)
            outcome = save_local_quality_review(root, "SourceArtistQ", record)
            self.assertEqual(outcome["status"], "user_q_standard_eligible")
            self.assertEqual(
                load_local_quality_review(root, "SourceArtistQ")["status"],
                "user_q_standard_eligible")
            text = (root.parent.parent / "data" / "creator_quality_reviews" /
                    "SourceArtistQ.json")
            self.assertTrue(text.is_file())
            self.assertFalse((root / "SourceArtistQ" / "QUALITY.json").exists())

    def test_standee_human_rejection_and_removal_from_standard(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            _, frames = maker(root)
            receipt = review(root, frames, chibi_form="立牌/细长立绘")
            outcome = save_local_quality_review(root, "SourceArtistQ", receipt)
            self.assertEqual(outcome["status"], "rejected_standee")
            summary = summarize_local_quality(root, {"genshin_fischl": ["SourceArtistQ"]})
            self.assertEqual(summary["summary"]["rejected_standee_profiles"], 1)
            self.assertEqual(summary["summary"]["user_q_standard_eligible"], 0)

    def test_incomplete_motion_and_missing_desktop_check_block_approval(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            _, frames = maker(root, same_walk=True)
            self.assertEqual(
                evaluate_quality_receipt(root, "SourceArtistQ",
                                         review(root, frames))["status"],
                "rejected_motion")
            self.assertEqual(
                evaluate_quality_receipt(root, "SourceArtistQ",
                                         review(root, frames, desktop_checked=False))["status"],
                "candidate_not_approved")
            self.assertEqual(
                evaluate_quality_receipt(root, "SourceArtistQ",
                                         review(root, frames, chibi_form="未评价"))["status"],
                "candidate_not_approved")

    def test_source_file_change_invalidates_old_q_pass(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            role, frames = maker(root)
            receipt = review(root, frames)
            save_local_quality_review(root, "SourceArtistQ", receipt)
            Image.new("RGBA", (24, 32), (0, 0, 0, 255)).save(
                role / "action" / "idle_0.png")
            self.assertEqual(
                load_local_quality_review(root, "SourceArtistQ")["status"],
                "source_changed_recheck")
            with self.assertRaisesRegex(ValueError, "变化"):
                save_local_quality_review(root, "SourceArtistQ", receipt)

    def test_no_label_without_full_image_audit(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            _, frames = maker(root)
            r = review(root, frames)
            self.assertEqual(
                evaluate_quality_receipt(root, "SourceArtistQ", r,
                                         full_audit=False)["status"],
                "candidate_not_approved")


def maker_already(root):
    role = root / "SourceArtistQ"
    action = role / "action"
    return role, {"default": [action / "idle_0.png"],
                  "left_walk": [action / "walk_0.png", action / "walk_1.png"]}


if __name__ == "__main__":
    unittest.main()
