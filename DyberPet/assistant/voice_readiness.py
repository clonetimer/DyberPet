"""Passive setup hints for optional offline speech components.

Readiness means only that components can be found and model marker files exist.
No audio module is imported, model loaded, or device queried by this module.
"""
from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoiceReadiness:
    recognition_ready: bool
    recognition_message: str
    tts_ready: bool
    tts_message: str


def _discoverable(module_name: str) -> bool:
    # Top-level find_spec does not import the optional native audio packages.
    # A module already in sys.modules can have absent or malformed __spec__.
    try:
        return importlib.util.find_spec(module_name) is not None
    except (ImportError, AttributeError, OSError, ValueError):
        return False


def _component_help(missing) -> str:
    if getattr(sys, "frozen", False):
        return "请重新下载完整便携包，解压全部文件后重试；如仍缺失，请反馈候选包版本。"
    return ("请确认运行桌宠的 Python 环境已安装这些组件"
            "（python -m pip install " + " ".join(missing) + "），再重启桌宠。")


def _inspect_model_directory(model_dir: str) -> tuple[bool, str]:
    if not model_dir.strip():
        return False, "尚未选择 Vosk 模型目录；请先解压模型，再选择解压后的实际模型目录。"
    try:
        folder = Path(model_dir.strip()).expanduser()
        if not folder.is_dir():
            return False, "模型目录不存在或不是文件夹；请先解压 Vosk 模型，再重新选择实际模型目录。"
        # Vosk supports both current and legacy marker layouts. The remaining
        # model contents and native compatibility are checked only when loaded.
        layouts = (
            ("am/final.mdl", "conf/model.conf"),
            ("final.mdl", "mfcc.conf"),
        )
        if any(all((folder / marker).is_file() for marker in layout)
               for layout in layouts):
            return True, ""
    except (OSError, ValueError, RuntimeError):
        return False, "无法读取模型目录；请检查路径是否有效且可访问，再重新选择解压后的 Vosk 模型目录。"
    return False, (
        "所选目录未包含 Vosk 模型标识（am/final.mdl + conf/model.conf，"
        "或 final.mdl + mfcc.conf）；如果选中了外层文件夹，请进入其内的模型文件夹。"
    )


def inspect_voice_readiness(model_dir: str) -> VoiceReadiness:
    """Inspect local prerequisites without importing drivers or using devices."""
    missing = [name for name in ("vosk", "sounddevice") if not _discoverable(name)]
    model_ready, model_message = _inspect_model_directory(model_dir)
    recognition_ready = not missing and model_ready
    recognition_messages = []
    if missing:
        recognition_messages.append(
            "未能发现识别组件：" + "、".join(missing)
            + "；" + _component_help(missing)
        )
    if model_message:
        recognition_messages.append(model_message)
    if recognition_ready:
        recognition_messages.append("识别组件和 Vosk 模型目录结构初检通过。")
    recognition_messages.append("尚未加载模型，也未测试麦克风或音频驱动。")

    tts_ready = _discoverable("pyttsx3")
    if tts_ready:
        tts_message = "已发现 pyttsx3，朗读组件初检通过。"
    else:
        tts_message = (
            "未能发现 pyttsx3；" + _component_help(("pyttsx3",))
        )
    tts_message += "尚未测试系统语音驱动或扬声器。"
    return VoiceReadiness(
        recognition_ready=recognition_ready,
        recognition_message="".join(recognition_messages),
        tts_ready=tts_ready,
        tts_message=tts_message,
    )
