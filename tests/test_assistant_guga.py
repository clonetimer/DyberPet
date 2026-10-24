"""Regression tests for Guga visual/animation readiness and locally selected WAV.

No third-party frames or audio are embedded. Fixtures are generated from
scratch and make no authenticity claim.
"""
import json
import math
import struct
import tempfile
import unittest
import wave
import zlib
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.character_fidelity import (
    FidelityError, inspect_guga_role, inspect_wav, png_metadata
)
from DyberPet.assistant.guga_audio import (
    load_local_clip, record_local_clip, play_local_clip
)


def png(path, w=32, h=48):
    # Real valid RGBA PNG, containing only a fully opaque synthetic pixel fill.
    raw = b"".join(b"\x00" + b"\x12\x34\x56\xff" * w for _ in range(h))
    def chunk(tag, data):
        return (struct.pack(">I", len(data)) + tag + data +
                struct.pack(">I", zlib.crc32(tag + data) & 0xffffffff))
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n" +
        chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)) +
        chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    )


def audio(path, *, rate=16000, width=2, frames=3200):
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(width)
        f.setframerate(rate)
        f.writeframes(b"\x00" * width * frames)


class CharacterFidelityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.wav = self.root / "original_synthetic.wav"
        audio(self.wav)
        self.role = self.root / "Guga"
        (self.role / "action").mkdir(parents=True)
        (self.role / "pet_conf.json").write_text(
            json.dumps({"width": 32, "height": 48}))
        (self.role / "act_conf.json").write_text(
            json.dumps({
                "default": {"images": "stand"},
                "left_walk": {"images": "leftwalk"},
                "right_walk": {"images": "rightwalk"},
                "sleep": {"images": "sleep"},
            }))
        for name in ("stand", "leftwalk", "rightwalk", "sleep"):
            png(self.role / "action" / (name + "_0.png"))

    def test_fidelity_audit_never_claims_network_match(self):
        result = inspect_guga_role(self.role, self.wav)
        self.assertEqual(result["authenticity_status"], "not_verified")
        self.assertTrue(result["action_coverage"]["idle"]["available"])
        self.assertTrue(result["action_coverage"]["left_walk"]["available"])
        self.assertTrue(result["action_coverage"]["right_walk"]["available"])
        self.assertFalse(result["action_coverage"]["speak"]["available"])
        self.assertIn("No dedicated speaking/mouth animation",
                      " ".join(result["issues"]))
        self.assertFalse(result["image_size_mismatches"])
        self.assertEqual(result["sample_audio"]["encoding"], "PCM16")

    def test_missing_role_rejected(self):
        with self.assertRaises(FidelityError):
            inspect_guga_role(self.root / "unknown")

    def test_missing_frame_and_size_mismatch(self):
        png(self.role / "action" / "stand_0.png", 16, 16)
        result = inspect_guga_role(self.role)
        self.assertIn("stand_0.png", result["image_size_mismatches"])
        (self.role / "action" / "rightwalk_0.png").unlink()
        result = inspect_guga_role(self.role)
        self.assertFalse(result["action_coverage"]["right_walk"]["available"])

    def test_png_metadata_and_bad_file(self):
        self.assertTrue(
            png_metadata(self.role / "action" / "stand_0.png")["rgba_compatible"])
        sample = self.role / "action" / "broken_0.png"
        sample.write_bytes(b"not an image")
        self.assertRaises(FidelityError, png_metadata, sample)

    def test_wav_check_rejects_bad_format(self):
        self.assertEqual(inspect_wav(self.wav)["seconds"], 0.2)
        wrong = self.root / "bad.wav"
        audio(wrong, width=1)
        with self.assertRaisesRegex(FidelityError, "PCM16"):
            inspect_wav(wrong)

    def test_credentialed_manifest_only_records_local_attestation(self):
        manifest = self.root / "local_guga.json"
        source = "https://www.bilibili.com/video/example/"
        with self.assertRaisesRegex(FidelityError, "explicitly"):
            record_local_clip(self.wav, "artist", source,
                              acknowledged_local_rights=False, destination=manifest)
        with self.assertRaisesRegex(FidelityError, "creator"):
            record_local_clip(self.wav, "", source,
                              acknowledged_local_rights=True, destination=manifest)
        data = record_local_clip(
            self.wav, "synthetic fixture author", source,
            acknowledged_local_rights=True, destination=manifest
        )
        self.assertFalse(data["distribution_allowed"])
        self.assertFalse(data["voice_identity_verified"])
        loaded = load_local_clip(manifest)
        self.assertEqual(loaded["sha256"], data["sha256"])
        self.assertNotIn("audio", manifest.read_text())

    def test_wav_tampering_blocks_playback(self):
        manifest = self.root / "registered.json"
        record_local_clip(
            self.wav, "fixture", "https://example.org/clip",
            acknowledged_local_rights=True, destination=manifest)
        audio(self.wav, frames=4800)
        with self.assertRaisesRegex(FidelityError, "changed"):
            load_local_clip(manifest)
        with self.assertRaisesRegex(FidelityError, "changed"):
            play_local_clip(manifest)

    def test_corrupt_manifest_fails_closed(self):
        manifest = self.root / "registered.json"
        manifest.write_text("not-json")
        with self.assertRaises(FidelityError):
            load_local_clip(manifest)

    def test_no_clip_registered(self):
        with self.assertRaisesRegex(FidelityError, "No locally"):
            play_local_clip(self.root / "missing.json")


if __name__ == "__main__":
    unittest.main()
