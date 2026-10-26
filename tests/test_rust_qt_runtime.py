"""R7 control tests: offscreen Qt parity without inventing hardware results."""
import json
import tempfile
import unittest
from pathlib import Path

from tools.benchmark_qt_creator_runtime import paired_qt
from tools.install_artist_codex import REPO, REVISION, SOURCES


class R7QtRuntimeTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="r7-qt-parity-")
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.role = self.root / "SourceCodexNahida"
        (self.role / "action").mkdir(parents=True)
        (self.role / "PERSONAL_IMPORT.json").write_text(json.dumps({
            "source_repository": REPO,
            "source_commit": REVISION,
            "source_id": SOURCES["nahida"][0],
            "selected_profile": SOURCES["nahida"][2],
        }), encoding="utf-8")
        (self.role / "IMPORT_REPORT.json").write_text(json.dumps({
            "preserve_source_frames": True,
            "source_pixel_integrity_verified": True,
            "aligned_frames_per_action": {},
        }), encoding="utf-8")
        self.seen = []

    def worker(self, root, kind, mode, ticks):
        self.assertEqual(root, self.root)
        self.assertEqual(kind, "nahida")
        self.assertEqual(ticks, 32)
        self.seen.append(mode)
        return {
            "available": True, "backend": mode, "pixel_sha256": "a"*64,
            "qt_setup_ms": 150, "pixmap_decode_ms": 40,
            "petconfig_ms": 10, "qt_repaint_ms": 20,
            "process_ms": 250, "rss_snapshot_bytes": 64000000,
        }

    def test_realistic_order_even_medians_and_no_fps_claims(self):
        x = paired_qt(self.root, "nahida", blocks=2, ticks=32,
                      runner=self.worker)
        self.assertEqual(self.seen, ["python", "rust", "rust", "python",
                                     "rust", "python", "python", "rust"])
        self.assertTrue(x["qt_pixel_parity"])
        self.assertEqual(x["backends"]["rust"]["processes"], 4)
        self.assertEqual(x["backends"]["python"]["qt_repaint_median_ms"], 20)
        self.assertTrue(x["not_a_physical_windows_test"])
        self.assertTrue(x["timing_not_a_speed_acceptance_gate"])
        self.assertNotIn(str(self.root), json.dumps(x))

    def test_swapped_pixel_result_is_a_hard_failure(self):
        def wrong(*args):
            result = self.worker(*args)
            if result["backend"] == "rust":
                result["pixel_sha256"] = "b"*64
            return result
        with self.assertRaisesRegex(RuntimeError, "pixels differ"):
            paired_qt(self.root, "nahida", blocks=1, ticks=32,
                      runner=wrong)

    def test_missing_rust_must_not_silently_fallback_to_python(self):
        def fallback(*args):
            value = self.worker(*args)
            if value["backend"] == "rust":
                value["backend"] = "python"
            return value
        with self.assertRaisesRegex(RuntimeError, "fell back"):
            paired_qt(self.root, "nahida", blocks=1, ticks=32,
                      runner=fallback)

    def test_invalid_round_bounds(self):
        for opts in ({"blocks":0}, {"blocks":5}, {"ticks":0},
                     {"ticks":513}):
            with self.subTest(opts=opts):
                with self.assertRaises(ValueError):
                    paired_qt(self.root, "nahida", runner=self.worker, **opts)

    def test_reject_unverified_creator_source(self):
        (self.role / "IMPORT_REPORT.json").write_text(json.dumps({
            "preserve_source_frames": False,
            "source_pixel_integrity_verified": False,
            "aligned_frames_per_action": {"idle": 1},
        }), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "pinned"):
            paired_qt(self.root, "nahida", blocks=1, ticks=32,
                      runner=self.worker)


if __name__ == "__main__":
    unittest.main()
