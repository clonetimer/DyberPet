"""R29: Keqing 92 true author frame native importer (source-only opt-in)."""
from __future__ import annotations
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from PIL import Image
from tools.install_gmcy_keqing import (
    SOURCE_KEY, source_manifest, verify_original_frames,
    install_gmcy_keqing, _git_blob_sha, source_zip_url)
from tools.install_native_role import validate_native_role


def fixture():
    """Synthetic test-only PNGs (never marketed as author images)."""
    manifest=copy.deepcopy(source_manifest())
    content=[]
    for n in range(1,93):
        im=Image.new("RGBA",(18,18),((n*17)%255,(n*29)%255,(n*37)%255,255))
        output=io.BytesIO(); im.save(output,format="PNG"); raw=output.getvalue()
        manifest["files"][n-1]={"num":n,"bytes":len(raw),"git_blob_sha1":_git_blob_sha(raw)}
        content.append(raw)
    manifest["original_image_bytes"]=sum(len(x) for x in content)
    root=f"DesktopPet-Simple-{manifest['commit']}/resources/pet_1/"
    out=io.BytesIO()
    with zipfile.ZipFile(out,"w",zipfile.ZIP_DEFLATED) as z:
        for n,raw in enumerate(content,1):z.writestr(root+f"shime{n}.png",raw)
        z.writestr(f"DesktopPet-Simple-{manifest['commit']}/main.py","raise Exception('do not run')")
    return manifest,out.getvalue()


class KeqingOriginal92(unittest.TestCase):
    def test_manifest_is_exact_original_92_and_six_author_action_groups(self):
        data=source_manifest()
        self.assertEqual(data["source_directory"],"resources/pet_1")
        self.assertEqual(data["chinese_name"],"刻晴")
        self.assertEqual(data["original_image_bytes"],24545814)
        self.assertEqual(len(data["files"]),92)
        self.assertEqual(len(data["original_action_groups"]),6)
        self.assertEqual(sum(len(x["frames"]) for x in data["original_action_groups"]),92)
        self.assertIn(data["commit"],source_zip_url())

    def test_verified_zip_installs_native_role_with_separate_identity(self):
        data,archive=fixture()
        with tempfile.TemporaryDirectory() as tmp,patch("tools.install_gmcy_keqing.source_manifest",return_value=data):
            root=Path(tmp)/"role"
            with self.assertRaisesRegex(ValueError,"Explicit"):
                install_gmcy_keqing(SOURCE_KEY,root,archive_bytes=archive)
            self.assertEqual(len(verify_original_frames(archive,manifest=data)),92)
            role=install_gmcy_keqing(SOURCE_KEY,root,archive_bytes=archive,confirmed=True)
            result=validate_native_role(role)
            self.assertEqual(result["actions"],6)
            self.assertEqual(result["images"],92)
            receipt=json.loads((role/"PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertEqual(receipt["selected_profile"],"genshin_keqing")
            self.assertEqual(receipt["display_name_zh"],"刻晴")
            self.assertFalse(receipt["likeness_manually_reviewed"])
            self.assertFalse(receipt["real_windows_qa_verified"])
            other=install_gmcy_keqing(SOURCE_KEY,root,archive_bytes=archive,confirmed=True)
            self.assertNotEqual(role,other)
            self.assertTrue(role.is_dir())

    def test_wrong_person_identity_forged_blob_or_missing_frame_fail_closed(self):
        data,archive=fixture()
        with self.assertRaisesRegex(ValueError,"Wrong original"):
            install_gmcy_keqing("diona_170","/tmp/fake",archive_bytes=archive,confirmed=True)
        bad=copy.deepcopy(data)
        bad["files"][4]["git_blob_sha1"]="0"*40
        with self.assertRaisesRegex(ValueError,"Git blob identity mismatch"):
            verify_original_frames(archive,manifest=bad)
        buf=io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(archive)) as src,zipfile.ZipFile(buf,"w",zipfile.ZIP_DEFLATED) as out:
            for name in src.namelist():
                if not name.endswith("/shime57.png"):out.writestr(name,src.read(name))
        with self.assertRaisesRegex(ValueError,"lacks 92"):
            verify_original_frames(buf.getvalue(),manifest=data)


if __name__=="__main__":
    unittest.main()
