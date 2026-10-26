"""Real decoded sprite PNGs: Python and native auditor must stay equivalent.

Synthetic original RGBA pixels are created in temporary files; no artwork is
downloaded, bundled, uploaded or modified by either backend.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from PIL import Image

from DyberPet.assistant.character_fidelity import inspect_character_role
from DyberPet.assistant.native_bridge import backend_status, sha256_file


class RustCreatorSpriteParity(unittest.TestCase):
    def setUp(self):
        handle = tempfile.TemporaryDirectory(prefix="dyberpet-rust-real-png-")
        self.addCleanup(handle.cleanup)
        self.role = Path(handle.name) / "Guga"
        action = self.role / "action"
        action.mkdir(parents=True)
        (self.role / "pet_conf.json").write_text(
            json.dumps({"width":192,"height":208,"default":"idle",
                        "left":"left_walk","right":"right_walk"}),
            encoding="utf-8")
        (self.role / "act_conf.json").write_text(
            json.dumps({
                "default":{"images":"idle"},
                "left_walk":{"images":"left_walk"},
                "right_walk":{"images":"right_walk"},
                "happy":{"images":"idle"},
            }),encoding="utf-8")
        for prefix in ("idle", "left_walk", "right_walk"):
            for idx in range(6):
                frame = Image.new("RGBA",(192,208),(0,0,0,0))
                for x in range(20+idx,55+idx):
                    for y in range(55,145):
                        frame.putpixel((x,y),(255-idx,80+idx,135,255))
                frame.save(action / f"{prefix}_{idx}.png", "PNG")
        self.frame = action / "idle_0.png"

    def test_rust_hash_and_complete_role_report_match_python(self):
        with patch.dict(os.environ,{"DYBERPET_NATIVE_BACKEND":"python"}):
            source_hash = sha256_file(self.frame)
            baseline = inspect_character_role(self.role,"Guga")
        self.assertEqual(source_hash, hashlib.sha256(self.frame.read_bytes()).hexdigest())
        with patch.dict(os.environ,{"DYBERPET_NATIVE_BACKEND":"rust"}):
            if backend_status()["active"] != "rust":
                if os.environ.get("DYBERPET_REQUIRE_RUST") == "1":
                    self.fail("CI requires a real compiled Rust wheel")
                self.skipTest("Rust backend is optional on this interpreter")
            accelerated_hash = sha256_file(self.frame)
            accelerated = inspect_character_role(self.role,"Guga")
        self.assertEqual(source_hash,accelerated_hash)
        self.assertEqual(baseline,accelerated)
        self.assertEqual(baseline["frame_count_by_action"]["default"],6)
        self.assertEqual(baseline["image_size_mismatches"],[])
        self.assertEqual(baseline["invalid_images"],[])

    def test_rust_and_python_see_next_edit_without_stale_cache(self):
        with patch.dict(os.environ,{"DYBERPET_NATIVE_BACKEND":"rust"}):
            if backend_status()["active"] != "rust":
                self.skipTest("No optional Rust wheel")
        with patch.dict(os.environ,{"DYBERPET_NATIVE_BACKEND":"python"}):
            first = inspect_character_role(self.role,"Guga")
        with Image.new("RGBA",(100,208),(100,20,70,255)) as edited:
            edited.save(self.frame,"PNG")
        with patch.dict(os.environ,{"DYBERPET_NATIVE_BACKEND":"python"}):
            changed_py = inspect_character_role(self.role,"Guga")
        with patch.dict(os.environ,{"DYBERPET_NATIVE_BACKEND":"rust"}):
            changed_rs = inspect_character_role(self.role,"Guga")
        self.assertNotEqual(first,changed_py)
        self.assertEqual(changed_py,changed_rs)
        self.assertIn("idle_0.png",changed_rs["image_size_mismatches"])


if __name__ == "__main__":
    unittest.main()
