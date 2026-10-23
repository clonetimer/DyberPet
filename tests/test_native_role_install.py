"""Native DyberPet ZIP installer and existing source validator regression."""
import ast
import json
import os
import re
import glob
import tempfile
import unittest
import zipfile
from pathlib import Path

from PIL import Image

from tools.install_native_role import (
    inspect_zip, install_native_role, validate_native_role,
)


def make_native_role(directory):
    (directory / "action").mkdir(parents=True)
    (directory / "pet_conf.json").write_text(json.dumps({
        "default": "idle", "drag": "idle", "fall": "idle",
        "patpat": "idle", "focus": "idle",
        "random_act": [{"name": "stand", "act_list": ["idle"], "act_prob": 1}]
    }), encoding="utf-8")
    (directory / "act_conf.json").write_text(json.dumps({
        "idle": {"images": "idle", "frame_refresh": 0.15}
    }), encoding="utf-8")
    Image.new("RGBA", (80, 100), (255, 0, 0, 0)).save(directory / "action" / "idle_0.png")


def zip_role(source, archive, prefix="Paimon"):
    with zipfile.ZipFile(archive, "w") as writer:
        for path in source.rglob("*"):
            if path.is_file():
                writer.write(path, str(Path(prefix) / path.relative_to(source)))


class NativeRoleZipTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "src"
        self.source.mkdir()
        make_native_role(self.source)
        self.out = self.root / "roles"
        self.archive = self.root / "mod.zip"

    def test_install_with_nested_folder(self):
        zip_role(self.source, self.archive, "res/role/纳西妲")
        installed = install_native_role(self.archive, self.out)
        self.assertTrue(installed.is_dir())
        self.assertEqual(installed.name, "ChibiPet")
        self.assertEqual(validate_native_role(installed)["actions"], 1)
        self.assertTrue((installed / "INSTALL_REPORT.json").exists())
        self.assertTrue((installed / "action" / "idle_0.png").exists())

    def test_install_single_level_and_do_not_overwrite(self):
        zip_role(self.source, self.archive, "Paimon")
        installed = install_native_role(self.archive, self.out)
        self.assertEqual(installed.name, "Paimon")
        second = install_native_role(self.archive, self.out)
        self.assertEqual(second.name, "Paimon_2")
        with self.assertRaises(FileExistsError):
            install_native_role(self.archive, self.out, role_folder="Paimon")

    def test_missing_animation_fails_with_no_partial_role(self):
        (self.source / "action" / "idle_0.png").unlink()
        zip_role(self.source, self.archive)
        with self.assertRaises(ValueError):
            install_native_role(self.archive, self.out)
        self.assertEqual(list(self.out.iterdir()), [])

    def test_path_traversal_rejected(self):
        with zipfile.ZipFile(self.archive, "w") as archive:
            archive.writestr("../evil.txt", "test")
            archive.writestr("Role/pet_conf.json", "{}")
        with zipfile.ZipFile(self.archive) as archive:
            with self.assertRaises(ValueError):
                inspect_zip(archive)

    def test_symlinks_rejected(self):
        with zipfile.ZipFile(self.archive, "w") as archive:
            info = zipfile.ZipInfo("Role/action/malicious_link.png")
            info.create_system = 3
            info.external_attr = (0o120777 << 16)
            archive.writestr(info, "target")
        with zipfile.ZipFile(self.archive) as archive:
            with self.assertRaises(ValueError):
                inspect_zip(archive)

    def test_archive_executable_rejected(self):
        zip_role(self.source, self.archive)
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("Paimon/launch.bat", "echo hello")
        with self.assertRaises(ValueError):
            install_native_role(self.archive, self.out)

    def test_multiple_roles_fail_instead_of_guessing(self):
        zip_role(self.source, self.archive)
        with zipfile.ZipFile(self.archive, "a") as archive:
            archive.writestr("Second/pet_conf.json", "{}")
        with self.assertRaises(ValueError):
            install_native_role(self.archive, self.out)

    def test_declared_but_missing_frame_preflight_fails(self):
        conf = json.loads((self.source / "act_conf.json").read_text("utf-8"))
        conf["wave"] = {"images": "wave", "frame_refresh": 0.15}
        (self.source / "act_conf.json").write_text(json.dumps(conf), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Missing PNG"):
            validate_native_role(self.source)


class ExistingCodeValidationTest(unittest.TestCase):
    def test_real_CheckCharFiles_handles_missing_action_without_index_error(self):
        # Extract the actual repo function, not a reimplementation; it only
        # needs stdlib glob/re/json/os for this minimal integration test.
        source = Path(__file__).resolve().parents[1] / "DyberPet" / "conf.py"
        tree = ast.parse(source.read_text(encoding="utf-8"))
        func = next(node for node in tree.body if
                    isinstance(node, ast.FunctionDef) and node.name == "CheckCharFiles")
        scope = {"os": os, "glob": glob, "re": re, "json": json}
        exec(compile(ast.Module(body=[func], type_ignores=[]),
                     filename=str(source), mode="exec"), scope)
        with tempfile.TemporaryDirectory() as tmp:
            role = Path(tmp)
            make_native_role(role)
            conf = json.loads((role / "act_conf.json").read_text("utf-8"))
            conf["wave"] = {"images": "wave", "frame_refresh": 0.15}
            (role / "act_conf.json").write_text(json.dumps(conf), encoding="utf-8")
            status, files = scope["CheckCharFiles"](str(role))
            self.assertEqual(status, 4)
            self.assertTrue(any("wave" in item for item in files))


if __name__ == "__main__":
    unittest.main()
