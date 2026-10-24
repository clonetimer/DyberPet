"""First-run character selection must not depend on Python hash seed."""
import tempfile
import unittest
from pathlib import Path

from DyberPet.settings import get_petlist


class DeterministicPetTests(unittest.TestCase):
    def test_original_kitty_is_first_despite_directory_order(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("DemoG_zhongli", "ChrisKitty", "sys", "DemoG_lisa", "Kitty"):
                (Path(folder) / name).mkdir()
            (Path(folder) / "READ_ME.txt").write_text("not a pet")
            expected = ["Kitty", "ChrisKitty", "DemoG_lisa", "DemoG_zhongli"]
            self.assertEqual(get_petlist(folder), expected)
            self.assertEqual(get_petlist(folder), expected)

    def test_stable_fallback_when_kitty_is_not_installed(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("zeta", "Alpha", "alpha", "sys"):
                (Path(folder) / name).mkdir()
            self.assertEqual(get_petlist(folder), ["Alpha", "alpha", "zeta"])


if __name__ == "__main__":
    unittest.main()
