"""Linux readiness must report the external eSpeak NG executable separately."""
import importlib.machinery
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from DyberPet.assistant.voice_readiness import inspect_voice_readiness


class LinuxTtsReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.model = Path(self.temp.name)
        (self.model / "am").mkdir()
        (self.model / "conf").mkdir()
        (self.model / "am/final.mdl").write_bytes(b"marker")
        (self.model / "conf/model.conf").write_text("marker", encoding="utf-8")

    def _inspect(self, executable):
        def find_spec(name):
            return importlib.machinery.ModuleSpec(name, loader=None)
        with patch("DyberPet.assistant.voice_readiness.sys.platform", "linux"), \
                patch("DyberPet.assistant.voice_readiness.importlib.util.find_spec",
                      side_effect=find_spec), \
                patch("DyberPet.assistant.voice_readiness.shutil.which",
                      return_value=executable):
            return inspect_voice_readiness(str(self.model))

    def test_missing_espeak_ng_is_not_reported_as_tts_ready(self):
        result = self._inspect(None)
        self.assertFalse(result.tts_ready)
        self.assertIn("apt install espeak-ng", result.tts_message)
        self.assertTrue(result.recognition_ready)

    def test_installed_espeak_ng_satisfies_linux_tts_prerequisite_only(self):
        result = self._inspect("/usr/bin/espeak-ng")
        self.assertTrue(result.tts_ready)
        self.assertIn("初检通过", result.tts_message)
        self.assertIn("尚未测试", result.tts_message)


if __name__ == "__main__":
    unittest.main()
