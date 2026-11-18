"""Real PortAudio capture through the ALSA host API using an ALSA null PCM."""
import os
import sys
import threading
import unittest

from DyberPet.assistant.audio_probe import probe_microphone


@unittest.skipUnless(sys.platform.startswith("linux"), "ALSA integration is Linux-only")
class AlsaProbeIntegrationTests(unittest.TestCase):
    def test_alsa_null_pcm_is_opened_through_product_capture_path(self):
        if os.environ.get("DYBERPET_ALSA_INTEGRATION") != "1":
            self.skipTest("explicit ALSA integration environment is not enabled")
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
            if "alsa" in host_name.lower():
                candidates.append((str(device.get("name", "")), host_name))
        self.assertTrue(candidates, "PortAudio does not expose an ALSA input PCM")
        preferred = next((item for item in candidates if item[0] == "default"), candidates[0])
        name, host_api = preferred
        result = probe_microphone(
            threading.Event(),
            microphone={"name": name, "host_api": host_api},
            duration_seconds=0.25,
        )
        self.assertIsNotNone(result)
        self.assertGreaterEqual(result.frames, int(result.sample_rate * 0.25))
        self.assertGreaterEqual(result.peak, 0)
        self.assertGreaterEqual(result.rms, 0)


if __name__ == "__main__":
    unittest.main()
