"""R40: read real bound PNG sequences, distinguish motion evidence from QA."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.artist_motion_audit import (
    audit_native_motion, write_motion_evidence, _sample_paths,
)


def native_fixture(folder, *, moving=True, walk_fallback=False,
                   cropped=False, has_blank=False):
    (folder / "action").mkdir(parents=True)
    pet = {"default": "idle", "drag": "idle", "fall": "idle",
           "left": "idle" if walk_fallback else "left_walk",
           "right": "idle" if walk_fallback else "right_walk"}
    acts = {"idle": {"images": "idle", "frame_refresh": 0.2}}
    if not walk_fallback:
        acts.update({key: {"images": key, "frame_refresh": 0.1}
                     for key in ("left_walk", "right_walk")})
    (folder / "pet_conf.json").write_text(json.dumps(pet))
    (folder / "act_conf.json").write_text(json.dumps(acts))
    for name in acts:
        for i in range(5):
            frame = Image.new("RGBA", (48, 56), (0, 0, 0, 0))
            if not (has_blank and name == "left_walk" and i == 3):
                x = 3 + i * 3 if moving and name != "idle" else 3
                if cropped and name == "right_walk":
                    x = 0
                for xx in range(x, x + 10):
                    for yy in range(12, 28):
                        frame.putpixel((xx, yy), (140, 80, 200, 255))
            frame.save(folder / "action" / f"{name}_{i}.png")


class ArtistMotionEvidenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.role = Path(tmp.name) / "作者原画"

    def test_real_distinct_frames_and_no_modified_art(self):
        native_fixture(self.role)
        frame = self.role / "action" / "left_walk_0.png"
        original = frame.read_bytes()
        report = audit_native_motion(self.role)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["actions"]["left"]["visually_distinct_samples"], 5)
        self.assertEqual(report["actions"]["right"]["visually_distinct_samples"], 5)
        self.assertEqual(report["actions"]["default"]["visually_distinct_samples"], 1)
        self.assertEqual(report["analyzed_actions"], 5)
        self.assertFalse(report["animation_quality_automatically_approved"])
        self.assertFalse(report["rights_or_identity_certified"])
        self.assertTrue(report["manual_visual_review_pending"])
        self.assertFalse(report["warnings"])
        self.assertFalse((self.role / "ANIMATION_MOTION_QA.json").exists())
        made = write_motion_evidence(self.role)
        self.assertEqual(made["actions"]["left"]["frames_in_source"], 5)
        self.assertEqual(frame.read_bytes(), original)
        parsed = json.loads((self.role / "ANIMATION_MOTION_QA.json").read_text(encoding="utf-8"))
        self.assertEqual(parsed["role_folder"], self.role.name)
        with self.assertRaises(FileExistsError):
            write_motion_evidence(self.role)

    def test_reused_idle_or_static_motion_is_flagged_not_certified(self):
        native_fixture(self.role, moving=False, walk_fallback=True)
        result = audit_native_motion(self.role)
        warnings = " ".join(result["warnings"])
        self.assertIn("walk reuses idle animation binding", warnings)
        self.assertIn("no visual pose changes", warnings)
        self.assertIn("both movement directions bind same animation", warnings)
        self.assertFalse(result["animation_quality_automatically_approved"])

    def test_cropping_and_blank_frames_are_review_warnings(self):
        native_fixture(self.role, cropped=True, has_blank=True)
        result = audit_native_motion(self.role)
        warnings = " ".join(result["warnings"])
        self.assertIn("source may touch viewport boundary", warnings)
        self.assertIn("sampled transparent/empty frames", warnings)
        self.assertEqual(result["actions"]["left"]["blank_samples"], 1)
        self.assertEqual(result["actions"]["right"]["edge_touch_samples"], 5)

    def test_bounded_sampling_and_no_privacy_leaking_absolute_paths(self):
        sample = _sample_paths(list(range(999)))
        self.assertEqual(len(sample), 9)
        self.assertEqual(sample[0], 0)
        self.assertEqual(sample[-1], 998)
        native_fixture(self.role)
        result = audit_native_motion(self.role)
        self.assertNotIn(str(self.role.parent), json.dumps(result))
        self.assertEqual(result["actions"]["default"]["sampled_frames"], 5)

    def test_bad_source_is_rejected_not_dressed_as_success(self):
        native_fixture(self.role)
        (self.role / "action" / "idle_0.png").write_bytes(b"corrupt")
        with self.assertRaises(ValueError):
            audit_native_motion(self.role)
        self.assertFalse((self.role / "ANIMATION_MOTION_QA.json").exists())


if __name__ == "__main__":
    unittest.main()
