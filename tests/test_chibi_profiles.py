"""Regression tests for Q-style character presets and grounded animations."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.chibi_layout import normalize_grounded_frames, suggested_scale, bbox, offset_frame
from tools.chibi_profiles import CHIBI_PROFILES, get_profile, make_bubble_config
from tools.import_codex_pet import convert


def make_sprite(left=70, top=30, right=130, bottom=160):
    img = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
    ImageDraw.Draw(img).rectangle((left, top, right, bottom - 1), fill=(200, 80, 120, 255))
    return img


class TestChibiLayout(unittest.TestCase):
    def test_grounded_baseline_aligns_idle_and_wait(self):
        frames = {
            "idle": [make_sprite(bottom=170), make_sprite(bottom=167)],
            "wait": [make_sprite(bottom=158)],
            "jump": [make_sprite(bottom=100)],
        }
        result, counts, warnings = normalize_grounded_frames(frames, max_shift=16)
        self.assertEqual([bbox(x)[3] for x in result["idle"]], [168, 168])
        self.assertEqual(bbox(result["wait"][0])[3], 168)
        self.assertEqual(bbox(result["jump"][0])[3], 100)
        self.assertEqual(counts["wait"], 1)
        self.assertEqual(warnings, [])

    def test_large_drift_reports_instead_of_teleport(self):
        frames = {"idle": [make_sprite(bottom=180)],
                  "right_walk": [make_sprite(bottom=120)]}
        result, _, warnings = normalize_grounded_frames(frames)
        self.assertEqual(bbox(result["right_walk"][0])[3], 120)
        self.assertTrue(any("ground drift" in w for w in warnings))

    def test_translation_rejects_clipping(self):
        with self.assertRaises(ValueError):
            offset_frame(make_sprite(left=1), -5, 0)

    def test_scale_is_bounded(self):
        scale, limited = suggested_scale([make_sprite(top=5, bottom=205)], 116)
        self.assertGreaterEqual(scale, 0.55)
        self.assertLessEqual(scale, 1.35)
        self.assertFalse(limited)
        scale, limited = suggested_scale([make_sprite(top=20, bottom=30)], 116)
        self.assertTrue(limited)
        self.assertEqual(scale, 1.35)


class TestChibiProfiles(unittest.TestCase):
    def test_required_character_profiles_exist(self):
        expected = ("genshin_paimon", "genshin_nahida", "genshin_klee",
                    "genshin_furina", "ailimit_arrisa", "chibi")
        self.assertTrue(set(expected).issubset(CHIBI_PROFILES))

    def test_templates_have_separate_text_no_audio(self):
        for key in CHIBI_PROFILES:
            bubbles = make_bubble_config(key)
            for required in ("pat_random_1", "pat_focus", "pat_frequent", "feed_done"):
                self.assertIn(required, bubbles)
                self.assertIsNone(bubbles[required]["start_audio"])
                self.assertTrue(bubbles[required]["message"])

    def test_templates_are_not_mutable_singletons(self):
        p = get_profile("ailimit_arrisa")
        p["dialogue"]["pat_random_1"] = "changed"
        self.assertNotEqual(get_profile("ailimit_arrisa")["dialogue"]["pat_random_1"], "changed")

    def test_unknown_profile_rejected(self):
        with self.assertRaises(ValueError):
            get_profile("genshin_imaginary-character")

    def test_q_style_e2e_template_with_synthetic_images(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "pet"
            source.mkdir()
            atlas = Image.new("RGBA", (1536, 1872), (0, 0, 0, 0))
            frame = make_sprite(bottom=176)
            for col in range(6):
                atlas.alpha_composite(frame, (col * 192, 0))
            atlas.save(source / "spritesheet.webp", lossless=True)
            (source / "pet.json").write_text(json.dumps({
                "id": "custom-artist-id", "displayName": "Unknown art source"
            }), encoding="utf-8")
            target = convert(source, root / "roles", profile="ailimit_arrisa",
                             folder="ArrisaChibi")
            conf = json.loads((target / "pet_conf.json").read_text(encoding="utf-8"))
            info = json.loads((target / "info" / "info.json").read_text(encoding="utf-8"))
            report = json.loads((target / "IMPORT_REPORT.json").read_text(encoding="utf-8"))
            bubbles = json.loads((target / "note" / "bubble_conf.json").read_text(encoding="utf-8"))
            self.assertEqual(target.name, "ArrisaChibi")
            self.assertEqual(info["petName"], "阿丽莎")
            self.assertIn("无限机兵 / AI LIMIT", info["tages"])
            self.assertIn("Q版", info["tages"])
            self.assertEqual(info["author"]["name"], "Unspecified")
            self.assertEqual(report["style"], "chibi")
            self.assertEqual(report["profile"], "ailimit_arrisa")
            self.assertEqual(report["recommended_scale"], conf["scale"])
            self.assertIn("信号", bubbles["pat_frequent"]["message"])
            self.assertEqual(report["frame_counts"]["idle"], 6)
            self.assertTrue((target / "info" / "cover.png").exists())

    def test_uncertain_author_not_falsely_assigned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            atlas = Image.new("RGBA", (1536, 1872), (0, 0, 0, 0))
            atlas.alpha_composite(make_sprite(), (0, 0))
            image_path = root / "spritesheet.webp"
            atlas.save(image_path, lossless=True)
            target = convert(image_path, root / "roles", preset="doro")
            info = json.loads((target / "info" / "info.json").read_text(encoding="utf-8"))
            self.assertEqual(info["author"]["name"], "Unspecified")
            self.assertIn("Unverified", (target / "ASSET_SOURCE.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
