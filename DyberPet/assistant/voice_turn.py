"""Opt-in, one-utterance capture for a sequential voice conversation."""
from __future__ import annotations

import json
import time
from pathlib import Path

from .voice_devices import resolve_microphone
from .voice_errors import VoiceUnavailable


def _recognition_text(payload, field):
    try:
        result = json.loads(payload)
    except (TypeError, ValueError) as exc:
        raise VoiceUnavailable("Invalid Vosk recognition result") from exc
    if not isinstance(result, dict) or not isinstance(result.get(field), str):
        raise VoiceUnavailable("Invalid Vosk recognition result")
    return result[field].strip()[:2000]


class VoiceTurnRecognizer:
    """Reuse a Vosk model across sequential worker-owned listening turns.

    Construction does not import audio drivers or load a model. Call ``listen``
    on the audio worker; each call owns and closes its own microphone stream and
    recognizer. An instance belongs to one conversation and is not concurrent.
    Audio stays in memory and a cancelled turn never submits its partial text.
    """

    def __init__(self, model_dir: str | Path):
        self._model_dir = model_dir
        self._model = None

    def listen(self, stop_event, *, on_partial=None, on_ready=None,
               sample_rate: int = 16000, max_seconds: float = 30.0,
               microphone=None) -> str:
        """Return one utterance after closing capture, or ``""`` on stop.

        A timeout may finish the current nonempty utterance. No speech or a
        driver/recognizer error raises ``VoiceUnavailable`` without retrying.
        The listening limit is positive and at most 30 seconds, bounded by both
        captured PCM duration and wall time; native driver calls may still block.
        """
        if stop_event is None or not callable(getattr(stop_event, "is_set", None)):
            raise VoiceUnavailable("A stop event is required for voice conversation")
        if stop_event.is_set():
            return ""
        try:
            if (isinstance(max_seconds, bool)
                    or not isinstance(max_seconds, (int, float))
                    or not 0 < max_seconds <= 30):
                raise VoiceUnavailable(
                    "Voice turn listening limit must be greater than 0 and at most 30 seconds")
            if (isinstance(sample_rate, bool) or not isinstance(sample_rate, int)
                    or sample_rate <= 0):
                raise VoiceUnavailable("Microphone sample rate must be a positive integer")
            if on_partial is not None and not callable(on_partial):
                raise VoiceUnavailable("Partial transcript callback must be callable")
            if on_ready is not None and not callable(on_ready):
                raise VoiceUnavailable("Microphone ready callback must be callable")
            if isinstance(self._model_dir, str) and not self._model_dir.strip():
                raise VoiceUnavailable(
                    "Select an installed offline Vosk language model folder")
            path = Path(self._model_dir).expanduser().resolve()
            if not path.is_dir():
                raise VoiceUnavailable(
                    "Select an installed offline Vosk language model folder")
            try:
                import sounddevice as sd
                import vosk
            except ImportError as exc:
                raise VoiceUnavailable(
                    "Offline recognition requires pip install vosk sounddevice") from exc

            if stop_event.is_set():
                return ""
            if self._model is None:
                self._model = vosk.Model(str(path))
            if stop_event.is_set():
                return ""
            recognizer = vosk.KaldiRecognizer(self._model, sample_rate)
            if stop_event.is_set():
                return ""
            device = resolve_microphone(microphone, sd)
            if stop_event.is_set():
                return ""
            device_options = {} if device is None else {"device": device}

            frame_limit = max(1, int(max_seconds * sample_rate))
            captured_frames = 0
            last_partial = ""
            transcript = ""
            stream = sd.RawInputStream(samplerate=sample_rate, blocksize=4000,
                                       channels=1, dtype="int16", **device_options)
            try:
                if stop_event.is_set():
                    return ""
                with stream:
                    deadline = time.monotonic() + max_seconds
                    if not stop_event.is_set() and on_ready is not None:
                        on_ready()
                    while (not stop_event.is_set()
                           and captured_frames < frame_limit
                           and time.monotonic() < deadline):
                        frames = min(4000, frame_limit - captured_frames)
                        payload, overflow = stream.read(frames)
                        if stop_event.is_set():
                            break
                        if overflow:
                            raise VoiceUnavailable("Microphone overflow; please try again")
                        try:
                            audio = memoryview(payload).tobytes()
                        except (TypeError, ValueError) as exc:
                            raise VoiceUnavailable("Microphone returned invalid PCM audio") from exc
                        if len(audio) != frames * 2:
                            raise VoiceUnavailable("Microphone returned empty or invalid PCM audio")
                        captured_frames += len(audio) // 2
                        accepted = recognizer.AcceptWaveform(audio)
                        if stop_event.is_set():
                            break
                        if not isinstance(accepted, int) or accepted not in (0, 1):
                            raise VoiceUnavailable("Invalid Vosk recognition status")
                        if accepted:
                            transcript = _recognition_text(recognizer.Result(), "text")
                            if transcript:
                                break
                            last_partial = ""
                        else:
                            partial = _recognition_text(recognizer.PartialResult(), "partial")
                            if stop_event.is_set():
                                break
                            if partial and partial != last_partial and on_partial is not None:
                                on_partial(partial)
                            last_partial = partial
            finally:
                # RawInputStream opens in its constructor, then starts in
                # __enter__. A failed start never reaches __exit__.
                if not stream.closed:
                    stream.close()

            # Cancellation can arrive during __exit__, so returning from inside
            # the context manager would risk submitting a cancelled utterance.
            if stop_event.is_set():
                return ""
            if transcript:
                return transcript
            transcript = _recognition_text(recognizer.FinalResult(), "text")
            if stop_event.is_set():
                return ""
            if transcript:
                return transcript
            raise VoiceUnavailable("语音监听超时，没有识别到语音；请重新开始语音对话")
        except Exception as exc:
            if stop_event.is_set():
                return ""
            if isinstance(exc, VoiceUnavailable):
                raise
            raise VoiceUnavailable("Voice turn recognition failed: " + str(exc)) from exc
