"""Driver-boundary regressions for opt-in microphone and TTS lifecycles."""
import json
import sys
import tempfile
import threading
import unittest
from types import ModuleType
from unittest.mock import patch

from DyberPet.assistant.voice import (
    VoiceUnavailable, recognize_until_stopped, speak_interruptible,
)


def _driver_module(name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    return module


class _RecognitionDriver:
    """A controllable device boundary; the production capture loop stays real."""

    def __init__(self, stop, *, stop_at=None, final="识别结果", enter_error=False):
        self.stop = stop
        self.stop_at = stop_at
        self.final = final
        self.enter_error = enter_error
        self.events = []
        self.sounddevice = _driver_module("sounddevice", RawInputStream=self.stream)
        self.vosk = _driver_module("vosk", Model=self.model,
                                  KaldiRecognizer=self.recognizer)

    def record(self, event):
        self.events.append(event)
        if event == self.stop_at:
            self.stop.set()

    def model(self, path):
        self.record("model")
        return object()

    def recognizer(self, model, sample_rate):
        self.record("recognizer")
        return self

    def stream(self, **kwargs):
        self.record("stream")
        return self

    def __enter__(self):
        self.record("enter")
        if self.enter_error:
            raise OSError("device unavailable")
        return self

    def __exit__(self, *_args):
        self.record("exit")

    def read(self, frames):
        self.record("read")
        self.stop.set()
        return b"\x00" * frames * 2, False

    def AcceptWaveform(self, payload):
        self.record("accept")
        return False

    def PartialResult(self):
        return json.dumps({"partial": self.final})

    def FinalResult(self):
        self.record("final")
        return json.dumps({"text": self.final})

    def modules(self):
        return {"sounddevice": self.sounddevice, "vosk": self.vosk}


class _SpeechDriver:
    def __init__(self, stop, *, stop_at=None, finish_on_iterate=False,
                 finish_completed=True, stop_after_finish=False,
                 iterate_error=None):
        self.stop_event = stop
        self.stop_at = stop_at
        self.finish_on_iterate = finish_on_iterate
        self.finish_completed = finish_completed
        self.stop_after_finish = stop_after_finish
        self.iterate_error = iterate_error
        self.events = []
        self.threads = []
        self.finished = None

    def record(self, event):
        self.events.append(event)
        self.threads.append(threading.get_ident())
        if event == self.stop_at:
            self.stop_event.set()

    def init(self):
        self.record("init")
        return self

    def setProperty(self, name, value):
        self.record("property")

    def connect(self, name, callback):
        self.record("connect")
        self.finished = callback

    def say(self, text):
        self.record("say")

    def startLoop(self, driver_loop):
        self.record("start")

    def iterate(self):
        self.record("iterate")
        if self.finish_on_iterate:
            self.finished("utterance", self.finish_completed)
            if self.stop_after_finish:
                self.stop_event.set()
        else:
            self.stop_event.set()
        if self.iterate_error is not None:
            raise self.iterate_error

    def stop(self):
        self.record("stop")

    def endLoop(self):
        self.record("end")


class VoiceLifecycleTests(unittest.TestCase):
    def recognize(self, driver, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            with patch.dict(sys.modules, driver.modules()):
                return recognize_until_stopped(folder, driver.stop, **kwargs)

    def speak(self, driver, **kwargs):
        with patch.dict(sys.modules, {
            "pyttsx3": _driver_module("pyttsx3", init=driver.init)
        }):
            return speak_interruptible("你好", driver.stop_event, **kwargs)

    def test_voice_failure_defaults_completion_to_unknown_and_keeps_message(self):
        failure = VoiceUnavailable("audio unavailable")
        self.assertEqual(str(failure), "audio unavailable")
        self.assertEqual(failure.args, ("audio unavailable",))
        self.assertIsNone(getattr(failure, "engine_completed", "missing"))

    def test_voice_failure_keeps_only_boolean_completion_metadata(self):
        for value, expected in ((False, False), (True, True), (None, None),
                                (0, None), (1, None), ("false", None),
                                ({"private": "value"}, None)):
            with self.subTest(value=value):
                failure = VoiceUnavailable("audio unavailable",
                                           engine_completed=value)
                self.assertIs(failure.engine_completed, expected)
                self.assertEqual(str(failure), "audio unavailable")

    def test_cancelled_capture_never_loads_model_or_opens_microphone(self):
        stop = threading.Event()
        stop.set()
        driver = _RecognitionDriver(stop)
        self.assertEqual(self.recognize(driver), "")
        self.assertEqual(driver.events, [])

    def test_stopping_during_model_loading_does_not_open_microphone(self):
        driver = _RecognitionDriver(threading.Event(), stop_at="model")
        self.assertEqual(self.recognize(driver), "")
        self.assertEqual(driver.events, ["model"])

    def test_stopping_during_recognizer_setup_does_not_open_microphone(self):
        driver = _RecognitionDriver(threading.Event(), stop_at="recognizer")
        self.assertEqual(self.recognize(driver), "")
        self.assertEqual(driver.events, ["model", "recognizer"])

    def test_microphone_ready_runs_only_after_open_before_first_read(self):
        driver = _RecognitionDriver(threading.Event())
        text = self.recognize(driver, on_ready=lambda: driver.record("ready"))
        self.assertEqual(text, "识别结果")
        self.assertEqual(driver.events,
                         ["model", "recognizer", "stream", "enter", "ready",
                          "read", "accept", "exit", "final"])

    def test_stop_during_device_open_closes_without_ready_or_capture(self):
        driver = _RecognitionDriver(threading.Event(), stop_at="enter")
        self.assertEqual(self.recognize(driver,
                                       on_ready=lambda: driver.record("ready")), "")
        self.assertEqual(driver.events,
                         ["model", "recognizer", "stream", "enter", "exit"])

    def test_failed_microphone_open_never_signals_ready(self):
        driver = _RecognitionDriver(threading.Event(), enter_error=True)
        with self.assertRaisesRegex(VoiceUnavailable, "device unavailable"):
            self.recognize(driver, on_ready=lambda: driver.record("ready"))
        self.assertNotIn("ready", driver.events)
        self.assertNotIn("read", driver.events)

    def test_capture_ready_callback_must_be_callable_before_open(self):
        driver = _RecognitionDriver(threading.Event())
        with self.assertRaisesRegex(VoiceUnavailable, "callback"):
            self.recognize(driver, on_ready=True)
        self.assertEqual(driver.events, [])

    def test_stopped_real_capture_without_words_keeps_existing_error(self):
        driver = _RecognitionDriver(threading.Event(), final="")
        with self.assertRaisesRegex(VoiceUnavailable, "没有识别到语音"):
            self.recognize(driver)
        self.assertIn("read", driver.events)
        self.assertIn("exit", driver.events)

    def test_pre_cancelled_speech_never_initializes_driver(self):
        stop = threading.Event()
        stop.set()
        driver = _SpeechDriver(stop)
        self.assertFalse(self.speak(driver))
        self.assertEqual(driver.events, [])

    def test_stopping_during_tts_init_does_not_queue_or_start_speech(self):
        driver = _SpeechDriver(threading.Event(), stop_at="init")
        self.assertFalse(self.speak(driver, on_ready=lambda: driver.record("ready")))
        self.assertEqual(driver.events, ["init", "stop"])
        self.assertEqual(set(driver.threads), {threading.get_ident()})

    def test_stopping_during_tts_configuration_does_not_queue_speech(self):
        driver = _SpeechDriver(threading.Event(), stop_at="connect")
        self.assertFalse(self.speak(driver, on_ready=lambda: driver.record("ready")))
        self.assertNotIn("say", driver.events)
        self.assertNotIn("start", driver.events)
        self.assertNotIn("ready", driver.events)
        self.assertEqual(driver.events[-1], "stop")

    def test_stopping_after_queue_does_not_start_loop(self):
        driver = _SpeechDriver(threading.Event(), stop_at="say")
        self.assertFalse(self.speak(driver, on_ready=lambda: driver.record("ready")))
        self.assertNotIn("start", driver.events)
        self.assertNotIn("ready", driver.events)
        self.assertEqual(driver.events[-1], "stop")

    def test_stopping_in_start_loop_suppresses_ready_and_ends_loop(self):
        driver = _SpeechDriver(threading.Event(), stop_at="start")
        self.assertFalse(self.speak(driver, on_ready=lambda: driver.record("ready")))
        self.assertNotIn("ready", driver.events)
        self.assertNotIn("iterate", driver.events)
        self.assertEqual(driver.events[-2:], ["stop", "end"])

    def test_normal_speech_announces_ready_once_and_cleans_up_on_worker(self):
        driver = _SpeechDriver(threading.Event(), finish_on_iterate=True)
        worker_ids = []
        results = []

        def run():
            worker_ids.append(threading.get_ident())
            results.append(self.speak(driver, on_ready=lambda: driver.record("ready")))

        worker = threading.Thread(target=run)
        worker.start()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [True])
        self.assertEqual(driver.events,
                         ["init", "property", "connect", "say", "start", "ready",
                          "iterate", "stop", "end"])
        self.assertEqual(set(driver.threads), set(worker_ids))
        self.assertNotEqual(worker_ids, [threading.get_ident()])

    def test_uncompleted_speech_without_user_stop_reports_failure_and_cleans_up(self):
        driver = _SpeechDriver(threading.Event(), finish_on_iterate=True,
                               finish_completed=False)
        with self.assertRaisesRegex(VoiceUnavailable, "did not complete") as raised:
            self.speak(driver)
        self.assertIs(getattr(raised.exception, "engine_completed", None), False)
        self.assertFalse(driver.stop_event.is_set())
        self.assertEqual(driver.events[-2:], ["stop", "end"])

    def test_stop_before_finish_callback_returns_cancelled_for_both_completion_flags(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                driver = _SpeechDriver(threading.Event(), stop_at="iterate",
                                       finish_on_iterate=True,
                                       finish_completed=completed)
                self.assertFalse(self.speak(driver))
                self.assertEqual(driver.events[-2:], ["stop", "end"])

    def test_stop_after_finish_callback_returns_cancelled_for_both_completion_flags(self):
        for completed in (False, True):
            with self.subTest(completed=completed):
                driver = _SpeechDriver(threading.Event(), finish_on_iterate=True,
                                       finish_completed=completed,
                                       stop_after_finish=True)
                self.assertFalse(self.speak(driver))
                self.assertEqual(driver.events[-2:], ["stop", "end"])

    def test_driver_error_is_not_masked_by_completion_or_stop(self):
        for completed in (False, True):
            for stop_after_finish in (False, True):
                with self.subTest(completed=completed,
                                  stop_after_finish=stop_after_finish):
                    failure = OSError("driver failed after completion callback")
                    driver = _SpeechDriver(
                        threading.Event(), finish_on_iterate=True,
                        finish_completed=completed,
                        stop_after_finish=stop_after_finish,
                        iterate_error=failure)
                    with self.assertRaisesRegex(
                            VoiceUnavailable, "driver failed") as raised:
                        self.speak(driver)
                    self.assertIs(raised.exception.__cause__, failure)
                    self.assertIs(getattr(raised.exception, "engine_completed", None),
                                  completed)
                    self.assertEqual(driver.events[-2:], ["stop", "end"])

    def test_driver_error_without_finish_callback_keeps_completion_unknown(self):
        driver = _SpeechDriver(threading.Event(),
                               iterate_error=OSError("driver stopped before callback"))
        with self.assertRaisesRegex(VoiceUnavailable, "before callback") as raised:
            self.speak(driver)
        self.assertIsNone(getattr(raised.exception, "engine_completed", "missing"))
        self.assertEqual(driver.events[-2:], ["stop", "end"])

    def test_driver_voice_failure_uses_only_this_utterances_observed_completion(self):
        for completed in (None, False, True):
            with self.subTest(completed=completed):
                failure = VoiceUnavailable("driver voice failure",
                                           engine_completed=True)
                driver = _SpeechDriver(
                    threading.Event(), finish_on_iterate=completed is not None,
                    finish_completed=completed, iterate_error=failure)
                with self.assertRaisesRegex(VoiceUnavailable, "driver voice") as raised:
                    self.speak(driver)
                self.assertIs(raised.exception, failure)
                self.assertIs(raised.exception.engine_completed, completed)
                self.assertEqual(driver.events[-2:], ["stop", "end"])

    def test_invalid_finish_callback_value_cannot_claim_completion(self):
        for completed in (0, 1, "false", {"private": "value"}):
            with self.subTest(completed=completed):
                driver = _SpeechDriver(threading.Event(), finish_on_iterate=True,
                                       finish_completed=completed)
                with self.assertRaises(VoiceUnavailable) as raised:
                    self.speak(driver)
                self.assertIsNone(getattr(raised.exception, "engine_completed", "missing"))
                self.assertEqual(driver.events[-2:], ["stop", "end"])


if __name__ == "__main__":
    unittest.main()
