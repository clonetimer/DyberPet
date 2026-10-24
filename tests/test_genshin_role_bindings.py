"""Explicit local legacy MOD associations must never overwrite source artwork."""
from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.genshin_role_bindings import (
    associate_existing_role, unbind_existing_role, default_mapping_path,
    load_bindings, config_digest)
from tools.genshin_library import scan_genshin_library


def make_legacy_role(folder):
    (folder / "action").mkdir(parents=True)
    (folder / "pet_conf.json").write_text(json.dumps({
        "default": "idle", "drag": "idle", "fall": "idle",
        "focus": "idle", "patpat": "idle",
        "random_act": [{"name": "rest", "act_list": ["idle"]}]
    }), encoding="utf-8")
    (folder / "act_conf.json").write_text(json.dumps({
        "idle": {"images": "idle", "frame_refresh": 0.2}
    }), encoding="utf-8")
    Image.new("RGBA", (80, 110), (70, 140, 180, 255)).save(
        folder / "action" / "idle_0.png")
    return folder


def source_hash(folder):
    digest = hashlib.sha256()
    for file in sorted(folder.rglob("*")):
        if file.is_file():
            digest.update(str(file.relative_to(folder)).encode("utf-8"))
            digest.update(file.read_bytes())
    return digest.hexdigest()


class GenshinSidecarMappingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.roles = self.root / "res" / "role"
        self.first = make_legacy_role(self.roles / "LegacyLisa")
        self.second = make_legacy_role(self.roles / "OldAmber")
        self.bindings = default_mapping_path(self.roles)

    def test_opt_in_sidecar_association_does_not_modify_role(self):
        before = source_hash(self.first)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            associate_existing_role(self.roles, "LegacyLisa", "genshin_lisa")
        self.assertFalse(self.bindings.exists())
        result = associate_existing_role(
            self.roles, "LegacyLisa", "genshin_lisa", confirmed=True)
        self.assertEqual(result["profile"], "genshin_lisa")
        self.assertFalse(result["identity_verified"])
        self.assertFalse(result["rights_verified"])
        self.assertEqual(before, source_hash(self.first))
        self.assertTrue(self.bindings.is_file())
        self.assertFalse((self.first / "PERSONAL_IMPORT.json").exists())
        inventory = scan_genshin_library(self.roles)
        self.assertEqual(inventory["summary"]["installed_profile_count"], 1)
        self.assertEqual(inventory["summary"]["pending_template_count"], 122)
        self.assertEqual(inventory["summary"]["unmapped_folder_count"], 1)
        self.assertEqual(inventory["summary"]["stale_association_count"], 0)
        lisa = next(x for x in inventory["characters"] if x["profile"] == "genshin_lisa")
        self.assertEqual(lisa["status"], "structurally_installed")
        self.assertFalse(lisa["desktop_qa_verified"])
        self.assertFalse(lisa["rights_verified"])
        self.assertNotIn(str(self.root), json.dumps(inventory, ensure_ascii=False))

    def test_changed_config_expires_mapping_not_false_playability(self):
        associate_existing_role(self.roles, "LegacyLisa", "genshin_lisa", confirmed=True)
        conf = self.first / "pet_conf.json"
        data = json.loads(conf.read_text(encoding="utf-8"))
        data["focus"] = "idle"
        conf.write_text(json.dumps(data, sort_keys=True), encoding="utf-8")
        inv = scan_genshin_library(self.roles)
        self.assertEqual(inv["summary"]["installed_profile_count"], 0)
        self.assertEqual(inv["summary"]["stale_association_count"], 1)
        self.assertEqual(inv["summary"]["invalid_folder_count"], 0)
        self.assertTrue(any(x["folder"] == "LegacyLisa"
                            and x["status"] == "stale_association"
                            for x in inv["unmapped_local"]))

    def test_removing_mapping_only_changes_sidecar(self):
        before = source_hash(self.first)
        associate_existing_role(self.roles, "LegacyLisa", "genshin_lisa", confirmed=True)
        with self.assertRaisesRegex(ValueError, "confirmation"):
            unbind_existing_role(self.roles, "LegacyLisa")
        status = unbind_existing_role(self.roles, "LegacyLisa", confirmed=True)
        self.assertTrue(status["association_removed"])
        self.assertFalse(status["original_role_modified"])
        self.assertEqual(source_hash(self.first), before)
        self.assertEqual(load_bindings(self.roles), {})
        inv = scan_genshin_library(self.roles)
        self.assertEqual(inv["summary"]["installed_profile_count"], 0)
        self.assertEqual(inv["summary"]["unmapped_folder_count"], 2)

    def test_refuse_double_bind_and_non_genhsin(self):
        associate_existing_role(self.roles, "LegacyLisa", "genshin_lisa", confirmed=True)
        with self.assertRaisesRegex(ValueError, "association"):
            associate_existing_role(self.roles, "LegacyLisa", "genshin_xiao",
                                    confirmed=True)
        with self.assertRaisesRegex(ValueError, "Genshin"):
            associate_existing_role(self.roles, "OldAmber", "chibi", confirmed=True)
        self.assertEqual(len(load_bindings(self.roles)), 1)

    def test_receipt_identity_is_authoritative(self):
        (self.first / "PERSONAL_IMPORT.json").write_text(json.dumps({
            "selected_profile": "genshin_amber"
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "explicit import profile"):
            associate_existing_role(self.roles, "LegacyLisa", "genshin_lisa",
                                    confirmed=True)
        self.assertFalse(self.bindings.exists())

    def test_bad_paths_and_linked_mapping_refused_without_writes(self):
        for folder in ("../escape", "Bad/Child", "..", "", "Invalid\\Child"):
            with self.subTest(folder=folder):
                with self.assertRaises(ValueError):
                    associate_existing_role(self.roles, folder, "genshin_lisa",
                                            confirmed=True)
        external = self.root / "outside.json"
        external.write_text("sentinel", encoding="utf-8")
        self.bindings.parent.mkdir()
        try:
            self.bindings.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks are not available")
        with self.assertRaisesRegex(ValueError, "symlink"):
            associate_existing_role(self.roles, "LegacyLisa", "genshin_lisa",
                                    confirmed=True)
        self.assertEqual(external.read_text(encoding="utf-8"), "sentinel")

    def test_malformed_or_overlarge_sidecar_is_blocked(self):
        self.bindings.parent.mkdir()
        self.bindings.write_text("{broken", encoding="utf-8")
        with self.assertRaises(json.JSONDecodeError):
            scan_genshin_library(self.roles)
        self.bindings.write_text("X" * (256 * 1024 + 1), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "safe limits"):
            load_bindings(self.roles)
        self.assertEqual(source_hash(self.first), source_hash(self.first))

    def test_cli_link_and_unlink_work_without_resaving_images(self):
        cli = Path(__file__).resolve().parents[1] / "tools" / "genshin_role_bindings.py"
        prefix = [sys.executable, str(cli), "--role-root", str(self.roles)]
        missing = subprocess.run(
            prefix + ["link", "--folder", "LegacyLisa", "--character", "Lisa"],
            capture_output=True, text=True, encoding="utf-8", timeout=20)
        self.assertNotEqual(missing.returncode, 0)
        old = source_hash(self.first)
        installed = subprocess.run(
            prefix + ["link", "--folder", "LegacyLisa", "--character", "丽莎",
                      "--confirm-local"],
            capture_output=True, text=True, encoding="utf-8", timeout=25, check=True)
        self.assertEqual(json.loads(installed.stdout)["profile"], "genshin_lisa")
        self.assertEqual(source_hash(self.first), old)
        deleted = subprocess.run(
            prefix + ["unlink", "--folder", "LegacyLisa", "--confirm-local"],
            capture_output=True, text=True, encoding="utf-8", timeout=25, check=True)
        self.assertTrue(json.loads(deleted.stdout)["association_removed"])
        self.assertEqual(source_hash(self.first), old)

    def test_gui_uses_confirmed_explicit_action(self):
        file = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberSettings" / "CharCardUI.py"
        tree = ast.parse(file.read_text(encoding="utf-8"))
        method = next(x for x in ast.walk(tree)
                      if isinstance(x, ast.FunctionDef)
                      and x.name == "_associateExistingGenshinRole")
        source = ast.unparse(method)
        self.assertIn("associate_existing_role(", source)
        self.assertIn("confirmed=True", source)
        self.assertIn("self.__showMessageBox(", source)
        self.assertIn("Path(basedir) / 'data' / 'genshin_role_bindings.json'", source)


if __name__ == "__main__":
    unittest.main()
