"""Rust/Python behavior parity, rollback and fail-closed verification.

Synthetic files only. Installing the optional Rust wheel activates additional
native equivalence checks; DYBERPET_REQUIRE_RUST=1 makes the CI require it.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.character_fidelity import FidelityError, png_metadata
from DyberPet.assistant.native_bridge import (
    backend_status, native_png_metadata, sha256_file,
)
from DyberPet.assistant.guga_audio import _hash_file
from DyberPet.assistant.character_audio import digest

NATIVE_AVAILABLE = importlib.util.find_spec("dyberpet_native") is not None


def image(path: Path, width=192, height=208, kind=6) -> None:
    """Synthetic IHDR content matching the original audit contract."""
    head = bytearray(33)
    head[:8] = b"\x89PNG\r\n\x1a\n"
    head[12:16] = b"IHDR"
    head[16:20] = width.to_bytes(4, "big")
    head[20:24] = height.to_bytes(4, "big")
    head[24] = 8
    head[25] = kind
    path.write_bytes(head)


class RustBridgeTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.frame = self.root / "原创测试_001.png"
        self.sample = self.root / "原创测试_001.wav"
        image(self.frame)
        self.sample.write_bytes(bytes(range(256)) * 100)

    def test_default_is_unmodified_python(self):
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "python"}):
            self.assertEqual(backend_status()["active"], "python")
            self.assertIsNone(native_png_metadata(self.frame))
            self.assertEqual(png_metadata(self.frame)["width"], 192)
            self.assertEqual(sha256_file(self.sample),
                             hashlib.sha256(self.sample.read_bytes()).hexdigest())

    def test_file_hashing_matches_both_existing_audio_routes(self):
        expected = hashlib.sha256(self.sample.read_bytes()).hexdigest()
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "python"}):
            self.assertEqual(_hash_file(self.sample), expected)
            self.assertEqual(digest(self.sample), expected)

    def test_rust_requested_without_wheel_falls_back(self):
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "rust"}), patch(
                "DyberPet.assistant.native_bridge.importlib.import_module",
                side_effect=ImportError("synthetic missing native wheel")):
            self.assertTrue(backend_status()["fallback"])
            self.assertEqual(backend_status()["active"], "python")
            self.assertEqual(png_metadata(self.frame)["height"], 208)
            self.assertEqual(sha256_file(self.sample),
                             hashlib.sha256(self.sample.read_bytes()).hexdigest())

    def test_python_stays_strict_for_invalid_image(self):
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "python"}):
            for blob in (b"invalid", bytes(33)):
                self.frame.write_bytes(blob)
                with self.assertRaises(FidelityError):
                    png_metadata(self.frame)

    def test_native_errors_are_not_silently_ignored(self):
        class BrokenNative:
            def png_metadata(self, path):
                raise ValueError("synthetic Rust validation rejection")

            def sha256_file(self, path):
                raise OSError("synthetic Rust I/O rejection")

            def engine_version(self):
                return "test"

        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "rust"}), patch(
                "DyberPet.assistant.native_bridge.importlib.import_module",
                return_value=BrokenNative()):
            with self.assertRaisesRegex(FidelityError, "synthetic Rust"):
                png_metadata(self.frame)
            with self.assertRaisesRegex(OSError, "synthetic Rust"):
                sha256_file(self.sample)

    def test_native_required_gate(self):
        if os.environ.get("DYBERPET_REQUIRE_RUST") == "1":
            self.assertTrue(NATIVE_AVAILABLE, "CI must install the Rust wheel")

    @unittest.skipUnless(NATIVE_AVAILABLE, "Opt-in Rust wheel not installed")
    def test_installed_rust_exact_png_and_sha256_parity(self):
        import dyberpet_native
        self.assertEqual(dyberpet_native.engine_version(), "0.1.0")
        self.assertEqual(len(dyberpet_native.sha256_file(str(self.sample))), 64)
        for kind in (0, 2, 4, 6):
            image(self.frame, kind=kind)
            with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "python"}):
                reference = png_metadata(self.frame)
            with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "rust"}):
                result = png_metadata(self.frame)
                self.assertEqual(backend_status()["active"], "rust")
            self.assertEqual(result, reference)
        expected = hashlib.sha256(self.sample.read_bytes()).hexdigest()
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "rust"}):
            self.assertEqual(_hash_file(self.sample), expected)
            self.assertEqual(digest(self.sample), expected)

    @unittest.skipUnless(NATIVE_AVAILABLE, "Opt-in Rust wheel not installed")
    def test_installed_rust_preserves_invalid_image_rejection(self):
        for invalid in (b"no png", bytes(33)):
            self.frame.write_bytes(invalid)
            with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "rust"}):
                with self.assertRaises(FidelityError):
                    png_metadata(self.frame)
        image(self.frame, width=8193)
        with patch.dict(os.environ, {"DYBERPET_NATIVE_BACKEND": "rust"}):
            with self.assertRaises(FidelityError):
                png_metadata(self.frame)


if __name__ == "__main__":
    unittest.main()
