"""Exercise real pyttsx3 voice IDs through the Linux eSpeak NG CLI without audio hardware."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import pyttsx3


class LinuxEspeakVoiceCompatibilityTests(unittest.TestCase):
    def test_every_pyttsx3_enumerated_voice_is_accepted_by_espeak_ng(self):
        executable = shutil.which("espeak-ng")
        self.assertIsNotNone(executable, "Linux eSpeak NG system command is required")
        engine = pyttsx3.init()
        try:
            voices = engine.getProperty("voices")
            voice_ids = [voice.id for voice in voices
                         if isinstance(getattr(voice, "id", None), str) and voice.id]
        finally:
            engine.stop()
        self.assertTrue(voice_ids, "pyttsx3 must expose at least one eSpeak voice")
        failures = []
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for index, voice_id in enumerate(voice_ids):
                output = root / ("voice-" + str(index) + ".wav")
                try:
                    result = subprocess.run(
                        [executable, "-v", voice_id, "-s", "155", "--stdin",
                         "-w", str(output)],
                        input="DyberPet voice compatibility check.".encode("utf-8"),
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                        timeout=10, check=False,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    failures.append((voice_id, type(exc).__name__))
                    continue
                if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
                    failures.append((voice_id, "exit=" + str(result.returncode)))
        self.assertEqual(failures, [], "eSpeak CLI rejected pyttsx3 voice IDs")
        self.assertGreater(len(voice_ids), 1, "expected a meaningful installed voice catalogue")


if __name__ == "__main__":
    unittest.main()
