"""Source-pinned fallback recovery and real installed-interaction variant ranking."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image

from tools.personal_source_batch import plan_personal_sources, install_personal_plan
from tools.character_interaction_coverage import rank_installed_role_variants


def coverage():
    return {"characters": [
        {"id": "genshin_a", "name": "A", "source_candidates": [
            {"provider": "unverified_lfs", "source_key": "manual", "url": "https://a.test/manual"},
            {"provider": "native", "source_key": "nativeA", "url": "https://a.test/native"},
            {"provider": "codex", "source_key": "codexA", "url": "https://a.test/codex"},
            {"provider": "shimeji", "source_key": "shimejiA", "url": "https://a.test/shimeji"},
            {"provider": "codexpetdb_zip", "source_key": "petdbA", "url": "https://a.test/petdb"},
            {"provider": "nano_shimeji", "source_key": "nanoA", "url": "https://a.test/nano"}]},
        {"id": "genshin_b", "name": "B", "source_candidates": [
            {"provider": "shimeji", "source_key": "b", "url": "https://b.test/b"}]},
    ]}


def inventory():
    return {"characters": [], "invalid_local": []}


class PinnedCreatorFallbackTests(unittest.TestCase):
    def test_prefers_original_order_and_falls_back_without_unpinned_leads(self):
        with TemporaryDirectory() as temp:
            plan = plan_personal_sources(
                Path(temp) / "new", coverage=coverage(), inventory=inventory())
            role = plan["characters"][0]
            self.assertEqual(role["source_key"], "nativeA")
            self.assertEqual(role["automatic_source_count"], 5)
            self.assertEqual(plan["summary"]["roles_with_multiple_auto_sources"], 1)
            self.assertEqual([x["source_key"] for x in role["supported_sources"]],
                             ["nativeA", "codexA", "shimejiA", "petdbA", "nanoA"])
            calls = []
            def fake(provider, key, root):
                calls.append((provider, key))
                if key == "nativeA":
                    raise RuntimeError("first source unavailable")
                return {"profile": "genshin_a", "folder": "CreatorA"}
            with self.assertRaisesRegex(ValueError, "Explicit"):
                install_personal_plan(plan, temp, dispatch=fake)
            result = install_personal_plan(plan, temp, dispatch=fake,
                                           confirmed=True, max_roles=1)
            self.assertEqual(result["attempted"], 1)
            self.assertEqual(result["source_attempts"], 2)
            self.assertEqual(result["fallback_recovered_profiles"], 1)
            self.assertEqual(result["installed_unreviewed"], 1)
            self.assertEqual(calls, [("native", "nativeA"), ("codex", "codexA")])
            self.assertTrue(result["results"][0]["used_fallback"])
            self.assertEqual(len(result["results"][0]["source_attempts"]), 2)

    def test_retries_bounded_and_all_fail_reported_no_false_success(self):
        with TemporaryDirectory() as temp:
            plan = plan_personal_sources(temp, coverage=coverage(), inventory=inventory())
            calls = []
            def fail(provider, key, root):
                calls.append(key)
                raise ValueError("checksum mismatch")
            result = install_personal_plan(plan, temp, confirmed=True,
                                           dispatch=fail, max_roles=1)
            self.assertEqual(calls, ["nativeA", "codexA", "shimejiA", "petdbA"])
            self.assertEqual(result["source_attempts"], 4)
            self.assertEqual(result["installed_unreviewed"], 0)
            self.assertEqual(result["failed"], 1)
            self.assertEqual(len(result["results"][0]["source_attempts"]), 4)
            self.assertIn("checksum", result["results"][0]["reason"])


class NativeActionVariantRecommendationTests(unittest.TestCase):
    @staticmethod
    def _role(root, name, actions):
        folder = root / name
        (folder / "action").mkdir(parents=True)
        payload = {}
        for action in actions:
            payload[action] = {"images": action}
            Image.new("RGBA", (16, 16), (220, 130, 80, 255)).save(
                folder / "action" / (action + "_0.png"))
        (folder / "act_conf.json").write_text(
            json.dumps(payload), encoding="utf-8")
        return folder

    def test_ranks_actual_decodable_interaction_count_without_union(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self._role(root, "ArtistThin", ["wave", "idle"])
            self._role(root, "ArtistRich", ["jump", "wave", "rest"])
            self._role(root, "ArtistNoise", ["fight", "fake_patpat"])
            broken = root / "ArtistBroken"
            (broken / "action").mkdir(parents=True)
            (broken / "act_conf.json").write_text('{"wave":{"images":"wave"}}')
            ranked = rank_installed_role_variants(
                root, ["ArtistThin", "ArtistBroken", "ArtistNoise", "ArtistRich"])
            self.assertEqual([x["folder"] for x in ranked],
                             ["ArtistRich", "ArtistThin", "ArtistNoise", "ArtistBroken"])
            self.assertEqual(ranked[0]["available_interaction_count"], 3)
            self.assertEqual(ranked[1]["available_interaction_count"], 1)
            self.assertEqual(ranked[2]["available_interaction_count"], 0)
            self.assertTrue(all(x["manual_appearance_review_required"] for x in ranked))
            self.assertNotIn("fight", ranked[2]["interaction_categories"])

    def test_invalid_and_duplicate_paths_fail_closed(self):
        with TemporaryDirectory() as temp:
            root = Path(temp)
            self._role(root, "AuthorA", ["wave"])
            with self.assertRaisesRegex(ValueError, "Repeated"):
                rank_installed_role_variants(root, ["AuthorA", "AuthorA"])
            with self.assertRaisesRegex(ValueError, "Invalid installed role folder name"):
                rank_installed_role_variants(root, ["../outside"])
            outside = root / "linked"
            try:
                outside.symlink_to(root / "AuthorA", target_is_directory=True)
            except (OSError, NotImplementedError):
                return
            r = rank_installed_role_variants(root, ["linked"])
            self.assertEqual(r[0]["status"], "invalid_installed_sprite")
            self.assertEqual(r[0]["available_interaction_count"], 0)


if __name__ == "__main__":
    unittest.main()
