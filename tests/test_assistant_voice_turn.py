"""Single-utterance capture contracts at the optional audio driver boundary."""
import builtins
import importlib
import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

from DyberPet.assistant.voice import VoiceUnavailable


_DEFAULT_AUDIO = object()


def _module(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


def _response(value):
    return value if isinstance(value, str) else json.dumps(value)


class _AudioBoundary:
    """Replace native devices and Vosk only; keep the capture loop real."""

    def __init__(self, stop=None, *, turns=None, final=None, stop_at=None,
                 fail_at=None, audio=_DEFAULT_AUDIO, overflow=False):
        self.stop = stop if stop is not None else threading.Event()
        self.turns = turns if turns is not None else [[(True, {"text": "你好"})]]
        self.final = {"text": "未提交尾句"} if final is None else final
        self.stop_at = stop_at
        self.fail_at = fail_at
        self.audio = audio
        self.overflow = overflow
        self.events = []
        self.threads = []
        self.models = []
        self.recognizers = []
        self.streams = []
        self.after_read = None

    def record(self, event):
        self.events.append(event)
        self.threads.append(threading.get_ident())
        if self.stop_at == event:
            self.stop.set()
        if self.fail_at == event:
            raise OSError("driver failure at " + event)

    def model(self, path):
        self.record("model")
        self.model_path = path
        model = object()
        self.models.append(model)
        return model

    def recognizer(self, model, sample_rate):
        self.record("recognizer")
        index = len(self.recognizers)
        recognizer = _Recognizer(self, self.turns[index], model, sample_rate)
        self.recognizers.append(recognizer)
        return recognizer

    def stream(self, **kwargs):
        self.record("stream")
        stream = _Stream(self, kwargs)
        self.streams.append(stream)
        return stream

    def modules(self):
        return {
            "vosk": _module("vosk", Model=self.model,
                            KaldiRecognizer=self.recognizer),
            "sounddevice": _module("sounddevice", RawInputStream=self.stream),
        }


class _Recognizer:
    def __init__(self, driver, steps, model, sample_rate):
        self.driver = driver
        self.steps = iter(steps)
        self.model = model
        self.sample_rate = sample_rate
        self.audio = []

    def AcceptWaveform(self, audio):
        self.driver.record("accept")
        self.audio.append(audio)
        try:
            accepted, self.current = next(self.steps)
        except StopIteration:
            raise AssertionError("The recognizer read past the expected utterance")
        return accepted

    def PartialResult(self):
        self.driver.record("partial")
        return _response(self.current)

    def Result(self):
        self.driver.record("result")
        return _response(self.current)

    def FinalResult(self):
        self.driver.record("final")
        return _response(self.driver.final)


class _Stream:
    def __init__(self, driver, options):
        self.driver = driver
        self.options = options
        self.reads = []
        self.closed = False

    def __enter__(self):
        self.driver.record("enter")
        return self

    def __exit__(self, *_args):
        self.closed = True
        self.driver.record("exit")

    def close(self):
        self.driver.record("close")
        self.closed = True

    def read(self, frames):
        self.driver.record("read")
        self.reads.append(frames)
        if self.driver.after_read is not None:
            self.driver.after_read()
        payload = (b"\x00" * frames * 2 if self.driver.audio is _DEFAULT_AUDIO
                   else self.driver.audio)
        return payload, self.driver.overflow


class VoiceTurnTests(unittest.TestCase):
    def setUp(self):
        try:
            self.voice_turn = importlib.import_module("DyberPet.assistant.voice_turn")
        except ModuleNotFoundError as exc:
            if exc.name != "DyberPet.assistant.voice_turn":
                raise
            self.fail("Single-utterance voice recognition is not implemented")
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.folder = Path(folder.name)

    def listen(self, driver, **kwargs):
        recognizer = self.voice_turn.VoiceTurnRecognizer(self.folder)
        with patch.dict(sys.modules, driver.modules()):
            return recognizer.listen(driver.stop, **kwargs)

    def test_import_and_construction_do_not_import_audio_or_touch_devices(self):
        real_import = builtins.__import__

        def no_audio_import(name, *args, **kwargs):
            if name.split(".")[0] in {"vosk", "sounddevice", "pyttsx3"}:
                raise AssertionError("Audio dependencies were imported before listen")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=no_audio_import):
            module = importlib.reload(self.voice_turn)
            module.VoiceTurnRecognizer(self.folder / "not-installed")

    def test_first_nonempty_complete_result_ends_after_stream_closes(self):
        driver = _AudioBoundary(turns=[[
            (True, {"text": "  "}),
            (False, {"partial": "第一"}),
            (True, {"text": "  第一句  "}),
            (True, {"text": "不得读取第二句"}),
        ]])
        text = self.listen(driver)
        driver.record("returned")
        self.assertEqual(text, "第一句")
        self.assertEqual(len(driver.streams[0].reads), 3)
        self.assertTrue(driver.streams[0].closed)
        self.assertEqual(driver.events[-2:], ["exit", "returned"])
        self.assertNotIn("final", driver.events)

    def test_ready_runs_after_open_and_partial_updates_are_deduplicated(self):
        driver = _AudioBoundary(turns=[[
            (False, {"partial": "  你  "}),
            (False, {"partial": "你"}),
            (False, {"partial": ""}),
            (False, {"partial": "你好"}),
            (True, {"text": "你好呀"}),
        ]])
        partials = []
        result = self.listen(driver, on_partial=partials.append,
                             on_ready=lambda: driver.record("ready"))
        self.assertEqual(result, "你好呀")
        self.assertEqual(partials, ["你", "你好"])
        self.assertEqual(driver.events[:6],
                         ["model", "recognizer", "stream", "enter", "ready", "read"])
        self.assertEqual(driver.events.count("ready"), 1)
        self.assertEqual(driver.streams[0].options,
                         {"samplerate": 16000, "blocksize": 4000,
                          "channels": 1, "dtype": "int16"})

    def test_sequential_worker_turns_reuse_model_and_own_fresh_resources(self):
        driver = _AudioBoundary(turns=[[(True, {"text": "第一轮"})],
                                       [(True, {"text": "第二轮"})]])
        recognizer = self.voice_turn.VoiceTurnRecognizer(self.folder)
        results = []
        failures = []
        main_thread = threading.get_ident()

        def run():
            try:
                results.append(recognizer.listen(driver.stop))
            except BaseException as exc:
                failures.append(exc)

        with patch.dict(sys.modules, driver.modules()):
            for _ in range(2):
                worker = threading.Thread(target=run)
                worker.start()
                worker.join(2)
                self.assertFalse(worker.is_alive())
        self.assertEqual(failures, [])
        self.assertEqual(results, ["第一轮", "第二轮"])
        self.assertEqual(len(driver.models), 1)
        self.assertEqual(len(driver.recognizers), 2)
        self.assertIsNot(driver.recognizers[0], driver.recognizers[1])
        self.assertIs(driver.recognizers[0].model, driver.recognizers[1].model)
        self.assertEqual(driver.model_path, str(self.folder.resolve()))
        self.assertEqual(len(driver.streams), 2)
        self.assertIsNot(driver.streams[0], driver.streams[1])
        self.assertTrue(all(stream.closed for stream in driver.streams))
        self.assertNotIn(main_thread, driver.threads)

    def test_precancelled_turn_does_not_validate_model_or_import_audio(self):
        stop = threading.Event()
        stop.set()
        recognizer = self.voice_turn.VoiceTurnRecognizer(self.folder / "missing")
        with patch.dict(sys.modules, {"sounddevice": None, "vosk": None}):
            self.assertEqual(recognizer.listen(stop), "")

    def test_stop_during_preparation_does_not_open_microphone(self):
        for stage in ("model", "recognizer"):
            with self.subTest(stage=stage):
                driver = _AudioBoundary(stop_at=stage)
                self.assertEqual(self.listen(driver), "")
                self.assertNotIn("stream", driver.events)
                self.assertNotIn("final", driver.events)

    def test_stop_during_stream_open_closes_without_ready(self):
        for stage in ("stream", "enter"):
            with self.subTest(stage=stage):
                driver = _AudioBoundary(stop_at=stage)
                self.assertEqual(self.listen(
                    driver, on_ready=lambda: driver.record("ready")), "")
                self.assertTrue(driver.streams[0].closed)
                self.assertNotIn("ready", driver.events)
                self.assertNotIn("read", driver.events)

    def test_stop_after_stream_construction_closes_without_starting(self):
        driver = _AudioBoundary(stop_at="stream")
        self.assertEqual(self.listen(driver), "")
        self.assertTrue(driver.streams[0].closed)
        self.assertNotIn("enter", driver.events)
        self.assertNotIn("read", driver.events)

    def test_start_failure_explicitly_closes_stream_without_ready_or_capture(self):
        driver = _AudioBoundary(fail_at="enter")
        with self.assertRaisesRegex(VoiceUnavailable, "driver failure at enter"):
            self.listen(driver, on_ready=lambda: driver.record("ready"))
        self.assertTrue(driver.streams[0].closed)
        self.assertEqual(driver.events[-2:], ["enter", "close"])
        self.assertNotIn("ready", driver.events)
        self.assertNotIn("read", driver.events)

    def test_stop_discards_completed_or_pending_text_and_closes_stream(self):
        for stage in ("ready", "read", "accept", "result", "exit"):
            with self.subTest(stage=stage):
                driver = _AudioBoundary(stop_at=stage)
                text = self.listen(driver, on_ready=lambda: driver.record("ready"))
                self.assertEqual(text, "")
                self.assertTrue(driver.streams[0].closed)
                self.assertNotIn("final", driver.events)

    def test_stop_from_partial_callback_discards_tail_without_finalizing(self):
        driver = _AudioBoundary(turns=[[(False, {"partial": "不要发送"})]])
        partials = []

        def partial(text):
            partials.append(text)
            driver.stop.set()

        self.assertEqual(self.listen(driver, on_partial=partial), "")
        self.assertEqual(partials, ["不要发送"])
        self.assertTrue(driver.streams[0].closed)
        self.assertNotIn("final", driver.events)

    def test_audio_duration_limit_uses_final_text_after_stream_closes(self):
        driver = _AudioBoundary(
            turns=[[(False, {"partial": "最后"})]], final={"text": " 最后一句 "})
        self.assertEqual(self.listen(driver, max_seconds=0.25), "最后一句")
        self.assertEqual(driver.streams[0].reads, [4000])
        self.assertEqual(driver.events[-2:], ["exit", "final"])

    def test_wall_clock_limit_stops_slow_capture_before_audio_duration_limit(self):
        driver = _AudioBoundary(turns=[[(False, {"partial": ""})]],
                                final={"text": ""})
        clock = [100.0]
        driver.after_read = lambda: clock.__setitem__(0, 131.0)
        with patch.object(self.voice_turn.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaisesRegex(VoiceUnavailable, "超时|timeout|时长"):
                self.listen(driver)
        self.assertEqual(len(driver.streams[0].reads), 1)
        self.assertEqual(driver.events.count("final"), 1)
        self.assertTrue(driver.streams[0].closed)

    def test_no_speech_at_duration_limit_fails_once_without_retry(self):
        driver = _AudioBoundary(turns=[[(True, {"text": ""})]],
                                final={"text": " "})
        with self.assertRaisesRegex(VoiceUnavailable, "没有识别到|No speech|超时"):
            self.listen(driver, max_seconds=0.25)
        self.assertEqual(len(driver.streams), 1)
        self.assertEqual(len(driver.streams[0].reads), 1)
        self.assertEqual(driver.events.count("final"), 1)
        self.assertTrue(driver.streams[0].closed)

    def test_stop_during_final_result_discards_text(self):
        driver = _AudioBoundary(turns=[[(False, {"partial": "尾句"})]],
                                stop_at="final")
        self.assertEqual(self.listen(driver, max_seconds=0.25), "")
        self.assertTrue(driver.streams[0].closed)
        self.assertEqual(driver.events[-2:], ["exit", "final"])

    def test_transcript_and_partial_callbacks_are_capped_at_2000_characters(self):
        driver = _AudioBoundary(turns=[[
            (False, {"partial": "甲" * 2001}),
            (True, {"text": "乙" * 2001}),
        ]])
        partials = []
        self.assertEqual(self.listen(driver, on_partial=partials.append), "乙" * 2000)
        self.assertEqual(partials, ["甲" * 2000])

    def test_timeout_final_text_is_capped_at_2000_characters(self):
        driver = _AudioBoundary(turns=[[(False, {"partial": ""})]],
                                final={"text": "尾" * 2001})
        self.assertEqual(self.listen(driver, max_seconds=0.25), "尾" * 2000)

    def test_invalid_stop_event_is_a_voice_failure_before_audio_import(self):
        for stop in (None, False, object(), {"is_set": True}):
            with self.subTest(stop=stop):
                recognizer = self.voice_turn.VoiceTurnRecognizer(self.folder)
                error = None
                with patch.dict(sys.modules, {"sounddevice": None, "vosk": None}):
                    try:
                        recognizer.listen(stop)
                    except Exception as exc:
                        error = exc
                self.assertIsInstance(error, VoiceUnavailable)
                self.assertIn("stop event", str(error))

    def test_invalid_callbacks_fail_before_model_or_device_initialization(self):
        for options in ({"on_partial": 1}, {"on_ready": True}):
            with self.subTest(options=options):
                driver = _AudioBoundary()
                with self.assertRaisesRegex(VoiceUnavailable, "callback"):
                    self.listen(driver, **options)
                self.assertEqual(driver.events, [])

    def test_invalid_duration_fails_before_model_or_device_initialization(self):
        for duration in (0, -1, 30.1, True, None, "30", float("nan"), float("inf")):
            with self.subTest(duration=duration):
                driver = _AudioBoundary()
                with self.assertRaisesRegex(VoiceUnavailable, "limit|duration|时长"):
                    self.listen(driver, max_seconds=duration)
                self.assertEqual(driver.events, [])

    def test_invalid_sample_rate_fails_before_model_or_device_initialization(self):
        for sample_rate in (0, -1, 16000.0, True, None, "16000"):
            with self.subTest(sample_rate=sample_rate):
                driver = _AudioBoundary()
                with self.assertRaisesRegex(VoiceUnavailable, "sample rate"):
                    self.listen(driver, sample_rate=sample_rate)
                self.assertEqual(driver.events, [])

    def test_missing_or_blank_model_path_does_not_initialize_audio(self):
        model_file = self.folder / "model.zip"
        model_file.write_bytes(b"not an extracted model")
        for model_path in ("", " \t", None, self.folder / "missing", model_file):
            with self.subTest(model_path=model_path):
                driver = _AudioBoundary()
                recognizer = self.voice_turn.VoiceTurnRecognizer(model_path)
                with patch.dict(sys.modules, driver.modules()):
                    with self.assertRaises(VoiceUnavailable):
                        recognizer.listen(driver.stop)
                self.assertEqual(driver.events, [])

    def test_missing_optional_dependency_explains_installation_without_retry(self):
        for absent in ("vosk", "sounddevice"):
            with self.subTest(absent=absent):
                driver = _AudioBoundary()
                modules = driver.modules()
                modules[absent] = None
                recognizer = self.voice_turn.VoiceTurnRecognizer(self.folder)
                with patch.dict(sys.modules, modules):
                    with self.assertRaisesRegex(VoiceUnavailable, "pip install.*vosk.*sounddevice"):
                        recognizer.listen(driver.stop)
                self.assertEqual(driver.events, [])

    def test_invalid_json_or_text_shape_fails_and_closes_without_retry(self):
        for stage, field in (("result", "text"), ("partial", "partial"),
                             ("final", "text")):
            for response in ("broken-json", "[]", "null", {},
                             {field: None}, {field: 7}, {field: ["words"]}):
                with self.subTest(stage=stage, response=response):
                    steps = [(stage == "result", response)]
                    final = {"text": "不应返回"}
                    if stage == "final":
                        steps = [(False, {"partial": ""})]
                        final = response
                    driver = _AudioBoundary(turns=[steps], final=final)
                    with self.assertRaisesRegex(VoiceUnavailable, "Invalid.*recognition|无效.*识别"):
                        self.listen(driver, max_seconds=0.25)
                    self.assertTrue(driver.streams[0].closed)
                    self.assertEqual(len(driver.streams), 1)
                    self.assertEqual(driver.events.count(stage), 1)

    def test_invalid_acceptance_status_does_not_process_a_result(self):
        for status in (None, "true", {}, 2):
            with self.subTest(status=status):
                driver = _AudioBoundary(turns=[[(status, {"text": "无效结果"})]])
                with self.assertRaisesRegex(VoiceUnavailable, "Invalid.*recognition|无效.*识别"):
                    self.listen(driver, max_seconds=0.25)
                self.assertNotIn("result", driver.events)
                self.assertNotIn("partial", driver.events)
                self.assertNotIn("final", driver.events)
                self.assertTrue(driver.streams[0].closed)

    def test_empty_or_malformed_audio_fails_before_recognition_without_spinning(self):
        for audio in (b"", b"\x00", b"\x00" * 4, b"\x00" * 8002,
                      None, 7, "not PCM"):
            with self.subTest(audio=audio[:12] if isinstance(audio, bytes) else audio,
                              size=len(audio) if isinstance(audio, bytes) else None):
                driver = _AudioBoundary(audio=audio)
                with self.assertRaisesRegex(VoiceUnavailable, "audio|PCM|音频"):
                    self.listen(driver, max_seconds=0.25)
                self.assertEqual(len(driver.streams[0].reads), 1)
                self.assertNotIn("accept", driver.events)
                self.assertNotIn("final", driver.events)
                self.assertTrue(driver.streams[0].closed)

    def test_microphone_overflow_closes_without_recognition_or_retry(self):
        driver = _AudioBoundary(overflow=True)
        with self.assertRaisesRegex(VoiceUnavailable, "overflow"):
            self.listen(driver)
        self.assertEqual(len(driver.streams[0].reads), 1)
        self.assertNotIn("accept", driver.events)
        self.assertNotIn("final", driver.events)
        self.assertTrue(driver.streams[0].closed)

    def test_partial_final_audio_block_does_not_exceed_requested_duration(self):
        driver = _AudioBoundary(turns=[[(False, {"partial": ""}),
                                       (False, {"partial": "尾句"})]])
        self.assertEqual(self.listen(driver, sample_rate=8000, max_seconds=0.75),
                         "未提交尾句")
        self.assertEqual(driver.streams[0].reads, [4000, 2000])
        self.assertEqual(driver.recognizers[0].sample_rate, 8000)
        self.assertEqual(driver.streams[0].options["samplerate"], 8000)

    def test_native_errors_are_voice_failures_without_automatic_retry(self):
        for stage in ("model", "recognizer", "stream", "enter", "read", "accept",
                      "result", "partial", "exit", "final"):
            with self.subTest(stage=stage):
                steps = [(stage not in {"partial", "final"},
                          {"text": "完整句", "partial": "部分句"})]
                driver = _AudioBoundary(turns=[steps], fail_at=stage)
                with self.assertRaisesRegex(VoiceUnavailable, "driver failure at " + stage):
                    self.listen(driver, max_seconds=0.25)
                self.assertEqual(driver.events.count(stage), 1)
                if stage in {"read", "accept", "result", "partial", "exit", "final"}:
                    self.assertTrue(driver.streams[0].closed)

    def test_stop_takes_precedence_over_concurrent_driver_failure(self):
        for stage in ("model", "enter", "read", "result", "exit", "final"):
            with self.subTest(stage=stage):
                steps = [(stage != "final", {"text": "丢弃", "partial": "丢弃"})]
                driver = _AudioBoundary(turns=[steps], stop_at=stage, fail_at=stage)
                self.assertEqual(self.listen(driver, max_seconds=0.25), "")
                self.assertEqual(driver.events.count(stage), 1)

    def test_callback_failure_closes_stream_and_ends_turn(self):
        def fail(*_args):
            raise RuntimeError("callback failed")

        for callbacks in ({"on_ready": fail}, {"on_partial": fail}):
            with self.subTest(callbacks=callbacks):
                driver = _AudioBoundary(turns=[[(False, {"partial": "中止"})]])
                with self.assertRaisesRegex(VoiceUnavailable, "callback failed"):
                    self.listen(driver, **callbacks)
                self.assertEqual(len(driver.streams), 1)
                self.assertTrue(driver.streams[0].closed)
                self.assertNotIn("final", driver.events)

    def test_successful_model_load_is_reused_after_preparation_was_cancelled(self):
        driver = _AudioBoundary(stop_at="model")
        recognizer = self.voice_turn.VoiceTurnRecognizer(self.folder)
        with patch.dict(sys.modules, driver.modules()):
            self.assertEqual(recognizer.listen(driver.stop), "")
            driver.stop.clear()
            driver.stop_at = None
            self.assertEqual(recognizer.listen(driver.stop), "你好")
        self.assertEqual(len(driver.models), 1)
        self.assertEqual(len(driver.streams), 1)

    def test_distinct_conversations_do_not_share_a_cached_model(self):
        driver = _AudioBoundary(turns=[[(True, {"text": "一"})],
                                       [(True, {"text": "二"})]])
        self.assertEqual(self.listen(driver), "一")
        self.assertEqual(self.listen(driver), "二")
        self.assertEqual(len(driver.models), 2)
        self.assertIsNot(driver.recognizers[0].model, driver.recognizers[1].model)


if __name__ == "__main__":
    unittest.main()
