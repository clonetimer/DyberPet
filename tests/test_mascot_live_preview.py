"""Read-only preview: real action timing, safe frames and no source changes."""
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.generate_mascot_demos import generate_mascot_demos
from tools.role_action_preview import action_preview_plan


class MascotPreviewTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root=Path(tmp.name)/"res"/"role"
        generate_mascot_demos(self.root)
        self.guga=self.root/"DemoMascotGuga"
        self.doro=self.root/"DemoMascotDoro"

    @staticmethod
    def snapshot(folder):
        h=hashlib.sha256()
        for file in sorted(folder.rglob("*")):
            if file.is_file():
                h.update(file.relative_to(folder).as_posix().encode())
                h.update(file.read_bytes())
        return h.hexdigest()

    def test_real_animation_actions_and_intervals(self):
        for folder in (self.guga,self.doro):
            with self.subTest(folder=folder.name):
                before=self.snapshot(folder)
                plan=action_preview_plan(folder)
                self.assertTrue(plan["read_only"])
                self.assertEqual(plan["total_frames"],66)
                self.assertEqual(len(plan["actions"]),10)
                self.assertEqual(plan["actions"][0]["name"],"idle")
                self.assertEqual(plan["actions"][1]["name"],"left_walk")
                self.assertEqual(plan["actions"][2]["name"],"right_walk")
                self.assertEqual(plan["actions"][1]["frame_count"],6)
                self.assertEqual(plan["actions"][1]["interval_ms"],120)
                names={x["name"] for x in plan["actions"]}
                self.assertTrue({"run","failed","lookaround"}.issubset(names))
                self.assertEqual(
                    sorted(a["name"] for a in plan["actions"]),
                    sorted(["idle","left_walk","right_walk","wave",
                            "jump","wait","review","run","failed","lookaround"]))
                self.assertTrue(all(f.is_file() for action in plan["actions"]
                                    for f in action["frames"]))
                self.assertEqual(before,self.snapshot(folder))

    def test_corrupt_or_unsafe_frames_block_preview(self):
        corrupt=self.guga/"action"/"idle_0.png"
        corrupt.write_bytes(b"not a png")
        with self.assertRaisesRegex(ValueError,"PNG"):
            action_preview_plan(self.guga)
        try:
            link=self.doro/"action"/"idle_0.png"
            link.unlink()
            link.symlink_to(self.doro/"action"/"idle_1.png")
        except (OSError,NotImplementedError):
            self.skipTest("No symlinks on this platform")
        with self.assertRaisesRegex(ValueError,"Linked"):
            action_preview_plan(self.doro)

    def test_size_bounds_reject_oversized_header(self):
        file=self.doro/"action"/"idle_0.png"
        data=bytearray(file.read_bytes())
        data[16:20]=(4000).to_bytes(4,"big")
        file.write_bytes(data)
        with self.assertRaisesRegex(ValueError,"dimensions"):
            action_preview_plan(self.doro)

    def test_ui_dispatch_uses_existing_switch_signal(self):
        root=Path(__file__).resolve().parents[1]
        path=root/"DyberPet"/"DyberSettings"/"CharCardUI.py"
        tree=ast.parse(path.read_text(encoding="utf-8"))
        viewer=next(n for n in ast.walk(tree)
                    if isinstance(n,ast.FunctionDef) and n.name=="_showMascotLibrary")
        calls=ast.unparse(viewer)
        self.assertIn("MascotActionPreview(",calls)
        self.assertIn("viewer.exec()",calls)
        self.assertIn("self.__onLaunchClicked(name)",calls)
        self.assertNotIn("rmtree(",calls)
        self.assertNotIn("install_creator_mascot(",calls)


if __name__=="__main__":
    unittest.main()
