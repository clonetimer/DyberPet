"""Read-only original-art pose alternatives: only conservative review leads."""
from __future__ import annotations

import unittest

from tools.creator_motion_alternatives import compare_motion_evidence


def motion(*, action="crawl", frames=1, poses=1, risks=(), move=True):
    return {"action": action, "frame_count": frames,
            "unique_visible_poses": poses, "movement_expected": move,
            "risk_indicators": list(risks)}


class MotionAlternativeReviewTests(unittest.TestCase):
    def test_single_frame_vs_real_different_poses_recommends_only_review(self):
        weak = motion(risks=("single_frame_motion",))
        rich = motion(frames=6, poses=4)
        a = compare_motion_evidence(weak, rich)
        self.assertEqual(a["candidate_index"], 1)
        self.assertEqual(a["status"], "stronger_pose_evidence_pending_human_review")
        self.assertIn("右侧 B", a["text"])
        self.assertFalse(a["human_likeness_approved"])
        self.assertFalse(a["motion_semantics_approved"])
        self.assertFalse(a["source_art_modified"])
        b = compare_motion_evidence(rich, weak)
        self.assertEqual(b["candidate_index"], 0)
        self.assertIn("左侧 A", b["text"])

    def test_translated_sprite_does_not_beat_real_distinct_poses(self):
        bad = motion(action="fall", frames=8, poses=1,
                     risks=("translation_only_or_static_pose",))
        richer = motion(action="fall", frames=8, poses=6)
        self.assertEqual(compare_motion_evidence(bad, richer)["candidate_index"], 1)

    def test_both_weak_both_good_and_unknown_never_award_winner(self):
        cases = [
            (motion(risks=("single_frame_motion",)),
             motion(risks=("single_frame_motion",))),
            (motion(frames=3, poses=3), motion(frames=8, poses=7)),
            (motion(frames=9, poses=3, risks=("long_identical_pose_run",)),
             motion(frames=8, poses=1, risks=("translation_only_or_static_pose",))),
            (motion(frames=8, poses=3, risks=("fully_transparent_frame",)),
             motion(frames=8, poses=5)),
            (motion(move=False), motion(frames=5, poses=5)),
            (None, motion(frames=5, poses=5)),
            (motion(frames=1, poses=1, risks=("single_frame_motion",)),
             {"action": "crawl", "movement_expected": True}),
        ]
        for left, right in cases:
            with self.subTest(left=left, right=right):
                result = compare_motion_evidence(left, right)
                self.assertIsNone(result["candidate_index"])
                self.assertFalse(result["human_likeness_approved"])

    def test_invalid_and_inconsistent_audits_never_win(self):
        wrong = motion(frames=1, poses=5)
        self.assertIsNone(compare_motion_evidence(
            motion(risks=("single_frame_motion",)), wrong)["candidate_index"])
        wrong2 = motion(frames=True, poses=True)
        self.assertIsNone(compare_motion_evidence(
            wrong2, motion(frames=5, poses=4))["candidate_index"])


if __name__ == "__main__":
    unittest.main()
