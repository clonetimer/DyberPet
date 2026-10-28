"""R27 source-to-GUI and batch-plan acceptance with zero artwork downloads."""
import ast
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from tools.personal_source_batch import plan_personal_sources
from tools.react_shimeji_source_leads import verified_lfs_sources
from tools.install_verified_react_lfs import ALLOWED


class R27TwoNewCreatorRoles(unittest.TestCase):
    def test_fresh_personal_plan_adds_two_real_auto_sources_not_demos(self):
        with TemporaryDirectory() as td:
            result = plan_personal_sources(Path(td) / "fresh")
        summary = result["summary"]
        self.assertEqual(summary["selected_profiles"], 123)
        self.assertEqual(summary["ready_for_opt_in"], 68)
        self.assertEqual(summary["missing_source"], 55)
        self.assertEqual(summary["manual_import_only"], 0)
        self.assertEqual(len(verified_lfs_sources()), 4)
        by_profile = {entry["profile"]: entry for entry in result["characters"]}
        for profile, expected in (
            ("genshin_neuvillette", "neuvillette"),
            ("genshin_wriothesley", "wriothesley"),
        ):
            record = by_profile[profile]
            self.assertEqual(record["status"], "ready_for_opt_in")
            self.assertEqual(record["provider"], "react_lfs")
            self.assertEqual(record["source_key"], expected)
            self.assertFalse(record["original_likeness_verified"])
            self.assertFalse(record["rights_verified_by_tool"])
            self.assertFalse(record["real_device_playback_verified"])
            self.assertEqual(ALLOWED[expected], profile)

    def test_character_gui_has_background_opt_in_and_no_js_execution(self):
        source = (Path(__file__).resolve().parents[1] /
                  "DyberPet/DyberSettings/CharCardUI.py").read_text("utf-8")
        ast.parse(source)
        self.assertIn('mode="react_verified_auto"', source)
        self.assertIn('elif self.mode == "react_verified_auto":', source)
        self.assertIn("install_verified_react_lfs(", source)
        self.assertIn("ChibiImportThread(", source)
        self.assertIn("confirmed=True", source)
        self.assertIn('"react_verified_auto",', source)


if __name__ == "__main__":
    unittest.main()
