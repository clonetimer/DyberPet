"""R5 transparent canvas normalization retains every real pixel and source PNG byte."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tools.artist_animation_audit import audit_native_character
from tools.normalize_creator_canvas import create_lossless_canvas_candidate


def artist(root, *, profile="genshin_ayaka"):
    role = root / "SourceShimejiAyaka"
    (role / "action").mkdir(parents=True)
    (role / "pet_conf.json").write_text(json.dumps({
        "default": "default", "width": 20, "height": 33,
        "left": "left_walk", "right": "left_walk",
    }), encoding="utf-8")
    (role / "act_conf.json").write_text(json.dumps({
        "default": {"images": "stand"},
        "left_walk": {"images": "walk", "need_move": True},
    }), encoding="utf-8")
    (role / "PERSONAL_IMPORT.json").write_text(json.dumps({
        "selected_profile": profile, "source_repository": "creator pinned",
    }), encoding="utf-8")
    frames = [("stand_0.png", (23, 32), (160, 50, 80, 255)),
              ("stand_1.png", (21, 34), (160, 65, 80, 255)),
              ("walk_0.png", (25, 34), (140, 70, 80, 255)),
              ("walk_1.png", (27, 29), (140, 95, 80, 255))]
    for name, shape, rgba in frames:
        Image.new("RGBA", shape, rgba).save(role/"action"/name)
    return role, frames


class ExactCreatorPixelNormalizationTests(unittest.TestCase):
    def test_inconsistent_original_dimensions_fixed_without_resizing_content(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)/"res"/"role"
            raw, files = artist(root)
            before = {x.name: hashlib.sha256(x.read_bytes()).hexdigest()
                      for x in (raw/"action").glob("*.png")}
            failed = audit_native_character(raw)
            self.assertFalse(failed["summary"]["animation_structure_passed"])
            self.assertIn("inconsistent_frame_dimensions",
                          failed["summary"]["issue_categories"])
            transformed = create_lossless_canvas_candidate(root, "SourceShimejiAyaka")
            self.assertEqual(transformed["folder"], "SourceCanvasR5Ayaka")
            self.assertTrue(transformed["only_transparent_canvas_added"])
            self.assertTrue(transformed["source_original_bytes_preserved"])
            self.assertFalse(transformed["q_likeness_manually_verified"])
            derived = root / transformed["folder"]
            self.assertTrue(audit_native_character(derived)["summary"]["animation_structure_passed"])
            provenance = json.loads((derived/"ORIGINAL_CANVAS_PADDING_R5.json").read_text())
            self.assertFalse(provenance["human_q_likeness_approved"])
            self.assertEqual(len(provenance["frames"]), len(files))
            for original_name, _shape, _rgba in files:
                raw_file = raw/"action"/original_name
                backup_file = derived/"source_original"/"action"/original_name
                fixed_file = derived/"action"/original_name
                self.assertEqual(hashlib.sha256(raw_file.read_bytes()).hexdigest(),
                                 before[original_name])
                self.assertEqual(backup_file.read_bytes(), raw_file.read_bytes())
                info = provenance["frames"][original_name]
                ox, oy = info["transparent_padding_left"], info["transparent_padding_above"]
                w, h = info["original_dimensions"]
                with Image.open(raw_file) as actual, Image.open(fixed_file) as fixed:
                    self.assertEqual(fixed.size, tuple(info["derived_dimensions"]))
                    self.assertEqual(fixed.crop((ox, oy, ox+w, oy+h)).convert("RGBA").tobytes(),
                                     actual.convert("RGBA").tobytes())

    def test_wrong_identity_and_second_install_cannot_be_overwritten(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)/"res"/"role"
            raw, files = artist(root, profile="genshin_furina")
            with self.assertRaisesRegex(ValueError, "does not match"):
                create_lossless_canvas_candidate(root, "SourceShimejiAyaka")
            (raw/"PERSONAL_IMPORT.json").write_text('{"selected_profile":"genshin_ayaka"}')
            create_lossless_canvas_candidate(root, "SourceShimejiAyaka")
            with self.assertRaisesRegex(ValueError, "Never replace"):
                create_lossless_canvas_candidate(root, "SourceShimejiAyaka")


if __name__ == "__main__":
    unittest.main()
