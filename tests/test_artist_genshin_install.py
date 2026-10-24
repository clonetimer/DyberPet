"""Offline tests: real source ZIP layout, not generated character-like art."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile

from tools.install_artist_genshin import (
    install_artist_genshin, ROOT_PREFIX, REVISION, ROLES,
    _prune_missing_optional_actions,
)


def fake_archive(*, extra=None):
    stream = io.BytesIO()
    prefix = ROOT_PREFIX + "纳西妲/"
    with ZipFile(stream, "w") as zipfile:
        zipfile.writestr(prefix + "pet_conf.json", json.dumps({
            "default": "idle", "drag": "idle", "fall": "idle",
            "left": "idle", "right": "idle"}))
        zipfile.writestr(prefix + "act_conf.json", json.dumps({
            "idle": {"images": "idle", "act_num": 1, "frame_refresh": 0.2}}))
        zipfile.writestr(prefix + "action/idle_0.png", b"fake-png")
        zipfile.writestr(ROOT_PREFIX + "魈/action/ignore_0.png", b"other-role")
        if extra:
            zipfile.writestr(prefix + extra, b"unsafe")
    return stream.getvalue()


class ArtistInstallTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "res" / "role"
        self.archive = fake_archive()

    def opener(self, request, timeout=60):
        self.assertIn(REVISION, request.full_url)
        return io.BytesIO(self.archive)

    def test_installs_exact_upstream_frames_without_overwriting_or_generating(self):
        role = install_artist_genshin("nahida", self.root,
                                      confirmed=True, opener=self.opener)
        folder = self.root / role["folder"]
        self.assertEqual((folder / "action/idle_0.png").read_bytes(), b"fake-png")
        self.assertFalse((folder / "action/ignore_0.png").exists())
        receipt = json.loads((folder / "PERSONAL_IMPORT.json").read_text("utf-8"))
        self.assertEqual(receipt["selected_profile"], "genshin_nahida")
        self.assertEqual(receipt["source_commit"], REVISION)
        self.assertFalse(receipt["likeness_manually_reviewed"])
        self.assertEqual(role["actions"], 1)
        with self.assertRaises(FileExistsError):
            install_artist_genshin("nahida", self.root,
                                   confirmed=True, opener=self.opener)
        self.assertTrue((folder / "action/idle_0.png").exists())

    def test_explicit_confirmation_is_required_without_network(self):
        with self.assertRaises(ValueError):
            install_artist_genshin("nahida", self.root, opener=self.opener)
        self.assertFalse(self.root.exists())

    def test_rejects_unsafe_archive_and_leaves_no_role(self):
        self.archive = fake_archive(extra="../evil.py")
        with self.assertRaises(ValueError):
            install_artist_genshin("nahida", self.root,
                                   confirmed=True, opener=self.opener)
        self.assertFalse((self.root / "SourceGenshinNahida").exists())

    def test_drop_unpublished_optional_effect_but_never_redraw_art(self):
        folder = self.root / "example"
        (folder / "action").mkdir(parents=True)
        original = b"original-artist-bytes"
        (folder / "action/idle_0.png").write_bytes(original)
        (folder / "pet_conf.json").write_text(json.dumps({
            "default":"idle", "drag":"idle", "fall":"idle",
            "left":"unused", "random_act":[{"act_list":["unused"]}]}))
        (folder / "act_conf.json").write_text(json.dumps({
            "idle":{"images":"idle", "act_num":1, "frame_refresh":0.2},
            "unused":{"images":"not_distributed", "act_num":1, "frame_refresh":0.2}}))
        self.assertEqual(_prune_missing_optional_actions(folder), ["unused"])
        self.assertEqual((folder / "action/idle_0.png").read_bytes(), original)
        self.assertTrue((folder / "UPSTREAM_ACT_CONF.json").is_file())
        updated = json.loads((folder / "pet_conf.json").read_text())
        self.assertEqual(updated["left"], "idle")
        self.assertEqual(updated["random_act"], [])

    def test_all_named_roles_have_pinned_profiles(self):
        self.assertEqual(set(ROLES), {"nahida", "xiao", "wanderer"})
        self.assertEqual(len({x[1] for x in ROLES.values()}), 3)


if __name__ == "__main__":
    unittest.main()
