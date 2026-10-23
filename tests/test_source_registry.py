"""Ensure source channel discovery is traceable and never confuses license with download."""
import copy
import datetime as dt
import unittest

from tools.audit_character_sources import check_catalog
from tools.character_pipeline import registry


class SourceCatalogAuditTest(unittest.TestCase):
    def test_repo_catalog_is_valid(self):
        report = check_catalog(today=dt.date(2026, 10, 23))
        self.assertEqual(report["errors"], [])
        self.assertGreaterEqual(report["channels"], 4)
        self.assertTrue(report["no_remote_requests"])

    def test_stale_catalog_surfaces_review_warning(self):
        report = check_catalog(today=dt.date(2027, 3, 1), max_age_days=90)
        self.assertTrue(any("last manually checked" in w for w in report["warnings"]))

    def test_duplicate_or_invalid_sources_fail(self):
        catalog = copy.deepcopy(registry())
        catalog["channels"].append(dict(catalog["channels"][0]))
        catalog["channels"][1]["url"] = "http://example.com/bad"
        report = check_catalog(catalog, today=dt.date(2026, 10, 23))
        self.assertTrue(any("Duplicate" in err for err in report["errors"]))
        self.assertTrue(any("HTTPS" in err for err in report["errors"]))

    def test_individual_permissions_are_not_inferred(self):
        report = registry()
        self.assertTrue(all(channel["requires_manual_review"]
                            for channel in report["channels"]))
        self.assertTrue(all(candidate["rights_status"] == "unknown"
                            for candidate in report["candidates"]))


if __name__ == "__main__":
    unittest.main()
