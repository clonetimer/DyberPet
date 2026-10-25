"""A broken community ZIP must not hide independently valid source identities."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.verify_pending_codexpetdb import verify_new_sources


class IndependentPublisherProbeTests(unittest.TestCase):
    def test_missing_one_source_still_checks_three_others_without_promotion(self):
        keys = ("alpha", "bravo", "charlie", "delta")
        manifest = {
            "schema": 1,
            "status": "catalog_metadata_only_not_verified",
            "sources": {
                key: {"profile": "genshin_" + key, "slug": "gi-" + key,
                      "revision": "r-" + key, "sha256": key, "verified_bytes": 200}
                for key in keys
            },
        }
        with tempfile.TemporaryDirectory() as td:
            candidate = Path(td) / "proposed.json"
            candidate.write_text(json.dumps(manifest), encoding="utf-8")
            examined = []

            def fetch(key, **kwargs):
                examined.append(key)
                if key == "bravo":
                    raise OSError("HTTP Error 404: absent source")
                return (b"fake-zip", manifest["sources"][key])

            def parse(path):
                return {"manifest": {"id": path.stem}}

            def install(key, root, **kwargs):
                folder = Path(root) / ("SourcePetDb" + key.title())
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "PERSONAL_IMPORT.json").write_text(json.dumps({
                    "selected_profile": "genshin_" + key}), encoding="utf-8")
                (folder / "ACTION_PIXEL_AUDIT.json").write_text(json.dumps({
                    "summary": {"actions_with_pixel_issues": 0,
                                "original_frames_inspected": 57}}), encoding="utf-8")
                (folder / "ANIMATION_PREVIEW.png").write_bytes(b"test")
                return folder

            out = StringIO()
            with patch("tools.verify_pending_codexpetdb.get_verified_package",
                       side_effect=fetch), patch(
                       "tools.verify_pending_codexpetdb.inspect_codex_zip",
                       side_effect=parse), patch(
                       "tools.verify_pending_codexpetdb.install_pinned_codexpetdb",
                       side_effect=install), patch(
                       "tools.verify_pending_codexpetdb.validate_native_role",
                       return_value={"images": 57, "actions": 9}), patch(
                       "tools.verify_pending_codexpetdb.time.sleep"), redirect_stdout(out):
                with self.assertRaisesRegex(ValueError, "bravo"):
                    verify_new_sources(candidate)
        self.assertEqual(examined, list(keys))
        self.assertEqual(out.getvalue().count("NEW_SOURCE_VERIFIED"), 3)
        self.assertEqual(out.getvalue().count("NEW_SOURCE_UNVERIFIED"), 1)
        self.assertIn("HTTP Error 404", out.getvalue())
        self.assertIn('"character_likeness_manually_verified": false',
                      out.getvalue())


if __name__ == "__main__":
    unittest.main()
