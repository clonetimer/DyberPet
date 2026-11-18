"""Content-free trial evidence, resource arithmetic and explicit JSON export."""
import importlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class _Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now


class _Sampler:
    def __init__(self):
        self.cpu = 10.0
        self.rss = 8192
        self.error = False

    def __call__(self):
        if self.error:
            raise OSError("PRIVATE /home/person/model")
        return {"cpu_seconds": self.cpu, "rss_bytes": self.rss}


class _ModuleTest(unittest.TestCase):
    def setUp(self):
        try:
            self.module = importlib.import_module("DyberPet.assistant.trial_records")
        except ModuleNotFoundError as exc:
            self.fail("Trial record feature is not implemented: " + str(exc))


class TrialRecorderTests(_ModuleTest):
    def setUp(self):
        super().setUp()
        self.clock = _Clock()
        self.sampler = _Sampler()
        self.recorder = self.module.TrialRecorder(
            clock=self.clock, sampler=self.sampler, environment={})

    def row(self):
        return self.recorder.snapshot()["observations"][-1]

    def test_timing_and_resource_arithmetic_describe_observed_activity(self):
        run = self.recorder.begin("chat")
        self.clock.now = 101.5
        self.recorder.text(run, 2)
        self.recorder.text(run, 3)
        self.clock.now = 102.0
        self.recorder.ready(run)
        self.clock.now = 102.5
        self.recorder.ready(run)
        self.clock.now = 104.0
        self.sampler.cpu, self.sampler.rss = 16.0, 12288
        self.recorder.observe(run, result_chars=5)
        self.recorder.finish(run, "completed")
        row = self.row()
        self.assertEqual(row["elapsed_ms"], 4000)
        self.assertEqual(row["first_text_ms"], 1500)
        self.assertEqual(row["ready_ms"], 2000)
        self.assertEqual(row["displayed_chars"], 5)
        self.assertEqual(row["result_chars"], 5)
        self.assertEqual(row["cpu_seconds"], 6)
        self.assertEqual(row["cpu_percent_one_core"], 150)
        self.assertEqual(row["rss_max_bytes"], 12288)
        self.assertEqual(row["sample_count"], 2)
        self.clock.now = 500.0
        self.assertEqual(self.row(), row)

    def test_sampling_is_throttled_but_finish_forces_a_fresh_sample(self):
        run = self.recorder.begin("speech")
        self.clock.now = 100.5
        self.sampler.rss = 16384
        self.recorder.sample(run)
        self.assertEqual(self.row()["rss_max_bytes"], 8192)
        self.assertEqual(self.row()["sample_count"], 1)
        self.clock.now = 101.0
        self.recorder.sample(run)
        self.sampler.rss = 12288
        self.clock.now = 101.1
        self.recorder.finish(run, "completed")
        self.assertEqual(self.row()["sample_count"], 3)
        self.assertEqual(self.row()["rss_max_bytes"], 16384)

    def test_stop_can_preserve_a_final_transcript_without_becoming_success(self):
        run = self.recorder.begin("listen")
        self.clock.now = 101.0
        self.recorder.ready(run)
        self.clock.now = 102.0
        self.recorder.request_stop(run)
        self.clock.now = 103.0
        self.recorder.request_stop(run, "window_closed")
        self.recorder.observe(run, result_chars=18)
        self.clock.now = 104.5
        self.recorder.finish(run, "completed")
        row = self.row()
        self.assertEqual(row["outcome"], "cancelled")
        self.assertEqual(row["result_chars"], 18)
        self.assertEqual(row["stop_reason"], "user")
        self.assertEqual(row["stop_requested_ms"], 2000)
        self.assertEqual(row["stop_settled_ms"], 2500)

    def test_missing_completion_evidence_is_interrupted_and_unknown_stays_null(self):
        run = self.recorder.begin("speech")
        self.recorder.ready(run)
        self.recorder.finish(run, "running")
        row = self.row()
        self.assertEqual(row["outcome"], "interrupted")
        for name in ("first_text_ms", "result_chars", "model_count",
                     "recognition_ready", "tts_ready", "engine_completed",
                     "stop_requested_ms", "stop_settled_ms", "stop_reason",
                     "error_code"):
            self.assertIsNone(row[name], name)

    def test_errors_are_fixed_codes_and_cancellation_wins_over_failure(self):
        run = self.recorder.begin("chat")
        self.recorder.fail(run, "PRIVATE http://localhost/path /Users/name/model")
        self.recorder.finish(run, "completed")
        self.assertEqual(self.row()["outcome"], "failed")
        self.assertEqual(self.row()["error_code"], "internal_error")
        run = self.recorder.begin("model_probe")
        self.recorder.request_stop(run, "configuration_changed")
        self.recorder.fail(run, "timeout")
        self.recorder.finish(run, "failed")
        self.assertEqual(self.row()["outcome"], "cancelled")
        self.assertEqual(self.row()["error_code"], "timeout")
        self.assertNotIn("PRIVATE", json.dumps(self.recorder.snapshot()))

    def test_finished_or_unknown_ids_ignore_every_late_event(self):
        run = self.recorder.begin("speech")
        self.recorder.observe(run, engine_completed=True)
        self.recorder.finish(run, "completed")
        before = self.recorder.snapshot()
        for target in (run, run + 1):
            self.recorder.text(target, 100)
            self.recorder.ready(target)
            self.recorder.observe(target, engine_completed=False, result_chars=20)
            self.recorder.request_stop(target)
            self.recorder.fail(target, "voice_unavailable")
            self.recorder.sample(target)
            self.recorder.finish(target, "failed")
        self.assertEqual(self.recorder.snapshot(), before)

    def test_bounded_history_and_clear_never_reuse_operation_identity(self):
        for _ in range(31):
            run = self.recorder.begin("models")
            self.recorder.observe(run, model_count=2)
            self.recorder.finish(run, "completed")
        rows = self.recorder.snapshot()["observations"]
        self.assertEqual(len(rows), 30)
        self.assertEqual([rows[0]["id"], rows[-1]["id"]], [2, 31])
        self.recorder.set_feedback("model_reply", "satisfied")
        self.recorder.clear()
        self.assertEqual(self.recorder.snapshot()["observations"], [])
        self.assertEqual(self.recorder.snapshot()["feedback"]["model_reply"], "not_checked")
        self.assertEqual(self.recorder.begin("chat"), 32)
        with self.assertRaises(ValueError):
            self.recorder.clear()

    def test_feedback_is_explicit_and_snapshot_does_not_share_mutable_state(self):
        run = self.recorder.begin("speech")
        self.recorder.observe(run, engine_completed=True)
        self.recorder.finish(run, "completed")
        self.assertEqual(self.recorder.snapshot()["feedback"], {
            "model_reply": "not_checked", "recognition": "not_checked",
            "speech": "not_checked"})
        self.recorder.set_feedback("speech", "problem")
        snapshot = self.recorder.snapshot()
        snapshot["feedback"]["speech"] = "satisfied"
        snapshot["observations"][0]["result_chars"] = 900
        snapshot["environment"]["system"] = "PRIVATE"
        snapshot["limitations"].clear()
        self.assertEqual(self.recorder.snapshot()["feedback"]["speech"], "problem")
        self.assertIsNone(self.row()["result_chars"])
        self.assertTrue(self.recorder.snapshot()["limitations"])
        self.recorder.reset_feedback()
        self.assertEqual(self.recorder.snapshot()["feedback"]["speech"], "not_checked")
        for key, value in (("notes", "PRIVATE"), ("speech", "PRIVATE")):
            with self.assertRaises(ValueError):
                self.recorder.set_feedback(key, value)

    def test_recorder_accepts_only_finite_typed_observations(self):
        run = self.recorder.begin("listen")
        for value in (-1, True, "PRIVATE", float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                self.recorder.text(run, value)
        with self.assertRaises(ValueError):
            self.recorder.observe(run, result_chars=3, recognition_ready="PRIVATE")
        self.assertIsNone(self.row()["result_chars"])
        with self.assertRaises(ValueError):
            self.recorder.begin("/Users/PRIVATE")
        with self.assertRaises(ValueError):
            self.recorder.request_stop(run, "PRIVATE")

    def test_resource_failures_do_not_invent_zero_usage_or_prevent_completion(self):
        self.sampler.error = True
        run = self.recorder.begin("other")
        self.clock.now = 102.0
        self.recorder.sample(run)
        self.recorder.finish(run, "completed")
        self.assertEqual(self.row()["outcome"], "completed")
        for name in ("cpu_seconds", "cpu_percent_one_core", "rss_max_bytes"):
            self.assertIsNone(self.row()[name])
        self.assertEqual(self.row()["sample_count"], 0)
        self.assertNotIn("PRIVATE", json.dumps(self.recorder.snapshot()))

    def test_missing_final_cpu_sample_does_not_relabel_partial_cpu_as_total(self):
        run = self.recorder.begin("chat")
        self.clock.now = 102.0
        self.sampler.cpu, self.sampler.rss = 11.0, 16384
        self.recorder.sample(run)
        self.clock.now = 104.0
        self.sampler.error = True
        self.recorder.finish(run, "completed")
        self.assertIsNone(self.row()["cpu_seconds"])
        self.assertIsNone(self.row()["cpu_percent_one_core"])
        self.assertEqual(self.row()["rss_max_bytes"], 16384)

    def test_invalid_resource_values_are_missing_instead_of_json_nan(self):
        self.sampler.cpu, self.sampler.rss = float("nan"), -1
        run = self.recorder.begin("other")
        self.sampler.cpu, self.sampler.rss = True, "PRIVATE"
        self.recorder.finish(run, "completed")
        self.assertIsNone(self.row()["cpu_seconds"])
        self.assertIsNone(self.row()["rss_max_bytes"])
        json.dumps(self.recorder.snapshot(), allow_nan=False)


class ProcessUsageTests(_ModuleTest):
    def test_linux_uses_resident_pages_and_page_size_not_virtual_or_peak_memory(self):
        with patch.object(self.module.sys, "platform", "linux"):
            with patch.object(self.module.Path, "read_text", return_value="999 3 1 0 0 0 0\n"):
                with patch.object(self.module.os, "sysconf", return_value=4096, create=True):
                    with patch.object(self.module.time, "process_time", return_value=1.25):
                        result = self.module.sample_process_usage()
        self.assertEqual(result, {"cpu_seconds": 1.25, "rss_bytes": 12288})

    def test_windows_reports_current_working_set_and_survives_api_failure(self):
        class Function:
            def __init__(self, callback):
                self.callback = callback

            def __call__(self, *args):
                return self.callback(*args)

        succeeded = [True]
        counter_types = set()

        def memory(process, counters, size):
            self.assertEqual(process, 1234)
            self.assertEqual(counters._obj.cb, size)
            counter_types.add(type(counters._obj))
            counters._obj.WorkingSetSize = 24576
            counters._obj.PeakWorkingSetSize = 999999999
            return int(succeeded[0])

        kernel = SimpleNamespace(GetCurrentProcess=Function(lambda: 1234))
        psapi = SimpleNamespace(GetProcessMemoryInfo=Function(memory))

        def dll(name, **_kwargs):
            return {"kernel32": kernel, "psapi": psapi}[name]

        with patch.object(self.module.sys, "platform", "win32"):
            with patch("ctypes.WinDLL", side_effect=dll, create=True):
                with patch.object(self.module.time, "process_time", return_value=2.5):
                    self.assertEqual(self.module.sample_process_usage(),
                                     {"cpu_seconds": 2.5, "rss_bytes": 24576})
                    succeeded[0] = False
                    self.assertEqual(self.module.sample_process_usage(),
                                     {"cpu_seconds": 2.5, "rss_bytes": None})
        # ctypes retains POINTER types: a fresh structure on every periodic
        # sample would itself cause unbounded diagnostic memory growth.
        self.assertEqual(len(counter_types), 1)

    def test_unsupported_or_unreadable_memory_is_null_without_losing_cpu(self):
        for system in ("linux", "darwin"):
            with patch.object(self.module.sys, "platform", system):
                with patch.object(self.module.Path, "read_text", side_effect=OSError("PRIVATE")):
                    with patch.object(self.module.time, "process_time", return_value=0.5):
                        self.assertEqual(self.module.sample_process_usage(),
                                         {"cpu_seconds": 0.5, "rss_bytes": None})


class RuntimeEnvironmentTests(_ModuleTest):
    def environment_at(self, folder, *, frozen=False):
        module_file = Path(folder) / "DyberPet" / "assistant" / "trial_records.py"
        with patch.object(self.module, "__file__", str(module_file)):
            with patch.object(self.module.sys, "frozen", frozen, create=True):
                with patch.object(self.module.sys, "executable", str(Path(folder) / "DyberPet.exe")):
                    return self.module.runtime_environment()

    def test_existing_build_commit_is_labeled_checkout_and_free_text_is_excluded(self):
        for frozen, candidate in ((False, "linux-x86_64-ci-review"),
                                  (True, "portable-ci-review")):
            with tempfile.TemporaryDirectory() as folder:
                (Path(folder) / "BUILD_INFO.json").write_text(json.dumps({
                    "source_commit": "a" * 40, "candidate": candidate,
                    "note": "PRIVATE /home/name", "environment": "PRIVATE",
                    "optional_services": ["PRIVATE"], "voice": "PRIVATE"}), encoding="utf-8")
                result = self.environment_at(folder, frozen=frozen)
            self.assertEqual(result["checkout_commit"], "a" * 40)
            self.assertNotIn("source_commit", result)
            self.assertEqual(result["candidate"], candidate)
            self.assertEqual(result["build_info_status"], "valid")
            self.assertEqual(result["mode"], "frozen" if frozen else "source")
            self.assertNotIn("PRIVATE", json.dumps(result))

    def test_missing_damaged_and_oversized_build_metadata_are_explicit(self):
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(self.environment_at(folder)["build_info_status"], "missing")
            target = Path(folder) / "BUILD_INFO.json"
            for content in ("{broken", "[]", json.dumps({"source_commit": "PRIVATE"}),
                            " " * 17000):
                target.write_text(content, encoding="utf-8")
                result = self.environment_at(folder)
                self.assertEqual(result["build_info_status"], "invalid")
                self.assertIsNone(result["checkout_commit"])
                self.assertNotIn("PRIVATE", json.dumps(result))

    def test_versions_and_architecture_are_allowlisted_without_importing_qt(self):
        missing = self.module.metadata.PackageNotFoundError("PySide6")
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(self.module.platform, "machine", return_value="/home/PRIVATE"):
                with patch.dict(self.module.sys.modules, {"PySide6": None, "PySide6.QtCore": None}):
                    with patch.object(self.module.metadata, "version", side_effect=missing):
                        result = self.environment_at(folder)
        self.assertIsNone(result["architecture"])
        self.assertIsNone(result["qt_version"])
        self.assertIsNone(result["pyside_version"])
        self.assertNotIn("PRIVATE", json.dumps(result))


class ReportExportTests(_ModuleTest):
    def report(self):
        recorder = self.module.TrialRecorder(
            clock=lambda: 10, sampler=lambda: {}, environment={})
        run = recorder.begin("chat")
        recorder.observe(run, result_chars=4)
        recorder.finish(run, "completed")
        return recorder.snapshot()

    def test_export_rebuilds_all_levels_of_whitelist_and_removes_nonfinite_numbers(self):
        report = self.report()
        report["PRIVATE"] = "PRIVATE prompt /home/name"
        report["environment"].update({"hostname": "PRIVATE", "qt_version": "PRIVATE",
                                      "checkout_commit": "PRIVATE", "system": "PRIVATE"})
        report["feedback"].update({"notes": "PRIVATE", "speech": "PRIVATE"})
        report["limitations"] = ["PRIVATE"]
        report["observations"][0].update({"reply": "PRIVATE", "error_code": "PRIVATE",
                                          "elapsed_ms": float("nan"), "rss_max_bytes": True})
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "diagnostic.json"
            self.module.export_report(target, report)
            payload = target.read_bytes()
        self.assertLessEqual(len(payload), 65536)
        self.assertNotIn(b"PRIVATE", payload)
        result = json.loads(payload)
        self.assertEqual(set(result), {"schema_version", "environment", "observations",
                                       "feedback", "limitations"})
        self.assertIsNone(result["observations"][0]["elapsed_ms"])
        self.assertIsNone(result["observations"][0]["rss_max_bytes"])
        self.assertEqual(result["feedback"]["speech"], "not_checked")
        self.assertTrue(result["limitations"])

    def test_export_never_overwrites_existing_or_symbolic_link_destinations(self):
        report = self.report()
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "diagnostic.json"
            target.write_text("KEEP", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                self.module.export_report(target, report)
            self.assertEqual(target.read_text(encoding="utf-8"), "KEEP")
            link = Path(folder) / "link.json"
            try:
                link.symlink_to(target)
            except OSError:
                return  # Windows may not grant permission to create test links.
            with self.assertRaises(FileExistsError):
                self.module.export_report(link, report)
            self.assertEqual(target.read_text(encoding="utf-8"), "KEEP")

    def test_invalid_or_oversized_export_creates_no_file(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "diagnostic.json"
            for report in (None, {"schema_version": 2}, {"schema_version": True},
                           {"schema_version": 1, "observations": [None]}):
                with self.assertRaises(ValueError):
                    self.module.export_report(target, report)
                self.assertFalse(target.exists())
            with patch.object(self.module, "MAX_REPORT_BYTES", 64):
                with self.assertRaises(ValueError):
                    self.module.export_report(target, self.report())
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
