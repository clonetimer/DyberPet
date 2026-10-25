"""Compare real role-index reports using both installed backends.

Tests create their own *synthetic* tiny IHDR headers, never copyrighted art.
No persistent cache is allowed: editing a file must change the next audit.
"""
from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import json

from DyberPet.assistant.character_fidelity import (
    FidelityError, inspect_character_role,
)
from DyberPet.assistant.native_bridge import backend_status, native_batch_png_headers


def synthetic_png(path: Path, width=192, height=208):
    header = bytearray(33)
    header[:8] = b"\x89PNG\r\n\x1a\n"
    header[12:16] = b"IHDR"
    header[16:20] = width.to_bytes(4, "big")
    header[20:24] = height.to_bytes(4, "big")
    header[24] = 8
    header[25] = 6
    path.write_bytes(header)


class IndexedRoleParityTests(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.root = Path(holder.name) / "Guga"
        (self.root / "action").mkdir(parents=True)
        (self.root / "pet_conf.json").write_text(
            json.dumps({"width": 192, "height": 208}), encoding="utf-8")
        (self.root / "act_conf.json").write_text(json.dumps({
            "default": {"images": "idle"},
            "happy": {"images": "idle"},  # duplicate prefix uses local cache
            "left_walk": {"images": "left"},
            "right_walk": {"images": "right"},
            "speaking": {"images": "speech"},
            "bad/name": {"images": "../outside"},
        }), encoding="utf-8")
        for prefix in ("idle", "left", "right", "speech"):
            for index in range(6):
                synthetic_png(self.root / "action" / f"{prefix}_{index}.png")
        synthetic_png(self.root / "action" / "idle_2.png", 96, 208)
        (self.root / "action" / "left_5.png").write_bytes(b"invalid PNG")
        (self.root / "action" / "right_wrong.png").write_bytes(b"invalid PNG")
        (self.root / "action" / "speech_6.PNG").write_bytes(b"invalid PNG")

    def _audit(self, mode):
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": mode}):
            return inspect_character_role(self.root, "Guga")

    def test_python_report_counts_and_broken_frame(self):
        report = self._audit("python")
        self.assertEqual(report["frame_count_by_action"]["default"], 6)
        self.assertEqual(report["frame_count_by_action"]["happy"], 6)
        self.assertEqual(report["frame_count_by_action"]["right_walk"], 6)
        self.assertIn("idle_2.png", report["image_size_mismatches"])
        self.assertIn("left_5.png", report["invalid_images"])
        self.assertNotIn("right_wrong.png", report["invalid_images"])
        self.assertNotIn("speech_6.PNG", report["invalid_images"])
        self.assertEqual(report["authenticity_status"], "not_verified")

    def test_frame_cache_reused_only_within_one_report(self):
        with patch("DyberPet.assistant.character_fidelity.native_batch_png_headers",
                   wraps=native_batch_png_headers) as batch:
            self._audit("python")
            self.assertEqual(batch.call_count, 4)
            self._audit("python")
            self.assertEqual(batch.call_count, 8)
        synthetic_png(self.root / "action" / "idle_2.png")
        self.assertNotIn("idle_2.png",
                         self._audit("python")["image_size_mismatches"])

    def test_native_invalid_batch_result_is_rejected(self):
        with patch("DyberPet.assistant.character_fidelity.native_batch_png_headers",
                   return_value=[]):
            with self.assertRaisesRegex(FidelityError, "length mismatch"):
                inspect_character_role(self.root, "Guga")

    def test_optional_rust_is_bitwise_equivalent_to_python_report(self):
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "rust"}):
            available = backend_status()["active"] == "rust"
        if not available:
            if os.environ.get("DYBERPET_REQUIRE_RUST") == "1":
                self.fail("Required Rust module was not installed")
            self.skipTest("Rust module not installed")
        self.assertEqual(self._audit("python"), self._audit("rust"))

    def test_symlinked_frames_are_excluded_when_platform_supports_it(self):
        link = self.root / "action" / "right_7.png"
        try:
            link.symlink_to(self.root / "action" / "idle_0.png")
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable on this runner")
        for mode in ("python", "rust"):
            self.assertEqual(self._audit(mode)["frame_count_by_action"]["right_walk"], 6)


if __name__ == "__main__":
    unittest.main()
