"""Audio option metadata and exact device resolution at native boundaries."""
import builtins
import importlib
import sys
import threading
import unittest
from dataclasses import FrozenInstanceError
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


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


def _host(name="Windows WASAPI", *, devices=(0,)):
    return {"name": name, "devices": list(devices),
            "default_input_device": 0, "default_output_device": -1}


def _voice(voice_id="voice-zh", name="中文", languages=None):
    return SimpleNamespace(id=voice_id, name=name,
                           languages=["zh-CN"] if languages is None else languages,
                           gender=None, age=None)


class _CatalogBoundary:
    """Only replace driver imports, device queries and native engine ownership."""

    def __init__(self, *, devices=None, hosts=None, voices=None, stop=None,
                 stop_at=None, fail_at=None):
        self.devices = [_device()] if devices is None else devices
        self.hosts = [_host()] if hosts is None else hosts
        self.voices = [_voice()] if voices is None else voices
        self.stop = threading.Event() if stop is None else stop
        self.stop_at = stop_at
        self.fail_at = fail_at
        self.events = []
        self.threads = []
        self.sd = _module("sounddevice", query_devices=self.query_devices,
                          query_hostapis=self.query_hostapis,
                          RawInputStream=self.forbidden,
                          _terminate=self.forbidden, _initialize=self.forbidden)
        self.tts = _module("pyttsx3", init=self.init)

    def record(self, name):
        self.events.append(name)
        self.threads.append(threading.get_ident())
        if name == self.stop_at:
            self.stop.set()
        if name == self.fail_at:
            raise OSError("native failure at " + name)

    def forbidden(self, *_args, **_kwargs):
        raise AssertionError("Catalog inspection must not record, speak or reset PortAudio")

    def query_devices(self):
        self.record("devices")
        return self.devices

    def query_hostapis(self):
        self.record("hostapis")
        return self.hosts

    def init(self):
        self.record("tts-init")
        return _Engine(self)

    def modules(self):
        return {"sounddevice": self.sd, "pyttsx3": self.tts, "vosk": None}


class _Engine:
    def __init__(self, boundary):
        self.boundary = boundary

    def getProperty(self, name):
        if name != "voices":
            raise AssertionError("Inspection queried a non-catalog speech property")
        self.boundary.record("voices")
        return self.boundary.voices

    def stop(self):
        self.boundary.record("tts-stop")

    def say(self, *_args, **_kwargs):
        self.boundary.forbidden()


