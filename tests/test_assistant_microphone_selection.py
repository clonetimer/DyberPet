"""Chosen microphone identity through all production capture entry points."""
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from DyberPet.assistant import voice, voice_devices, voice_turn


_SELECTION = {"name": "USB Mic", "host_api": "Windows WASAPI"}
_KINDS = ("once", "continuous", "turn")


def _module(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


def _device(name="USB Mic", *, index=0, hostapi=0, inputs=1):
    return {
        "name": name, "index": index, "hostapi": hostapi,
        "max_input_channels": inputs, "max_output_channels": 0,
        "default_low_input_latency": 0.01, "default_low_output_latency": 0.01,
        "default_high_input_latency": 0.1, "default_high_output_latency": 0.1,
        "default_samplerate": 48000.0,
    }


class _CaptureBoundary:
    def __init__(self, *, devices=None, stop_at=None, fail_at=None):
        self.devices = [_device(index=7)] if devices is None else devices
        self.hosts = [
            {"name": "Windows WASAPI", "devices": [0, 7],
             "default_input_device": 0, "default_output_device": -1},
            {"name": "MME", "devices": [1],
             "default_input_device": 1, "default_output_device": -1},
        ]
        self.stop = threading.Event()
        self.stop_at = stop_at
        self.fail_at = fail_at
        self.stop_after_read = False
        self.complete = True
        self.events = []
        self.threads = []
        self.streams = []
        self.stream_options = []
        self.recognizers = []
        self.on_model = None

    def record(self, event):
        self.events.append(event)
        self.threads.append(threading.get_ident())
        if event == self.stop_at:
            self.stop.set()
        if event == self.fail_at:
            raise OSError("native failure at " + event)

    def query_devices(self):
        self.record("devices")
        return self.devices

    def query_hostapis(self):
        self.record("hostapis")
        return self.hosts

    def model(self, path):
        self.record("model")
        if self.on_model is not None:
            self.on_model()
        return object()

    def recognizer(self, model, sample_rate):
        self.record("recognizer")
        result = _Recognizer(self, model, sample_rate)
        self.recognizers.append(result)
        return result

    def stream(self, **options):
        self.stream_options.append(options)
        self.record("stream")
        result = _Stream(self)
        self.streams.append(result)
        return result

    def modules(self):
        return {
            "sounddevice": _module("sounddevice", query_devices=self.query_devices,
                                   query_hostapis=self.query_hostapis,
                                   RawInputStream=self.stream),
            "vosk": _module("vosk", Model=self.model, KaldiRecognizer=self.recognizer),
        }


class _Recognizer:
    def __init__(self, boundary, model, sample_rate):
        self.boundary = boundary
        self.model = model
        self.sample_rate = sample_rate

    def AcceptWaveform(self, audio):
        self.boundary.record("accept")
        return self.boundary.complete

    def Result(self):
        self.boundary.record("result")
        return json.dumps({"text": "完整一句"})

    def PartialResult(self):
        return json.dumps({"partial": "未完"})

    def FinalResult(self):
        self.boundary.record("final")
        return json.dumps({"text": "手动收尾"})


class _Stream:
    def __init__(self, boundary):
        self.boundary = boundary
        self.closed = False

    def __enter__(self):
        self.boundary.record("enter")
        return self

    def __exit__(self, *_args):
        self.closed = True
        self.boundary.record("exit")

    def close(self):
        self.closed = True
        self.boundary.record("close")

    def read(self, frames):
        self.boundary.record("read")
        if self.boundary.stop_after_read:
            self.boundary.stop.set()
        return b"\x00" * frames * 2, False


class MicrophoneSelectionTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def capture(self, kind, boundary, *, microphone=_SELECTION, recognizer=None,
                **options):
        if kind == "continuous":
            boundary.complete = False
            boundary.stop_after_read = True
        with patch.dict(sys.modules, boundary.modules()):
            try:
                if kind == "once":
                    return voice.recognize_once(self.folder, seconds=0.5,
                                                microphone=microphone, **options)
                if kind == "continuous":
                    return voice.recognize_until_stopped(
                        self.folder, boundary.stop, microphone=microphone,
                        max_seconds=1.0, **options)
                recognizer = recognizer or voice_turn.VoiceTurnRecognizer(self.folder)
                return recognizer.listen(boundary.stop, microphone=microphone,
                                         max_seconds=1.0, **options)
            except TypeError as exc:
                if "unexpected keyword argument 'microphone'" in str(exc):
                    self.fail(kind + " capture does not accept microphone selection")
                raise

    def test_all_entry_points_capture_from_the_same_exact_selected_identity(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary(devices=[
                    _device("Other", index=0), _device(index=1, hostapi=1),
                    _device(index=7)])
                result = self.capture(kind, boundary)
                self.assertEqual(result, "完整一句" if kind == "turn" else "手动收尾")
                self.assertEqual(boundary.stream_options, [{
                    "samplerate": 16000, "blocksize": 4000, "channels": 1,
                    "dtype": "int16", "device": 7,
                }])
                self.assertTrue(boundary.streams[0].closed)
                self.assertLess(boundary.events.index("hostapis"),
                                boundary.events.index("stream"))

    def test_system_default_keeps_existing_stream_options_without_catalog_queries(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary(fail_at="devices")
                self.capture(kind, boundary, microphone=None)
                self.assertNotIn("devices", boundary.events)
                self.assertNotIn("hostapis", boundary.events)
                self.assertEqual(boundary.stream_options, [{
                    "samplerate": 16000, "blocksize": 4000,
                    "channels": 1, "dtype": "int16",
                }])

    def test_current_device_index_is_resolved_for_each_new_capture(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary()
                recognizer = voice_turn.VoiceTurnRecognizer(self.folder)
                self.capture(kind, boundary, recognizer=recognizer)
                boundary.stop.clear()
                boundary.devices = [_device(index=12)]
                self.capture(kind, boundary, recognizer=recognizer)
                self.assertEqual([options["device"] for options in boundary.stream_options],
                                 [7, 12])
                self.assertEqual(boundary.events.count("devices"), 2)
                self.assertEqual(boundary.events.count("model"), 1 if kind == "turn" else 2)
                self.assertTrue(all(stream.closed for stream in boundary.streams))

    def test_lookup_after_model_load_observes_renumbered_device(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary()
                boundary.on_model = lambda: setattr(boundary, "devices", [_device(index=19)])
                self.capture(kind, boundary)
                self.assertEqual(boundary.stream_options[0]["device"], 19)
                self.assertLess(boundary.events.index("model"), boundary.events.index("devices"))

    def test_missing_ambiguous_and_output_only_selection_never_opens_any_stream(self):
        cases = [[], [_device(index=0), _device(index=7)],
                 [_device(inputs=0)], [_device(hostapi=1)]]
        for kind in _KINDS:
            for entries in cases:
                with self.subTest(kind=kind, entries=entries):
                    boundary = _CaptureBoundary(devices=entries)
                    with self.assertRaises(voice.VoiceUnavailable):
                        self.capture(kind, boundary)
                    self.assertNotIn("stream", boundary.events)
                    self.assertNotIn("read", boundary.events)
                    self.assertNotIn("final", boundary.events)

    def test_invalid_saved_selection_never_falls_back_to_default_capture(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary()
                with self.assertRaises(voice.VoiceUnavailable):
                    self.capture(kind, boundary, microphone={"index": 7})
                self.assertNotIn("stream", boundary.events)

    def test_pre_cancelled_listening_skips_model_and_device_resolution(self):
        for kind in ("continuous", "turn"):
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary()
                boundary.stop.set()
                self.assertEqual(self.capture(kind, boundary, microphone={}), "")
                self.assertEqual(boundary.events, [])

    def test_cancel_during_selected_device_lookup_never_opens_stream_or_emits_ready(self):
        for kind in ("continuous", "turn"):
            for stop_at in ("devices", "hostapis"):
                with self.subTest(kind=kind, stop_at=stop_at):
                    boundary = _CaptureBoundary(stop_at=stop_at)
                    self.assertEqual(self.capture(
                        kind, boundary, on_ready=lambda: boundary.record("ready")), "")
                    self.assertNotIn("stream", boundary.events)
                    self.assertNotIn("ready", boundary.events)
                    self.assertNotIn("final", boundary.events)

    def test_cancelled_device_lookup_failure_remains_cancellation(self):
        for kind in ("continuous", "turn"):
            for stage in ("devices", "hostapis"):
                with self.subTest(kind=kind, stage=stage):
                    boundary = _CaptureBoundary(stop_at=stage, fail_at=stage)
                    self.assertEqual(self.capture(kind, boundary), "")
                    self.assertNotIn("stream", boundary.events)

    def test_cancel_after_stream_construction_closes_without_starting_capture(self):
        for kind in ("continuous", "turn"):
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary(stop_at="stream")
                self.assertEqual(self.capture(
                    kind, boundary, on_ready=lambda: boundary.record("ready")), "")
                self.assertTrue(boundary.streams[0].closed)
                self.assertNotIn("enter", boundary.events)
                self.assertNotIn("ready", boundary.events)
                self.assertNotIn("read", boundary.events)

    def test_failed_selected_stream_start_closes_constructed_stream(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary(fail_at="enter")
                with self.assertRaisesRegex(voice.VoiceUnavailable, "native failure at enter"):
                    self.capture(kind, boundary)
                self.assertTrue(boundary.streams[0].closed)
                self.assertEqual(boundary.events[-2:], ["enter", "close"])
                self.assertNotIn("read", boundary.events)

    def test_disappearance_after_resolution_fails_once_without_default_retry(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary(fail_at="stream")
                with self.assertRaisesRegex(voice.VoiceUnavailable, "native failure at stream"):
                    self.capture(kind, boundary)
                self.assertEqual([options["device"] for options in boundary.stream_options], [7])
                self.assertEqual(boundary.events.count("devices"), 1)
                self.assertNotIn("read", boundary.events)

    def test_read_failure_closes_selected_stream_and_does_not_finalize(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary(fail_at="read")
                with self.assertRaisesRegex(voice.VoiceUnavailable, "native failure at read"):
                    self.capture(kind, boundary)
                self.assertTrue(boundary.streams[0].closed)
                self.assertNotIn("final", boundary.events)

    def test_manual_stop_retains_final_text_but_conversation_stop_discards_it(self):
        for kind, expected in (("continuous", "手动收尾"), ("turn", "")):
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary(stop_at="read")
                self.assertEqual(self.capture(kind, boundary), expected)
                self.assertEqual("final" in boundary.events, kind == "continuous")
                self.assertTrue(boundary.streams[0].closed)

    def test_custom_sample_rate_reaches_both_recognizer_and_selected_stream(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary()
                self.capture(kind, boundary, sample_rate=8000)
                self.assertEqual(boundary.recognizers[0].sample_rate, 8000)
                self.assertEqual(boundary.stream_options[0]["samplerate"], 8000)
                self.assertEqual(boundary.stream_options[0]["device"], 7)

    def test_selected_device_query_and_capture_remain_on_calling_worker(self):
        for kind in _KINDS:
            with self.subTest(kind=kind):
                boundary = _CaptureBoundary()
                outcome = []

                def capture_on_worker():
                    try:
                        outcome.append(self.capture(kind, boundary))
                    except BaseException as exc:
                        outcome.append(exc)

                worker = threading.Thread(target=capture_on_worker)
                worker.start()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual(outcome, ["完整一句" if kind == "turn" else "手动收尾"])
                self.assertEqual(set(boundary.threads), {worker.ident})
                self.assertNotEqual(worker.ident, threading.get_ident())

    def test_public_voice_error_type_catches_device_boundary_errors(self):
        try:
            voice_devices.resolve_microphone({}, object())
        except Exception as exc:
            self.assertIsInstance(exc, voice.VoiceUnavailable)
        else:
            self.fail("Invalid selection did not produce a catchable voice error")


if __name__ == "__main__":
    unittest.main()
