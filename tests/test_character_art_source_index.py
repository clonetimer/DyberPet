"""R38: no source entry can imply unverified art is completed or licensed."""
import ast
import unittest
from pathlib import Path

from tools.character_art_source_index import (
    SOURCES, source_coverage, sources_for_role, validate_sources,
)
from tools.character_progress import character_progress


class CreatorSourceIndexTests(unittest.TestCase):
    def test_125_character_index_and_zero_false_approvals(self):
        self.assertEqual(validate_sources(), len(SOURCES))
        coverage = source_coverage()
        self.assertEqual(coverage["template_count"], 125)
        self.assertEqual(coverage["specific_source_leads"], 5)
        self.assertEqual(coverage["family_discovery_only"], 120)
        self.assertEqual(coverage["without_source_lead"], 0)
        self.assertEqual(coverage["creator_fidelity_approved"], 0)
        self.assertEqual(coverage["physical_desktop_qa_approved"], 0)

    def test_guga_and_doro_track_original_creators_and_same_live2d_line(self):
        guga = sources_for_role("mascot_guga")
        self.assertEqual(len(guga), 3)
        self.assertEqual(guga[0]["creator"], "氧化钙你五月")
        self.assertEqual(guga[0]["type"], "dyberpet_native_preview")
        self.assertEqual(guga[0]["rights"], "unknown")
        doro = sources_for_role("mascot_doro")
        self.assertEqual(len(doro), 2)
        self.assertEqual(doro[0]["lineage"], doro[1]["lineage"])
        self.assertTrue(all(s["rights"] == "no_redistribution" for s in doro))
        self.assertTrue(all(s["scope"] == "role" for s in guga + doro))
        self.assertFalse(any("sketchfab" in s["url"] for s in SOURCES))

    def test_family_link_is_not_role_specific_artwork(self):
        for name in ("genshin_lisa", "genshin_raiden_shogun"):
            links = sources_for_role(name)
            self.assertEqual(len(links), 1)
            self.assertEqual(links[0]["scope"], "family")
            self.assertEqual(links[0]["rights"], "unknown")
        nahida = sources_for_role("genshin_nahida")
        self.assertEqual([s["scope"] for s in nahida], ["role", "family"])
        self.assertEqual(nahida[0]["creator"], "栎曦_Nuo")
        ayaka = sources_for_role("genshin_ayaka")
        self.assertEqual(ayaka[0]["rights"], "restricted")
        self.assertEqual(sources_for_role("genshin_xiao")[0]["scope"], "role")

    def test_no_made_up_character_ids_or_false_positive(self):
        for name in ("genshin_made_up", "mascot_unknown", "genshin_123",
                     "../secret"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                sources_for_role(name)
        coverage = character_progress(Path("/a/definitely/nonexistent/role"))
        self.assertEqual(len(coverage["characters"]), 125)
        self.assertFalse(any(x["creator_art_and_likeness_verified"]
                             for x in coverage["characters"]))

    def test_ui_opens_only_author_url_without_network_installation(self):
        ui = Path(__file__).resolve().parents[1] / "DyberPet" / "DyberSettings" / "character_catalog_dialog.py"
        tree = ast.parse(ui.read_text(encoding="utf-8"))
        methods = {m.name: ast.unparse(m) for m in ast.walk(tree)
                   if isinstance(m, ast.FunctionDef)}
        self.assertIn("sources_for_role(selected)", methods["_refresh_sources"])
        self.assertIn("QDesktopServices.openUrl", methods["_open_source"])
        self.assertIn("scope", methods["_update_source_note"])
        for name in ("_refresh_sources", "_open_source"):
            for forbidden in ("urlopen(", "requests.get(", "install_creator_mascot(",
                              "subprocess.run(", "copy2("):
                self.assertNotIn(forbidden, methods[name])


if __name__ == "__main__":
    unittest.main()
