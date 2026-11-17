"""Opt-in offline microphone transcription and speech synthesis.

Neither package is installed by default. No always-on listening, automatic
mic activation, cloud recognition, recording retention or background uploads.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path


class VoiceUnavailable(RuntimeError):
    pass


def recognize_once(model_dir: str | Path, *, seconds: float = 4.0,
                   sample_rate: int = 16000) -> str:
    if not 0.5 <= seconds <= 10:
        raise VoiceUnavailable("Listening duration must be 0.5–10 seconds")
    path = Path(model_dir).expanduser().resolve()
    if not path.is_dir():
        raise VoiceUnavailable("Select an installed offline Vosk language model folder")
    try:
        import sounddevice as sd
        import vosk
    except ImportError as exc:
        raise VoiceUnavailable(
            "Offline recognition requires pip install vosk sounddevice"
        ) from exc
    model = vosk.Model(str(path))
    recognizer = vosk.KaldiRecognizer(model, sample_rate)
    # Raw 16-bit mono PCM at 16kHz. Stops once the requested period ends.
    try:
        with sd.RawInputStream(samplerate=sample_rate, blocksize=4000,
                               channels=1, dtype="int16") as microphone:
            for _ in range(int(seconds * sample_rate / 4000)):
                payload, overflow = microphone.read(4000)
                if overflow:
                    raise VoiceUnavailable("Microphone overflow; please try again")
                recognizer.AcceptWaveform(bytes(payload))
    except VoiceUnavailable:
        raise
    except Exception as exc:
        raise VoiceUnavailable("Microphone unavailable: " + str(exc)) from exc
    text = json.loads(recognizer.FinalResult()).get("text", "").strip()
    if not text:
        raise VoiceUnavailable("No speech recognized; please retry")
    return text[:2000]


def recognize_until_stopped(model_dir: str | Path, stop_event, *, on_partial=None,
                            sample_rate: int = 16000, max_seconds: float = 120.0) -> str:
    """Capture opt-in microphone audio until user stops or the safety limit.

    Audio is processed in memory by Vosk and never written to disk. Partial
    recognition is callback-only; the final transcript is returned once.
    """
    if not 1 <= max_seconds <= 300:
        raise VoiceUnavailable("Continuous listening limit must be 1–300 seconds")
    if stop_event is None or not callable(getattr(stop_event, "is_set", None)):
        raise VoiceUnavailable("A stop event is required for continuous listening")
    if on_partial is not None and not callable(on_partial):
        raise VoiceUnavailable("Partial transcript callback must be callable")
    path = Path(model_dir).expanduser().resolve()
    if not path.is_dir():
        raise VoiceUnavailable("Select an installed offline Vosk language model folder")
    try:
        import sounddevice as sd
        import vosk
    except ImportError as exc:
        raise VoiceUnavailable(
            "Offline recognition requires pip install vosk sounddevice"
        ) from exc
    try:
        model = vosk.Model(str(path))
        recognizer = vosk.KaldiRecognizer(model, sample_rate)
        last_partial = ""
        final_segments = []
        elapsed = 0.0
        with sd.RawInputStream(samplerate=sample_rate, blocksize=4000,
                               channels=1, dtype="int16") as microphone:
            while not stop_event.is_set() and elapsed < max_seconds:
                payload, overflow = microphone.read(4000)
                if overflow:
                    raise VoiceUnavailable("Microphone overflow; please try again")
                audio = bytes(payload)
                elapsed += len(audio) / 2 / sample_rate
                if recognizer.AcceptWaveform(audio):
                    result = json.loads(recognizer.Result()).get("text", "").strip()
                    if result:
                        final_segments.append(result)
                        if on_partial is not None:
                            on_partial(" ".join(final_segments)[-2000:])
                    last_partial = ""
                else:
                    partial = json.loads(recognizer.PartialResult()).get("partial", "").strip()
                    if partial and partial != last_partial and on_partial is not None:
                        preview = " ".join(final_segments + [partial])
                        on_partial(preview[-2000:])
                    last_partial = partial
        final = json.loads(recognizer.FinalResult()).get("text", "").strip()
        if final:
            final_segments.append(final)
        transcript = " ".join(final_segments).strip()
        if transcript:
            return transcript[:2000]
        if stop_event.is_set():
            raise VoiceUnavailable("没有识别到语音；可以重新开始监听")
        raise VoiceUnavailable("连续监听达到安全时长上限；请检查识别结果并重新开始")
    except VoiceUnavailable:
        raise
    except Exception as exc:
        raise VoiceUnavailable("Continuous microphone recognition failed: " + str(exc)) from exc


def speak_once(text: str, *, rate: int = 170, on_ready=None) -> None:
    if not text.strip():
        return
    if not 100 <= rate <= 230:
        raise VoiceUnavailable("Speech rate must be 100–230")
    try:
        import pyttsx3
    except ImportError as exc:
        raise VoiceUnavailable("Offline TTS requires pip install pyttsx3") from exc
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        engine.say(text[:500])
        # Called from the worker only after the local speech engine has been
        # initialized and an utterance has been queued. Still not phoneme sync.
        if on_ready is not None:
            on_ready()
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        raise VoiceUnavailable("Offline speech output failed: " + str(exc)) from exc


def speak_interruptible(text: str, stop_event, *, rate: int = 170,
                        on_ready=None, max_seconds: float = 180.0) -> bool:
    """Speak locally while pumping the engine loop; return False if interrupted.

    The engine is created and driven on the calling worker thread. The UI only
    sets a thread-safe event; it never calls into the speech driver cross-thread.
    """
    if not isinstance(text, str) or not text.strip():
        return True
    if stop_event is None or not callable(getattr(stop_event, "is_set", None)):
        raise VoiceUnavailable("A stop event is required for interruptible speech")
    if not 100 <= rate <= 230:
        raise VoiceUnavailable("Speech rate must be 100–230")
    if not 1 <= max_seconds <= 300:
        raise VoiceUnavailable("Speech timeout must be 1–300 seconds")
    try:
        import pyttsx3
    except ImportError as exc:
        raise VoiceUnavailable("Offline TTS requires pip install pyttsx3") from exc

    engine = None
    loop_started = False
    finished = threading.Event()
    try:
        engine = pyttsx3.init()
        engine.setProperty("rate", rate)
        engine.connect("finished-utterance",
                       lambda name, completed: finished.set())
        engine.say(text[:500])
        engine.startLoop(False)
        loop_started = True
        if on_ready is not None:
            on_ready()
        deadline = time.monotonic() + max_seconds
        while not finished.is_set() and not stop_event.is_set():
            if time.monotonic() >= deadline:
                raise VoiceUnavailable("Speech playback exceeded its safety timeout")
            engine.iterate()
            time.sleep(0.01)
        interrupted = stop_event.is_set() and not finished.is_set()
        if interrupted:
            engine.stop()
        return not interrupted
    except VoiceUnavailable:
        raise
    except Exception as exc:
        raise VoiceUnavailable("Interruptible offline speech failed: " + str(exc)) from exc
    finally:
        if engine is not None:
            try:
                engine.stop()
            except Exception:
                pass
            if loop_started:
                try:
                    engine.endLoop()
                except Exception:
                    pass
