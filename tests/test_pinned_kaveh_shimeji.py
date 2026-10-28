"""R19 offline acceptance: real Kaveh art remains opt-in, unbundled, unapproved."""
from __future__ import annotations
import ast
import tempfile
import unittest
from pathlib import Path

from tools.install_pinned_kaveh_shimeji import (
    ARCHIVE_SIZE, ARCHIVE_SHA256, SOURCE_KEY,
    verified_zip, install_pinned_kaveh_shimeji)
from tools.character_source_coverage import source_coverage


class KavehAlternativeTests(unittest.TestCase):
    def test_not_a_new_character_or_fake_approved_source(self):
        r = source_coverage()["summary"]
        self.assertEqual(r["characters_with_pinned_sources"], 68)
        self.assertEqual(r["characters_without_pinned_sources"], 55)
        self.assertEqual(r["pinned_source_options"], 91)

    def test_explicit_confirmation_and_fixed_identity_before_any_network(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "role"
            calls = []
            def fetch(url):
                calls.append(url)
                return b"any bytes"
            with self.assertRaisesRegex(ValueError, "consent"):
                install_pinned_kaveh_shimeji(SOURCE_KEY, root, downloader=fetch)
            with self.assertRaisesRegex(ValueError, "Only"):
                install_pinned_kaveh_shimeji("unknown", root, confirmed=True,
                                            downloader=fetch)
            self.assertEqual(calls, [])
            self.assertFalse(root.exists())

    def test_pinned_sha_and_exact_length_protect_destination(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "role"
            with self.assertRaisesRegex(ValueError, "byte length"):
                install_pinned_kaveh_shimeji(
                    SOURCE_KEY, root, confirmed=True,
                    downloader=lambda url: b"fake")
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                verified_zip(downloader=lambda url: b"x" * ARCHIVE_SIZE)
            self.assertFalse(root.exists())
            self.assertEqual(len(ARCHIVE_SHA256), 64)

    def test_gui_routes_actual_pinned_candidate_to_separate_native_role(self):
        p = Path(__file__).resolve().parents[1]
        source = (p / "DyberPet/DyberSettings/CharCardUI.py").read_text("utf-8")
        ast.parse(source)
        self.assertIn('"pinned_kaveh_shimeji", KAVEH_KEY)', source)
        self.assertIn('elif self.mode == "pinned_kaveh_shimeji":', source)
        self.assertIn("install_pinned_kaveh_shimeji(", source)
        self.assertIn("匍匐和坠落各只有一帧", source)
        self.assertIn('"pinned_kaveh_shimeji",', source)


if __name__ == "__main__":
    unittest.main()
