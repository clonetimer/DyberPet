"""Versioned, full 7.1 Genshin *template* inventory regression checks.

The tests do not assert that source art, permissions, or real playable roles
exist for any listed character.
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from tools.chibi_profiles import CHIBI_PROFILES
from tools.genshin_complete_roster import (
    RAW_SUPPLEMENTAL, SNAPSHOT_DATE, SNAPSHOT_SOURCES, SNAPSHOT_VERSION)
from tools.genshin_roster import GENSHIN_ROSTER
from tools.genshin_batch import catalogue, seed_missing, status
from tools.character_pipeline import registry
from tools.personal_role_import import personal_install


class FullGenshinRosterTests(unittest.TestCase):
    def test_all_7_1_templates_including_travelers_and_old_companions(self):
        self.assertEqual(SNAPSHOT_VERSION, "7.1")
        self.assertEqual(SNAPSHOT_DATE, "2026-10-24")
        self.assertEqual(len(SNAPSHOT_SOURCES), 2)
        lines = RAW_SUPPLEMENTAL.splitlines()
        self.assertEqual(len(lines), 92)
        self.assertEqual(len(GENSHIN_ROSTER), 118)
        self.assertEqual(len(set(GENSHIN_ROSTER)), 118)
        current = {"genshin_" + key for key in GENSHIN_ROSTER}
        originals = {"genshin_paimon", "genshin_nahida",
                     "genshin_klee", "genshin_furina"}
        self.assertEqual(len(current | originals), 122)
        self.assertTrue(current.isdisjoint(originals))
        self.assertTrue(current | originals <= set(CHIBI_PROFILES))
        expected = ("amber", "zhongli", "raiden_shogun", "nahida",
                    "neuvillette", "mavuika", "columbina", "vodyanitsa",
                    "vesna", "odette", "traveler_aether", "traveler_lumine")
        for key in expected:
            with self.subTest(key=key):
                self.assertIn("genshin_" + key, CHIBI_PROFILES)
        for not_yet_playable in ("mitya", "valeriy", "tsaritsa", "noy"):
            self.assertNotIn("genshin_" + not_yet_playable, CHIBI_PROFILES)

    def test_snapshot_candidates_are_not_pretend_sprite_assets(self):
        catalog = catalogue()
        self.assertEqual(len(catalog), 118)
        for key, person in GENSHIN_ROSTER.items():
            with self.subTest(key=key):
                candidate = catalog["genshin_" + key]
                self.assertEqual(candidate["id"], "genshin_" + key + "_main")
                self.assertEqual(candidate["rights_status"], "unknown")
                self.assertFalse(person["original_art_included"])
                self.assertFalse(person["original_voice_included"])
                self.assertFalse(person["publishable"])
                self.assertGreaterEqual(len(person["visual_checks"]), 3)
                self.assertGreaterEqual(len(person["motion_checks"]), 3)
        for key in ("aether", "lumine"):
            self.assertIn("genshin_traveler_" + key, CHIBI_PROFILES)
        self.assertEqual(registry()["roster_snapshot"]["version"], "7.1")

    def test_personal_import_uses_new_template_without_rights_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "my-art"
            source.mkdir()
            for idx in range(2):
                Image.new("RGBA", (72, 96), (100 + idx * 15, 115, 200, 255)).save(
                    source / ("idle_" + str(idx) + ".png"))
            output = personal_install(
                source, root / "roles",
                profile="genshin_vodyanitsa", confirm_local_only=True)
            receipt = json.loads((output / "PERSONAL_IMPORT.json").read_text("utf-8"))
            self.assertEqual(receipt["selected_profile"], "genshin_vodyanitsa")
            self.assertFalse(receipt["source_rights_verified"])
            self.assertFalse(receipt["visual_identity_verified"])

    def test_full_roster_seed_missing_is_repeatable_and_read_only_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "intake"
            first = seed_missing(root, ("amber", "vodyanitsa", "traveler_aether"))
            self.assertEqual(first["created"], 3)
            second = seed_missing(root, ("amber", "vodyanitsa", "traveler_aether"))
            self.assertEqual(second["created"], 0)
            self.assertEqual(second["preserved"], 3)
            board = status(root, ("amber", "vodyanitsa", "traveler_aether"))
            self.assertEqual(board["counts"]["seeded"], 3)
            self.assertEqual(board["counts"]["qa_verified"], 0)


if __name__ == "__main__":
    unittest.main()
