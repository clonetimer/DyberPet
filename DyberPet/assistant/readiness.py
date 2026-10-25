"""Read-only local assistant capability check; no audio/network/file mutation.

This reports configuration readiness, not proof that a microphone, speaker, LM
Studio model or PPL service will work on this computer.
"""
from __future__ import annotations

from importlib.util import find_spec
from pathlib import Path
from urllib.parse import urlsplit


def _local_http(url):
    try:
        parsed = urlsplit(str(url).strip())
        return (parsed.scheme == "http"
                and parsed.hostname in ("127.0.0.1", "localhost", "::1")
                and parsed.port is not None
                and not parsed.username and not parsed.password
                and parsed.path in ("", "/")
                and not parsed.query and not parsed.fragment)
    except (ValueError, TypeError):
        return False


def inspect_readiness(*, voice_model="", llm_endpoint="", llm_model="",
                      ppl_enabled=False, ppl_endpoint="", dependency_lookup=None,
                      directory_check=None):
    """Return deterministic per-feature readiness without connecting to anything."""
    lookup = dependency_lookup or (lambda name: find_spec(name) is not None)
    is_directory = directory_check or (lambda path: Path(path).expanduser().is_dir())
    items = []

    def emit(name, ready, detail):
        items.append({"feature": name, "status": "configured" if ready else "needs_setup",
                      "detail": detail})

    tts = bool(lookup("pyttsx3"))
    emit("语音播报", tts,
         "已找到 pyttsx3；扬声器和中文音色仍需实际试听" if tts
         else "缺少 pyttsx3：可在本机安装后再试听")

    dependencies = bool(lookup("vosk")) and bool(lookup("sounddevice"))
    directory = str(voice_model).strip()
    model_ok = bool(directory) and bool(is_directory(directory))
    emit("离线语音识别", dependencies and model_ok,
         "已找到 Vosk、sounddevice 和模型目录；尚未访问麦克风" if dependencies and model_ok
         else "请安装 vosk、sounddevice 并选取有效的 Vosk 模型目录；不会自动录音")

    chat_ok = _local_http(llm_endpoint) and bool(str(llm_model).strip())
    emit("本地 AI 对话", chat_ok,
         "已填写本机地址与模型 ID；LM Studio 服务未连接验证" if chat_ok
         else "请填写 loopback HTTP 模型地址和已加载的模型 ID")

    if ppl_enabled:
        emit("PPL 人设关系", _local_http(ppl_endpoint),
             "PPL 本地地址格式正确；服务未连接验证" if _local_http(ppl_endpoint)
             else "PPL 已启用，但地址不是有效的本机 HTTP 地址")
    else:
        items.append({"feature": "PPL 人设关系", "status": "disabled",
                      "detail": "未启用（可选）；不会访问本地 PPL 服务"})

    return {"checks": items, "network_accessed": False, "microphone_accessed": False,
            "writes_performed": False}


def readiness_text(report):
    markers = {"configured": "已配置", "needs_setup": "待配置", "disabled": "未启用"}
    rows = ["本机功能自检（只读；不联网、不录音、不更改文件）"]
    for item in report["checks"]:
        rows.append("{}：{} — {}".format(
            item["feature"], markers[item["status"]], item["detail"]))
    rows.append("说明：配置就绪不代表音色、模型服务或 PPL API 已经过实机验收。")
    return "\n".join(rows)
