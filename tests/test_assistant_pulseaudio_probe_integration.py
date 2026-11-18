"""Real PortAudio capture through a PulseAudio null source; no physical microphone required."""
import importlib.util
import os
import subprocess
import sys
import threading
import unittest

from DyberPet.assistant.audio_probe import probe_microphone


@unittest.skipUnless(sys.platform.startswith("linux"), "PulseAudio integration is Linux-only")
class PulseAudioProbeIntegrationTests(unittest.TestCase):
    def test_selected_pulse_input_source_can_be_opened_and_captured(self):
        if os.environ.get("DYBERPET_PULSEAUDIO_INTEGRATION") != "1":
            self.skipTest("explicit PulseAudio integration environment is not enabled")
        if importlib.util.find_spec("sounddevice") is None:
            self.skipTest("sounddevice is installed only in the Linux audio integration environment")
        import sounddevice as sd

        hosts = sd.query_hostapis()
        default = subprocess.run(
            ["pactl", "get-default-source"], check=True, text=True,
            capture_output=True, timeout=5).stdout.strip()
        expected = os.environ.get("DYBERPET_EXPECTED_PULSE_SOURCE", "")
        self.assertTrue(expected, "CI must declare the exact PulseAudio source under test")
        self.assertEqual(default, expected, "PulseAudio default source is not the test source")
        default_input = sd.default.device[0]
        self.assertIsInstance(default_input, int, "PortAudio has no default input device")
        device = sd.query_devices(default_input, "input")
        self.assertIsInstance(device, dict)
        host_index = device.get("hostapi")
        self.assertIsInstance(host_index, int)
        self.assertTrue(0 <= host_index < len(hosts))
        host_api = str(hosts[host_index].get("name", ""))
        self.assertIn("pulse", host_api.lower(),
                      "PortAudio default input is not using the PulseAudio host API: " + host_api)
        name = str(device.get("name", ""))
        self.assertTrue(name, "PortAudio default PulseAudio input has no name")
        result = probe_microphone(
            threading.Event(),
            microphone={"name": name, "host_api": host_api},
            duration_seconds=0.25,
        )
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.frames, int(result.sample_rate * 0.25))
        self.assertIn(result.sample_rate, (8000, 16000, 22050, 32000, 44100, 48000,
                                          88200, 96000, 192000))
        self.assertGreaterEqual(result.peak, 0)
        self.assertGreaterEqual(result.rms, 0)


if __name__ == "__main__":
    unittest.main()
