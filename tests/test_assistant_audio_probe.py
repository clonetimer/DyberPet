"""Explicit microphone probe contracts; audio samples are never persisted."""
import struct
import threading
import unittest
from types import ModuleType
from unittest.mock import patch

from DyberPet.assistant.audio_probe import probe_microphone
from DyberPet.assistant.voice_errors import VoiceUnavailable


class _Stream:
    def __init__(self, *, samples, overflow=False, stop_event=None, stop_on_read=False):
        self.samples = samples
        self.overflow = overflow
        self.stop_event = stop_event
        self.stop_on_read = stop_on_read
        self.closed = False
        self.entered = False
        self.read_count = 0

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *_args):
        self.close()

    def read(self, frames):
        self.read_count += 1
        if self.stop_on_read and self.stop_event is not None:
            self.stop_event.set()
        values = (self.samples * ((frames + len(self.samples) - 1) // len(self.samples)))[:frames]
        return struct.pack("<" + "h" * frames, *values), self.overflow

    def close(self):
        self.closed = True


class AudioProbeTests(unittest.TestCase):
    def run_probe(self, stream, stop=None, **kwargs):
        module = ModuleType("sounddevice")
        module.RawInputStream = lambda **_options: stream
        module.query_devices = lambda: []
        module.query_hostapis = lambda: []
        event = threading.Event() if stop is None else stop
        with patch.dict("sys.modules", {"sounddevice": module}):
            result = probe_microphone(event, **kwargs)
        return result, event

    def test_captures_pcm_computes_levels_and_closes_stream(self):
        stream = _Stream(samples=[1000, -1000, 2000, -2000])
        result, _ = self.run_probe(stream, duration_seconds=0.25)
        self.assertEqual(result.frames, 4000)
        self.assertEqual(result.sample_rate, 16000)
        self.assertEqual(result.peak, 2000)
        self.assertEqual(result.clipped_samples, 0)
        self.assertGreater(result.rms, 1000)
        self.assertTrue(stream.closed)
        self.assertFalse(hasattr(result, "audio"))
        self.assertFalse(hasattr(result, "pcm"))

    def test_unsupported_16khz_falls_back_to_96khz_device_default_rate(self):
        stream = _Stream(samples=[1000, -1000])
        attempts = []
        module = ModuleType("sounddevice")
        module.query_devices = lambda *args, **kwargs: {"default_samplerate": 96000}
        def open_stream(**options):
            attempts.append(options["samplerate"])
            if options["samplerate"] == 16000:
                raise ValueError("Invalid sample rate")
            return stream
        module.RawInputStream = open_stream
        with patch.dict("sys.modules", {"sounddevice": module}):
            result = probe_microphone(threading.Event(), duration_seconds=0.25)
        self.assertEqual(attempts, [16000, 96000])
        self.assertEqual(result.sample_rate, 96000)
        self.assertEqual(result.frames, 24000)
        self.assertTrue(stream.closed)

    def test_reports_clear_error_when_all_supported_rates_are_rejected(self):
        module = ModuleType("sounddevice")
        module.query_devices = lambda *args, **kwargs: {"default_samplerate": 48000}
        attempts = []
        def reject(**options):
            attempts.append(options["samplerate"])
            raise ValueError("unsupported format")
        module.RawInputStream = reject
        with patch.dict("sys.modules", {"sounddevice": module}):
            with self.assertRaisesRegex(VoiceUnavailable, "不接受"):
                probe_microphone(threading.Event(), duration_seconds=0.25)
        self.assertEqual(attempts, [16000, 48000, 192000, 96000, 88200, 44100, 32000, 22050, 8000])

    def test_clipping_is_counted_without_retaining_samples(self):
        stream = _Stream(samples=[32767, -32768, 100])
        result, _ = self.run_probe(stream, duration_seconds=0.25)
        self.assertGreater(result.clipped_samples, 0)
        self.assertEqual(result.peak, 32768)

    def test_overflow_fails_and_closes_stream(self):
        stream = _Stream(samples=[500], overflow=True)
        with self.assertRaisesRegex(VoiceUnavailable, "溢出"):
            self.run_probe(stream, duration_seconds=0.25)
        self.assertTrue(stream.closed)

    def test_stop_during_read_discards_result_and_closes_stream(self):
        stop = threading.Event()
        stream = _Stream(samples=[500], stop_event=stop, stop_on_read=True)
        result, _ = self.run_probe(stream, stop, duration_seconds=0.25)
        self.assertIsNone(result)
        self.assertTrue(stream.closed)

    def test_stop_before_start_does_not_open_device(self):
        stop = threading.Event()
        stop.set()
        stream = _Stream(samples=[500])
        module = ModuleType("sounddevice")
        module.RawInputStream = lambda **_options: self.fail("stream must not open")
        with patch.dict("sys.modules", {"sounddevice": module}):
            self.assertIsNone(probe_microphone(stop))
        self.assertFalse(stream.entered)

    def test_invalid_duration_is_rejected(self):
        for value in (0, 0.1, 2.1, True, float("nan")):
            with self.subTest(value=value):
                with self.assertRaises(VoiceUnavailable):
                    probe_microphone(threading.Event(), duration_seconds=value)

    def test_missing_sounddevice_has_actionable_error(self):
        with patch.dict("sys.modules", {"sounddevice": None}):
            with self.assertRaisesRegex(VoiceUnavailable, "sounddevice"):
                probe_microphone(threading.Event())


if __name__ == "__main__":
    unittest.main()
