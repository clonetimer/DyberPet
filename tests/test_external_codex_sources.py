"""Independent creator art must be pinned, locally installed and QA-pending."""
from __future__ import annotations
from io import BytesIO
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from tools.install_external_codex import source_manifest, install_external_codex
from tools.character_source_coverage import source_coverage
from tools.install_native_role import validate_native_role


class ExternalCreatorSourcesTests(unittest.TestCase):
    def test_pinned_sources_and_31_character_coverage(self):
        source = source_manifest()
        self.assertEqual(set(source["sources"]), {"linnea","hu_tao_pixel","nahida_mini","sandrone","sandrone_marionette","keqing_chibi","keqing_classic","klee_fan","yoimiya_fan","furina_fan","sayu_cozy"})
        self.assertEqual(source["sources"]["linnea"]["profile"], "genshin_linnea")
        self.assertEqual(source["sources"]["hu_tao_pixel"]["profile"], "genshin_hu_tao")
        self.assertEqual(source["sources"]["nahida_mini"]["profile"], "genshin_nahida")
        self.assertEqual(source["sources"]["sandrone"]["profile"], "genshin_sandrone")
        self.assertEqual(source["sources"]["keqing_chibi"]["profile"], "genshin_keqing")
        self.assertEqual(source["sources"]["keqing_classic"]["profile"], "genshin_keqing")
        for name, profile in (("klee_fan","genshin_klee"),("yoimiya_fan","genshin_yoimiya"),("furina_fan","genshin_furina"),("sayu_cozy","genshin_sayu")):
            self.assertEqual(source["sources"][name]["profile"], profile)
        for row in source["sources"].values():
            self.assertEqual(len(row["revision"]), 40)
            for key in ("pet","sprites"):
                self.assertEqual(len(row[key]["sha"]), 40)
                self.assertGreater(row[key]["size"], 100)
        catalog = source_coverage()
        self.assertEqual(catalog["summary"]["template_count"], 123)
        self.assertEqual(catalog["summary"]["pinned_source_options"], 58)
        self.assertEqual(catalog["summary"]["characters_with_pinned_sources"], 35)
        self.assertEqual(catalog["summary"]["characters_without_pinned_sources"], 88)
        sayu = next(x for x in catalog["characters"] if x["id"]=="genshin_sayu")
        self.assertTrue(sayu["source_found"])
        self.assertEqual(sayu["source_candidate_count"], 1)
        self.assertFalse(sayu["visual_likeness_qa_passed"])
        self.assertFalse(sayu["installed"])
        self.assertFalse(sayu["rights_verified"])
        self.assertEqual(source["sources"]["sayu_cozy"]["sprites"]["sha"], "6aaefa1074a2e72d73333a171575b4ff8b9693e7")
        linnea = next(x for x in catalog["characters"] if x["id"]=="genshin_linnea")
        self.assertTrue(linnea["source_found"])
        self.assertFalse(linnea["installed"])
        self.assertFalse(linnea["visual_likeness_qa_passed"])

    def test_no_consent_no_network(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                install_external_codex("linnea", td)
            with self.assertRaises(ValueError):
                install_external_codex("unknown", td, confirmed=True)

    def test_fake_atlas_cannot_substitute_for_real_creator_proof(self):
        # Tests that the import script refuses a wrong manifest ID before conversion.
        invalid = {"id":"other-character", "spritesheetPath":"spritesheet.webp"}
        pet = json.dumps(invalid).encode()
        sheet = BytesIO()
        Image.new("RGBA", (1536,1872), (0,0,0,0)).save(sheet, "WEBP")
        source = {"schema":1,"sources":{"linnea":{
            "repository":"creator/repo","revision":"a"*40,"directory":"pet",
            "profile":"genshin_linnea","manifest_id":"linnea","name":"莉奈娅",
            "pet":{"size":len(pet),"sha":"0"*40},
            "sprites":{"size":len(sheet.getvalue()),"sha":"0"*40}}}}
        def fake_download(url, spec):
            return pet if url.endswith("pet.json") else sheet.getvalue()
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaisesRegex(ValueError, "Wrong artist"):
                install_external_codex("linnea", td, confirmed=True,
                                       manifest=source, downloader=fake_download)
            self.assertEqual(list(Path(td).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
