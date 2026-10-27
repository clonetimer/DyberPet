"""No automatic third-party download: allowlisted opt-in and SHA verification."""
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.install_creator_mascots import (
    UPSTREAM, DORO_VARIANTS, PINNED_REVISION, ROOT,
    _download_pinned, install_creator_mascot)


class RemoteMascotInstallTests(unittest.TestCase):
    def setUp(self):
        td=tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root=Path(td.name)/"res"/"role"

    def test_does_not_download_until_explicit_confirmation(self):
        hits=[]
        def reject(*args):
            hits.append(args)
            raise AssertionError("should not connect")
        with self.assertRaisesRegex(ValueError,"confirmation"):
            install_creator_mascot("doro",self.root,downloader=reject)
        self.assertFalse(self.root.exists())
        self.assertFalse(hits)
        with self.assertRaisesRegex(ValueError,"supported"):
            install_creator_mascot("evil",self.root,confirmed=True,downloader=reject)

    def test_pinned_source_has_real_exact_author_ids_and_static_https(self):
        self.assertEqual(set(UPSTREAM),{"guga","doro"})
        self.assertEqual(UPSTREAM["guga"]["id"],"guga--circus")
        self.assertEqual(UPSTREAM["doro"]["id"],"doro--lingxiaotian")
        self.assertTrue(ROOT.startswith("https://raw.githubusercontent.com/"))
        self.assertEqual(len(PINNED_REVISION),40)
        self.assertIn("Unknown",UPSTREAM["guga"]["license"])
        self.assertIn("CC BY-NC",UPSTREAM["doro"]["license"])
        for metadata in UPSTREAM.values():
            self.assertEqual(len(metadata["atlas_sha256"]),64)
            self.assertEqual(len(metadata["manifest_sha256"]),64)
            self.assertLess(metadata["atlas_bytes"],6*1024*1024)

    def test_handdrawn_doro_v2_is_real_sha256_pinned_and_separate(self):
        v2 = DORO_VARIANTS["handdrawn_v2"]
        self.assertEqual(v2["id"], "doro--godxxy1229")
        self.assertEqual(v2["atlas_bytes"], 702066)
        self.assertEqual(v2["manifest_bytes"], 252)
        self.assertEqual(v2["atlas_sha256"],
                         "a22d84a8836f60c535b7bf418eda5d68ba99ca36338f3816fc8a043b77bf3228")
        self.assertEqual(len(v2["manifest_sha256"]), 64)
        self.assertNotEqual(v2["atlas_sha256"], UPSTREAM["doro"]["atlas_sha256"])
        self.assertIn("non-commercial", v2["license"])
        self.assertIn("Unknown", UPSTREAM["guga"]["license"])

    def test_v2_download_requires_opt_in_and_cannot_replace_guga(self):
        with self.assertRaisesRegex(ValueError, "confirmation"):
            install_creator_mascot("doro", self.root, variant="handdrawn_v2")
        with self.assertRaisesRegex(ValueError, "only available for Doro"):
            install_creator_mascot("guga", self.root, confirmed=True,
                                   variant="handdrawn_v2")
        self.assertFalse(self.root.exists())

    def test_checksum_mismatch_blocks_import_with_no_installed_roles(self):
        hits=[]
        def corrupt(url,digest,length):
            hits.append(url)
            return b"CORRUPT CONTENT"
        with self.assertRaises((ValueError,UnicodeError,json.JSONDecodeError)):
            install_creator_mascot("guga",self.root,confirmed=True,downloader=corrupt)
        self.assertEqual(len(hits),2)
        self.assertFalse((self.root/"SourceGuga").exists())

    def test_bounded_verified_fetch(self):
        payload=b"creator sample bytes, not a game image"
        sha=hashlib.sha256(payload).hexdigest()
        class Response:
            def __init__(self,v):self.v=v
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return self.v[:n]
        history=[]
        def opener(url,timeout):
            history.append((url,timeout))
            return Response(payload)
        data=_download_pinned("https://raw.githubusercontent.com/test",
                              sha,len(payload),opener=opener)
        self.assertEqual(data,payload)
        self.assertEqual(history[0][1],15)
        with self.assertRaisesRegex(ValueError,"SHA-256"):
            _download_pinned("https://raw.githubusercontent.com/test",
                             "0"*64,len(payload),opener=opener)
        with self.assertRaisesRegex(ValueError,"size"):
            _download_pinned("https://raw.githubusercontent.com/test",
                             sha,len(payload)+1,opener=opener)

    def _fake_download(self, url, _sha, _size):
        if url.endswith("/pet.json"):
            return json.dumps({"id":"guga--circus",
                               "spritesheetPath":"spritesheet.webp"}).encode("utf-8")
        return b"fake-byte-atlas-only-for-isolated-test"

    @staticmethod
    def _fake_convert(source, target_root, *, folder, **kwargs):
        path=Path(target_root)/folder
        path.mkdir(parents=True)
        (path/"IMPORT_REPORT.json").write_text(
            json.dumps({"mascot_preset":"guga",
                        "source_manifest_id":"guga--circus"}),encoding="utf-8")
        return path

    def test_failed_native_or_motion_validation_keeps_live_roster_clean(self):
        with (patch("tools.install_creator_mascots.convert",
                    side_effect=self._fake_convert),
              patch("tools.install_creator_mascots.validate_native_role",
                    side_effect=ValueError("bad original source config"))):
            with self.assertRaisesRegex(ValueError,"bad original"):
                install_creator_mascot("guga",self.root,confirmed=True,
                                       downloader=self._fake_download)
        self.assertEqual(list(self.root.iterdir()),[])
        with (patch("tools.install_creator_mascots.convert",
                    side_effect=self._fake_convert),
              patch("tools.install_creator_mascots.validate_native_role",
                    return_value={"actions":2,"images":6}),
              patch("tools.install_creator_mascots.analyze_creator_actions",
                    side_effect=ValueError("unreadable later PNG"))):
            with self.assertRaisesRegex(ValueError,"unreadable later"):
                install_creator_mascot("guga",self.root,confirmed=True,
                                       downloader=self._fake_download)
        self.assertEqual(list(self.root.iterdir()),[])
        self.assertFalse((self.root/"SourceGuga").exists())

    def test_success_publishes_only_complete_identity_and_motion_receipt(self):
        motion={"folder":"SourceGuga",
                "summary":{"actions_inspected":2,"frames_inspected":6,
                           "all_frames_examined":True,"original_art_modified":False,
                           "motion_semantics_approved":False},
                "actions":[{"action":"left_walk","frame_count":4,
                           "unique_visible_poses":3,"risk_indicators":[]},
                          {"action":"crawl","frame_count":2,
                           "unique_visible_poses":1,
                           "risk_indicators":["translation_only_or_static_pose"]}]}
        with (patch("tools.install_creator_mascots.convert",
                    side_effect=self._fake_convert),
              patch("tools.install_creator_mascots.validate_native_role",
                    return_value={"actions":2,"images":6}),
              patch("tools.install_creator_mascots.analyze_creator_actions",
                    return_value=motion)):
            result=install_creator_mascot("guga",self.root,confirmed=True,
                                           downloader=self._fake_download)
        self.assertEqual(result["folder"],"SourceGuga")
        role=self.root/"SourceGuga"
        self.assertTrue((role/"CREATOR_ORIGINAL_MOTION_QA.json").is_file())
        receipt=json.loads((role/"PERSONAL_IMPORT.json").read_text("utf-8"))
        self.assertEqual(receipt["motion_risk_actions"],["crawl"])
        self.assertFalse(receipt["motion_semantics_manually_reviewed"])
        self.assertEqual(receipt["source_id"],"guga--circus")
        self.assertEqual([p.name for p in self.root.iterdir()],["SourceGuga"])

    def test_existing_creator_folder_is_never_replaced(self):
        self.root.mkdir(parents=True)
        protected=self.root/"SourceGuga"
        protected.mkdir()
        (protected/"keep.txt").write_text("my art")
        with self.assertRaises(FileExistsError):
            install_creator_mascot(
                "guga",self.root,folder="SourceGuga",confirmed=True,
                downloader=lambda *args: (_ for _ in ()).throw(
                    AssertionError("should not network on existing folder")))
        self.assertEqual((protected/"keep.txt").read_text(),"my art")

    def test_gui_uses_real_offthread_worker_and_confirmation(self):
        path=Path(__file__).resolve().parents[1]/"DyberPet"/"DyberSettings"/"CharCardUI.py"
        tree=ast.parse(path.read_text(encoding="utf-8"))
        methods={f.name:ast.unparse(f) for f in ast.walk(tree)
                 if isinstance(f,ast.FunctionDef)}
        self.assertIn("_installCreatorMascot",methods)
        self.assertIn("self.__showMessageBox(",methods["_installCreatorMascot"])
        self.assertIn("ChibiImportThread(",methods["_installCreatorMascot"])
        self.assertIn("source_mode = 'creator_source'", methods["_installCreatorMascot"])
        self.assertIn("'creator_source_v2'", methods["_installCreatorMascot"])
        self.assertIn("QInputDialog.getItem(", methods["_installCreatorMascot"])
        self.assertIn("if not accepted:", methods["_installCreatorMascot"])
        self.assertIn("godxxy1229", methods["_installCreatorMascot"])
        self.assertIn("handdrawn_v2", methods["run"])
        self.assertIn("if self.mode == 'creator_source_v2' and self.preset != 'doro':",
                      methods["run"])
        self.assertIn("install_creator_mascot(",methods["run"])
        self.assertIn("confirmed=True",methods["run"])
        self.assertIn("scan_mascot_library(", methods["run"])
        self.assertIn("source_id", methods["run"])
        self.assertIn("if len(matching) != 1:", methods["run"])


if __name__=="__main__":
    unittest.main()
