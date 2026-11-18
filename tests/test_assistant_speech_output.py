"""Complete speech uses the real worker loop and a queued native-driver boundary."""
import importlib
import sys
import threading
import types
import unittest
from unittest.mock import patch

from DyberPet.assistant.voice_errors import VoiceUnavailable


class _Clock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class QueuedSpeechEngine:
    """Public engine boundary with pyttsx3's queued commands/error semantics.

    Configuration is processed on the first external iterate. Command failures
    emit error and continue the queue, and notification callbacks swallow raised
    exceptions, as pyttsx3 2.99 DriverProxy._pump and Engine._notify do.
    """

    def __init__(self, stop_event=None):
        self.stop_event = stop_event or threading.Event()
        self.clock = _Clock()
        self.events = []
        self.thread_ids = []
        self.callbacks = {}
        self.queue = []
        self.busy = True
        self.prepared = False
        self.current = None
        self.queued_speech = []
        self.started = []
        self.completed = []
        self.iterations = {}
        self.properties = {"voice": "system-default", "rate": 200}
        self.voices = [types.SimpleNamespace(id="voice-a"),
                       types.SimpleNamespace(id="voice-b")]
        self.property_errors = {}
        self.say_errors = {}
        self.ignored_properties = set()
        self.swallowed_callbacks = []
        self.on_iteration = None
        self.on_event = None
        self.step_seconds = 0.0
        self.prepare_seconds = 0.0
        self.init_seconds = 0.0

    def record(self, event):
        self.events.append(event)
        self.thread_ids.append(threading.get_ident())
        if self.on_event is not None:
            self.on_event(self, event)

    def initialize(self):
        self.record(("init",))
        self.clock.advance(self.init_seconds)
        return self

    def connect(self, topic, callback):
        self.record(("connect", topic))
        token = object()
        self.callbacks[token] = (topic, callback)
        return token

    def disconnect(self, token):
        self.record(("disconnect",))
        del self.callbacks[token]

    def notify(self, topic, **kwargs):
        for registered, callback in tuple(self.callbacks.values()):
            if registered == topic:
                try:
                    callback(**kwargs)
                except Exception as exc:
                    self.swallowed_callbacks.append(exc)

    def getProperty(self, name):
        self.record(("get", name))
        return self.voices if name == "voices" else self.properties[name]

    def setProperty(self, name, value):
        self.record(("property", name, value))
        self.queue.append(("property", name, value))
        self.pump()

    def isBusy(self):
        self.thread_ids.append(threading.get_ident())
        return self.busy

    def say(self, text, name=None):
        # pyttsx3 2.99 Engine.say ignores strip-empty input without queuing a
        # command or emitting a completion event.
        if not str(text or "").strip():
            return "Argument value can't be None or empty"
        self.record(("say", name))
        self.queued_speech.append((text, name))
        self.queue.append(("say", text, name))
        self.pump()

    def pump(self):
        while not self.busy and self.queue:
            kind, key, value = self.queue.pop(0)
            if kind == "property":
                error = self.property_errors.get(key)
                if error is not None:
                    self.notify("error", name=None, exception=error)
                elif key not in self.ignored_properties:
                    self.properties[key] = value
            else:
                index = len(self.started) + 1
                error = self.say_errors.get(index)
                if error is not None:
                    self.notify("error", name=value, exception=error)
                    continue
                self.current = (key, value)
                self.busy = True
                self.started.append((key, value, dict(self.properties)))

    def startLoop(self, use_driver_loop):
        self.record(("start", use_driver_loop))

    def iterate(self):
        if not self.prepared:
            self.record(("configure",))
            self.prepared = True
            self.clock.advance(self.prepare_seconds)
            self.busy = False
            self.pump()
            return
        self.record(("iterate",))
        self.clock.advance(self.step_seconds)
        if self.current is not None:
            name = self.current[1]
            self.iterations[name] = self.iterations.get(name, 0) + 1
            if self.on_iteration is not None:
                self.on_iteration(self)
            else:
                self.finish(True)

    def finish(self, completed):
        text, name = self.current
        self.notify("finished-utterance", name=name, completed=completed)
        if completed is True:
            self.completed.append(text)
        self.current = None
        self.busy = False
        self.pump()

    def stop(self):
        self.record(("stop",))
        self.queue.clear()
        self.current = None
        self.busy = False

    def endLoop(self):
        self.record(("end",))


