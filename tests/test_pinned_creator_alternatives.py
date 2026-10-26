"""Isolated source alternative probes don't approve shapes or touch installed pets."""
from __future__ import annotations

import unittest

from tools.probe_pinned_creator_alternatives import probe_pinned_alternatives


def sources():
    return {"characters": [
        {"id": "genshin_ayaka", "source_candidates": [
            {"provider": "codex", "source_key": "first"},
            {"provider": "shimeji", "source_key": "second"},
            {"provider": "nano_shimeji", "source_key": "third"},
        ]},
        {"id": "genshin_venti", "source_candidates": [
            {"provider": "shimeji", "source_key": "first"},
            {"provider": "nano_shimeji", "source_key": "second"},
        ]},
    ]}


def faux_scan(root):
    return {"characters": [{"profile": "genshin_ayaka",
                             "installed_folders": [{
                                 "folder": "SourceReal", "is_original_demo": False,
                             }]}]}


def faux_inspect(root, folder):
    return {
        "silhouette_width_height_ratio": 0.74,
        "risk_indicators": [],
        "weak_movement_action_evidence": [],
    }


class PinnedAlternativeTests(unittest.TestCase):
    def test_explicit_consent_and_only_known_risk_profiles(self):
        with self.assertRaisesRegex(ValueError, "opt-in"):
            probe_pinned_alternatives(profiles=["genshin_ayaka"])
        with self.assertRaisesRegex(ValueError, "Only five"):
            probe_pinned_alternatives(confirmed=True, profiles=["genshin_amber"],
                                      coverage=sources())

    def test_only_second_and_third_sources_in_isolated_empty_roots(self):
        calls = []
        def dispatch(provider, key, root):
            calls.append((provider, key, root.exists(), not list(root.iterdir())))
        r = probe_pinned_alternatives(
            confirmed=True, profiles=["genshin_ayaka"],
            coverage=sources(), dispatch=dispatch,
            scan=faux_scan, inspect=faux_inspect)
        self.assertEqual([(x[0], x[1]) for x in calls],
                         [("shimeji", "second"), ("nano_shimeji", "third")])
        self.assertTrue(all(x[2] and x[3] for x in calls))
        self.assertEqual(r["summary"]["structurally_installed_alternatives"], 2)
        self.assertEqual(r["summary"]["human_approved_q_alternatives"], 0)
        self.assertFalse(r["summary"]["art_uploaded"])

    def test_mismatched_role_never_claimed_as_valid_alternative(self):
        def mismatch(root):
            return {"characters": [{
                "profile": "genshin_furina",
                "installed_folders": [{"folder": "Fake", "is_original_demo": False}],
            }]}
        r = probe_pinned_alternatives(
            confirmed=True, profiles=["genshin_ayaka"],
            coverage=sources(), dispatch=lambda *args: None,
            scan=mismatch, inspect=faux_inspect)
        self.assertEqual(r["summary"]["structurally_installed_alternatives"], 0)
        self.assertEqual(r["summary"]["unavailable_or_invalid"], 2)
        self.assertTrue(all(x["status"] == "source_unavailable_or_invalid"
                            for x in r["probes"]))

    def test_attempt_cap(self):
        r = probe_pinned_alternatives(
            confirmed=True, profiles=["genshin_ayaka", "genshin_venti"],
            coverage=sources(), max_attempts=1,
            dispatch=lambda *args: None, scan=faux_scan, inspect=faux_inspect)
        self.assertEqual(r["summary"]["attempted_pinned_alternative_sources"], 1)


if __name__ == "__main__":
    unittest.main()
