"""End-to-end, license-gate and state-integrity checks for character pipeline."""
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from tools.character_pipeline import (
    PipelineError, SOURCE_REGISTRY, registry, init_case, attach_case,
    rights_review, check_build_gate, build_case, qa_review, package_release,
    inspect_case, create_render_plan, identify_local, record_path,
)


def image():
    art = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
    ImageDraw.Draw(art).ellipse((50, 15, 130, 180), fill="#6a88de")
    return art


class CharacterPipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.art = self.root / "art"
        self.art.mkdir()
        image().save(self.art / "idle.png")
        self.case = init_case(
            self.workspace, "nahida_001", "纳西妲", "bilibili",
            "https://www.bilibili.com/", "frames",
            profile="genshin_nahida", creator="Demo artist")
        self.rights = "https://artist.example/character/license"

    def test_registry_grounded_channels_and_unknown_license(self):
        data = registry()
        self.assertEqual(data["schema_version"], 1)
        self.assertTrue({"aplaybox", "bilibili", "dyberpet_collection", "codex_pets"}
                        .issubset({r["id"] for r in data["channels"]}))
        self.assertTrue(all(x["rights_status"] == "unknown" for x in data["candidates"]))

    def test_init_case_does_not_overwrite(self):
        with self.assertRaises(FileExistsError):
            init_case(self.workspace, "nahida_001", "Duplicate",
                      "bilibili", "", "frames")
        self.assertIn("discovered", inspect_case(self.case)["status"])

    def test_source_attach_records_checksum_without_copy(self):
        data = attach_case(self.case, self.art)
        self.assertEqual(data["status"], "source_attached")
        self.assertEqual(len(data["source"]["sha256"]), 64)
        self.assertTrue((self.art / "idle.png").exists())

    def test_missing_evidence_blocks_build(self):
        attach_case(self.case, self.art)
        with self.assertRaisesRegex(PipelineError, "rights review"):
            build_case(self.case)
        self.assertFalse((self.workspace / "build").exists())

    def test_no_derivative_permission_blocks_image_conversion(self):
        attach_case(self.case, self.art)
        rights_review(self.case, "Tester", self.rights, local_use=True)
        with self.assertRaisesRegex(PipelineError, "derivatives"):
            build_case(self.case)

    def test_stale_source_invalidates_intake(self):
        attach_case(self.case, self.art)
        rights_review(self.case, "Tester", self.rights,
                      local_use=True, derivatives=True)
        image().resize((180, 190)).save(self.art / "idle.png")
        with self.assertRaisesRegex(PipelineError, "Source files changed"):
            build_case(self.case)

    def test_replacing_source_resets_license_and_qa(self):
        attach_case(self.case, self.art)
        rights_review(self.case, "Tester", self.rights,
                      local_use=True, derivatives=True, redistribution=True)
        attach_case(self.case, self.art)
        data = json.loads(self.case.read_text("utf-8"))
        self.assertEqual(data["rights"]["evidence"], "")
        self.assertFalse(data["rights"]["redistribution"])

    def test_full_local_build_and_visual_qa_but_no_release(self):
        attach_case(self.case, self.art)
        rights_review(self.case, "Rights reviewer", self.rights,
                      local_use=True, derivatives=True)
        role = build_case(self.case)
        self.assertTrue((role / "pet_conf.json").is_file())
        self.assertTrue((role / "action" / "idle_0.png").is_file())
        self.assertTrue((role / "ANIMATION_PREVIEW.png").is_file())
        self.assertTrue((role / "PIPELINE_SOURCE.json").is_file())
        with self.assertRaisesRegex(PipelineError, "Both visual and real"):
            qa_review(self.case, "User", visual_pass=True)
        qa_review(self.case, "User", visual_pass=True, runtime_pass=True)
        with self.assertRaisesRegex(PipelineError, "redistribution"):
            package_release(self.case)
        data = json.loads(self.case.read_text("utf-8"))
        self.assertEqual(data["status"], "qa_reviewed")

    def test_release_requires_rights_and_qc_and_prevents_overwrite(self):
        attach_case(self.case, self.art)
        rights_review(self.case, "Rights reviewer", self.rights,
                      local_use=True, derivatives=True, redistribution=True)
        role = build_case(self.case)
        with self.assertRaisesRegex(PipelineError, "visual AND runtime"):
            package_release(self.case)
        qa_review(self.case, "Visual reviewer",
                  visual_pass=True, runtime_pass=True)
        archive = package_release(self.case)
        self.assertTrue(archive.is_file())
        with zipfile.ZipFile(archive) as bundle:
            files = bundle.namelist()
        self.assertTrue(any(x.endswith("PIPELINE_SOURCE.json") for x in files))
        self.assertTrue(all(x.startswith("nahida_001/") for x in files))
        with self.assertRaisesRegex(PipelineError, "human visual"):
            package_release(self.case)  # packaged state should not silently republish
        self.assertTrue(role.is_dir())

    def test_qa_invalid_after_role_content_changes(self):
        attach_case(self.case, self.art)
        rights_review(self.case, "Rights reviewer", self.rights,
                      local_use=True, derivatives=True, redistribution=True)
        role = build_case(self.case)
        qa_review(self.case, "User", visual_pass=True, runtime_pass=True)
        (role / "action" / "idle_0.png").write_bytes(b"tampered")
        with self.assertRaisesRegex(PipelineError, "changed since QA"):
            package_release(self.case)

    def test_3d_model_is_render_plan_only(self):
        file = self.root / "demo.pmx"
        file.write_bytes(b"synthetic only; not a real PMX model")
        case = init_case(self.workspace, "arisa_3d", "阿丽莎",
                         "aplaybox", "", "model3d", profile="ailimit_arrisa")
        attach_case(case, file)
        rights_review(case, "Maker", self.rights,
                      local_use=True, derivatives=True)
        plan = create_render_plan(case)
        data = json.loads(plan.read_text(encoding="utf-8"))
        self.assertIn("transparent RGBA", data["requirements"]["render"])
        self.assertEqual(identify_local(file), "model3d")
        with self.assertRaisesRegex(PipelineError, "3D source"):
            build_case(case)
        self.assertFalse((self.workspace / "build" / "arisa_3d").exists())

    def test_archive_and_corrupt_media_mismatch(self):
        archive = self.root / "asset.zip"
        archive.write_bytes(b"stub")
        with self.assertRaisesRegex(PipelineError, "Expected frames"):
            attach_case(self.case, archive)

    def test_bad_id_rejected(self):
        for candidate in ("../evil", "PAIMON", "x", "with whitespace"):
            with self.assertRaises(PipelineError):
                record_path(self.workspace, candidate)


if __name__ == "__main__":
    unittest.main()
