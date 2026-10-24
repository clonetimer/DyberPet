"""Personal non-commercial workflow: local install, never a release decision."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw

from tools.personal_role_import import inspect_personal_asset, personal_install
from tools.character_pipeline import PipelineError
from tools.install_native_role import validate_native_role


def make_original_frames(path):
    path.mkdir(parents=True)
    for action in ("idle", "wave"):
        for i in range(2):
            img = Image.new("RGBA", (192, 208), (0, 0, 0, 0))
            ImageDraw.Draw(img).ellipse((49+i*3, 20, 120+i*3, 158),
                                        fill=(70, 150, 195, 255))
            img.save(path / f"{action}_{i}.png")


def make_original_native(folder):
    (folder / "action").mkdir(parents=True)
    Image.new("RGBA", (64, 72), (100, 180, 120, 255)).save(
        folder / "action" / "idle_0.png")
    (folder / "pet_conf.json").write_text(json.dumps({
        "default": "idle", "drag": "idle", "fall": "idle", "focus": "idle",
        "patpat": "idle", "random_act": [{"name": "idle", "act_list": ["idle"]}]
    }), encoding="utf-8")
    (folder / "act_conf.json").write_text(json.dumps({
        "idle": {"images": "idle", "frame_refresh": 0.2}
    }), encoding="utf-8")


class PersonalRoleImportTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.dest = self.root / "installed"

    def test_original_frames_install_without_permission_claims(self):
        source = self.root / "my-private-frames"
        make_original_frames(source)
        self.assertEqual(inspect_personal_asset(source)["kind"], "frames")
        with self.assertRaisesRegex(PipelineError, "Explicit"):
            personal_install(source, self.dest, profile="genshin_xiao")
        self.assertFalse(self.dest.exists())
        role = personal_install(source, self.dest, profile="genshin_xiao",
                                confirm_local_only=True)
        report = json.loads((role / "PERSONAL_IMPORT.json").read_text("utf-8"))
        self.assertEqual(report["mode"], "personal_local_only")
        self.assertEqual(report["selected_profile"], "genshin_xiao")
        self.assertFalse(report["source_rights_verified"])
        self.assertFalse(report["visual_identity_verified"])
        self.assertFalse(report["redistribution_allowed_by_tool"])
        self.assertEqual(validate_native_role(role)["actions"], 2)
        self.assertTrue((source / "idle_0.png").exists())
        self.assertFalse((self.root / "cases").exists())
        self.assertFalse((self.root / "releases").exists())

    def test_identical_candidate_gets_new_folder_no_overwrite(self):
        source = self.root / "frames"
        make_original_frames(source)
        a = personal_install(source, self.dest, confirm_local_only=True,
                             profile="genshin_xiao")
        old = (a / "pet_conf.json").read_bytes()
        b = personal_install(source, self.dest, confirm_local_only=True,
                             profile="genshin_xiao")
        self.assertNotEqual(a, b)
        self.assertEqual((a / "pet_conf.json").read_bytes(), old)
        with self.assertRaises(FileExistsError):
            personal_install(source, self.dest, confirm_local_only=True,
                             folder=a.name)
        self.assertEqual((a / "pet_conf.json").read_bytes(), old)

    def test_native_extracted_and_zip_are_installed_privately(self):
        native = self.root / "native"
        make_original_native(native)
        folder = personal_install(native, self.dest, confirm_local_only=True)
        self.assertTrue((folder / "INSTALL_REPORT.json").is_file())
        self.assertEqual(validate_native_role(folder)["images"], 1)
        archive = self.root / "personal-native.zip"
        with zipfile.ZipFile(archive, "w") as writer:
            for file in native.rglob("*"):
                if file.is_file():
                    writer.write(file, "MyRole/" + file.relative_to(native).as_posix())
        copy = personal_install(archive, self.dest, confirm_local_only=True,
                                profile="genshin_wanderer")
        self.assertNotEqual(copy, folder)
        self.assertEqual(validate_native_role(copy)["actions"], 1)
        self.assertEqual(json.loads((copy / "PERSONAL_IMPORT.json").read_text(
            "utf-8"))["source_kind"], "native_zip")

    def test_invalid_zip_and_3d_do_not_create_role(self):
        bad_zip = self.root / "bad.zip"
        bad_zip.write_bytes(b"this is not ZIP")
        with self.assertRaisesRegex(PipelineError, "Invalid"):
            personal_install(bad_zip, self.dest, confirm_local_only=True)
        pmx = self.root / "original.pmx"
        pmx.write_bytes(b"test, no model content")
        with self.assertRaisesRegex(PipelineError, "3D"):
            personal_install(pmx, self.dest, confirm_local_only=True)
        self.assertFalse(self.dest.exists())

    def test_symlink_refused_before_source_read(self):
        source = self.root / "frames"
        make_original_frames(source)
        link = self.root / "linked"
        try:
            link.symlink_to(source, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("No symlink support")
        with self.assertRaisesRegex(PipelineError, "Linked"):
            inspect_personal_asset(link)
        self.assertFalse(self.dest.exists())

    def test_genshin_cli_one_character_personal_use_no_audit_mutations(self):
        source = self.root / "frames"
        make_original_frames(source)
        cli = Path(__file__).resolve().parents[1] / "tools" / "genshin_batch.py"
        base = [sys.executable, str(cli), "personal-install", "--role", "xiao",
                "--asset", str(source), "--output-root", str(self.dest)]
        missing = subprocess.run(base, capture_output=True, text=True,
                                 encoding="utf-8", timeout=30)
        self.assertNotEqual(missing.returncode, 0)
        self.assertFalse(self.dest.exists())
        ok = subprocess.run(base + ["--personal-use"], capture_output=True,
                            text=True, encoding="utf-8", timeout=50, check=True)
        report = json.loads(ok.stdout)
        self.assertEqual(report["mode"], "personal_local_only")
        self.assertFalse(report["rights_verified"])
        self.assertFalse(report["art_identity_verified"])
        self.assertFalse(report["case_or_rights_records_modified"])
        self.assertTrue((self.dest / report["installed_role_folder"]).is_dir())
        self.assertFalse((self.root / "cases").exists())


if __name__ == "__main__":
    unittest.main()
