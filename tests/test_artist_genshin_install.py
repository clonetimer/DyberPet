"""Offline tests: real source ZIP layout, not generated character-like art."""
import io
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from PIL import Image
from unittest.mock import patch
from zipfile import ZipFile

from tools.install_artist_genshin import (
    install_artist_genshin, ROOT_PREFIX, REVISION, ROLES,
    _prune_missing_optional_actions, verify_artist_role_identity,
    SOURCE_IDENTITY,
)


def fixture_sprite():
    output = io.BytesIO()
    Image.new("RGBA", (16, 16), (114, 204, 150, 255)).save(output, "PNG")
    return output.getvalue()


def fake_archive(*, extra=None):
    stream = io.BytesIO()
    prefix = ROOT_PREFIX + "纳西妲/"
    with ZipFile(stream, "w") as zipfile:
        zipfile.writestr(prefix + "pet_conf.json", json.dumps({
            "default": "idle", "drag": "idle", "fall": "idle",
            "left": "idle", "right": "idle"}))
        zipfile.writestr(prefix + "act_conf.json", json.dumps({
            "idle": {"images": "idle", "act_num": 1, "frame_refresh": 0.2}}))
        zipfile.writestr(prefix + "action/idle_0.png", fixture_sprite())
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
        # The fixture is deliberately synthetic; bind the expected hashes to
        # its exact bytes while production always uses real pinned Git blobs.
        with ZipFile(io.BytesIO(self.archive)) as z:
            expected = {}
            for name in ("pet_conf.json", "act_conf.json", "action/idle_0.png"):
                data = z.read(ROOT_PREFIX + "纳西妲/" + name)
                expected[name] = hashlib.sha1(
                    b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        patcher = patch.dict(SOURCE_IDENTITY, {"nahida": expected})
        patcher.start()
        self.addCleanup(patcher.stop)

    def opener(self, request, timeout=60):
        self.assertIn(REVISION, request.full_url)
        return io.BytesIO(self.archive)

    def test_installs_exact_upstream_frames_without_overwriting_or_generating(self):
        role = install_artist_genshin("nahida", self.root,
                                      confirmed=True, opener=self.opener)
        folder = self.root / role["folder"]
        self.assertEqual((folder / "action/idle_0.png").read_bytes(), fixture_sprite())
        self.assertTrue((folder / "ANIMATION_PREVIEW.png").is_file())
        self.assertTrue((folder / "ANIMATION_MOTION_QA.json").is_file())
        motion = json.loads((folder / "ANIMATION_MOTION_QA.json").read_text("utf-8"))
        self.assertTrue(motion["manual_visual_review_pending"])
        self.assertFalse(motion["animation_quality_automatically_approved"])
        with Image.open(folder / "ANIMATION_PREVIEW.png") as preview:
            self.assertGreaterEqual(preview.width, 700)
            self.assertGreaterEqual(preview.height, 180)
        self.assertFalse((folder / "action/ignore_0.png").exists())
        receipt = json.loads((folder / "PERSONAL_IMPORT.json").read_text("utf-8"))
        self.assertEqual(receipt["selected_profile"], "genshin_nahida")
        self.assertEqual(receipt["display_name"], "纳西妲")
        self.assertEqual(receipt["source_commit"], REVISION)
        self.assertEqual(role["source_identity_verified"], True)
        self.assertEqual(len(receipt["source_identity_anchors_verified"]), 3)
        self.assertFalse(receipt["visual_review"]["likeness_manually_reviewed"])
        self.assertTrue(receipt["visual_review"]["source_frames_unmodified"])
        self.assertFalse(receipt["likeness_manually_reviewed"])
        self.assertEqual(receipt["motion_evidence_file"], "ANIMATION_MOTION_QA.json")
        self.assertFalse(receipt["animation_quality_automatically_approved"])
        self.assertEqual(role["actions"], 1)
        with self.assertRaises(FileExistsError):
            install_artist_genshin("nahida", self.root,
                                   confirmed=True, opener=self.opener)
        self.assertTrue((folder / "action/idle_0.png").exists())

    def test_swapped_or_tampered_artist_idle_frame_must_not_install(self):
        with ZipFile(io.BytesIO(self.archive)) as src:
            entries = {info.filename: src.read(info.filename)
                       for info in src.infolist()}
        target_frame = ROOT_PREFIX + "纳西妲/action/idle_0.png"
        entries[target_frame] = b"other-character-frame"
        payload = io.BytesIO()
        with ZipFile(payload, "w") as dest:
            for name, value in entries.items():
                dest.writestr(name, value)
        self.archive = payload.getvalue()
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            install_artist_genshin("nahida", self.root,
                                   confirmed=True, opener=self.opener)
        self.assertFalse((self.root / "SourceGenshinNahida").exists())

    def test_production_source_has_exact_three_config_art_anchors(self):
        self.assertEqual(set(SOURCE_IDENTITY), set(ROLES))
        for kind, anchors in SOURCE_IDENTITY.items():
            self.assertEqual(len(anchors), 3)
            self.assertIn("pet_conf.json", anchors)
            self.assertIn("act_conf.json", anchors)
            self.assertEqual(len([name for name in anchors if name.endswith("_0.png")]), 1)
            self.assertTrue(all(len(sha) == 40 for sha in anchors.values()))

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