class VoiceDeviceTests(unittest.TestCase):
    def setUp(self):
        try:
            self.devices = importlib.import_module("DyberPet.assistant.voice_devices")
        except ModuleNotFoundError as exc:
            if exc.name != "DyberPet.assistant.voice_devices":
                raise
            self.fail("Audio option inspection and exact microphone selection are missing")

    def inspect(self, boundary, **kwargs):
        with patch.dict(sys.modules, boundary.modules()):
            return self.devices.inspect_audio_options(**kwargs)

    def test_import_does_not_initialize_optional_audio(self):
        original = builtins.__import__

        def import_without_audio(name, *args, **kwargs):
            if name.split(".")[0] in {"sounddevice", "pyttsx3", "vosk"}:
                raise AssertionError("Audio was imported before explicit inspection")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_audio):
            importlib.reload(self.devices)

    def test_inspection_returns_only_inputs_with_exact_host_api_identity(self):
        boundary = _CatalogBoundary(
            devices=[_device(index=0), _device(index=1, inputs=0),
                     _device(index=2, hostapi=1)],
            hosts=[_host(devices=(0, 1)), _host("MME", devices=(2,))])
        result = self.inspect(boundary)
        self.assertEqual([(mic.name, mic.host_api, mic.index)
                          for mic in result.microphones],
                         [("USB Mic", "Windows WASAPI", 0), ("USB Mic", "MME", 2)])
        self.assertTrue(result.microphone_message)
        self.assertTrue(result.voice_message)
        self.assertEqual(boundary.events, ["devices", "hostapis", "tts-init",
                                           "voices", "tts-stop"])

    def test_metadata_is_frozen_plain_and_detached_from_driver_objects(self):
        boundary = _CatalogBoundary()
        result = self.inspect(boundary)
        self.assertIsInstance(result.microphones, tuple)
        self.assertIsInstance(result.voices, tuple)
        self.assertEqual(result.voices[0].languages, ("zh-CN",))
        boundary.devices[0]["name"] = "changed"
        boundary.voices[0].languages.append("changed")
        self.assertEqual(result.microphones[0].name, "USB Mic")
        self.assertEqual(result.voices[0].languages, ("zh-CN",))
        for value, attribute in ((result, "voices"),
                                 (result.microphones[0], "name"),
                                 (result.voices[0], "id")):
            with self.subTest(record=type(value).__name__):
                with self.assertRaises(FrozenInstanceError):
                    setattr(value, attribute, "replacement")

    def test_voice_metadata_decodes_language_tags_and_falls_back_to_id_for_name(self):
        boundary = _CatalogBoundary(voices=[
            _voice("en-id", None, [b"\x05en-US", "en-GB", None, b"\xff"]),
            _voice("zh-id", "中文声线", []),
        ])
        result = self.inspect(boundary)
        self.assertEqual([(voice.id, voice.name, voice.languages) for voice in result.voices],
                         [("en-id", "en-id", ("en-US", "en-GB")),
                          ("zh-id", "中文声线", ())])

    def test_system_default_resolution_does_not_query_any_devices(self):
        self.assertIsNone(self.devices.resolve_microphone(None, object()))

    def test_resolution_uses_current_index_each_time_not_saved_or_cached_index(self):
        boundary = _CatalogBoundary()
        selection = {"name": "USB Mic", "host_api": "Windows WASAPI", "index": 99}
        self.assertEqual(self.devices.resolve_microphone(selection, boundary.sd), 0)
        boundary.devices = [_device("Other", index=0), _device(index=7)]
        self.assertEqual(self.devices.resolve_microphone(selection, boundary.sd), 7)
        self.assertEqual(boundary.events.count("devices"), 2)

    def test_same_name_in_another_host_api_is_not_ambiguous(self):
        boundary = _CatalogBoundary(
            devices=[_device(index=0), _device(index=3, hostapi=1)],
            hosts=[_host(), _host("MME", devices=(3,))])
        self.assertEqual(self.devices.resolve_microphone(
            {"name": "USB Mic", "host_api": "MME"}, boundary.sd), 3)

    def test_missing_output_only_and_partial_name_never_fall_back(self):
        cases = [[], [_device(inputs=0)], [_device("USB Mic Extended")]]
        for entries in cases:
            with self.subTest(entries=entries):
                boundary = _CatalogBoundary(devices=entries)
                with self.assertRaises(self.devices.VoiceUnavailable):
                    self.devices.resolve_microphone(
                        {"name": "USB Mic", "host_api": "Windows WASAPI"}, boundary.sd)

    def test_duplicate_exact_identity_is_rejected_instead_of_selecting_first(self):
        boundary = _CatalogBoundary(devices=[_device(index=0), _device(index=9)])
        with self.assertRaises(self.devices.VoiceUnavailable):
            self.devices.resolve_microphone(
                {"name": "USB Mic", "host_api": "Windows WASAPI"}, boundary.sd)

    def test_malformed_duplicate_cannot_turn_ambiguous_identity_into_unique_match(self):
        boundary = _CatalogBoundary(devices=[_device(index=0), _device(index="9")])
        with self.assertRaises(self.devices.VoiceUnavailable):
            self.devices.resolve_microphone(
                {"name": "USB Mic", "host_api": "Windows WASAPI"}, boundary.sd)

    def test_identity_whitespace_is_preserved_for_exact_matching(self):
        boundary = _CatalogBoundary(devices=[_device(" USB Mic ")])
        self.assertEqual(self.devices.resolve_microphone(
            {"name": " USB Mic ", "host_api": "Windows WASAPI"}, boundary.sd), 0)
        with self.assertRaises(self.devices.VoiceUnavailable):
            self.devices.resolve_microphone(
                {"name": "USB Mic", "host_api": "Windows WASAPI"}, boundary.sd)

    def test_invalid_selection_is_rejected_before_querying_driver(self):
        cases = ["USB Mic", 0, False, [], {}, {"name": "USB Mic"},
                 {"name": " ", "host_api": "MME"},
                 {"name": "x" * 257, "host_api": "MME"},
                 {"name": "USB Mic", "host_api": "x" * 129},
                 {"name": "USB Mic", "host_api": 0}]
        for selection in cases:
            with self.subTest(selection=selection):
                with self.assertRaises(self.devices.VoiceUnavailable):
                    self.devices.resolve_microphone(selection, object())

    def test_microphone_failure_preserves_installed_voice_options(self):
        boundary = _CatalogBoundary(fail_at="devices")
        result = self.inspect(boundary)
        self.assertEqual(result.microphones, ())
        self.assertEqual([voice.id for voice in result.voices], ["voice-zh"])
        self.assertIn("失败", result.microphone_message)
        self.assertEqual(boundary.events[-1], "tts-stop")

    def test_voice_query_failure_preserves_microphones_and_stops_engine(self):
        boundary = _CatalogBoundary(fail_at="voices")
        result = self.inspect(boundary)
        self.assertEqual([mic.index for mic in result.microphones], [0])
        self.assertEqual(result.voices, ())
        self.assertIn("失败", result.voice_message)
        self.assertEqual(boundary.events[-1], "tts-stop")

    def test_empty_catalogs_are_reported_without_inventing_default_items(self):
        result = self.inspect(_CatalogBoundary(devices=[], voices=[]))
        self.assertEqual(result.microphones, ())
        self.assertEqual(result.voices, ())
        self.assertIn("未", result.microphone_message)
        self.assertIn("未", result.voice_message)

    def test_missing_optional_modules_are_independent_results(self):
        boundary = _CatalogBoundary()
        for absent in ("sounddevice", "pyttsx3"):
            with self.subTest(absent=absent):
                modules = boundary.modules()
                modules[absent] = None
                with patch.dict(sys.modules, modules):
                    result = self.devices.inspect_audio_options()
                if absent == "sounddevice":
                    self.assertEqual(result.microphones, ())
                    self.assertEqual(len(result.voices), 1)
                    self.assertIn("sounddevice", result.microphone_message)
                else:
                    self.assertEqual(len(result.microphones), 1)
                    self.assertEqual(result.voices, ())
                    self.assertIn("pyttsx3", result.voice_message)

    def test_pre_cancel_does_not_import_drivers(self):
        stop = threading.Event()
        stop.set()
        original = builtins.__import__

        def no_audio(name, *args, **kwargs):
            if name in {"sounddevice", "pyttsx3"}:
                raise AssertionError("Cancelled inspection imported a driver")
            return original(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=no_audio):
            self.assertIsNone(self.devices.inspect_audio_options(stop))

    def test_cancel_during_device_query_does_not_query_hostapis_or_initialize_tts(self):
        boundary = _CatalogBoundary(stop_at="devices")
        self.assertIsNone(self.inspect(boundary, stop_event=boundary.stop))
        self.assertEqual(boundary.events, ["devices"])

    def test_cancel_after_microphones_does_not_initialize_tts(self):
        boundary = _CatalogBoundary(stop_at="hostapis")
        self.assertIsNone(self.inspect(boundary, stop_event=boundary.stop))
        self.assertEqual(boundary.events, ["devices", "hostapis"])

    def test_cancel_during_tts_initialization_skips_query_and_closes_created_engine(self):
        boundary = _CatalogBoundary(stop_at="tts-init")
        self.assertIsNone(self.inspect(boundary, stop_event=boundary.stop))
        self.assertEqual(boundary.events, ["devices", "hostapis", "tts-init", "tts-stop"])

    def test_cancel_during_voice_query_or_cleanup_discards_all_metadata(self):
        for stop_at in ("voices", "tts-stop"):
            with self.subTest(stop_at=stop_at):
                boundary = _CatalogBoundary(stop_at=stop_at)
                self.assertIsNone(self.inspect(boundary, stop_event=boundary.stop))
                self.assertEqual(boundary.events[-1], "tts-stop")

    def test_native_calls_and_engine_cleanup_stay_on_calling_worker(self):
        boundary = _CatalogBoundary()
        values = []
        errors = []

        def inspect_on_worker():
            try:
                values.append((threading.get_ident(), self.inspect(boundary)))
            except BaseException as exc:
                errors.append(exc)

        worker = threading.Thread(target=inspect_on_worker)
        worker.start()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(len(values), 1)
        self.assertTrue(values[0][1].voices)
        self.assertEqual(set(boundary.threads), {values[0][0]})
        self.assertNotEqual(values[0][0], threading.get_ident())

    def test_invalid_stop_event_fails_before_loading_any_driver(self):
        for stop in (False, 1, object(), SimpleNamespace(is_set=True)):
            with self.subTest(stop=stop):
                with patch.dict(sys.modules, {"sounddevice": None, "pyttsx3": None}):
                    with self.assertRaises(self.devices.VoiceUnavailable):
                        self.devices.inspect_audio_options(stop)

    def test_tts_initialization_failure_keeps_microphones_without_stopping_unknown_engine(self):
        boundary = _CatalogBoundary(fail_at="tts-init")
        result = self.inspect(boundary)
        self.assertEqual(len(result.microphones), 1)
        self.assertEqual(result.voices, ())
        self.assertIn("失败", result.voice_message)
        self.assertNotIn("tts-stop", boundary.events)

    def test_tts_cleanup_failure_is_reported_without_hiding_microphones(self):
        boundary = _CatalogBoundary(fail_at="tts-stop")
        result = self.inspect(boundary)
        self.assertEqual(len(result.microphones), 1)
        self.assertEqual(result.voices, ())
        self.assertIn("失败", result.voice_message)
        self.assertEqual(boundary.events[-1], "tts-stop")

    def test_cancellation_takes_precedence_over_native_and_cleanup_errors(self):
        for stop_at in ("devices", "hostapis", "tts-init", "voices", "tts-stop"):
            with self.subTest(stop_at=stop_at):
                boundary = _CatalogBoundary(stop_at=stop_at, fail_at=stop_at)
                self.assertIsNone(self.inspect(boundary, stop_event=boundary.stop))
                if stop_at in ("devices", "hostapis"):
                    self.assertNotIn("tts-init", boundary.events)
                if stop_at == "voices":
                    self.assertEqual(boundary.events[-1], "tts-stop")

    def test_selected_device_query_failure_is_a_voice_error(self):
        boundary = _CatalogBoundary(fail_at="hostapis")
        with self.assertRaises(self.devices.VoiceUnavailable):
            self.devices.resolve_microphone(
                {"name": "USB Mic", "host_api": "Windows WASAPI"}, boundary.sd)

    def test_malformed_device_records_do_not_become_selectable_options(self):
        boundary = _CatalogBoundary(devices=[
            _device(index=0), _device("x" * 257, index=1),
            _device(" ", index=2), _device("Bad API", index=3, hostapi=99),
            _device("Bad index", index=True),
            _device("Bad input", index=5, inputs=True), None,
        ])
        result = self.inspect(boundary)
        self.assertEqual([(mic.name, mic.index) for mic in result.microphones],
                         [("USB Mic", 0)])
        self.assertTrue(result.voices)
        self.assertIn("忽略", result.microphone_message)

    def test_exact_identity_limits_are_accepted_without_truncation(self):
        name, host_api, voice_id = "名" * 256, "A" * 128, "v" * 512
        boundary = _CatalogBoundary(devices=[_device(name)], hosts=[_host(host_api)],
                                    voices=[_voice(voice_id)])
        result = self.inspect(boundary)
        self.assertEqual(result.microphones[0].name, name)
        self.assertEqual(result.microphones[0].host_api, host_api)
        self.assertEqual(result.voices[0].id, voice_id)
        self.assertEqual(self.devices.resolve_microphone(
            {"name": name, "host_api": host_api}, boundary.sd), 0)

    def test_malformed_voice_id_is_omitted_not_truncated_into_valid_selection(self):
        boundary = _CatalogBoundary(voices=[
            _voice("valid"), _voice("v" * 513), _voice(""),
            _voice(42), object(),
        ])
        result = self.inspect(boundary)
        self.assertEqual([voice.id for voice in result.voices], ["valid"])
        self.assertIn("忽略", result.voice_message)
        self.assertEqual(boundary.events[-1], "tts-stop")

    def test_optional_display_metadata_is_bounded_and_stays_plain(self):
        boundary = _CatalogBoundary(voices=[_voice(
            "voice-id", "名" * 10000,
            ["zh-CN", "en-US", "x" * 10000] + [str(i) for i in range(100)])])
        voice = self.inspect(boundary).voices[0]
        self.assertIsInstance(voice.name, str)
        self.assertLessEqual(len(voice.name), 256)
        self.assertEqual(voice.languages[:2], ("zh-CN", "en-US"))
        self.assertLessEqual(len(voice.languages), 16)
        self.assertTrue(all(isinstance(tag, str) and len(tag) <= 64
                            for tag in voice.languages))

    def test_oversized_catalog_is_rejected_instead_of_hiding_late_duplicate_identity(self):
        entries = [_device("other-" + str(i), index=i) for i in range(1023)]
        entries.extend([_device(index=1023), _device(index=1024)])
        boundary = _CatalogBoundary(devices=entries)
        result = self.inspect(boundary)
        self.assertEqual(result.microphones, ())
        self.assertTrue(result.voices)
        with self.assertRaises(self.devices.VoiceUnavailable):
            self.devices.resolve_microphone(
                {"name": "USB Mic", "host_api": "Windows WASAPI"}, boundary.sd)

    def test_non_sequence_catalogs_are_reported_and_engine_is_cleaned_up(self):
        boundary = _CatalogBoundary(devices={"name": "not a device list"}, voices=object())
        result = self.inspect(boundary)
        self.assertEqual(result.microphones, ())
        self.assertEqual(result.voices, ())
        self.assertIn("失败", result.microphone_message)
        self.assertIn("失败", result.voice_message)
        self.assertEqual(boundary.events[-1], "tts-stop")

    def test_cancellation_during_driver_import_prevents_native_calls(self):
        for name in ("sounddevice", "pyttsx3"):
            with self.subTest(name=name):
                boundary = _CatalogBoundary()
                original = builtins.__import__

                def cancelling_import(import_name, *args, **kwargs):
                    result = original(import_name, *args, **kwargs)
                    if import_name == name:
                        boundary.stop.set()
                    return result

                with patch("builtins.__import__", side_effect=cancelling_import):
                    self.assertIsNone(self.inspect(boundary, stop_event=boundary.stop))
                if name == "sounddevice":
                    self.assertEqual(boundary.events, [])
                else:
                    self.assertEqual(boundary.events, ["devices", "hostapis"])


if __name__ == "__main__":
    unittest.main()
