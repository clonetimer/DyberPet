"""R7 catches fake action diversity hidden by padding and all-frame repeats."""
from __future__ import annotations
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image
from tools.creator_motion_quality import analyze_creator_actions


def fixture(root, folder="SourceMover", mode="shift"):
    role = root / folder
    (role / "action").mkdir(parents=True)
    (role / "pet_conf.json").write_text('{"default":"default"}', encoding="utf-8")
    (role / "act_conf.json").write_text(json.dumps({
        "default": {"images":"idle"}, "left_walk": {"images":"walk","need_move":True}
    }), encoding="utf-8")
    Image.new("RGBA",(60,75),(33,44,55,255)).save(role/"action"/"idle_0.png")
    for i in range(5):
        canvas = Image.new("RGBA",(80,85),(0,0,0,0))
        rect=Image.new("RGBA",(12,22),(210,45,65,255))
        if mode=="real_pose" and i>=2:
            rect=Image.new("RGBA",(14,20),(210,45,65,255))
        elif mode=="last_frame" and i==4:
            rect=Image.new("RGBA",(15,20),(120,55,65,255))
        canvas.paste(rect,(i*4,60 if mode=="shift" else 45))
        canvas.save(role/"action"/f"walk_{i}.png")
    return role


class RealPixelPoseRiskTests(unittest.TestCase):
    def test_transparent_canvas_shifts_are_not_new_authored_poses(self):
        with TemporaryDirectory() as d:
            root = Path(d) / "res" / "role"
            role=fixture(root)
            before={p.name:p.read_bytes() for p in (role/"action").glob("*.png")}
            r=analyze_creator_actions(root,role.name)
            walking=next(x for x in r["actions"] if x["action"]=="left_walk")
            self.assertEqual(walking["frame_count"],5)
            self.assertEqual(walking["unique_visible_poses"],1)
            self.assertEqual(walking["longest_identical_pose_run"],5)
            self.assertIn("translation_only_or_static_pose",walking["risk_indicators"])
            self.assertTrue(r["summary"]["all_frames_examined"])
            self.assertFalse(r["summary"]["original_art_modified"])
            self.assertEqual(before,{p.name:p.read_bytes() for p in (role/"action").glob("*.png")})

    def test_first_two_equal_but_later_pose_differs_reported(self):
        with TemporaryDirectory() as d:
            root=Path(d)/"res"/"role"
            role=fixture(root,mode="real_pose")
            r=analyze_creator_actions(root,role.name)
            walking=next(x for x in r["actions"] if x["action"]=="left_walk")
            self.assertEqual(walking["unique_visible_poses"],2)
            self.assertNotIn("translation_only_or_static_pose",walking["risk_indicators"])

    def test_long_repeated_pose_run_detected_even_if_final_frame_differs(self):
        with TemporaryDirectory() as d:
            root=Path(d)/"res"/"role"
            role=fixture(root,mode="last_frame")
            r=analyze_creator_actions(root,role.name)
            x=next(x for x in r["actions"] if x["action"]=="left_walk")
            self.assertEqual(x["unique_visible_poses"],2)
            self.assertEqual(x["longest_identical_pose_run"],4)
            self.assertIn("long_identical_pose_run",x["risk_indicators"])
            self.assertEqual(r["summary"]["motion_semantics_approved"],False)

    def test_reject_demo_symlink_and_broken_png(self):
        with TemporaryDirectory() as d:
            root=Path(d)/"res"/"role"
            role=fixture(root)
            (role/"BUILTIN_CHIBI_DEMO.json").write_text("{}")
            with self.assertRaisesRegex(ValueError,"[Dd]emo"):
                analyze_creator_actions(root,role.name)
            (role/"BUILTIN_CHIBI_DEMO.json").unlink()
            (role/"action"/"walk_3.png").write_bytes(b"invalid")
            with self.assertRaises((OSError,ValueError)):
                analyze_creator_actions(root,role.name)


if __name__=="__main__":
    unittest.main()
