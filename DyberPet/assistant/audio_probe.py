"""Explicit, short microphone capture probe; PCM is measured in memory and discarded."""
from __future__ import annotations

import math
import struct
import threading
import time
from dataclasses import dataclass

from .voice_devices import resolve_microphone
from .voice_errors import VoiceUnavailable


@dataclass(frozen=True)
class MicrophoneProbeResult:
    sample_rate: int
    frames: int
    duration_seconds: float
    rms: float
    peak: int
    clipped_samples: int


def probe_microphone(stop_event, *, microphone=None, sample_rate: int = 16000,
                     duration_seconds: float = 1.0) -> MicrophoneProbeResult | None:
    """Capture a bounded mono int16 sample, report levels, and retain no audio."""
    if stop_event is None or not callable(getattr(stop_event, "is_set", None)):
        raise VoiceUnavailable("麦克风测试需要有效的停止事件")
    if stop_event.is_set():
        return None
    if type(sample_rate) is not int or not 8000 <= sample_rate <= 48000:
        raise VoiceUnavailable("麦克风测试采样率必须为 8000–48000 Hz")
    if (isinstance(duration_seconds, bool)
            or not isinstance(duration_seconds, (int, float))
            or not math.isfinite(duration_seconds)
            or not 0.25 <= duration_seconds <= 2.0):
        raise VoiceUnavailable("麦克风测试时长必须为 0.25–2 秒")
    try:
        import sounddevice as sd
    except ImportError as exc:
        raise VoiceUnavailable("麦克风测试需要安装 sounddevice") from exc
    if stop_event.is_set():
        return None
    try:
        device = resolve_microphone(microphone, sd)
        if stop_event.is_set():
            return None
        requested_rate = sample_rate
        candidates = [requested_rate]
        try:
            info = (sd.query_devices(device, "input") if device is not None
                    else sd.query_devices(kind="input"))
            if isinstance(info, dict):
                default_rate = info.get("default_samplerate")
                if (isinstance(default_rate, (int, float))
                        and not isinstance(default_rate, bool)
                        and math.isfinite(default_rate)
                        and 8000 <= default_rate <= 192000):
                    candidates.append(int(round(default_rate)))
        except Exception:
            # Device metadata may be unavailable on a host API; common rates
            # below still provide a bounded negotiation path.
            pass
        candidates.extend((192000, 96000, 88200, 48000, 44100, 32000, 22050, 16000, 8000))
        unique_rates = tuple(dict.fromkeys(candidates))
        stream = None
        selected_rate = None
        failures = []
        for candidate in unique_rates:
            if stop_event.is_set():
                return None
            frames_limit = int(candidate * duration_seconds)
            try:
                stream = sd.RawInputStream(
                    samplerate=candidate, blocksize=min(4000, frames_limit),
                    channels=1, dtype="int16",
                    **({} if device is None else {"device": device}))
                selected_rate = candidate
                break
            except Exception as exc:
                failures.append(str(exc).splitlines()[0][:120])
        if stream is None:
            detail = failures[-1] if failures else "no supported sample rate"
            raise VoiceUnavailable(
                "麦克风不接受 16/192/96/88.2/48/44.1/32/22.05/8 kHz 常见采样率；"
                "请检查设备格式或系统音频服务：" + detail)
        frames_limit = int(selected_rate * duration_seconds)
        started = time.monotonic()
        captured = 0
        sum_squares = 0
        peak = 0
        clipped = 0
        try:
            with stream:
                while captured < frames_limit and not stop_event.is_set():
                    count = min(4000, frames_limit - captured)
                    payload, overflow = stream.read(count)
                    if stop_event.is_set():
                        return None
                    if overflow:
                        raise VoiceUnavailable("麦克风测试发生输入溢出；请关闭其他占用设备的程序后重试")
                    raw = memoryview(payload).tobytes()
                    if len(raw) != count * 2:
                        raise VoiceUnavailable("麦克风返回的 PCM 数据长度无效")
                    samples = struct.unpack("<" + "h" * count, raw)
                    for value in samples:
                        magnitude = abs(value)
                        sum_squares += value * value
                        peak = max(peak, magnitude)
                        if magnitude >= 32760:
                            clipped += 1
                    captured += count
        finally:
            if not stream.closed:
                stream.close()
        if stop_event.is_set():
            return None
        if captured < max(1, int(selected_rate * 0.25)):
            raise VoiceUnavailable("麦克风测试采集时间不足；请重新测试")
        elapsed = max(0.0, time.monotonic() - started)
        return MicrophoneProbeResult(
            sample_rate=selected_rate,
            frames=captured,
            duration_seconds=elapsed,
            rms=math.sqrt(sum_squares / captured),
            peak=peak,
            clipped_samples=clipped,
        )
    except VoiceUnavailable:
        raise
    except Exception as exc:
        if stop_event.is_set():
            return None
        raise VoiceUnavailable("麦克风测试失败：" + " ".join(str(exc).split())[:240]) from exc
