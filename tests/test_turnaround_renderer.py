"""Offline validation for same-model orthographic 3-view evidence."""
import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

from tools.render_turnaround_blender import (
    check_source, check_three_views, render_turnaround,
    TurnaroundRenderError,
)


class ThreeViewRendererTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def prepare_views(self):
        folder = self.root / "views"
        folder.mkdir()
        for i, name in enumerate(("front", "side", "back")):
            im = Image.new("RGBA", (512, 512))
            draw = ImageDraw.Draw(im)
            draw.ellipse((130 + i * 11, 75, 380, 460),
                         fill=(30 + 50 * i, 30, 220, 255))
            im.save(folder / (name + ".png"))
        return folder

    def test_nonidentical_transparent_views(self):
        hashes = check_three_views(self.prepare_views())
        self.assertEqual(set(hashes), {"front", "side", "back"})
        self.assertEqual(len(set(hashes.values())), 3)

    def test_missing_and_opaque_or_clipped_frames_fail(self):
        folder = self.prepare_views()
        (folder / "back.png").unlink()
        with self.assertRaisesRegex(TurnaroundRenderError, "Missing"):
            check_three_views(folder)
        Image.new("RGBA", (512, 512), (200, 20, 20, 255)).save(folder / "back.png")
        with self.assertRaisesRegex(TurnaroundRenderError, "clipped"):
            check_three_views(folder)

    def test_mismatched_duplicate_views_fail(self):
        folder = self.prepare_views()
        (folder / "back.png").write_bytes((folder / "front.png").read_bytes())
        with self.assertRaisesRegex(TurnaroundRenderError, "Identical"):
            check_three_views(folder)

    def test_unapproved_non_glb_input_blocked_before_start(self):
        source = self.root / "original.fbx"
        source.write_bytes(b"NOT A GLB")
        with self.assertRaisesRegex(TurnaroundRenderError, "GLB"):
            render_turnaround("missing-blender", self.root / "output", source=source)
        with self.assertRaisesRegex(TurnaroundRenderError, "GLB"):
            check_source(source)

    def test_invalid_glb_header_blocked(self):
        source = self.root / "fake.glb"
        source.write_bytes(b"glTF" + (1).to_bytes(4, "little") +
                           (20).to_bytes(4, "little") + b"12345678")
        with self.assertRaisesRegex(TurnaroundRenderError, "Invalid GLB"):
            check_source(source)

    def test_invalid_yaw_and_input_modes_blocked(self):
        with self.assertRaisesRegex(TurnaroundRenderError, "exactly one"):
            render_turnaround("blender", self.root / "out")
        with self.assertRaisesRegex(TurnaroundRenderError, "yaw"):
            render_turnaround("blender", self.root / "out", demo=True,
                              front_yaw=float("nan"))


if __name__ == "__main__":
    unittest.main()
