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
        pulse_hosts = [
            (index, host) for index, host in enumerate(hosts)
            if isinstance(host, dict) and "pulse" in str(host.get("name", "")).lower()
        ]
        self.assertEqual(len(pulse_hosts), 1, "PortAudio must expose exactly one PulseAudio Host API")
        host_index, host = pulse_hosts[0]
        default_input = host.get("default_input_device")
        self.assertIsInstance(default_input, int, "PulseAudio Host API has no default input device")
        self.assertGreaterEqual(default_input, 0)
        device = sd.query_devices(default_input, "input")
        self.assertIsInstance(device, dict)
        self.assertEqual(device.get("hostapi"), host_index)
        host_api = str(host.get("name", ""))
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
