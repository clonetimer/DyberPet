"""R30: never conceal real source failures or replay untrusted report URLs."""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from urllib.error import HTTPError, URLError
import unittest

from tools.personal_source_batch import (
    classify_source_failure, install_personal_plan, plan_personal_sources,
    read_failed_profiles_from_report,
)


def toy_sources():
    return {"characters": [
        {"id": "genshin_alpha", "name": "A", "source_candidates": [
            {"provider": "codexpetdb_zip", "source_key": "a", "url": "https://example.invalid/a"},
            {"provider": "native", "source_key": "afallback", "url": "https://example.invalid/fallback"}]},
        {"id": "genshin_beta", "name": "B", "source_candidates": [
            {"provider": "shimeji", "source_key": "b", "url": "https://example.invalid/b"}]},
        {"id": "genshin_gamma", "name": "C", "source_candidates": []},
    ]}


class R30FailuresAndSafeRetries(unittest.TestCase):
    def test_classifies_http_network_integrity_and_existing(self):
        self.assertEqual(classify_source_failure(
            HTTPError("https://example.invalid/a", 404, "missing", {}, None)), "source_http_404")
        self.assertEqual(classify_source_failure(TimeoutError()), "network_timeout")
        self.assertEqual(classify_source_failure(URLError("blocked")), "source_network")
        self.assertEqual(classify_source_failure(FileExistsError("exists")), "source_folder_exists")
        self.assertEqual(classify_source_failure(ValueError("bad SHA")), "source_integrity_or_format")

    def test_both_sources_fail_show_reason_per_source_and_unapproved_status(self):
        with tempfile.TemporaryDirectory() as td:
            plan = plan_personal_sources(td, coverage=toy_sources(),
                inventory={"characters": [], "invalid_local": []})
            observed = []
            def source(*args):
                if args[0] == "native":
                    raise ValueError("incorrect SHA")
                raise HTTPError("https://example.invalid/", 404, "not found", {}, None)
            result = install_personal_plan(plan, td, confirmed=True, dispatch=source,
                    progress=observed.append, inventory_reader=lambda _: {
                        "characters": [], "invalid_local": []})
            self.assertEqual(result["failed"], 2)
            self.assertEqual(result["failed_profiles"],
                             ["genshin_alpha", "genshin_beta"])
            self.assertEqual(result["failure_class_counts"],
                             {"source_http_404": 2, "source_integrity_or_format": 1})
            events = [e for e in observed if e["stage"] == "source_failed"]
            self.assertEqual(len(events), 3)
            self.assertEqual(events[0]["failure_class"], "source_http_404")
            self.assertTrue(events[0]["has_next_pinned_source"])
            self.assertFalse(events[-1]["has_next_pinned_source"])
            self.assertIn("404", events[0]["reason"])

    def test_untrusted_retry_report_source_urls_not_used_and_existing_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            old = Path(tmp) / "old.json"
            old.write_text(json.dumps({
                "installation": {"scope": "local_personal_install_only",
                    "results": [
                        {"profile": "genshin_alpha", "status": "failed",
                         "source_attempts": [{"url": "https://evil.invalid"}]},
                        {"profile": "genshin_beta", "status": "installed_unreviewed"},
                    ]}}))
            selected = read_failed_profiles_from_report(old)
            self.assertEqual(selected, ["genshin_alpha"])
            self.assertNotIn("https://evil.invalid", str(selected))
            plan = plan_personal_sources(
                Path(tmp)/"role", only_profiles=selected,
                coverage=toy_sources(),
                inventory={"characters": [{"profile":"genshin_alpha",
                              "installed_folders":[{"folder":"SourceOriginal", "is_original_demo":False}]}],
                           "invalid_local":[]})
            self.assertEqual(plan["characters"][0]["status"], "already_installed")
            calls = []
            result = install_personal_plan(plan, Path(tmp)/"role", confirmed=True,
                 dispatch=lambda *_: calls.append("wrong"),
                 inventory_reader=lambda _: {"characters": [],"invalid_local":[]})
            self.assertEqual(result["attempted"], 0)
            self.assertEqual(calls, [])

    def test_refuse_corrupt_or_unbounded_report_and_no_failed_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"bad.json"
            file.write_text("not JSON")
            with self.assertRaises(ValueError):
                read_failed_profiles_from_report(file)
            file.write_text(json.dumps({"installation": {
                "scope":"local_personal_install_only",
                "results":[{"profile":"genshin_a", "status":"installed_unreviewed"}]}}))
            self.assertEqual(read_failed_profiles_from_report(file), [])
            file.write_text("x"*(2*1024*1024+1))
            with self.assertRaisesRegex(ValueError,"bounded"):
                read_failed_profiles_from_report(file)


if __name__ == "__main__":
    unittest.main()
