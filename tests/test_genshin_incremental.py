"""Incremental Genshin intake must not overwrite earlier source/rights evidence."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.character_pipeline import PipelineError, load_case, record_path
from tools.genshin_roster import GENSHIN_ROSTER
from tools.genshin_batch import seed, seed_missing


class IncrementalGenshinIntakeTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name) / "character-workspace"

    def test_seed_missing_only_creates_new_wave_and_preserves_old_evidence(self):
        old = tuple(GENSHIN_ROSTER)[:14]
        self.assertEqual(len(old), 14)
        seed(self.root, old)
        existing_case = record_path(self.root, "genshin_xiao_main")
        checklist = self.root / "reviews" / "genshin_xiao_main.json"
        data = json.loads(existing_case.read_text(encoding="utf-8"))
        data["status"] = "source_attached"
        existing_case.write_text(json.dumps(data, ensure_ascii=False),
                                 encoding="utf-8")
        notes = json.loads(checklist.read_text(encoding="utf-8"))
        notes["operator_note"] = "keep previous manual review"
        checklist.write_text(json.dumps(notes, ensure_ascii=False),
                             encoding="utf-8")
        case_before, notes_before = existing_case.read_bytes(), checklist.read_bytes()

        result = seed_missing(self.root, tuple(GENSHIN_ROSTER))
        self.assertEqual(result["created"], 105)
        self.assertEqual(result["preserved"], 14)
        self.assertEqual(result["total_selected"], 119)
        self.assertEqual(existing_case.read_bytes(), case_before)
        self.assertEqual(checklist.read_bytes(), notes_before)
        for key in tuple(GENSHIN_ROSTER)[14:]:
            case = load_case(record_path(self.root, "genshin_" + key + "_main"))
            self.assertEqual(case["status"], "discovered")
            self.assertFalse(case["rights"]["local_use"])
            self.assertFalse(case["rights"]["redistribution"])
            self.assertFalse(case["qa"]["runtime_pass"])

        second = seed_missing(self.root, tuple(GENSHIN_ROSTER))
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["preserved"], 119)
        self.assertEqual(existing_case.read_bytes(), case_before)
        self.assertEqual(checklist.read_bytes(), notes_before)

    def test_incomplete_pair_prevents_all_new_writes(self):
        seed(self.root, ("xiao",))
        (self.root / "reviews" / "genshin_xiao_main.json").unlink()
        with self.assertRaisesRegex(PipelineError, "Incomplete case/review pair"):
            seed_missing(self.root, ("diluc", "xiao"))
        self.assertFalse(record_path(self.root, "genshin_diluc_main").exists())

    def test_existing_wrong_profile_refuses_all_new_writes(self):
        seed(self.root, ("xiao",))
        original = record_path(self.root, "genshin_xiao_main")
        case = load_case(original)
        case["profile"] = "genshin_diluc"
        original.write_text(json.dumps(case, ensure_ascii=False),
                            encoding="utf-8")
        with self.assertRaisesRegex(PipelineError, "identity mismatch"):
            seed_missing(self.root, ("diluc", "xiao"))
        self.assertFalse(record_path(self.root, "genshin_diluc_main").exists())

    def test_untrusted_review_symlink_is_not_followed(self):
        seed(self.root, ("xiao",))
        review = self.root / "reviews" / "genshin_xiao_main.json"
        review.unlink()
        external = self.root.parent / "external-review.json"
        external.write_text("sentinel", encoding="utf-8")
        try:
            review.symlink_to(external)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unsupported on this runner")
        with self.assertRaisesRegex(PipelineError, "Unsafe case or review"):
            seed_missing(self.root, ("diluc", "xiao"))
        self.assertEqual(external.read_text(encoding="utf-8"), "sentinel")
        self.assertFalse(record_path(self.root, "genshin_diluc_main").exists())

    def test_cli_seed_missing_produces_machine_readable_summary(self):
        cli = Path(__file__).resolve().parents[1] / "tools" / "genshin_batch.py"
        result = subprocess.run([
            sys.executable, str(cli), "--workspace", str(self.root),
            "seed-missing", "--roles", "diluc,lynette"
        ], capture_output=True, text=True, encoding="utf-8", timeout=35,
           check=True)
        summary = json.loads(result.stdout)
        self.assertEqual(summary["created"], 2)
        self.assertEqual(summary["preserved"], 0)
        self.assertEqual(summary["total_selected"], 2)
        self.assertEqual(len(summary["created_ids"]), 2)


if __name__ == "__main__":
    unittest.main()
