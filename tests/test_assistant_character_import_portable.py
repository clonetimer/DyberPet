"""Desktop installer acceptance: original local PNG -> playable role conversion."""
import unittest

from DyberPet.assistant.character_import_smoke import verify_portable_character_importer


class PortableCharacterImporterTests(unittest.TestCase):
    def test_disposable_synthetic_role_uses_actual_importer(self):
        report = verify_portable_character_importer()
        self.assertTrue(report["ok"])
        self.assertGreaterEqual(report["profile_count"], 1)
        self.assertGreaterEqual(report["synthetic_actions"], 1)
        self.assertGreaterEqual(report["synthetic_frames"], 1)
        self.assertFalse(report["modified_user_roles"])
        self.assertFalse(report["third_party_art_included"])


if __name__ == "__main__":
    unittest.main()
