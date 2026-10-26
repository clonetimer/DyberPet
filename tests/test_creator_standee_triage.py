"""Automated standee-shape flags are triage ONLY; never Q acceptance."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tools.creator_standee_triage import triage_one_creator


def mock_art(root, name, *, thin=False, stationary=False):
    dest = root / name
    (dest / "action").mkdir(parents=True)
    config = {"default": {"images": "idle"},
              "left_walk": {"images": "walk", "need_move": True}}
    (dest / "act_conf.json").write_text(json.dumps(config), encoding="utf-8")
    (dest / "pet_conf.json").write_text(
        '{"default":"default","left":"left_walk"}', encoding="utf-8")
    size = (20, 70) if thin else (60, 60)
    Image.new("RGBA", size, (225, 89, 101, 255)).save(
        dest / "action" / "idle_0.png")
    for i in range(2):
        color = (25, 75, 105, 255) if stationary else (25 + 60*i, 75, 105, 255)
        Image.new("RGBA", size, color).save(dest / "action" / f"walk_{i}.png")
    return dest


class AutomatedReviewLeadTests(unittest.TestCase):
    def test_cardboard_thin_and_fake_walk_are_flags_never_a_verdict(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            mock_art(root, "SourceThin", thin=True, stationary=True)
            report = triage_one_creator(root, "SourceThin")
            self.assertEqual(report["status"], "review_priority")
            self.assertIn("extremely_thin_tall_silhouette_needs_human_review",
                          report["risk_indicators"])
            self.assertIn("one_or_more_weak_movement_sequences",
                          report["risk_indicators"])
            self.assertFalse(report["auto_generated_standee_verdict"])
            self.assertFalse(report["human_chibi_likeness_qa"])

    def test_round_shape_not_auto_passed_q(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            mock_art(root, "SourceRound", thin=False, stationary=False)
            report = triage_one_creator(root, "SourceRound")
            self.assertEqual(report["status"], "unverified_visual_candidate")
            self.assertEqual(report["risk_indicators"], [])
            self.assertTrue(report["not_a_pass_or_fail_classification"])
            self.assertFalse(report["human_chibi_likeness_qa"])

    def test_source_demo_and_traversal_not_reviewed_as_author_art(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            role = mock_art(root, "SourceDemo")
            (role / "BUILTIN_CHIBI_DEMO.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "Demo"):
                triage_one_creator(root, "SourceDemo")
            with self.assertRaisesRegex(ValueError, "folder"):
                triage_one_creator(root, "../outside")


if __name__ == "__main__":
    unittest.main()
