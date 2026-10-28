"""Offline tests for the REAL one-download artist-batch import workflow."""
import ast
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zipfile import ZipFile

from PIL import Image

from tools.install_artist_genshin import (
    ROLES, REVISION, ROOT_PREFIX, SOURCE_IDENTITY,
)
from tools.install_artist_genshin_batch import (
    install_artist_genshin_batch, parse_roles, CORE_ROLES, COMPANION_ROLES,
)


def _png_data(color):
    out = io.BytesIO()
    Image.new("RGBA", (32, 40), color).save(out, "PNG")
    return out.getvalue()


def _fixture():
    out = io.BytesIO()
    anchors = {}
    with ZipFile(out, "w") as archive:
        for index, (key, (name, _, _)) in enumerate(ROLES.items()):
            files = {
                "pet_conf.json": json.dumps({
                    "default": "idle", "drag": "idle", "fall": "idle",
                    "left": "idle", "right": "idle",
                }).encode("utf-8"),
                "act_conf.json": json.dumps({
                    "idle": {"images": "idle", "frame_refresh": 0.2}
                }).encode("utf-8"),
                "action/idle_0.png": _png_data(((90 + index * 40) % 256, 40, 90, 255)),
            }
            anchors[key] = {}
            for path, payload in files.items():
                archive.writestr(ROOT_PREFIX + name + "/" + path, payload)
                anchors[key][path] = hashlib.sha1(
                    b"blob " + str(len(payload)).encode() + b"\0" + payload
                ).hexdigest()
        # Source may contain unrelated modules, but none may install by mistake.
        archive.writestr(ROOT_PREFIX + "散猫猫/action/no_0.png",
                         b"unrelated not installed")
    return out.getvalue(), anchors


class SourceBatchTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name) / "res" / "role"
        self.payload, anchors = _fixture()
        patcher = patch.dict(SOURCE_IDENTITY, anchors, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.requests = 0

    def opener(self, request, timeout=60):
        self.assertIn(REVISION, request.full_url)
        self.requests += 1
        return io.BytesIO(self.payload)

    def test_batch_installs_three_genuine_bodies_in_one_network_request(self):
        got = install_artist_genshin_batch(
            "all", self.root, confirmed=True, opener=self.opener)
        self.assertEqual(self.requests, 1)
        self.assertEqual(got["installed_count"], 3)
        self.assertEqual(got["archive_download_count"], 1)
        self.assertFalse(got["likeness_manually_reviewed"])
        self.assertFalse(got["art_rights_verified"])
        self.assertEqual(set(x["profile"] for x in got["roles"]),
                         {ROLES[k][1] for k in CORE_ROLES})
        for i, key in enumerate(CORE_ROLES):
            cn_name, profile, _ = ROLES[key]
            folder = self.root / ("SourceGenshin" + key.title())
            receipt = json.loads((folder / "PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertEqual(receipt["display_name"], cn_name)
            self.assertEqual(receipt["selected_profile"], profile)
            self.assertEqual(receipt["source_commit"], REVISION)
            self.assertFalse(receipt["likeness_manually_reviewed"])
            self.assertTrue((folder / "ANIMATION_PREVIEW.png").is_file())
            with Image.open(folder / "action" / "idle_0.png") as img:
                self.assertEqual(img.getpixel((0, 0)),
                                 (90 + i * 40, 40, 90, 255))
            self.assertFalse((folder / "action" / "no_0.png").exists())

    def test_companions_four_are_real_native_source_roles_not_human_templates(self):
        result = install_artist_genshin_batch(
            "companions", self.root, confirmed=True, opener=self.opener)
        self.assertEqual(result["installed_count"], 4)
        self.assertEqual(result["archive_download_count"], 1)
        self.assertEqual(self.requests, 1)
        for key in COMPANION_ROLES:
            folder = self.root / ("SourceGenshin" + key.title())
            receipt = json.loads((folder / "PERSONAL_IMPORT.json").read_text(encoding="utf-8"))
            self.assertEqual(receipt["display_name"], ROLES[key][0])
            self.assertIsNone(receipt["selected_profile"])
            self.assertTrue(receipt["native_companion"])
            self.assertFalse(receipt["likeness_manually_reviewed"])
            self.assertTrue((folder / "ANIMATION_PREVIEW.png").exists())
            self.assertTrue((folder / "ANIMATION_MOTION_QA.json").exists())
        self.assertFalse((self.root / "SourceGenshinNahida").exists())

    def test_all_seven_staged_in_one_download_with_distinct_receipts(self):
        result = install_artist_genshin_batch(
            "all-seven", self.root, confirmed=True, opener=self.opener)
        self.assertEqual(result["installed_count"], 7)
        self.assertEqual(self.requests, 1)
        self.assertEqual(len({x["folder"] for x in result["roles"]}), 7)
        self.assertTrue((self.root / "SourceGenshinXiao_Bird").exists())

    def test_requires_consent_before_network_or_writing(self):
        with self.assertRaisesRegex(ValueError, "consent"):
            install_artist_genshin_batch("all", self.root, opener=self.opener)
        self.assertEqual(self.requests, 0)
        self.assertFalse(self.root.exists())

    def test_rejects_existing_destination_before_network(self):
        (self.root / "SourceGenshinXiao").mkdir(parents=True)
        protected = self.root / "SourceGenshinXiao" / "user_file.txt"
        protected.write_text("preserve")
        with self.assertRaises(FileExistsError):
            install_artist_genshin_batch("all", self.root,
                                          confirmed=True, opener=self.opener)
        self.assertEqual(protected.read_text(), "preserve")
        self.assertFalse((self.root / "SourceGenshinNahida").exists())
        self.assertEqual(self.requests, 0)

    def test_rollback_on_one_role_identity_mismatch(self):
        # Corrupt one role, while preserving the pinned original identity map.
        with ZipFile(io.BytesIO(self.payload)) as src:
            entries = {info.filename: src.read(info.filename)
                       for info in src.infolist()}
        changed = ROOT_PREFIX + "魈/action/idle_0.png"
        entries[changed] = _png_data((255, 20, 20, 255))
        out = io.BytesIO()
        with ZipFile(out, "w") as writer:
            for path, payload in entries.items():
                writer.writestr(path, payload)
        self.payload = out.getvalue()
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            install_artist_genshin_batch("all", self.root, confirmed=True,
                                          opener=self.opener)
        self.assertEqual(self.requests, 1)
        self.assertFalse(any(self.root.glob("SourceGenshin*")))

    def test_rollback_if_copy_to_final_install_fails(self):
        import tools.install_artist_genshin_batch as target
        real_copytree = target.shutil.copytree
        calls = 0

        def fail_second(src, dst, *args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("disk became unavailable")
            return real_copytree(src, dst, *args, **kwargs)

        with patch.object(target.shutil, "copytree", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "disk became"):
                install_artist_genshin_batch("all", self.root, confirmed=True,
                                              opener=self.opener)
        self.assertEqual(calls, 2)
        self.assertFalse(any(self.root.glob("SourceGenshin*")))

    def test_actual_gui_has_opt_in_batch_and_adds_all_three_roles(self):
        ui = (Path(__file__).resolve().parents[1] /
              "DyberPet" / "DyberSettings" / "CharCardUI.py")
        source = ui.read_text(encoding="utf-8")
        nodes = ast.walk(ast.parse(source))
        methods = {f.name: ast.unparse(f) for f in nodes
                   if isinstance(f, ast.FunctionDef)}
        self.assertIn("artist_genshin_batch", methods["_installArtistGenshin"])
        run = methods["run"]  # ChibiImportThread.run is the only named run in UI
        self.assertIn("install_artist_genshin_batch(", run)
        self.assertIn("CheckCharFiles(str(folder))", run)
        self.assertIn("self.done.emit(folder.name, '')", run)
        self.assertIn("batch_folders", run)
        self.assertIn("rmtree(folder, ignore_errors=True)", run)
        self.assertIn("artist_genshin_batch", methods["_onChibiImportComplete"])

    def test_subset_and_duplicate_validation(self):
        self.assertEqual(parse_roles("nahida,xiao"), ("nahida", "xiao"))
        self.assertEqual(parse_roles("all"), CORE_ROLES)
        self.assertEqual(parse_roles("companions"), COMPANION_ROLES)
        self.assertEqual(parse_roles("all-seven"), CORE_ROLES + COMPANION_ROLES)
        for raw in ("", "ALL,nahida", "nahida,nahida", "unknown", "xiao,"):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_roles(raw)
        got = install_artist_genshin_batch("xiao", self.root,
                                           confirmed=True, opener=self.opener)
        self.assertEqual(got["installed_count"], 1)
        self.assertEqual(self.requests, 1)
        self.assertTrue((self.root / "SourceGenshinXiao").is_dir())
        self.assertFalse((self.root / "SourceGenshinNahida").exists())


if __name__ == "__main__":
    unittest.main()
