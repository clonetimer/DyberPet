"""Real PortAudio capture through a PulseAudio null source; no physical microphone required."""
import importlib.util
import os
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
        devices = sd.query_devices()
        candidates = []
        for device in devices:
            if not isinstance(device, dict) or device.get("max_input_channels", 0) < 1:
                continue
            host_index = device.get("hostapi")
            if not isinstance(host_index, int) or not 0 <= host_index < len(hosts):
                continue
            host_name = str(hosts[host_index].get("name", ""))
            device_name = str(device.get("name", ""))
            if "pulse" in host_name.lower() or "pulse" in device_name.lower():
                candidates.append((device_name, host_name))
        self.assertTrue(candidates, "PortAudio does not expose the PulseAudio input source")
        name, host_api = candidates[0]
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
