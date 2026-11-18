"""Explicit audio catalogs and exact, current microphone resolution.

Importing this module does not import audio drivers. Call inspection on the
audio worker: it opens no streams, loads no Vosk model and speaks no text.
Names plus host API names are best-effort identities, not hardware UIDs.
PortAudio may retain a device list until restart; no private refresh is used.
"""
from __future__ import annotations

from dataclasses import dataclass

from .voice_errors import VoiceUnavailable


@dataclass(frozen=True)
class MicrophoneInfo:
    name: str
    host_api: str
    index: int


@dataclass(frozen=True)
class SystemVoiceInfo:
    id: str
    name: str
    languages: tuple[str, ...]


@dataclass(frozen=True)
class AudioOptions:
    microphones: tuple[MicrophoneInfo, ...]
    voices: tuple[SystemVoiceInfo, ...]
    microphone_message: str
    voice_message: str


def _stopped(stop_event):
    return stop_event is not None and stop_event.is_set()


def _identity(value, limit):
    return (isinstance(value, str) and bool(value.strip()) and len(value) <= limit
            and not any(ord(character) < 32 for character in value))


def _catalog(value):
    # Reject an oversized list rather than hiding a late duplicate identity.
    if not isinstance(value, (list, tuple)) or len(value) > 1024:
        raise VoiceUnavailable("音频设备目录格式无效或超过 1024 项")
    return value


def _microphones(sd, stop_event=None):
    devices = sd.query_devices()
    if _stopped(stop_event):
        return None
    devices = _catalog(devices)
    hosts = sd.query_hostapis()
    if _stopped(stop_event):
        return None
    hosts = _catalog(hosts)
    result = []
    skipped = 0
    for device in devices:
        if _stopped(stop_event):
            return None
        if not isinstance(device, dict):
            skipped += 1
            continue
        channels = device.get("max_input_channels")
        if type(channels) is int and channels == 0:
            continue
        host_index = device.get("hostapi")
        index = device.get("index")
        if (type(channels) is not int or channels < 1
                or type(index) is not int or index < 0
                or type(host_index) is not int or not 0 <= host_index < len(hosts)
                or not _identity(device.get("name"), 256)):
            skipped += 1
            continue
        host = hosts[host_index]
        if not isinstance(host, dict) or not _identity(host.get("name"), 128):
            skipped += 1
            continue
        result.append(MicrophoneInfo(device["name"], host["name"], index))
    return tuple(result), skipped


def _language_tags(value):
    if not isinstance(value, (list, tuple)):
        return ()
    result = []
    for tag in value[:16]:
        if isinstance(tag, bytes):
            if len(tag) > 65:
                continue
            try:
                tag = tag.decode("utf-8")
            except UnicodeError:
                continue
            # eSpeak can prefix a language with one control-byte priority.
            tag = tag.lstrip("".join(chr(number) for number in range(32)))
        if not _identity(tag, 64):
            continue
        tag = tag.strip()
        if tag not in result:
            result.append(tag)
    return tuple(result)


def _voices(engine, stop_event=None):
    voices = engine.getProperty("voices")
    if _stopped(stop_event):
        return None
    result = []
    skipped = 0
    for voice in _catalog(voices):
        if _stopped(stop_event):
            return None
        try:
            voice_id = getattr(voice, "id", None)
            if not _identity(voice_id, 512):
                skipped += 1
                continue
            name = getattr(voice, "name", None)
            name = name[:256].strip() if isinstance(name, str) else ""
            if not name:
                name = voice_id[:256]
            languages = _language_tags(getattr(voice, "languages", None))
        except Exception:
            skipped += 1
            continue
        result.append(SystemVoiceInfo(voice_id, name, languages))
    return tuple(result), skipped


def _message(label, count, skipped):
    message = (f"已读取 {count} 个{label}" if count else f"未发现可用的{label}")
    if skipped:
        message += f"；已忽略 {skipped} 项无效元数据"
    return message


def _failure(label, error):
    detail = " ".join(str(error).split())[:256]
    return f"{label}读取失败：{detail}"


def inspect_audio_options(stop_event=None) -> AudioOptions | None:
    """Return plain catalogs, or None when cancelled; own all native work here.

    The two sides fail independently. Cancellation cannot interrupt a native
    initialization/query already in progress, but prevents the next operation.
    Any successfully created speech engine is stopped on this calling worker.
    """
    if stop_event is not None and not callable(getattr(stop_event, "is_set", None)):
        raise VoiceUnavailable("音频设备刷新需要有效的停止事件")
    if _stopped(stop_event):
        return None

    microphones = ()
    voices = ()
    try:
        import sounddevice as sd
        if _stopped(stop_event):
            return None
        inspected = _microphones(sd, stop_event)
        if inspected is None:
            return None
        microphones, skipped = inspected
        microphone_message = _message("输入设备", len(microphones), skipped)
    except ImportError:
        microphone_message = "输入设备读取失败：未安装 sounddevice"
    except Exception as exc:
        microphone_message = _failure("输入设备", exc)
    if _stopped(stop_event):
        return None

    try:
        import pyttsx3
        if _stopped(stop_event):
            return None
        engine = pyttsx3.init()
        try:
            if _stopped(stop_event):
                return None
            inspected = _voices(engine, stop_event)
            if inspected is None:
                return None
        finally:
            engine.stop()
        voices, skipped = inspected
        voice_message = _message("系统音色", len(voices), skipped)
    except ImportError:
        voice_message = "系统音色读取失败：未安装 pyttsx3"
    except Exception as exc:
        voice_message = _failure("系统音色", exc)
    if _stopped(stop_event):
        return None
    return AudioOptions(microphones, voices, microphone_message, voice_message)


def resolve_microphone(selection, sounddevice_module) -> int | None:
    """Resolve an exact saved identity now; None preserves the system default.

    Device indices are transient and must not be persisted. Missing or duplicate
    matches require reselection; neither case falls back to another microphone.
    """
    if selection is None:
        return None
    if (not isinstance(selection, dict)
            or not _identity(selection.get("name"), 256)
            or not _identity(selection.get("host_api"), 128)):
        raise VoiceUnavailable("麦克风选择无效；请重新选择输入设备")
    try:
        microphones, skipped = _microphones(sounddevice_module)
    except Exception as exc:
        raise VoiceUnavailable(_failure("输入设备", exc)) from exc
    if skipped:
        # A malformed entry could be another match. A partial catalog is useful
        # for display, but cannot establish a unique identity for recording.
        raise VoiceUnavailable("输入设备目录含无效元数据，无法确认唯一麦克风；请刷新或重启应用")
    matches = [microphone for microphone in microphones
               if microphone.name == selection["name"]
               and microphone.host_api == selection["host_api"]]
    if not matches:
        raise VoiceUnavailable("所选麦克风不可用；请刷新设备或重新选择，列表未更新时重启应用")
    if len(matches) != 1:
        raise VoiceUnavailable("所选麦克风名称与音频接口存在重复；请重新选择输入设备")
    return matches[0].index
