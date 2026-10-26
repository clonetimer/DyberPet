import unittest
from tools.probe_shimejis_xyz_missing import candidate_report, PACK_URL


class GenshinSourceDirectoryTests(unittest.TestCase):
    def setUp(self):
        self.coverage = {"characters": [
            {"id":"genshin_noelle","name":"诺艾尔","source_found":False},
            {"id":"genshin_arataki_itto","name":"荒泷一斗","source_found":False},
            {"id":"genshin_ayaka","name":"绫华","source_found":True},
            {"id":"genshin_lisa","name":"丽莎","source_found":False},
        ]}

    def test_does_not_promote_links_or_duplicate_old_characters(self):
        page = """<a href="/directory/shimeji/genshin-noelle-by-art">Noelle</a>
        <a href="https://shimejis.xyz/directory/shimeji/arataki-itto-by-art">Itto</a>
        <a href="/directory/shimeji/genshin-ayaka">Ayaka</a>
        <a href="/directory/shimeji/genshin-lisas">incorrect</a>"""
        report = candidate_report(page=page, coverage=self.coverage)
        self.assertEqual(report["uncovered_matching_candidates"], 2)
        self.assertEqual(report["previously_covered_matches"], 1)
        self.assertEqual({x["profile"] for x in report["candidates"]},
                         {"genshin_noelle", "genshin_arataki_itto"})
        self.assertTrue(all(not x["pinned_source_promoted"]
                            for x in report["candidates"]))
        self.assertEqual(report["source_page"], PACK_URL)

    def test_explicit_traveler_and_childe_aliases_are_not_new_coverage(self):
        rows = list(self.coverage["characters"])
        rows.extend([
            {"id": "genshin_traveler_aether", "name": "空", "source_found": True},
            {"id": "genshin_traveler_lumine", "name": "荧", "source_found": True},
            {"id": "genshin_tartaglia", "name": "达达利亚", "source_found": True},
        ])
        html = """<a href="/directory/shimeji/genshin-impact-aether-by-artist">Aether</a>
        <a href="/directory/shimeji/genshin-impact-lumine-by-artist">Lumine</a>
        <a href="/directory/shimeji/genshin-impact-childe-by-artist">Childe</a>"""
        result = candidate_report(page=html, coverage={"characters": rows})
        self.assertEqual(result["uncovered_matching_candidates"], 0)
        self.assertEqual(result["previously_covered_matches"], 3)
        self.assertEqual(result["unmatched_or_ambiguous"], 0)

    def test_unsafe_domains_no_slugs_or_ambiguous_names_refused(self):
        page = """<a href="https://evil.test/directory/shimeji/genshin-noelle">bad</a>
                  <a href="/directory/shimeji/genshin-lisa-ayaka">ambiguous</a>"""
        report = candidate_report(page=page, coverage=self.coverage)
        self.assertEqual(report["uncovered_matching_candidates"], 0)
        self.assertEqual(report["unmatched_or_ambiguous"], 1)
        with self.assertRaisesRegex(ValueError, "no public character"):
            candidate_report(page="<script src='evil.test'></script>",coverage=self.coverage)

if __name__ == "__main__":
    unittest.main()