class SpeechOutputTests(unittest.TestCase):
    def speech_module(self, *, baseline=False):
        try:
            return importlib.import_module("DyberPet.assistant.speech")
        except ModuleNotFoundError as exc:
            if exc.name != "DyberPet.assistant.speech":
                raise
            if baseline:
                # Before extraction, this one regression exposes the real
                # legacy 500-character cutoff instead of only a missing module.
                return importlib.import_module("DyberPet.assistant.voice")
            self.fail("Complete, selected-voice speech output is not implemented")

    def speak(self, engine, text, *, baseline=False, once=False, **kwargs):
        speech = self.speech_module(baseline=baseline)
        module = types.ModuleType("pyttsx3")
        module.init = engine.initialize
        with patch.dict(sys.modules, {"pyttsx3": module}), \
                patch.object(speech.sys, "platform", "win32"), \
                patch.object(speech.time, "monotonic", engine.clock.monotonic), \
                patch.object(speech.time, "sleep", engine.clock.advance):
            if once:
                return speech.speak_once(text, **kwargs)
            return speech.speak_interruptible(text, engine.stop_event, **kwargs)

    def assert_cleaned(self, engine, *, loop=True):
        self.assertEqual(engine.queue, [])
        self.assertIsNone(engine.current)
        self.assertEqual(engine.callbacks, {})
        self.assertEqual(engine.events.count(("stop",)), 1)
        self.assertEqual(engine.events.count(("end",)), int(loop))

    def test_complete_2000_characters_are_spoken_without_the_legacy_cutoff(self):
        engine = QueuedSpeechEngine()
        text = "甲" * 500 + "乙" * 500 + "丙" * 500 + "丁" * 500
        self.assertTrue(self.speak(engine, text, baseline=True))
        self.assertEqual("".join(engine.completed), text)
        self.assertEqual([len(item[0]) for item in engine.queued_speech], [500] * 4)

    def test_split_uses_natural_punctuation_and_preserves_every_character(self):
        split = self.speech_module().split_speech_text
        parts = ("前" * 240 + "。", "中" * 270 + "；",
                 "尾" * 350 + "\n", "余" * 300 + "！")
        self.assertEqual(split("".join(parts)), parts)
        spaced = ("\t" + "甲" * 497 + "。 ") * 4
        chunks = split(spaced)
        self.assertEqual("".join(chunks), spaced)
        self.assertTrue(all(0 < len(chunk) <= 500 for chunk in chunks))

    def test_split_rejects_oversize_and_nontext_instead_of_truncating(self):
        split = self.speech_module().split_speech_text
        for text in ("甲" * 2001, None, 17, ["hello"]):
            with self.subTest(text_type=type(text).__name__):
                with self.assertRaises(VoiceUnavailable):
                    split(text)

    def test_whitespace_only_chunks_never_wait_for_unemitted_driver_completion(self):
        split = self.speech_module().split_speech_text
        for text in ("甲" * 500 + "\n\n" + "乙" * 500,
                     " " * 600 + "甲" * 500,
                     "甲" * 500 + "\n" * 600,
                     "甲" * 500 + " " * 1000):
            with self.subTest(length=len(text), prefix=text[:2]):
                engine = QueuedSpeechEngine()
                progress, ready = [], []
                expected = tuple(chunk for chunk in split(text) if chunk.strip())
                self.assertEqual("".join(split(text)), text)
                self.assertTrue(self.speak(
                    engine, text, max_seconds=1,
                    on_ready=lambda: ready.append(True),
                    on_progress=lambda done, total: progress.append((done, total))))
                self.assertEqual(tuple(engine.completed), expected)
                self.assertEqual([part[0] for part in engine.queued_speech], list(expected))
                self.assertEqual(progress,
                                 [(i, len(expected)) for i in range(1, len(expected) + 1)])
                self.assertEqual(ready, [True])
                self.assert_cleaned(engine)

    def test_invalid_options_fail_before_initializing_the_native_engine(self):
        for options in ({"rate": 99}, {"rate": 231}, {"rate": True},
                        {"rate": 170.5}, {"voice_id": None},
                        {"voice_id": "v" * 513}, {"voice_id": "bad\nvoice"},
                        {"on_ready": "callback"}, {"on_progress": []},
                        {"max_seconds": 0}, {"max_seconds": 301},
                        {"max_seconds": float("nan")}):
            with self.subTest(options=options):
                engine = QueuedSpeechEngine()
                with self.assertRaises(VoiceUnavailable):
                    self.speak(engine, "hello", **options)
                self.assertEqual(engine.events, [])

    def test_oversize_playback_and_empty_text_never_initialize_tts(self):
        engine = QueuedSpeechEngine()
        with self.assertRaisesRegex(VoiceUnavailable, "2000"):
            self.speak(engine, "x" * 2001)
        self.assertTrue(self.speak(engine, " \n\t"))
        self.assertEqual(engine.events, [])

    def test_selected_installed_voice_and_rate_apply_before_every_chunk(self):
        engine = QueuedSpeechEngine()
        progress, ready = [], []
        self.assertTrue(self.speak(
            engine, "甲" * 1200, voice_id="voice-b", rate=230,
            on_ready=lambda: ready.append(True),
            on_progress=lambda completed, total: progress.append((completed, total))))
        self.assertEqual([item[2] for item in engine.started],
                         [{"voice": "voice-b", "rate": 230}] * 3)
        self.assertEqual(progress, [(1, 3), (2, 3), (3, 3)])
        self.assertEqual(ready, [True])
        self.assertEqual(engine.events.count(("init",)), 1)
        self.assertEqual(engine.events.count(("start", False)), 1)
        self.assertEqual(len({item[1] for item in engine.started}), 3)
        self.assertTrue(all(isinstance(item[1], str) and item[1] for item in engine.started))
        self.assert_cleaned(engine)

    def test_default_voice_does_not_enumerate_or_override_system_voice(self):
        engine = QueuedSpeechEngine()
        engine.voices = None
        self.assertTrue(self.speak(engine, "默认音色"))
        self.assertEqual(engine.started[0][2], {"voice": "system-default", "rate": 170})
        self.assertNotIn(("get", "voices"), engine.events)
        self.assertFalse(any(event[:2] == ("property", "voice") for event in engine.events))

    def test_missing_voice_never_falls_back_to_a_default_voice(self):
        for selected in ("missing", "VOICE-B", " voice-b"):
            with self.subTest(selected=selected):
                engine = QueuedSpeechEngine()
                with self.assertRaisesRegex(VoiceUnavailable, "voice"):
                    self.speak(engine, "不能使用错误音色", voice_id=selected)
                self.assertEqual(engine.queued_speech, [])
                self.assert_cleaned(engine, loop=False)

    def test_queued_property_errors_are_handled_before_any_speech_is_queued(self):
        for property_name in ("voice", "rate"):
            with self.subTest(property_name=property_name):
                engine = QueuedSpeechEngine()
                failure = OSError("driver rejected " + property_name)
                engine.property_errors[property_name] = failure
                ready = []
                with self.assertRaisesRegex(VoiceUnavailable, "driver rejected") as caught:
                    self.speak(engine, "不得使用默认音色发声", voice_id="voice-b",
                               on_ready=lambda: ready.append(True))
                self.assertIs(caught.exception.__cause__, failure)
                self.assertIsNone(caught.exception.engine_completed)
                self.assertEqual(engine.queued_speech, [])
                self.assertEqual(engine.swallowed_callbacks, [])
                self.assertEqual(ready, [])
                self.assert_cleaned(engine)

    def test_driver_silently_ignoring_selected_voice_is_rejected_before_speech(self):
        engine = QueuedSpeechEngine()
        engine.ignored_properties.add("voice")
        with self.assertRaisesRegex(VoiceUnavailable, "voice"):
            self.speak(engine, "不能播放", voice_id="voice-b")
        self.assertEqual(engine.queued_speech, [])
        self.assert_cleaned(engine)

    def test_stale_and_duplicate_finished_events_do_not_advance_the_next_chunk(self):
        engine = QueuedSpeechEngine()
        progress = []

        def iterate(driver):
            name = driver.current[1]
            if len(driver.started) == 2 and driver.iterations[name] == 1:
                old_name = driver.started[0][1]
                driver.notify("finished-utterance", name=old_name, completed=True)
                driver.notify("finished-utterance", name=old_name, completed=False)
                driver.notify("finished-utterance", name="other-session", completed=True)
                return
            driver.finish(True)
            driver.notify("finished-utterance", name=name, completed=False)

        engine.on_iteration = iterate
        self.assertTrue(self.speak(
            engine, "甲" * 700,
            on_progress=lambda completed, total: progress.append((completed, total))))
        self.assertEqual([engine.iterations[item[1]] for item in engine.started], [1, 2])
        self.assertEqual("".join(engine.completed), "甲" * 700)
        self.assertEqual(progress, [(1, 2), (2, 2)])

    def test_utterance_names_are_unique_across_playback_invocations(self):
        first, second = QueuedSpeechEngine(), QueuedSpeechEngine()
        self.assertTrue(self.speak(first, "第一场"))
        old_name = first.started[0][1]

        def iterate(driver):
            if driver.iterations[driver.current[1]] == 1:
                driver.notify("finished-utterance", name=old_name, completed=True)
                return
            driver.finish(True)

        second.on_iteration = iterate
        self.assertTrue(self.speak(second, "第二场"))
        self.assertNotEqual(first.started[0][1], second.started[0][1])
        self.assertEqual(second.completed, ["第二场"])
        self.assertEqual(second.iterations[second.started[0][1]], 2)

    def test_incomplete_or_nonboolean_completion_is_not_success(self):
        for value, expected in ((False, False), (0, None), (1, None),
                                ("true", None), (None, None)):
            with self.subTest(value=value):
                engine = QueuedSpeechEngine()
                engine.on_iteration = lambda driver: driver.finish(value)
                with self.assertRaisesRegex(VoiceUnavailable, "did not complete") as caught:
                    self.speak(engine, "甲" * 700)
                self.assertIs(caught.exception.engine_completed, expected)
                self.assertEqual(len(engine.queued_speech), 1)
                self.assert_cleaned(engine)

    def test_second_chunk_error_stops_all_remaining_chunks_and_keeps_completion_unknown(self):
        engine = QueuedSpeechEngine()
        failure = OSError("second chunk failed")
        engine.say_errors[2] = failure
        progress = []
        with self.assertRaisesRegex(VoiceUnavailable, "second chunk") as caught:
            self.speak(engine, "甲" * 1500,
                       on_progress=lambda completed, total: progress.append((completed, total)))
        self.assertIs(caught.exception.__cause__, failure)
        self.assertIsNone(caught.exception.engine_completed)
        self.assertEqual(len(engine.queued_speech), 2)
        self.assertEqual(progress, [(1, 3)])
        self.assert_cleaned(engine)

    def test_successful_prefix_cannot_report_whole_reply_complete_on_failure(self):
        for source in ("driver", "progress"):
            with self.subTest(source=source):
                engine = QueuedSpeechEngine()
                failure = OSError("failure after a completed prefix")
                kwargs = {}
                if source == "driver":
                    def iterate(driver):
                        driver.notify("error", name=driver.current[1], exception=failure)
                        driver.finish(True)
                    engine.on_iteration = iterate
                else:
                    def progress(_completed, _total):
                        raise failure
                    kwargs["on_progress"] = progress
                with self.assertRaisesRegex(VoiceUnavailable, "completed prefix") as caught:
                    self.speak(engine, "甲" * 700, **kwargs)
                self.assertIsNone(caught.exception.engine_completed)
                self.assertEqual(len(engine.queued_speech), 1)
                self.assert_cleaned(engine)

    def test_error_event_is_not_masked_by_same_tick_finish_or_cancel(self):
        for completed in (False, True):
            engine = QueuedSpeechEngine()
            failure = VoiceUnavailable("native failure", engine_completed=True)

            def iterate(driver):
                driver.notify("error", name=driver.current[1], exception=failure)
                driver.finish(completed)
                driver.stop_event.set()

            engine.on_iteration = iterate
            with self.assertRaisesRegex(VoiceUnavailable, "native failure") as caught:
                self.speak(engine, "不能报告成功")
            self.assertIs(caught.exception, failure)
            self.assertIs(caught.exception.engine_completed, completed)
            self.assert_cleaned(engine)

    def test_stop_during_second_chunk_cancels_every_unplayed_chunk(self):
        engine = QueuedSpeechEngine()
        progress, ready = [], []

        def iterate(driver):
            if len(driver.started) == 2:
                driver.stop_event.set()
            else:
                driver.finish(True)

        engine.on_iteration = iterate
        self.assertFalse(self.speak(
            engine, "甲" * 1500, on_ready=lambda: ready.append(True),
            on_progress=lambda completed, total: progress.append((completed, total))))
        self.assertEqual(len(engine.queued_speech), 2)
        self.assertEqual(progress, [(1, 3)])
        self.assertEqual(ready, [True])
        self.assert_cleaned(engine)

    def test_stop_at_progress_boundary_cannot_queue_another_chunk(self):
        engine = QueuedSpeechEngine()
        self.assertFalse(self.speak(
            engine, "甲" * 1500,
            on_progress=lambda _completed, _total: engine.stop_event.set()))
        self.assertEqual(len(engine.queued_speech), 1)
        self.assert_cleaned(engine)

    def test_stop_after_last_finish_still_returns_cancelled(self):
        engine = QueuedSpeechEngine()

        def iterate(driver):
            driver.finish(True)
            if len(driver.started) == 2:
                driver.stop_event.set()

        engine.on_iteration = iterate
        self.assertFalse(self.speak(engine, "甲" * 700))
        self.assertEqual(len(engine.queued_speech), 2)
        self.assert_cleaned(engine)

    def test_total_timeout_is_not_restarted_for_each_chunk(self):
        engine = QueuedSpeechEngine()
        engine.step_seconds = 0.6
        progress = []
        with self.assertRaisesRegex(VoiceUnavailable, "timeout"):
            self.speak(engine, "甲" * 1200, max_seconds=1,
                       on_progress=lambda completed, total: progress.append((completed, total)))
        self.assertEqual(len(engine.queued_speech), 2)
        self.assertEqual(progress, [(1, 3)])
        self.assert_cleaned(engine)

    def test_one_total_deadline_also_covers_engine_and_property_preparation(self):
        for stage in ("init_seconds", "prepare_seconds"):
            with self.subTest(stage=stage):
                engine = QueuedSpeechEngine()
                setattr(engine, stage, 1.1)
                with self.assertRaisesRegex(VoiceUnavailable, "timeout"):
                    self.speak(engine, "尚未发声", max_seconds=1)
                self.assertEqual(engine.queued_speech, [])
                self.assert_cleaned(engine, loop=stage == "prepare_seconds")

    def test_default_total_limit_allows_a_complete_reply_beyond_180_seconds(self):
        engine = QueuedSpeechEngine()
        engine.step_seconds = 149
        self.assertTrue(self.speak(engine, "甲" * 700))
        self.assertEqual(engine.clock.now, 298)

    def test_speak_once_uses_the_same_complete_selected_voice_path(self):
        engine = QueuedSpeechEngine()
        progress, ready = [], []
        self.assertIsNone(self.speak(
            engine, "甲" * 700, once=True, voice_id="voice-a", rate=100,
            on_ready=lambda: ready.append(True),
            on_progress=lambda completed, total: progress.append((completed, total))))
        self.assertEqual("".join(engine.completed), "甲" * 700)
        self.assertEqual([item[2] for item in engine.started],
                         [{"voice": "voice-a", "rate": 100}] * 2)
        self.assertEqual(ready, [True])
        self.assertEqual(progress, [(1, 2), (2, 2)])
        self.assert_cleaned(engine)

    def test_ready_and_progress_callback_failures_run_in_worker_and_clean_up(self):
        for callback in ("on_ready", "on_progress"):
            with self.subTest(callback=callback):
                engine = QueuedSpeechEngine()
                failure = OSError("consumer callback failed")

                def fail(*_args):
                    raise failure

                with self.assertRaisesRegex(VoiceUnavailable, "consumer callback") as caught:
                    self.speak(engine, "甲" * 700, **{callback: fail})
                self.assertIs(caught.exception.__cause__, failure)
                self.assertEqual(len(engine.queued_speech), 1)
                self.assertEqual(engine.swallowed_callbacks, [])
                self.assert_cleaned(engine)

    def test_all_native_calls_and_progress_stay_on_the_calling_worker(self):
        engine = QueuedSpeechEngine()
        results, worker_ids, callback_ids = [], [], []

        def run():
            worker_ids.append(threading.get_ident())
            results.append(self.speak(
                engine, "甲" * 700,
                on_ready=lambda: callback_ids.append(threading.get_ident()),
                on_progress=lambda *_args: callback_ids.append(threading.get_ident())))

        worker = threading.Thread(target=run)
        worker.start()
        worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertEqual(results, [True])
        self.assertEqual(set(engine.thread_ids), set(worker_ids))
        self.assertEqual(set(callback_ids), set(worker_ids))
        self.assertNotEqual(worker_ids, [threading.get_ident()])


class VoiceErrorContractTests(unittest.TestCase):
    def test_shared_failure_preserves_message_and_only_boolean_completion(self):
        try:
            errors = importlib.import_module("DyberPet.assistant.voice_errors")
        except ModuleNotFoundError:
            self.fail("The shared voice error type has not been extracted")
        for value, expected in ((True, True), (False, False), (None, None),
                                (0, None), (1, None), ("true", None), ({}, None)):
            with self.subTest(value=value):
                error = errors.VoiceUnavailable("native output failed", engine_completed=value)
                self.assertIsInstance(error, RuntimeError)
                self.assertEqual(str(error), "native output failed")
                self.assertEqual(error.args, ("native output failed",))
                self.assertIs(error.engine_completed, expected)


if __name__ == "__main__":
    unittest.main()
