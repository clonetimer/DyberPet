"""Bounded, content-free observations of user-started assistant operations.

Nothing here starts a model, audio driver, subprocess or network request. Only
fixed categories and numeric observations cross this boundary; transcripts and
exception details are deliberately absent from the API and exported schema.
"""
from __future__ import annotations

import json
import math
import os
import platform
import re
import sys
import time
from importlib import metadata
from pathlib import Path


MAX_RECORDS = 30
MAX_REPORT_BYTES = 64 * 1024
MAX_BUILD_INFO_BYTES = 16 * 1024
MAX_NUMBER = (1 << 53) - 1
KINDS = frozenset(("chat", "model_probe", "plan", "listen", "speech",
                   "models", "voice_check", "voice_options", "other"))
OUTCOMES = frozenset(("running", "completed", "cancelled", "failed", "interrupted"))
STOP_REASONS = frozenset(("user", "scope_changed", "window_closed", "configuration_changed"))
ERROR_CODES = frozenset(("invalid_endpoint", "connection", "timeout", "http",
                        "redirect", "response", "no_models", "service",
                        "voice_unavailable", "internal_error", "invalid_result"))
FEEDBACK_KEYS = ("model_reply", "recognition", "speech")
FEEDBACK_VALUES = frozenset(("not_checked", "satisfied", "problem"))
BUILD_CANDIDATES = frozenset(("portable-ci-review", "linux-x86_64-ci-review"))
LIMITATIONS = (
    "仅记录本次助手窗口中的程序观察；模型质量、识别准确度和实际听感由人工反馈表达。",
    "CPU 为桌宠进程在活动期间的占用，不含独立模型服务；100% 表示一个逻辑核心，可超过 100%。",
    "内存为当前进程驻留量的采样最大值；活动中通常每秒采样，开始/结束额外采样，可能漏过瞬时峰值；不可用数据为 null。",
    "未测量 GPU、帧率、端到端音频延迟或长期稳定性；程序完成不等于实机验收通过。",
)
_INTEGER_FIELDS = ("id", "displayed_chars", "result_chars", "model_count",
                   "rss_max_bytes", "sample_count")
_NUMBER_FIELDS = ("elapsed_ms", "first_text_ms", "ready_ms", "stop_requested_ms",
                  "stop_settled_ms", "cpu_seconds", "cpu_percent_one_core")
_BOOLEAN_FIELDS = ("recognition_ready", "tts_ready", "engine_completed")
_ENUM_FIELDS = {"kind": KINDS, "outcome": OUTCOMES,
                "stop_reason": STOP_REASONS, "error_code": ERROR_CODES}
_VERSION = re.compile(r"[0-9]{1,3}\.[0-9]{1,3}(?:\.[0-9]{1,3}){0,2}(?:(?:a|b|rc)[0-9]{1,3})?")
_COMMIT = re.compile(r"[0-9a-fA-F]{40}")
_WINDOWS_COUNTERS = None


def _number(value):
    if type(value) not in (int, float) or not 0 <= value <= MAX_NUMBER:
        return None
    return value if math.isfinite(value) else None


def _integer(value):
    return value if type(value) is int and 0 <= value <= MAX_NUMBER else None


def _choice(value, choices):
    return value if type(value) is str and value in choices else None


def _version(value):
    return value if type(value) is str and _VERSION.fullmatch(value) else None


def _commit(value):
    return value.lower() if type(value) is str and _COMMIT.fullmatch(value) else None


def _elapsed_ms(start, end):
    if start is None or end is None:
        return None
    return _number(round(max(0.0, end - start) * 1000, 3))


def _clean_environment(raw):
    raw = raw if type(raw) is dict else {}
    return {
        "system": _choice(raw.get("system"), ("Linux", "Windows", "Darwin")),
        "architecture": _choice(raw.get("architecture"), ("x86_64", "x86", "arm64", "arm")),
        "python_version": _version(raw.get("python_version")),
        "qt_version": _version(raw.get("qt_version")),
        "pyside_version": _version(raw.get("pyside_version")),
        "mode": _choice(raw.get("mode"), ("source", "frozen")),
        "build_info_status": _choice(raw.get("build_info_status"), ("valid", "missing", "invalid")),
        "checkout_commit": _commit(raw.get("checkout_commit")),
        "candidate": _choice(raw.get("candidate"), BUILD_CANDIDATES),
    }


