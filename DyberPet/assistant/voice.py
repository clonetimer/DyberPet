"""Opt-in offline microphone transcription and speech synthesis.

Neither package is installed by default. No always-on listening, automatic
mic activation, cloud recognition, recording retention or background uploads.
"""
from __future__ import annotations

import json
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


def speak_once(text: str, *, rate: int = 170) -> None:
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
        engine.runAndWait()
        engine.stop()
    except Exception as exc:
        raise VoiceUnavailable("Offline speech output failed: " + str(exc)) from exc
