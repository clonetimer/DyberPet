"""Opt-in offline microphone transcription and speech synthesis.

Neither package is installed by default. No always-on listening, automatic
mic activation, cloud recognition, recording retention or background uploads.
"""
from __future__ import annotations

import json
from pathlib import Path

from .voice_devices import resolve_microphone
from .voice_errors import VoiceUnavailable
from .speech import speak_once, speak_interruptible


def recognize_once(model_dir: str | Path, *, seconds: float = 4.0,
                   sample_rate: int = 16000, microphone=None) -> str:
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
        device = resolve_microphone(microphone, sd)
        device_options = {} if device is None else {"device": device}
        stream = sd.RawInputStream(samplerate=sample_rate, blocksize=4000,
                                   channels=1, dtype="int16", **device_options)
        try:
            with stream:
                for _ in range(int(seconds * sample_rate / 4000)):
                    payload, overflow = stream.read(4000)
                    if overflow:
                        raise VoiceUnavailable("Microphone overflow; please try again")
                    recognizer.AcceptWaveform(bytes(payload))
        finally:
            # Construction opens the device; a failed __enter__ still owns it.
            if not stream.closed:
                stream.close()
    except VoiceUnavailable:
        raise
    except Exception as exc:
        raise VoiceUnavailable("Microphone unavailable: " + str(exc)) from exc
    text = json.loads(recognizer.FinalResult()).get("text", "").strip()
    if not text:
        raise VoiceUnavailable("No speech recognized; please retry")
    return text[:2000]


def recognize_until_stopped(model_dir: str | Path, stop_event, *, on_partial=None,
                            on_ready=None,
                            sample_rate: int = 16000, max_seconds: float = 120.0,
                            microphone=None) -> str:
    """Capture opt-in microphone audio until user stops or the safety limit.

    Audio is processed in memory by Vosk and never written to disk. Partial
    recognition is callback-only; the final transcript is returned once.
    Ready means the input stream has opened, not merely that model loading began.
    Stopping during preparation returns an empty transcript without starting capture.
    """
    if not 1 <= max_seconds <= 300:
        raise VoiceUnavailable("Continuous listening limit must be 1–300 seconds")
    if stop_event is None or not callable(getattr(stop_event, "is_set", None)):
        raise VoiceUnavailable("A stop event is required for continuous listening")
    if on_partial is not None and not callable(on_partial):
        raise VoiceUnavailable("Partial transcript callback must be callable")
    if on_ready is not None and not callable(on_ready):
        raise VoiceUnavailable("Microphone ready callback must be callable")
    if stop_event.is_set():
        return ""
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
        if stop_event.is_set():
            return ""
        model = vosk.Model(str(path))
        if stop_event.is_set():
            return ""
        recognizer = vosk.KaldiRecognizer(model, sample_rate)
        if stop_event.is_set():
            return ""
        try:
            device = resolve_microphone(microphone, sd)
        except VoiceUnavailable:
            if stop_event.is_set():
                return ""
            raise
        if stop_event.is_set():
            return ""
        device_options = {} if device is None else {"device": device}
        last_partial = ""
        final_segments = []
        elapsed = 0.0
        stream = sd.RawInputStream(samplerate=sample_rate, blocksize=4000,
                                   channels=1, dtype="int16", **device_options)
        try:
            if stop_event.is_set():
                return ""
            with stream:
                if stop_event.is_set():
                    return ""
                if on_ready is not None:
                    on_ready()
                while not stop_event.is_set() and elapsed < max_seconds:
                    payload, overflow = stream.read(4000)
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
        finally:
            if not stream.closed:
                stream.close()
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
