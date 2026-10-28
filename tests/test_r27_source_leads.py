"""Neuvillette/Wriothesley must have exact upstream LFS identities, not art substitutions."""
from __future__ import annotations
import unittest

from tools.react_shimeji_source_leads import CANDIDATES, REVISION, REPOSITORY
from tools.chibi_profiles import CHIBI_PROFILES

EXPECTED = {
    "genshin_neuvillette": ("neuvillette-10d1e7",
        "0baef99c84ba33cbc28b6f607fcc0df3d04a6494f45a34be6db1f1394a7fa59e",
        1148440),
    "genshin_wriothesley": ("wriothesley-01fe24",
        "10737b31db7fb5958950754cecb9ad7d60eba5cfc95c49ec066a52a41f5d0cb8",
        993331),
}


class OriginalReactLeads(unittest.TestCase):
    def test_lfs_pointer_identity_maps_to_exact_roster_profiles(self):
        self.assertEqual(REPOSITORY, "CarbonNeuron/react-shimeji")
        self.assertEqual(REVISION, "35b507062be71e8b9dbea6d20b77a9901dfe9114")
        for profile, identity in EXPECTED.items():
            self.assertIn(profile, CHIBI_PROFILES)
            self.assertEqual(CANDIDATES[profile][:3], identity)
            self.assertEqual(len(CANDIDATES[profile][3]), 40)
            self.assertEqual(len(CANDIDATES[profile][4]), 40)
        self.assertNotEqual(EXPECTED["genshin_neuvillette"][1],
                            EXPECTED["genshin_wriothesley"][1])


if __name__ == "__main__":
    unittest.main()
