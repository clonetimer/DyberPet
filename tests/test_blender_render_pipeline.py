"""P5 Blender renderer launch and rights-gated 3D→2D pipeline tests.

These tests do not assert that fake frames came from Blender. A separate
opt-in Blender integration job tests the real Blender rendering process.
"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from tools.render_chibi_blender import RenderError, render_blender, validate_frames
from tools.character_pipeline import (
    PipelineError, init_case, attach_case, rights_review, render_3d_case,
    load_case, attach_turnaround, review_turnaround, validate_derived_provenance,
)


def fake_blender_process(args, **kwargs):
    # Produces transparent PNG fixtures, without claiming any 3D rendering.
    output = Path(args[args.index("--output")+1])
    acts = args[args.index("--actions")+1].split(",")
    count = int(args[args.index("--frames")+1])
    for action in acts:
        for i in range(count):
            im = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
            for x in range(50, 140):
                for y in range(60, 168):
                    im.putpixel((x, y), (120, 60, 220, 255))
            im.save(output / f"{action}_{i}.png")
    (output / "BLENDER_RENDER_REPORT.json").write_text(json.dumps({
        "demo": "--demo" in args, "actions": {a: count for a in acts},
        "renderer": "FAKE TEST ONLY"
    }), encoding="utf-8")
    return type("Process", (), {"returncode": 0, "stdout": "FAKE"})()


class RenderLaunchTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.exe = self.root / "blender"
        self.exe.write_text("fake executable", encoding="utf-8")
        self.model = self.root / "model.glb"
        self.model.write_bytes(b"synthetic fake model fixture")
        self.output = self.root / "rendered"

    def test_do_not_launch_for_pmx_or_vrm(self):
        for ext in (".pmx", ".vrm", ".blend"):
            sample = self.root / ("file" + ext)
            sample.write_bytes(b"fake")
            with self.assertRaisesRegex(RenderError, "Only GLB/GLTF/FBX"):
                render_blender(str(self.exe), self.output, source=sample)
        self.assertFalse(self.output.exists())

    def test_reject_gltf_with_untracked_external_textures(self):
        model = self.root / "scene.gltf"
        model.write_text(json.dumps({
            "asset": {"version": "2.0"},
            "buffers": [{"uri": "scene.bin"}],
            "images": [{"uri": "../private_texture.png"}]
        }), encoding="utf-8")
        with self.assertRaisesRegex(RenderError, "self-contained GLB"):
            render_blender(str(self.exe), self.output, source=model)
        self.assertFalse(self.output.exists())

    def test_no_override_existing_render(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            render_blender(str(self.exe), self.output, source=self.model)

    def test_validate_transparent_frames(self):
        with patch("tools.render_chibi_blender.subprocess.run", side_effect=fake_blender_process):
            result = render_blender(str(self.exe), self.output, source=self.model,
                                    frames=2, actions=("idle", "wave"))
        self.assertEqual(result, self.output.resolve())
        report = json.loads((result / "BLENDER_RENDER_REPORT.json").read_text("utf-8"))
        self.assertEqual(report["frame_qa"]["idle"]["frames"], 2)
        self.assertFalse(report["launcher"]["automated_rights_verification"])
        self.assertTrue(report["launcher"]["disable_autoexec"])

    def test_reject_incorrect_or_opaque_png(self):
        self.output.mkdir()
        opaque = Image.new("RGBA", (192, 208), (255, 0, 0, 255))
        opaque.save(self.output / "idle_0.png")
        with self.assertRaisesRegex(RenderError, "opaque"):
            validate_frames(self.output, ("idle",), 1)

    def test_failure_does_not_create_final_folder(self):
        with patch("tools.render_chibi_blender.subprocess.run") as run:
            run.return_value = type("Process", (), {"returncode": 3, "stdout": "fail"})()
            with self.assertRaisesRegex(RenderError, "Blender failed"):
                render_blender(str(self.exe), self.output, source=self.model)
        self.assertFalse(self.output.exists())

    def test_invalid_actions_or_timeout(self):
        with self.assertRaisesRegex(RenderError, "Invalid actions"):
            render_blender(str(self.exe), self.output, demo=True, actions=("wave",))
        with self.assertRaisesRegex(RenderError, "timeout"):
            render_blender(str(self.exe), self.output, demo=True, timeout=1)


class RightsAndDerivationTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.workspace = self.root / "workspace"
        self.model = self.root / "model.glb"
        self.model.write_bytes(b"fake model")
        self.case = init_case(
            self.workspace, "artist_model_001", "原创模型", "aplaybox",
            "https://www.aplaybox.com/model", "model3d", "chibi",
            creator="Demo Author"
        )
        attach_case(self.case, self.model)
        self.views = self.root / "views"
        self.views.mkdir()
        for i, name in enumerate(("front", "side", "back")):
            im = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
            for x in range(30 + i * 3, 110 + i * 3):
                for y in range(25, 170):
                    im.putpixel((x, y), (30 + 50 * i, 80, 200, 255))
            im.save(self.views / (name + ".png"))

    def approve_views(self):
        attach_turnaround(
            self.case, front=self.views / "front.png",
            side=self.views / "side.png", back=self.views / "back.png",
            reference_url="https://artist.example/model-turnaround",
            artist="Demo Author", variant="one-source-Q-model")
        review_turnaround(self.case, "Human", {
            "silhouette": True, "outfit": True, "identity": True,
            "cross_view": True,
        })

    def test_requires_explicit_local_and_derivative_permission(self):
        with self.assertRaisesRegex(PipelineError, "permission"):
            render_3d_case(self.case, blender="fake")
        rights_review(self.case, "Reviewer", "https://author.example/terms",
                      local_use=True)
        with self.assertRaisesRegex(PipelineError, "permission"):
            render_3d_case(self.case, blender="fake")

    def test_child_frames_record_requires_own_rights_review(self):
        rights_review(self.case, "Reviewer", "https://author.example/terms",
                      local_use=True, derivatives=True)
        self.approve_views()
        def fake_render(blender, output, *, source, actions, frames, timeout):
            output.mkdir(parents=True)
            for act in actions:
                Image.new("RGBA", (192, 208), (20, 30, 40, 90)).save(
                    output / f"{act}_0.png")
            (output / "BLENDER_RENDER_REPORT.json").write_text('{"synthetic":true}')
            return output
        with patch("tools.render_chibi_blender.render_blender",
                   side_effect=fake_render):
            child = render_3d_case(self.case, blender="dummy", frames=1)
        child_data = load_case(child)
        self.assertEqual(child_data["source"]["kind"], "frames")
        self.assertEqual(child_data["turnaround"], load_case(self.case)["turnaround"])
        self.assertEqual(child_data["rights"]["reviewer"], "")
        self.assertTrue(child_data["derived_from"]["preview_only"])
        with self.assertRaisesRegex(PipelineError, "preview-only"):
            validate_derived_provenance(child, child_data, for_release=True)
        validate_derived_provenance(child, child_data)
        self.assertFalse(child_data["rights"]["redistribution"])
        self.assertEqual(child_data["derived_from"]["parent_case"], "artist_model_001")
        self.assertEqual(load_case(self.case)["status"], "rendered")
        with self.assertRaises(FileExistsError):
            render_3d_case(self.case, blender="dummy", frames=1)
        self.assertTrue((self.workspace / "renders" / "artist_model_001").is_dir())


    def test_strict_clip_lineage_is_package_eligible_only_with_real_clips(self):
        rights_review(self.case, "Reviewer", "https://author.example/terms",
                      local_use=True, derivatives=True)
        self.approve_views()

        def render_strict(blender, output, *, source, actions, frames, timeout,
                          require_clips=False):
            self.assertTrue(require_clips)
            output.mkdir(parents=True)
            for act in actions:
                Image.new("RGBA", (192, 208), (20, 30, 40, 90)).save(
                    output / (act + "_0.png"))
            (output / "BLENDER_RENDER_REPORT.json").write_text(
                json.dumps({"animation_sources": {a: "clip" for a in actions}}))
            return output

        with patch("tools.render_chibi_blender.render_blender",
                   side_effect=render_strict):
            child = render_3d_case(self.case, blender="dummy", frames=1,
                                   require_clips=True)
        data = load_case(child)
        self.assertFalse(data["derived_from"]["preview_only"])
        self.assertTrue(data["derived_from"]["all_actions_use_real_clips"])
        validate_derived_provenance(child, data, for_release=True)

        # Parent source changes immediately invalidate the child.
        self.model.write_bytes(b"new model geometry")
        with self.assertRaisesRegex(PipelineError, "Parent model changed"):
            validate_derived_provenance(child, data, for_release=True)

    def test_strict_mode_rejects_fake_motion_without_child(self):
        rights_review(self.case, "Reviewer", "https://author.example/terms",
                      local_use=True, derivatives=True)
        self.approve_views()

        def fake_fallback(blender, output, *, source, actions, frames, timeout,
                          require_clips=False):
            output.mkdir(parents=True)
            (output / "BLENDER_RENDER_REPORT.json").write_text(
                json.dumps({"animation_sources": {a: "procedural_fallback"
                                                  for a in actions}}))
            return output

        with patch("tools.render_chibi_blender.render_blender",
                   side_effect=fake_fallback):
            with self.assertRaisesRegex(PipelineError, "genuine imported"):
                render_3d_case(self.case, blender="dummy", frames=1,
                               require_clips=True)
        self.assertFalse((self.workspace / "cases" /
                          "artist_model_001_frames.json").exists())
        self.assertFalse((self.workspace / "renders" /
                          "artist_model_001").exists())


if __name__ == "__main__":
    unittest.main()
