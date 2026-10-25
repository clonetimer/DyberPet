"""R4 runtime profiling contract: no role assets disclosed and no fake speed claims."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.profile_role_backends import profile, _create_synthetic


class RuntimeProfilerTests(unittest.TestCase):
    def test_disposable_fixture_yields_independent_worker_results(self):
        with tempfile.TemporaryDirectory() as td:
            role = _create_synthetic(Path(td), 3)
            output = profile(role, "Guga", rounds=2, warmup=0)
        self.assertEqual(output["schema_version"], 1)
        self.assertTrue(output["no_role_asset_content_emitted"])
        self.assertTrue(output["backend_measurements"]["python"]["available"])
        self.assertEqual(len(output["backend_measurements"]["python"]["report_sha256"]), 64)
        self.assertGreaterEqual(output["backend_measurements"]["python"]["process_elapsed_ms"], 0)
        if output["backend_measurements"]["rust"]["available"]:
            self.assertTrue(output["report_parity"])
        else:
            self.assertIsNone(output["report_parity"])
        self.assertNotIn(str(role), json.dumps(output))

    def test_command_line_emits_one_parseable_report(self):
        script = Path(__file__).resolve().parents[1] / "tools" / "profile_role_backends.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--synthetic-frames", "2",
             "--rounds", "1", "--warmup", "0"],
            capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=40, check=True)
        report = json.loads(completed.stdout)
        self.assertEqual(report["fixture"],
                         "generated_33_byte_png_headers_not_real_art")
        self.assertEqual(report["role_profile"], "guga")
        self.assertTrue(report["backend_measurements"]["python"]["available"])

    def test_refuses_unregistered_names_or_invalid_counts(self):
        with tempfile.TemporaryDirectory() as td:
            role = _create_synthetic(Path(td), 1)
            with self.assertRaisesRegex(ValueError, "registered fidelity"):
                profile(role, "Unknown", rounds=1)
            with self.assertRaisesRegex(ValueError, "Rounds"):
                profile(role, "Guga", rounds=0)

    def test_missing_native_can_never_claim_report_parity(self):
        with tempfile.TemporaryDirectory() as td:
            role = _create_synthetic(Path(td), 1)
            def fake_run(_role, _name, mode, _rounds, _warmup):
                if mode == "python":
                    return {"available": True, "report_sha256": "a" * 64}
                return {"available": False, "backend": {"fallback": True}}
            with patch("tools.profile_role_backends._run_process",
                       side_effect=fake_run):
                report = profile(role, "Guga", rounds=1)
                self.assertIsNone(report["report_parity"])
                with self.assertRaisesRegex(RuntimeError, "Required Rust"):
                    profile(role, "Guga", rounds=1, require_rust=True)

    def test_mismatched_native_report_rejects_benchmark(self):
        with tempfile.TemporaryDirectory() as td:
            role = _create_synthetic(Path(td), 1)
            def fake_run(_role, _name, mode, _rounds, _warmup):
                return {"available": True,
                        "report_sha256": "a" * 64 if mode == "python" else "b" * 64}
            with patch("tools.profile_role_backends._run_process",
                       side_effect=fake_run):
                with self.assertRaisesRegex(RuntimeError, "reports differ"):
                    profile(role, "Guga", rounds=1)

    def test_role_directory_symlink_is_not_followed(self):
        with tempfile.TemporaryDirectory() as td:
            actual = _create_synthetic(Path(td), 1)
            link = Path(td) / "alias"
            try:
                link.symlink_to(actual, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable")
            with self.assertRaisesRegex(ValueError, "ordinary"):
                profile(link, "Guga", rounds=1)


if __name__ == "__main__":
    unittest.main()
