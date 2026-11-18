"""Complete, optional offline speech driven entirely by its calling worker."""
from __future__ import annotations

import math
import threading
import time
import uuid

from .voice_errors import VoiceUnavailable


def split_speech_text(text: str) -> tuple[str, ...]:
    """Preserve up to 2000 characters, preferring punctuation at 500-char cuts."""
    if not isinstance(text, str):
        raise VoiceUnavailable("Speech text must be a string")
    if len(text) > 2000:
        raise VoiceUnavailable("Speech text must not exceed 2000 characters")
    if not text.strip():
        return ()
    chunks = []
    offset = 0
    while len(text) - offset > 500:
        window = text[offset:offset + 500]
        boundary = max((window.rfind(mark) for mark in "。！？.!?；;\n"), default=-1)
        if boundary < 0:
            boundary = max((window.rfind(mark) for mark in "，,、：: \t"), default=-1)
        end = offset + (boundary + 1 if boundary >= 0 else 500)
        chunks.append(text[offset:end])
        offset = end
    if offset < len(text):
        chunks.append(text[offset:])
    return tuple(chunks)


def speak_interruptible(text: str, stop_event, *, rate: int = 170,
                        voice_id: str = "", on_ready=None, on_progress=None,
                        max_seconds: float = 300.0) -> bool:
    """Return True only after every named chunk finishes; requested stop is False.

    One engine, external loop, ready notification, and deadline cover the whole
    reply. Properties are applied before speech is queued: pyttsx3 catches queued
    driver errors and reports them through callbacks instead of raising them.
    Callbacks therefore only record state; the worker handles that state.
    """
    # Keep the splitter lossless, but do not queue silent whitespace-only
    # pieces: pyttsx3 ignores them without a finished-utterance notification.
    # Progress counts only chunks that can actually be spoken.
    chunks = tuple(chunk for chunk in split_speech_text(text) if chunk.strip())
    if not chunks:
        return True
    if stop_event is None or not callable(getattr(stop_event, "is_set", None)):
        raise VoiceUnavailable("A stop event is required for interruptible speech")
    if type(rate) is not int or not 100 <= rate <= 230:
        raise VoiceUnavailable("Speech rate must be 100–230")
    if (not isinstance(voice_id, str) or len(voice_id) > 512
            or any(ord(char) < 32 or ord(char) == 127 for char in voice_id)):
        raise VoiceUnavailable("Invalid system voice ID")
    if on_ready is not None and not callable(on_ready):
        raise VoiceUnavailable("Speech ready callback must be callable")
    if on_progress is not None and not callable(on_progress):
        raise VoiceUnavailable("Speech progress callback must be callable")
    if (not isinstance(max_seconds, (int, float)) or isinstance(max_seconds, bool)
            or not math.isfinite(max_seconds) or not 1 <= max_seconds <= 300):
        raise VoiceUnavailable("Speech timeout must be 1–300 seconds")
    if stop_event.is_set():
        return False
    deadline = time.monotonic() + max_seconds
    try:
        import pyttsx3
    except ImportError as exc:
        raise VoiceUnavailable("Offline TTS requires pip install pyttsx3") from exc

    engine = None
    loop_started = False
    connections = []
    finished = threading.Event()
    active_name = None
    utterance_completed = None
    current_chunk = 0
    driver_error = None

    def on_finished(name, completed):
        nonlocal utterance_completed
        if active_name is None or name != active_name or finished.is_set():
            return
        utterance_completed = completed if isinstance(completed, bool) else None
        finished.set()

    def on_error(name, exception):
        nonlocal driver_error
        # Property errors have no utterance name. Named stale errors, like
        # stale finish events, cannot belong to the current chunk.
        if name is not None and name != active_name:
            return
        if driver_error is None:
            driver_error = (exception if isinstance(exception, Exception) else
                            VoiceUnavailable("Speech driver reported an error"))

    def can_continue():
        # A driver failure remains a failure even when the same driver tick
        # also reports completion or observes a user stop.
        if driver_error is not None:
            raise driver_error
        if stop_event.is_set():
            return False
        if time.monotonic() >= deadline:
            raise VoiceUnavailable("Speech playback exceeded its safety timeout")
        return True

    try:
        if not can_continue():
            return False
        engine = pyttsx3.init()
        if not can_continue():
            return False
        for topic, callback in (("error", on_error), ("finished-utterance", on_finished)):
            connections.append(engine.connect(topic, callback))
            if not can_continue():
                return False
        if voice_id:
            voices = engine.getProperty("voices")
            if not can_continue():
                return False
            if not any(getattr(voice, "id", None) == voice_id for voice in voices):
                raise VoiceUnavailable(
                    "Selected system voice is no longer installed; refresh and select a voice")
            engine.setProperty("voice", voice_id)
            if not can_continue():
                return False
        engine.setProperty("rate", rate)
        if not can_continue():
            return False
        engine.startLoop(False)
        loop_started = True
        if not can_continue():
            return False
        # The first external iteration starts the driver and drains queued
        # properties. Never put a say command behind potentially failing setup.
        engine.iterate()
        if not can_continue():
            return False
        while engine.isBusy():
            engine.iterate()
            if not can_continue():
                return False
            if engine.isBusy():
                time.sleep(0.01)
        if voice_id:
            actual_voice = engine.getProperty("voice")
            if not can_continue():
                return False
            if actual_voice != voice_id:
                raise VoiceUnavailable("Speech driver did not apply the selected system voice")

        invocation = uuid.uuid4().hex
        for index, chunk in enumerate(chunks, 1):
            current_chunk = index
            active_name = "dyberpet-" + invocation + "-" + str(index)
            utterance_completed = None
            finished.clear()
            if not can_continue():
                return False
            engine.say(chunk, name=active_name)
            if not can_continue():
                return False
            if index == 1 and on_ready is not None:
                on_ready()
                if not can_continue():
                    return False
            while not finished.is_set():
                if not can_continue():
                    return False
                engine.iterate()
                if not can_continue():
                    return False
                if not finished.is_set():
                    time.sleep(0.01)
            if utterance_completed is not True:
                raise VoiceUnavailable("Speech playback did not complete")
            if on_progress is not None:
                on_progress(index, len(chunks))
            if not can_continue():
                return False
        return True
    except Exception as exc:
        # A completed prefix is not evidence that the complete reply played.
        # Preserve a driver's actual final True / any False / unknown result.
        observed = utterance_completed
        if observed is True and current_chunk < len(chunks):
            observed = None
        if isinstance(exc, VoiceUnavailable):
            exc.engine_completed = observed
            raise
        raise VoiceUnavailable(
            "Interruptible offline speech failed: " + str(exc),
            engine_completed=observed) from exc
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
            for connection in connections:
                try:
                    engine.disconnect(connection)
                except Exception:
                    pass


def speak_once(text: str, *, rate: int = 170, voice_id: str = "",
               on_ready=None, on_progress=None, max_seconds: float = 300.0) -> None:
    """Compatibility entry point using the same complete playback and cleanup."""
    speak_interruptible(text, threading.Event(), rate=rate, voice_id=voice_id,
                        on_ready=on_ready, on_progress=on_progress,
                        max_seconds=max_seconds)
