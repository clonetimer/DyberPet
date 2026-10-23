"""Tests for the self-contained Codex atlas conversion helper.

Run: python -m unittest discover -s tests -p "test_import_codex_pet.py" -v
"""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.import_codex_pet import convert, read_atlas, resolve_source


class ImportCodexPetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.dest = self.root / "roles"

    def make_atlas(self, version=1, populated_rows=range(9)):
        height = 1872 if version == 1 else 2288
        atlas = Image.new("RGBA", (1536, height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(atlas)
        for row in populated_rows:
            draw.rectangle((20, row * 208 + 20, 70, row * 208 + 75), fill=(100, 40, 60, 255))
        if version == 2:
            for i in range(16):
                col, row = i % 8, i // 8 + 9
                draw.rectangle((col * 192 + 20, row * 208 + 20,
                                col * 192 + 70, row * 208 + 75), fill=(10 + i, 40, 60, 255))
        atlas.save(self.source / "spritesheet.webp", lossless=True)
        (self.source / "pet.json").write_text(json.dumps({
            "id": "demo", "displayName": "Example",
            "spriteVersionNumber": version, "spritesheetPath": "spritesheet.webp"
        }), encoding="utf-8")

    def test_import_v1_preserves_alpha_and_actions(self):
        self.make_atlas()
        out = convert(self.source, self.dest, preset="guga")
        self.assertEqual(out.name, "Guga")
        role = json.loads((out / "pet_conf.json").read_text(encoding="utf-8"))
        acts = json.loads((out / "act_conf.json").read_text(encoding="utf-8"))
        self.assertEqual(role["default"], "idle")
        self.assertEqual(role["patpat"], "wave")
        self.assertTrue(acts["right_walk"]["need_move"])
        self.assertEqual(len(list((out / "action").glob("idle_*.png"))), 1)
        with Image.open(out / "action" / "idle_0.png") as image:
            self.assertEqual(image.size, (192, 208))
            self.assertEqual(image.convert("RGBA").getpixel((0, 0))[3], 0)
        self.assertIn("Unverified", (out / "ASSET_SOURCE.txt").read_text())
        bubbles = json.loads((out / "note" / "bubble_conf.json").read_text(encoding="utf-8"))
        self.assertIn("咕嘎", bubbles["pat_random_1"]["message"])
        self.assertIsNone(bubbles["pat_random_1"]["start_audio"])
        info = json.loads((out / "info" / "info.json").read_text(encoding="utf-8"))
        self.assertEqual(info["pfp"], "pfp.png")
        self.assertEqual(info["coverImages"], ["cover.png"])
        with Image.open(out / "info" / "pfp.png") as icon:
            self.assertEqual(icon.size, (160, 160))
            self.assertEqual(icon.convert("RGBA").getpixel((0, 0))[3], 0)
        with Image.open(out / "info" / "cover.png") as cover:
            self.assertEqual(cover.size, (300, 169))

    def test_import_v2_16_way_look(self):
        self.make_atlas(version=2)
        out = convert(self.source, self.dest, preset="doro")
        self.assertEqual(len(list((out / "action").glob("lookaround_*.png"))), 16)
        conf = json.loads((out / "pet_conf.json").read_text(encoding="utf-8"))
        self.assertTrue(any(group["name"] == "左顾右盼" for group in conf["random_act"]))
        bubbles = json.loads((out / "note" / "bubble_conf.json").read_text(encoding="utf-8"))
        self.assertIn("Doro", bubbles["pat_random_1"]["message"])

    def test_missing_optional_actions_fall_back(self):
        self.make_atlas(populated_rows=[0])
        out = convert(self.source, self.dest)
        conf = json.loads((out / "pet_conf.json").read_text(encoding="utf-8"))
        acts = json.loads((out / "act_conf.json").read_text(encoding="utf-8"))
        for key in ("default", "drag", "fall", "left", "right", "focus"):
            self.assertIn(conf[key], acts)
        for group in conf["random_act"]:
            self.assertTrue(all(action in acts for action in group["act_list"]))
        self.assertNotIn("打招呼", [group["name"] for group in conf["random_act"]])

    def test_do_not_overwrite_existing_character(self):
        self.make_atlas()
        convert(self.source, self.dest, preset="doro")
        with self.assertRaises(FileExistsError):
            convert(self.source, self.dest, preset="doro")

    def test_no_idle_no_import(self):
        self.make_atlas(populated_rows=[1])
        with self.assertRaises(ValueError):
            convert(self.source, self.dest, preset="doro")
        self.assertFalse((self.dest / "Doro").exists())

    def test_bad_atlas_dimensions(self):
        Image.new("RGBA", (100, 100)).save(self.source / "spritesheet.webp")
        with self.assertRaises(ValueError):
            read_atlas(self.source / "spritesheet.webp", {})

    def test_v2_missing_direction_gives_warning(self):
        self.make_atlas(version=2)
        atlas_path = self.source / "spritesheet.webp"
        with Image.open(atlas_path) as atlas:
            image = atlas.convert("RGBA")
        image.paste((0, 0, 0, 0), (20, 9 * 208 + 20, 75, 9 * 208 + 80))
        image.save(atlas_path, lossless=True)
        out = convert(self.source, self.dest)
        report = json.loads((out / "IMPORT_REPORT.json").read_text(encoding="utf-8"))
        self.assertLess(report["frame_counts"]["lookaround"], 16)
        self.assertTrue(any("look-direction" in w for w in report["warnings"]))

    def test_discontinuous_row_emits_qa_warning(self):
        self.make_atlas()
        atlas_path = self.source / "spritesheet.webp"
        with Image.open(atlas_path) as atlas:
            image = atlas.convert("RGBA")
        draw = ImageDraw.Draw(image)
        draw.rectangle((2 * 192 + 20, 208 + 20, 2 * 192 + 70, 208 + 75),
                       fill=(180, 30, 30, 255))
        image.save(atlas_path, lossless=True)
        out = convert(self.source, self.dest)
        report = json.loads((out / "IMPORT_REPORT.json").read_text(encoding="utf-8"))
        self.assertTrue(any("transparent gaps" in w for w in report["warnings"]))

    def test_manifest_traversal_rejected(self):
        (self.source / "pet.json").write_text(
            '{"spritesheetPath":"../outside.webp"}', encoding="utf-8"
        )
        with self.assertRaises(ValueError):
            resolve_source(self.source)


if __name__ == "__main__":
    unittest.main()