def _clean_observation(raw):
    result = {key: _integer(raw.get(key)) for key in _INTEGER_FIELDS}
    result.update({key: _number(raw.get(key)) for key in _NUMBER_FIELDS})
    result.update({key: raw.get(key) if type(raw.get(key)) is bool else None
                   for key in _BOOLEAN_FIELDS})
    result.update({key: _choice(raw.get(key), choices)
                   for key, choices in _ENUM_FIELDS.items()})
    return result


def _clean_feedback(raw):
    raw = raw if type(raw) is dict else {}
    return {key: _choice(raw.get(key), FEEDBACK_VALUES) or "not_checked"
            for key in FEEDBACK_KEYS}


def _clean_report(raw):
    if (type(raw) is not dict or type(raw.get("schema_version")) is not int
            or raw.get("schema_version") != 1):
        raise ValueError("Unsupported diagnostic report format")
    observations = raw.get("observations", [])
    if (type(observations) is not list or len(observations) > MAX_RECORDS
            or any(type(row) is not dict for row in observations)):
        raise ValueError("Invalid diagnostic observations")
    return {"schema_version": 1,
            "environment": _clean_environment(raw.get("environment")),
            "observations": [_clean_observation(row) for row in observations],
            "feedback": _clean_feedback(raw.get("feedback")),
            "limitations": list(LIMITATIONS)}


