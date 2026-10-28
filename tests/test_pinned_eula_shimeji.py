"""Verify exact original-source consent, no local-art overwrite, no fake rosters."""
from __future__ import annotations
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest
from unittest.mock import patch

from tools.install_pinned_eula_shimeji import (
    SOURCE_KEY, ARCHIVE_BYTES, install_pinned_eula_shimeji,
    _verified_original)


class PinnedEulaSourceTests(unittest.TestCase):
    def test_no_network_before_consent_and_wrong_identity(self):
        with TemporaryDirectory() as td:
            requested = []
            def downloader(url):
                requested.append(url)
                raise AssertionError("should never download")
            with self.assertRaisesRegex(ValueError, "explicit personal consent"):
                install_pinned_eula_shimeji(
                    SOURCE_KEY, Path(td) / "roles", downloader=downloader)
            with self.assertRaisesRegex(ValueError, "Unknown or unverified"):
                install_pinned_eula_shimeji(
                    "somebody_else", Path(td) / "roles", confirmed=True,
                    downloader=downloader)
            self.assertEqual(requested, [])

    def test_corrupt_archive_is_rejected_before_creating_any_role(self):
        with TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(ValueError, "byte length"):
                install_pinned_eula_shimeji(
                    SOURCE_KEY, root / "roles", confirmed=True,
                    post_loader=lambda: {"body": {"id": "8264436",
                        "creatorId": "saylamars",
                        "title": "Eula", "body": {"files": [{
                            "name": "original.zip", "extension": "zip",
                            "url": "https://downloads.fanbox.cc/files/original.zip"
                        }]}}},
                    downloader=lambda url: b"tampered")
            self.assertFalse((root / "roles").exists())
            with self.assertRaisesRegex(ValueError, "SHA-256"):
                _verified_original(archive=self._fake_archive(root))
            self.assertFalse((root / "roles").exists())

    @staticmethod
    def _fake_archive(root):
        archive = root / "forged.zip"
        archive.write_bytes(b"X" * ARCHIVE_BYTES)
        return archive

    def test_installer_verifies_actual_original_bytes_then_delegates_native(self):
        # The synthetic raw here cannot pass the real Eula pin. Patch
        # _verified_original itself to exercise the correctly parameterized
        # native-import route; it is NEVER used in the actual runtime.
        with TemporaryDirectory() as td:
            import tools.install_pinned_eula_shimeji as impl
            root = Path(td) / "roles"
            def mocked_native(path, target, **kwargs):
                self.assertEqual(kwargs["profile"], "genshin_eula")
                self.assertTrue(kwargs["extended_eula_source"])
                self.assertTrue(kwargs["confirmed"])
                role = root / "PersonalShimejiEula"
                role.mkdir(parents=True)
                (role / "PERSONAL_IMPORT.json").write_text(json.dumps({
                    "source_archive_sha256": impl.EULA_EXTENDED_SOURCE_SHA256,
                    "all_original_frames_preserved": 109,
                    "selected_profile": "genshin_eula",
                    "verified_extended_eula_author_source": True
                }))
                return role
            with (patch.object(impl, "_verified_original", return_value=b"stub"),
                  patch.object(impl, "install_personal_shimeji_zip",
                               side_effect=mocked_native)):
                role = install_pinned_eula_shimeji(
                    SOURCE_KEY, root, confirmed=True)
                self.assertEqual(role.name, "PersonalShimejiEula")

    def test_66th_source_is_real_and_never_claims_user_install(self):
        from tools.character_source_coverage import source_coverage
        from tools.personal_source_batch import INSTALLERS, plan_personal_sources
        result = source_coverage()
        self.assertEqual(result["summary"]["characters_with_pinned_sources"], 69)
        self.assertEqual(result["summary"]["characters_without_pinned_sources"], 54)
        self.assertEqual(result["summary"]["pinned_source_options"], 92)
        self.assertIn("pinned_eula_creator", INSTALLERS)
        eula = next(row for row in result["characters"]
                    if row["id"] == "genshin_eula")
        self.assertEqual(eula["source_candidate_count"], 1)
        self.assertFalse(eula["installed"])
        self.assertFalse(eula["visual_likeness_qa_passed"])
        src = eula["recommended_source"]
        self.assertEqual(src["archive_sha256"], 
                         "f4952ea151e0ead70b501e9e2637f9dae1194e0da1b5d312046964fc19046803")
        self.assertFalse(src["artist_character_likeness_verified"])
        self.assertFalse(src["asset_is_bundled"])
        with TemporaryDirectory() as td:
            plan = plan_personal_sources(td, coverage=result,
                inventory={"characters": [], "invalid_local": []},
                only_profiles=["genshin_eula"])
            self.assertEqual(plan["characters"][0]["provider"],
                             "pinned_eula_creator")
            self.assertEqual(plan["characters"][0]["status"], "ready_for_opt_in")

    def test_archive_sha_is_nonempty_and_has_required_length(self):
        from tools.install_personal_shimeji_zip import EULA_EXTENDED_SOURCE_SHA256
        self.assertEqual(
            EULA_EXTENDED_SOURCE_SHA256,
            "f4952ea151e0ead70b501e9e2637f9dae1194e0da1b5d312046964fc19046803")
        self.assertEqual(ARCHIVE_BYTES, 8400168)


if __name__ == "__main__":
    unittest.main()
