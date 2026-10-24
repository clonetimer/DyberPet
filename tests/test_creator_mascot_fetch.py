"""No automatic third-party download: allowlisted opt-in and SHA verification."""
from __future__ import annotations

import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.install_creator_mascots import (
    UPSTREAM, PINNED_REVISION, ROOT,
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

    def test_gui_uses_real_offthread_worker_and_confirmation(self):
        path=Path(__file__).resolve().parents[1]/"DyberPet"/"DyberSettings"/"CharCardUI.py"
        tree=ast.parse(path.read_text(encoding="utf-8"))
        methods={f.name:ast.unparse(f) for f in ast.walk(tree)
                 if isinstance(f,ast.FunctionDef)}
        self.assertIn("_installCreatorMascot",methods)
        self.assertIn("self.__showMessageBox(",methods["_installCreatorMascot"])
        self.assertIn("ChibiImportThread(",methods["_installCreatorMascot"])
        self.assertIn('mode="creator_source"',methods["_installCreatorMascot"])
        self.assertIn("install_creator_mascot(",methods["run"])
        self.assertIn("confirmed=True",methods["run"])


if __name__=="__main__":
    unittest.main()
