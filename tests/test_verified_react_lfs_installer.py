"""Verified React Git-LFS self-service install must never accept pointer art."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.install_verified_react_lfs import install_verified_react_lfs


class VerifiedReactInstallerTests(unittest.TestCase):
    def _fakes(self, role_root, *, tamper=False):
        payload = b"original pinned source module bytes; no execution"
        if tamper:
            payload += b"!"
        source = {
            "genshin_amber": {
                "profile": "genshin_amber",
                "verified_bytes": 48,
                "sha256": hashlib.sha256(b"original pinned source module bytes; no execution").hexdigest()
            },
        }
        def importer(module, root, *, profile, confirmed=False):
            self.assertTrue(confirmed)
            self.assertEqual(profile, "genshin_amber")
            self.assertEqual(module.read_bytes(), payload)
            directory = root / "SourceVerifiedAmber"
            directory.mkdir(parents=True, exist_ok=False)
            (directory / "PERSONAL_IMPORT.json").write_text(
                json.dumps({"selected_profile": profile}), encoding="utf-8")
            return directory
        return payload, source, importer

    def test_real_source_bytes_required_and_no_ts_execution(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            original = b"original pinned source module bytes; no execution"
            sha = hashlib.sha256(original).hexdigest()
            attestation = {"genshin_amber": {"profile": "genshin_amber",
                                            "verified_bytes": len(original),
                                            "sha256": sha}}
            def fetch(profile):
                self.assertEqual(profile, "genshin_amber")
                return original, "https://media.githubusercontent.com/media/test"
            def importer(module, dest, *, profile, confirmed):
                self.assertEqual(module.read_bytes(), original)
                self.assertTrue(confirmed)
                installed = dest / "SourceVerifiedAmber"
                installed.mkdir()
                (installed / "PERSONAL_IMPORT.json").write_text(
                    json.dumps({"selected_profile": profile}))
                return installed
            with patch("tools.install_verified_react_lfs.verified_lfs_sources",
                       return_value=attestation):
                result = install_verified_react_lfs(
                    "amber", root, confirmed=True, fetch=fetch, native_import=importer)
                self.assertEqual(result["profile"], "genshin_amber")
                self.assertTrue(result["full_lfs_sha256_verified"])
                self.assertFalse(result["human_likeness_verified"])

    def test_consent_and_only_known_verified_characters(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, "consent"):
                install_verified_react_lfs("amber", folder)
            with self.assertRaisesRegex(ValueError, "Only pinned"):
                install_verified_react_lfs("unverified_character", folder,
                                           confirmed=True)

    def test_tampered_source_rejected_before_import(self):
        with tempfile.TemporaryDirectory() as folder:
            real = b"authentic exact bytes"
            bad = real + b"malicious"
            record = {"genshin_fischl": {
                "profile": "genshin_fischl",
                "verified_bytes": len(real),
                "sha256": hashlib.sha256(real).hexdigest()}}
            def never_import(*args, **kwargs):
                self.fail("Corrupt bytes must never reach sprite import")
            with patch("tools.install_verified_react_lfs.verified_lfs_sources",
                       return_value=record):
                with self.assertRaisesRegex(ValueError, "SHA-256"):
                    install_verified_react_lfs(
                        "fischl", folder, confirmed=True,
                        fetch=lambda p: (bad, "https://raw.githubusercontent.com/x"),
                        native_import=never_import)

    def test_refuse_untrusted_download_host(self):
        with tempfile.TemporaryDirectory() as folder:
            payload = b"original"
            record = {"genshin_amber": {"profile": "genshin_amber",
                                        "verified_bytes": len(payload),
                                        "sha256": hashlib.sha256(payload).hexdigest()}}
            with patch("tools.install_verified_react_lfs.verified_lfs_sources",
                       return_value=record):
                with self.assertRaisesRegex(ValueError, "URL not permitted"):
                    install_verified_react_lfs(
                        "amber", folder, confirmed=True,
                        fetch=lambda p: (payload, "https://evil.example/asset"))


if __name__ == "__main__":
    unittest.main()
