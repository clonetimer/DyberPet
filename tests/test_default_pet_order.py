"""First-run character selection must not depend on Python hash seed."""
import tempfile
import unittest
from pathlib import Path

# The lightweight importer workflow deliberately has no Qt installed.
# The dedicated Windows/Linux desktop CI still runs these tests with PySide6.
try:
    from DyberPet.settings import get_petlist
except ModuleNotFoundError as exc:
    if exc.name != "PySide6":
        raise
    get_petlist = None


@unittest.skipIf(get_petlist is None, "PySide6 is not installed in importer-only CI")
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
            for name in ("zeta", "Bravo", "alpha", "sys"):
                (Path(folder) / name).mkdir()
            self.assertEqual(get_petlist(folder), ["alpha", "Bravo", "zeta"])


if __name__ == "__main__":
    unittest.main()
