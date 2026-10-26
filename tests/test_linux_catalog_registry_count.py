"""The Linux X11 catalog count must follow verified source growth, not history."""
from __future__ import annotations

import unittest

from tools.character_source_coverage import source_coverage
from tools.linux_gui_smoke import assert_source_catalog_matches_registry


class LinuxCatalogRegistryCountTests(unittest.TestCase):
    def test_current_registry_and_future_source_expansion(self):
        report = source_coverage()
        current = report["summary"]["characters_with_pinned_sources"]
        self.assertEqual(current, 61)
        self.assertEqual(report["summary"]["characters_without_pinned_sources"],
                         123 - current)
        for count in (current, current + 1, 123):
            # This represents the actual Qt list count and the associated
            # source ledger after new original characters are verified.
            self.assertIsNone(
                assert_source_catalog_matches_registry(count, count, "source"))
            with self.assertRaisesRegex(RuntimeError, "disagrees"):
                assert_source_catalog_matches_registry(count - 1, count, "source")
            with self.assertRaisesRegex(RuntimeError, "filter"):
                assert_source_catalog_matches_registry(count, count, "all")


if __name__ == "__main__":
    unittest.main()
