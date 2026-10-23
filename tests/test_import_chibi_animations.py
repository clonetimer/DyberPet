"""Tests for direct GIF/APNG/PNG-sequence import into a DyberPet character."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.import_chibi_animations import (
    convert_animation_folder, resolve_animations, prepare_animation_frames,
)


def frame(w=80, h=100, x=0):
    image = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(image).rectangle((10 + x, 10, 60 + x, h - 10),
                                   fill=(230, 100, 120, 255))
    return image


class AnimationImportTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.src = self.root / "art"
        self.src.mkdir()
        self.dest = self.root / "roles"

    def test_png_sequences_numeric_order_and_Q_template(self):
        frame(x=2).save(self.src / "idle_10.png")
        frame(x=0).save(self.src / "idle_9.png")
        frame().save(self.src / "wave_0.png")
        # Gaps are reported but never misordered as lexicographic filenames.
        found, warnings = resolve_animations(self.src)
        self.assertEqual([p.name for p in found["idle"]],
                         ["idle_9.png", "idle_10.png"])
        self.assertEqual(warnings, [])
        target = convert_animation_folder(self.src, self.dest,
                                          profile="genshin_nahida", folder="NahidaChibi")
        self.assertEqual(target.name, "NahidaChibi")
        pet = json.loads((target / "pet_conf.json").read_text(encoding="utf-8"))
        info = json.loads((target / "info" / "info.json").read_text(encoding="utf-8"))
        act = json.loads((target / "act_conf.json").read_text(encoding="utf-8"))
        report = json.loads((target / "IMPORT_REPORT.json").read_text(encoding="utf-8"))
        self.assertEqual(pet["patpat"], "wave")
        self.assertEqual(info["petName"], "纳西妲")
        self.assertEqual(info["author"]["name"], "Unspecified")
        self.assertIn("Q版", info["tages"])
        self.assertEqual(report["frame_counts"]["idle"], 2)
        self.assertEqual(len(list((target / "action").glob("idle_*.png"))), 2)
        self.assertIn("wave", act)
        with Image.open(target / "action" / "idle_0.png") as image:
            self.assertEqual(image.size, (192, 208))
            self.assertEqual(image.getpixel((0, 0))[3], 0)
        self.assertTrue((target / "info" / "pfp.png").is_file())
        with Image.open(target / "ANIMATION_PREVIEW.png") as sheet:
            self.assertEqual(sheet.width, 1024)
        self.assertEqual(report["preview"]["preview_path"], "ANIMATION_PREVIEW.png")
        self.assertTrue((target / "note" / "bubble_conf.json").is_file())

    def test_animated_gif_frames_and_timing(self):
        a, b = frame(), frame(x=5)
        a.save(self.src / "idle.gif", save_all=True, append_images=[b],
               duration=[120, 320], loop=0, disposal=2)
        (self.src / "sleep.png").write_bytes(b"")  # malformed input must be rejected
        with self.assertRaises(OSError):
            convert_animation_folder(self.src, self.dest, folder="Bad")
        (self.src / "sleep.png").unlink()
        out = convert_animation_folder(self.src, self.dest, folder="Good",
                                       author="User-provided original")
        report = json.loads((out / "IMPORT_REPORT.json").read_text(encoding="utf-8"))
        conf = json.loads((out / "act_conf.json").read_text(encoding="utf-8"))
        self.assertEqual(report["frame_counts"]["idle"], 2)
        self.assertEqual(conf["idle"]["frame_refresh"], 0.22)
        self.assertTrue(any("variable source frame timing" in item
                            for item in report["warnings"]))

    def test_sleep_uses_real_animation_if_present(self):
        frame().save(self.src / "idle.png")
        frame().save(self.src / "sleep.png")
        out = convert_animation_folder(self.src, self.dest)
        conf = json.loads((out / "act_conf.json").read_text(encoding="utf-8"))
        pet = json.loads((out / "pet_conf.json").read_text(encoding="utf-8"))
        self.assertIn("sleep", conf)
        self.assertTrue(any("sleep" in obj["act_list"]
                            for obj in pet["random_act"]))

    def test_avoid_overwriting_existing_role(self):
        frame().save(self.src / "idle.png")
        convert_animation_folder(self.src, self.dest, folder="Same")
        with self.assertRaises(FileExistsError):
            convert_animation_folder(self.src, self.dest, folder="Same")

    def test_reject_missing_idle_and_unsafe_folder(self):
        frame().save(self.src / "jump.png")
        with self.assertRaises(ValueError):
            convert_animation_folder(self.src, self.dest)
        frame().save(self.src / "idle.png")
        with self.assertRaises(ValueError):
            convert_animation_folder(self.src, self.dest, folder="../unsafe")

    def test_grounded_and_floating_distinct(self):
        frame().save(self.src / "idle.png")
        frame(h=80).save(self.src / "wave.png")
        grounded = convert_animation_folder(self.src, self.dest,
                                            folder="Grounded", profile="chibi")
        floating = convert_animation_folder(self.src, self.dest,
                                            folder="Flying", profile="genshin_paimon")
        report_ground = json.loads((grounded / "IMPORT_REPORT.json").read_text("utf-8"))
        report_float = json.loads((floating / "IMPORT_REPORT.json").read_text("utf-8"))
        self.assertGreaterEqual(report_ground["aligned_frames_per_action"]["idle"], 0)
        self.assertEqual(report_float["aligned_frames_per_action"], {})
        self.assertTrue(any("Floating profile" in w for w in report_float["warnings"]))

    def test_ascii_safe_folder_name_allocation(self):
        from tools.chibi_profiles import available_role_folder
        self.dest.mkdir()
        (self.dest / "ChibiPet").mkdir()
        self.assertEqual(available_role_folder(self.dest, "派蒙"), "ChibiPet_2")
        self.assertEqual(available_role_folder(self.dest, "genshin_nahida"), "genshin_nahida")

    def test_reject_too_many_frames(self):
        from tools.import_chibi_animations import load_sources
        with self.assertRaises(ValueError):
            frame().save(self.src / "idle.png")
            load_sources([self.src / "idle.png"] * 121)

if __name__ == "__main__":
    unittest.main()