def _windows_rss():
    import ctypes

    # Microsoft PROCESS_MEMORY_COUNTERS uses DWORD followed by pointer-sized
    # SIZE_T fields. WorkingSetSize is current bytes, not PeakWorkingSetSize.
    # https://learn.microsoft.com/windows/win32/api/psapi/ns-psapi-process_memory_counters
    global _WINDOWS_COUNTERS
    if _WINDOWS_COUNTERS is None:
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32)] + [
                (name, ctypes.c_size_t) for name in (
                    "PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
                    "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
                    "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]
        # ctypes caches POINTER classes strongly. Reuse this structure type so
        # periodic sampling cannot grow that cache once per operation/sample.
        _WINDOWS_COUNTERS = Counters
    counters_type = _WINDOWS_COUNTERS

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    current = kernel.GetCurrentProcess
    current.argtypes = []
    current.restype = ctypes.c_void_p
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    memory = psapi.GetProcessMemoryInfo
    memory.argtypes = [ctypes.c_void_p, ctypes.POINTER(counters_type), ctypes.c_uint32]
    memory.restype = ctypes.c_int
    counters = counters_type()
    counters.cb = ctypes.sizeof(counters)
    if not memory(current(), ctypes.byref(counters), counters.cb):
        return None
    return _integer(counters.WorkingSetSize)


def sample_process_usage() -> dict:
    """Sample this process only; unavailable values remain null, never zero."""
    try:
        cpu = _number(time.process_time())
    except Exception:
        cpu = None
    rss = None
    try:
        if sys.platform.startswith("linux"):
            # Kernel proc documentation defines statm's second field as
            # resident pages. It is inexpensive but itself an approximation.
            # https://docs.kernel.org/filesystems/proc.html
            pages = int(Path("/proc/self/statm").read_text(encoding="ascii").split()[1])
            page_size = os.sysconf("SC_PAGE_SIZE")
            if pages >= 0 and type(page_size) is int and page_size > 0:
                rss = _integer(pages * page_size)
        elif sys.platform == "win32":
            rss = _windows_rss()
    except Exception:
        pass
    return {"cpu_seconds": cpu, "rss_bytes": rss}


def runtime_environment() -> dict:
    """Read safe runtime/build facts without importing Qt or executing git."""
    raw = {
        "system": {"linux": "Linux", "win32": "Windows", "darwin": "Darwin"}.get(sys.platform),
        "python_version": ".".join(str(part) for part in sys.version_info[:3]),
        "mode": "frozen" if getattr(sys, "frozen", False) else "source",
        "build_info_status": "missing",
    }
    try:
        machine = platform.machine().lower()
        raw["architecture"] = {
            "amd64": "x86_64", "x86_64": "x86_64", "x64": "x86_64",
            "i386": "x86", "i486": "x86", "i586": "x86", "i686": "x86", "x86": "x86",
            "aarch64": "arm64", "arm64": "arm64", "armv7l": "arm", "armv6l": "arm",
        }.get(machine)
    except Exception:
        pass
    try:
        pyside = sys.modules.get("PySide6")
        raw["pyside_version"] = getattr(pyside, "__version__", None) or metadata.version("PySide6")
    except Exception:
        pass
    try:
        qt = sys.modules.get("PySide6.QtCore")
        if qt is not None:
            raw["qt_version"] = qt.qVersion()
    except Exception:
        pass
    try:
        root = (Path(sys.executable).resolve().parent if raw["mode"] == "frozen"
                else Path(__file__).resolve().parents[2])
        path = root / "BUILD_INFO.json"
        if path.is_symlink():
            raise ValueError("Build metadata cannot be a symbolic link")
        with path.open("rb") as file:
            payload = file.read(MAX_BUILD_INFO_BYTES + 1)
        if len(payload) > MAX_BUILD_INFO_BYTES:
            raise ValueError("Build metadata is too large")
        build = json.loads(payload.decode("utf-8-sig"))
        if type(build) is not dict:
            raise ValueError("Invalid build metadata")
        checkout = _commit(build.get("source_commit"))
        candidate = _choice(build.get("candidate"), BUILD_CANDIDATES)
        if checkout is None or candidate is None:
            raise ValueError("Invalid build identity")
        # Existing packages use git rev-parse HEAD; on PR CI this can be a
        # synthetic merge checkout, so never call it a source-branch commit.
        raw.update(checkout_commit=checkout, candidate=candidate, build_info_status="valid")
    except FileNotFoundError:
        pass
    except Exception:
        raw["build_info_status"] = "invalid"
    return _clean_environment(raw)


class TrialRecorder:
    """Single-window bounded observations; callers pass accepted UI events.

    Used on the owning Qt thread. Sampling and snapshots never retain user
    content. A completed operation ID cannot be reused or changed by callbacks.
    """

    def __init__(self, capacity=30, *, clock=None, sampler=None, environment=None):
        if type(capacity) is not int or not 1 <= capacity <= MAX_RECORDS:
            raise ValueError("Trial capacity must be 1 to 30")
        self._capacity = capacity
        self._clock = clock if clock is not None else time.monotonic
        self._sampler = sampler if sampler is not None else sample_process_usage
        self._environment = _clean_environment(
            runtime_environment() if environment is None else environment)
        self._runs = []
        self._next_id = 1
        self.reset_feedback()

    def _now(self):
        try:
            return _number(self._clock())
        except Exception:
            return None

    def _active(self, run_id):
        if type(run_id) is not int:
            return None
        return next((run for run in self._runs if run["id"] == run_id
                     and run["outcome"] == "running"), None)

    def begin(self, kind) -> int:
        if _choice(kind, KINDS) is None:
            raise ValueError("Invalid trial kind")
        now = self._now()
        run = _clean_observation({"id": self._next_id, "kind": kind, "outcome": "running",
                                  "displayed_chars": 0, "sample_count": 0})
        run.update(_started=now, _stopped=None, _sample_at=None, _cpu_baseline=None)
        self._next_id += 1
        self._runs.append(run)
        del self._runs[:-self._capacity]
        self._sample(run, now, force=True, initial=True)
        return run["id"]

    def text(self, run_id, count):
        run = self._active(run_id)
        if run is None or run["stop_reason"] is not None:
            return
        if _integer(count) is None:
            raise ValueError("Displayed character count must be a nonnegative integer")
        if count:
            if run["first_text_ms"] is None:
                run["first_text_ms"] = _elapsed_ms(run["_started"], self._now())
            run["displayed_chars"] = min(MAX_NUMBER, run["displayed_chars"] + count)

    def ready(self, run_id):
        run = self._active(run_id)
        if run is not None and run["stop_reason"] is None and run["ready_ms"] is None:
            run["ready_ms"] = _elapsed_ms(run["_started"], self._now())

    def request_stop(self, run_id, reason="user"):
        run = self._active(run_id)
        if run is None or run["stop_reason"] is not None:
            return
        if _choice(reason, STOP_REASONS) is None:
            raise ValueError("Invalid trial stop reason")
        run["stop_reason"] = reason
        run["_stopped"] = self._now()
        run["stop_requested_ms"] = _elapsed_ms(run["_started"], run["_stopped"])

    def observe(self, run_id, *, result_chars=None, model_count=None,
                recognition_ready=None, tts_ready=None, engine_completed=None):
        run = self._active(run_id)
        if run is None:
            return
        changes = {"result_chars": result_chars, "model_count": model_count,
                   "recognition_ready": recognition_ready, "tts_ready": tts_ready,
                   "engine_completed": engine_completed}
        # Validate the entire event before changing any field.
        for key, value in changes.items():
            if value is None:
                continue
            if ((key in _BOOLEAN_FIELDS and type(value) is not bool)
                    or (key not in _BOOLEAN_FIELDS and _integer(value) is None)):
                raise ValueError("Invalid trial observation")
        run.update({key: value for key, value in changes.items() if value is not None})

    def fail(self, run_id, code):
        run = self._active(run_id)
        if run is not None:
            run["error_code"] = _choice(code, ERROR_CODES) or "internal_error"

    def _sample(self, run, now, *, force=False, initial=False):
        previous = run["_sample_at"]
        if not force and (now is None or previous is None or now - previous < 1.0):
            return
        run["_sample_at"] = now
        try:
            usage = self._sampler()
        except Exception:
            usage = {}
        usage = usage if type(usage) is dict else {}
        cpu, rss = _number(usage.get("cpu_seconds")), _integer(usage.get("rss_bytes"))
        if cpu is not None or rss is not None:
            run["sample_count"] += 1
        if initial:
            run["_cpu_baseline"] = cpu
        baseline = run["_cpu_baseline"]
        run["cpu_seconds"] = None
        run["cpu_percent_one_core"] = None
        if cpu is not None and baseline is not None and cpu >= baseline:
            run["cpu_seconds"] = round(cpu - baseline, 6)
            elapsed = _elapsed_ms(run["_started"], now)
            if elapsed:
                run["cpu_percent_one_core"] = _number(
                    round(100000 * run["cpu_seconds"] / elapsed, 3))
        if rss is not None:
            previous_rss = run["rss_max_bytes"]
            run["rss_max_bytes"] = max(previous_rss, rss) if previous_rss is not None else rss

    def sample(self, run_id):
        run = self._active(run_id)
        if run is not None:
            self._sample(run, self._now())

    def finish(self, run_id, outcome):
        run = self._active(run_id)
        if run is None:
            return
        now = self._now()
        self._sample(run, now, force=True)
        run["elapsed_ms"] = _elapsed_ms(run["_started"], now)
        run["stop_settled_ms"] = _elapsed_ms(run["_stopped"], now)
        if run["stop_reason"] is not None or outcome == "cancelled":
            run["outcome"] = "cancelled"
        elif run["error_code"] is not None or outcome == "failed":
            run["outcome"] = "failed"
        elif outcome == "completed":
            run["outcome"] = "completed"
        else:
            # Thread termination alone is not evidence of successful work.
            run["outcome"] = "interrupted"

    def set_feedback(self, key, value):
        if _choice(key, FEEDBACK_KEYS) is None or _choice(value, FEEDBACK_VALUES) is None:
            raise ValueError("Invalid trial feedback")
        self._feedback[key] = value

    def reset_feedback(self):
        self._feedback = {key: "not_checked" for key in FEEDBACK_KEYS}

    def clear(self):
        if any(run["outcome"] == "running" for run in self._runs):
            raise ValueError("Wait for the active trial before clearing records")
        self._runs.clear()
        self.reset_feedback()

    def snapshot(self) -> dict:
        now = self._now()
        observations = []
        for run in self._runs:
            row = _clean_observation(run)
            if run["outcome"] == "running":
                row["elapsed_ms"] = _elapsed_ms(run["_started"], now)
            observations.append(row)
        return _clean_report({"schema_version": 1, "environment": self._environment,
                              "observations": observations, "feedback": self._feedback})


def export_report(path, report) -> None:
    """Export a fresh allowlisted snapshot, exclusively creating the target."""
    payload = (json.dumps(_clean_report(report), ensure_ascii=False, indent=2,
                          allow_nan=False) + "\n").encode("utf-8")
    if len(payload) > MAX_REPORT_BYTES:
        raise ValueError("Diagnostic report exceeds 64 KiB")
    target = Path(path)
    descriptor = os.open(str(target), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    identity = os.fstat(descriptor)
    try:
        with os.fdopen(descriptor, "wb") as file:
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
    except Exception:
        # Remove only this incomplete export, not a destination replaced by
        # another process while the write was failing.
        try:
            current = target.lstat()
            if (current.st_dev, current.st_ino) == (identity.st_dev, identity.st_ino):
                target.unlink()
        except OSError:
            pass
        raise
