"""Offline assistant readiness checking is read-only and never starts devices."""
from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from DyberPet.assistant.readiness import inspect_readiness, readiness_text, _local_http


class ReadinessTests(unittest.TestCase):
    def test_no_microphone_network_or_file_writes_for_default_missing_deps(self):
        seen = []
        def dependency(name):
            seen.append(name)
            return False
        report = inspect_readiness(llm_endpoint="https://example.com", llm_model="model",
                                   dependency_lookup=dependency, directory_check=lambda p: False)
        self.assertEqual([x["status"] for x in report["checks"]],
                         ["needs_setup", "needs_setup", "needs_setup", "disabled"])
        self.assertFalse(report["network_accessed"])
        self.assertFalse(report["microphone_accessed"])
        self.assertFalse(report["writes_performed"])
        self.assertEqual(set(seen), {"pyttsx3", "vosk"})

    def test_configured_features_do_not_claim_actual_device_tests(self):
        with tempfile.TemporaryDirectory() as d:
            report = inspect_readiness(voice_model=d,
                                       llm_endpoint="http://127.0.0.1:1234",
                                       llm_model="local-model",
                                       ppl_enabled=True,
                                       ppl_endpoint="http://localhost:8790",
                                       dependency_lookup=lambda x: True)
        self.assertTrue(all(x["status"] == "configured" for x in report["checks"]))
        wording = readiness_text(report)
        self.assertIn("不联网、不录音", wording)
        self.assertIn("未连接验证", wording)
        self.assertIn("未访问麦克风", wording)

    def test_remote_or_url_confusion_not_claimed_loopback(self):
        for endpoint in ("http://example.com:1234", "https://127.0.0.1:1234",
                         "http://127.0.0.1.evil.com:1234", "http://user@localhost:1234",
                         "http://localhost:1234/v1/models", "http://localhost:abc",
                         "file:///tmp/ppl", ""):
            self.assertFalse(_local_http(endpoint), endpoint)
        self.assertTrue(_local_http("http://[::1]:8790"))

    def test_empty_model_folder_and_missing_tts_are_non_fatal(self):
        report = inspect_readiness(voice_model="", llm_endpoint="http://127.0.0.1:1234",
                                   llm_model="", ppl_enabled=False,
                                   dependency_lookup=lambda x: x != "pyttsx3")
        self.assertEqual(report["checks"][0]["status"], "needs_setup")
        self.assertEqual(report["checks"][1]["status"], "needs_setup")
        self.assertEqual(report["checks"][2]["status"], "needs_setup")


if __name__ == "__main__":
    unittest.main()
