"""Pinned third-party Shimeji source audit, non-destructive offline installation."""
from __future__ import annotations

from io import BytesIO
import json
import hashlib
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.character_source_coverage import source_coverage
from tools.install_nanopet_shimeji import (source_manifest, install_nanopet_shimeji,
                                           GROUPS, EXTRA_GROUPS, mapped_groups)
from tools.install_native_role import validate_native_role
from DyberPet.assistant.native_groups import runtime_group_interactions


class NanoPetArtistTests(unittest.TestCase):
    def test_standard_shimeji_action_semantics_do_not_fabricate_petting(self):
        # Canonical Shimeji-ee actions.xml uses shime1 for Stand;
        # 38 is clone and 31-33 are edge-sitting, not user patting.
        self.assertEqual(GROUPS["stand"], (1,))
        self.assertEqual(GROUPS["walk"], (1, 2, 3))
        self.assertEqual(GROUPS["sit"], (11,))
        self.assertEqual(GROUPS["landing"], (18, 19))
        self.assertEqual(GROUPS["onfloor"], (21,))
        self.assertNotIn("pat", GROUPS)
        self.assertTrue(all(n not in GROUPS["stand"] for n in (31, 32, 33, 38)))

    def test_17_authored_source_versions_offer_only_complete_shimeji_gestures(self):
        archive = source_manifest()
        self.assertEqual(len(archive["roles"]), 17)
        self.assertEqual(len({r["profile"] for r in archive["roles"].values()}), 16)
        self.assertEqual(EXTRA_GROUPS["lookaround"],
                         (26, 15, 27, 16, 28, 17, 29))
        self.assertEqual(EXTRA_GROUPS["ceiling_crawl"], (23, 24, 25))
        self.assertEqual(EXTRA_GROUPS["edge_sit"], (30, 31, 32, 33))
        self.assertEqual(EXTRA_GROUPS["jump_pose"], (22,))
        self.assertNotIn("pat", mapped_groups(range(1, 47)))
        full = mapped_groups(range(1, 47))
        self.assertEqual(len(full), len(GROUPS) + len(EXTRA_GROUPS))
        # Aether source is 45 PNGs, WITHOUT source-authored shime29.
        aether = archive["roles"]["aether-by-tenkotenmeo"]["files"]
        by_id = {int(name.removeprefix("shime").replace(".png", "").replace("_", ""))
                 for name in aether}
        self.assertNotIn(29, by_id)
        no_head_turn = mapped_groups(by_id)
        self.assertNotIn("lookaround", no_head_turn)
        for action in ("ceiling_crawl", "edge_sit", "window_carry", "jump_pose"):
            self.assertIn(action, no_head_turn)

    def test_full_original_gestures_and_actual_petwidget_semantic_dispatch(self):
        raw = self.image_bytes()
        blob = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
        for omit in (None, 29):
            with self.subTest(missing_original_shime29=omit), tempfile.TemporaryDirectory() as td:
                indexes = [i for i in range(1, 47) if i != omit]
                files = {f"shime{i}.png": {"sha": blob, "size": len(raw)}
                         for i in indexes}
                manifest = {
                    "repository": "Poseima/nano-pet", "revision": "b" * 40,
                    "asset_root": "NanoPetAssets/genshin-impact",
                    "roles": {"aether-by-tenkotenmeo": {
                        "name": "空", "profile": "genshin_traveler_aether",
                        "artist": "tenkotenmeo",
                        "upstream_dir": "genshin-impact-aether-by-tenkotenmeo",
                        "files": files}}
                }
                root = Path(td)
                installed = install_nanopet_shimeji(
                    "aether-by-tenkotenmeo", root, confirmed=True,
                    manifest=manifest, downloader=lambda url, spec: raw)
                native = root / installed["folder"]
                actions = json.loads((native/"act_conf.json").read_text("utf-8"))
                pet = json.loads((native/"pet_conf.json").read_text("utf-8"))
                receipt = json.loads((native/"PERSONAL_IMPORT.json").read_text("utf-8"))
                self.assertIn("ceiling_crawl", actions)
                self.assertIn("edge_sit", actions)
                self.assertIn("jump_pose", actions)
                self.assertFalse(receipt["source_authored_petting_animation"])
                self.assertFalse(receipt["source_authored_animated_jump"])
                self.assertEqual(receipt["all_original_frames_preserved"], len(indexes))
                self.assertEqual((native/"source_frames"/"shime22.png").read_bytes(), raw)
                self.assertEqual("lookaround" in actions, omit is None)
                self.assertEqual(installed["native_observe_shortcut"], omit is None)
                for group in pet["random_act"]:
                    if group["name"] == "散步":
                        self.assertEqual(group["act_list"],
                                         ["left_walk", "right_walk"])
                opts = {g["name"]: {"act_type": "random_act", "unlocked": True}
                        for g in pet["random_act"]}
                gestures = {
                    item["id"]: item for item in runtime_group_interactions(
                        opts, pet["random_act"], actions.keys())
                }
                for category in ("walk", "rest"):
                    self.assertTrue(gestures[category]["available"], category)
                self.assertEqual(gestures["observe"]["available"], omit is None)
                self.assertFalse(gestures["jump"]["available"])
                # A user upgrading an already imported creator source must
                # retain the previous artwork, config and default pet intact.
                previous_config = (native / "act_conf.json").read_bytes()
                with self.assertRaises(FileExistsError):
                    install_nanopet_shimeji(
                        "aether-by-tenkotenmeo", root, confirmed=True,
                        manifest=manifest, downloader=lambda url, spec: raw)
                updated = install_nanopet_shimeji(
                    "aether-by-tenkotenmeo", root, confirmed=True,
                    install_as_new_variant=True,
                    manifest=manifest, downloader=lambda url, spec: raw)
                upgraded = root / updated["folder"]
                self.assertTrue(updated["new_variant_of_existing_original"])
                self.assertNotEqual(upgraded, native)
                self.assertEqual((native / "act_conf.json").read_bytes(),
                                 previous_config)
                self.assertEqual((upgraded / "source_frames" / "shime22.png").read_bytes(), raw)
                self.assertEqual(len([d for d in root.iterdir() if d.is_dir()]), 2)
                # The GUI passes opt-in variant install without overwriting.
                gui = (Path(__file__).resolve().parents[1] / "DyberPet" /
                       "DyberSettings" / "CharCardUI.py").read_text("utf-8")
                self.assertIn("install_as_new_variant=True", gui)
                # Any original sprite missing => no fabricated head-turn action.
                if omit == 29:
                    self.assertIn("lookaround", receipt["missing_optional_source_sequences"])

    def test_archived_genshin_character_sources_are_real_frames(self):
        r = source_manifest()
        self.assertEqual(len(r["roles"]), 17)
        total = sum(len(x["files"]) for x in r["roles"].values())
        self.assertEqual(total, 781)
        self.assertEqual(len(r["revision"]), 40)
        self.assertNotIn("xiao-catboy-by-uuteki", r["roles"])
        expected = {
            "aether-by-tenkotenmeo": "genshin_traveler_aether",
            "lumine-by-marcia": "genshin_traveler_lumine",
            "childe-by-nemururin": "genshin_tartaglia",
            "diluc-by-vol-tuna": "genshin_diluc",
            "kaeya-by-vol-tuna": "genshin_kaeya",
            "razor-by-batsouppe": "genshin_razor",
            "xiao-by-tachi-png": "genshin_xiao",
            "zhongli-by-vol-tuna": "genshin_zhongli",
        }
        for k, profile in expected.items():
            self.assertEqual(r["roles"][k]["profile"], profile)
        for key, item in r["roles"].items():
            with self.subTest(key=key):
                self.assertGreaterEqual(len(item["files"]), 45)
                self.assertTrue(all(len(f["sha"]) == 40 for f in item["files"].values()))

    def test_123_role_ledger_does_not_exaggerate_completed_characters(self):
        r = source_coverage()
        s = r["summary"]
        self.assertEqual(s["template_count"], 123)
        self.assertEqual(s["pinned_source_options"], 91)
        self.assertEqual(s["characters_with_pinned_sources"], 68)
        self.assertEqual(s["characters_without_pinned_sources"], 55)
        self.assertEqual(s["verified_likeness_count"], 0)
        candidates = {v["id"]: v for v in r["characters"]}
        for k in ("genshin_traveler_aether", "genshin_traveler_lumine",
                  "genshin_tartaglia", "genshin_zhongli", "genshin_diluc",
                  "genshin_kaeya", "genshin_razor", "genshin_xiao"):
            self.assertTrue(candidates[k]["source_found"], k)
            self.assertTrue(any(x["provider"] == "nano_shimeji"
                                for x in candidates[k]["source_candidates"]))
        for value in r["characters"]:
            self.assertFalse(value["installed"])
            self.assertFalse(value["visual_likeness_qa_passed"])

    @staticmethod
    def image_bytes():
        data = BytesIO()
        Image.new("RGBA", (45, 72), (80, 150, 230, 200)).save(data, "PNG")
        return data.getvalue()

    def test_offline_installer_preserves_source_bytes_and_rejects_overwrite(self):
        source = self.image_bytes()
        identity = hashlib.sha1(b"blob " + str(len(source)).encode() + b"\0" + source).hexdigest()
        used = {num for values in GROUPS.values() for num in values}
        specs = {f"shime{n}.png": {"sha": identity, "size": len(source)}
                 for n in sorted(used)}
        dummy = {"repository": "Poseima/nano-pet", "revision": "a" * 40,
                 "asset_root": "NanoPetAssets/genshin-impact",
                 "roles": {"zhongli-by-vol-tuna": {
                     "name": "钟离", "profile": "genshin_zhongli",
                     "upstream_dir": "genshin-impact-zhongli-by-vol-tuna",
                     "artist": "vol-tuna", "files": specs}}}
        calls = []
        def fake_download(url, spec):
            calls.append(url)
            self.assertTrue(url.endswith(".png"))
            self.assertEqual(spec["sha"], identity)
            return source
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            with self.assertRaises(ValueError):
                install_nanopet_shimeji("zhongli-by-vol-tuna", path,
                    manifest=dummy, downloader=fake_download)
            self.assertFalse(calls)
            result = install_nanopet_shimeji("zhongli-by-vol-tuna", path,
                confirmed=True, manifest=dummy, downloader=fake_download)
            role = path / result["folder"]
            self.assertEqual((role/"action"/"stand_0.png").read_bytes(), source)
            self.assertEqual((role/"source_frames"/"shime1.png").read_bytes(), source)
            self.assertTrue((role/"ANIMATION_PREVIEW.png").is_file())
            self.assertEqual(result["source_original_frames"], len(used))
            self.assertGreaterEqual(validate_native_role(role)["actions"], 9)
            self.assertFalse((role/"action"/"pat_0.png").exists())
            meta_actions = json.loads((role/"act_conf.json").read_text("utf-8"))
            self.assertNotIn("patpat", meta_actions)
            self.assertIn("rest", meta_actions)
            meta = json.loads((role/"PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertFalse(meta["source_rights_verified"])
            self.assertFalse(meta["likeness_manually_reviewed"])
            self.assertEqual(meta["all_original_frames_preserved"], len(used))
            with self.assertRaises(FileExistsError):
                install_nanopet_shimeji("zhongli-by-vol-tuna", path,
                    confirmed=True, manifest=dummy, downloader=fake_download)
            self.assertTrue(role.is_dir())


if __name__ == "__main__":
    unittest.main()
