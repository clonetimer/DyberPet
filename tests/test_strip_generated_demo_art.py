"""No real or imported role is ever stripped from a personal package."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.strip_generated_demo_art import remove_generated_art


class CleanPersonalBuildTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name) / "res" / "role"
        self.root.mkdir(parents=True)
        self.real = self.root / "SourceGenshinNahida"
        self.real.mkdir()
        (self.real / "PERSONAL_IMPORT.json").write_text(
            '{"display_name":"纳西妲","source_kind":"artist_original_animation"}')

    def _demo(self, folder, mascot=False):
        path = self.root / folder
        path.mkdir()
        marker = "BUILTIN_MASCOT_DEMO.json" if mascot else "BUILTIN_CHIBI_DEMO.json"
        record = ({"generator":"DyberPet-first-party-mascot-chibi-v1",
                   "external_artist_sprite_included":False,
                   "original_geometry":True} if mascot else {
                       "generator":"DyberPet-first-party-abstract-chibi-v1",
                       "original_illustration":True,
                       "official_character_art":False})
        (path / marker).write_text(json.dumps(record))
        (path / "test.png").write_bytes(b"demo")
        return path

    def test_exactly_known_generated_demo_only(self):
        gen = self._demo("DemoG_lisa")
        mascot = self._demo("DemoMascotDoro", mascot=True)
        result = remove_generated_art(self.root, expected=2)
        self.assertEqual(result["removed_low_fidelity_demos"], 2)
        self.assertFalse(gen.exists())
        self.assertFalse(mascot.exists())
        self.assertTrue(self.real.is_dir())
        self.assertEqual(remove_generated_art(self.root, verify_only=True),
                         {"remaining_low_fidelity_demos":0})

    def test_missing_expected_demo_count_refuses_mutation(self):
        gen = self._demo("DemoG_lisa")
        with self.assertRaises(ValueError):
            remove_generated_art(self.root, expected=125)
        self.assertTrue(gen.exists())
        self.assertTrue(self.real.exists())

    def test_forged_artist_receipt_cannot_remove_other_role(self):
        path = self.root / "CreatorOriginal"
        path.mkdir()
        (path / "BUILTIN_CHIBI_DEMO.json").write_text(json.dumps({
            "generator":"DyberPet-first-party-abstract-chibi-v1",
            "official_character_art":False,
            "original_illustration":True}))
        with self.assertRaises(ValueError):
            remove_generated_art(self.root, expected=1)
        self.assertTrue(path.is_dir())
        self.assertTrue(self.real.exists())

    def test_verification_detects_leftover(self):
        self._demo("DemoG_lisa")
        with self.assertRaises(ValueError):
            remove_generated_art(self.root, verify_only=True)


if __name__ == "__main__":
    unittest.main()
