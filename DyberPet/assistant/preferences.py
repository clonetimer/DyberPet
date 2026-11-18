"""Local-only assistant preferences with atomic updates and strict schema.

No dialogue, microphone recordings, PPL snapshot bodies or model outputs are
saved. A manually granted alternative file workspace is session-only.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .persona import DEFAULT_CHAT_URL, DEFAULT_PPL_URL, PERSONAS, _local_base, AssistantServiceError

PREF_VERSION = 1
MAX_PREF_BYTES = 16384


def default_preference_path() -> Path:
    if os.name == "nt" and os.environ.get("APPDATA"):
        return Path(os.environ["APPDATA"]) / "DyberPet" / "assistant.json"
    return Path.home() / ".config" / "DyberPet" / "assistant.json"


def defaults() -> dict:
    return {"schema_version": PREF_VERSION,
            "llm_url": DEFAULT_CHAT_URL,
            "llm_model": "",
            "ppl_url": DEFAULT_PPL_URL,
            "ppl_enabled": False,
            "voice_model": "",
            "microphone": None,
            "voice_profiles": {},
            "bubble_enabled": True,
            "auto_speak": False,
            "motion_enabled": True,
            "personas": {}}


def validate(raw) -> dict:
    if not isinstance(raw, dict) or raw.get("schema_version") != PREF_VERSION:
        raise ValueError("Unsupported assistant preference format")
    result = defaults()
    for key, size in (("llm_url", 128), ("ppl_url", 128),
                      ("llm_model", 120), ("voice_model", 1024)):
        val = raw.get(key, result[key])
        if not isinstance(val, str) or len(val) > size:
            raise ValueError("Invalid assistant preference: " + key)
        result[key] = val
    try:
        _local_base(result["llm_url"])
        _local_base(result["ppl_url"])
    except AssistantServiceError as exc:
        raise ValueError("Assistant endpoints must be local loopback services") from exc
    for key in ("ppl_enabled", "bubble_enabled", "auto_speak", "motion_enabled"):
        val = raw.get(key, result[key])
        if type(val) is not bool:
            raise ValueError("Invalid boolean assistant preference")
        result[key] = val
    persona = raw.get("personas", {})
    if not isinstance(persona, dict) or len(persona) > 100:
        raise ValueError("Invalid character persona settings")
    for character, key in persona.items():
        if (not isinstance(character, str) or len(character) > 120
                or not isinstance(key, str) or key not in PERSONAS):
            raise ValueError("Invalid character persona mapping")
    result["personas"] = dict(persona)
    microphone = raw.get("microphone")
    if microphone is not None:
        if (not isinstance(microphone, dict)
                or not isinstance(microphone.get("name"), str)
                or not microphone["name"].strip() or len(microphone["name"]) > 256
                or not isinstance(microphone.get("host_api"), str)
                or not microphone["host_api"].strip() or len(microphone["host_api"]) > 128):
            raise ValueError("Invalid microphone selection")
        result["microphone"] = {key: microphone[key] for key in ("name", "host_api")}
    profiles = raw.get("voice_profiles", {})
    if not isinstance(profiles, dict) or len(profiles) > 100:
        raise ValueError("Invalid character voice settings")
    for character, profile in profiles.items():
        if (not isinstance(character, str) or len(character) > 120
                or not isinstance(profile, dict)
                or not isinstance(profile.get("voice_id"), str)
                or len(profile["voice_id"]) > 512
                or type(profile.get("rate")) is not int
                or not 100 <= profile["rate"] <= 230):
            raise ValueError("Invalid character voice profile")
        result["voice_profiles"][character] = {
            "voice_id": profile["voice_id"], "rate": profile["rate"]}
    return result


def load(path=None) -> dict:
    path = Path(path) if path is not None else default_preference_path()
    if not path.is_file():
        return defaults()
    if path.stat().st_size > MAX_PREF_BYTES:
        raise ValueError("Assistant preferences exceed 16 KiB")
    return validate(json.loads(path.read_text(encoding="utf-8")))


def save(data, path=None) -> Path:
    path = Path(path) if path is not None else default_preference_path()
    payload = json.dumps(validate(data), ensure_ascii=False, indent=2).encode("utf-8")
    if len(payload) > MAX_PREF_BYTES:
        raise ValueError("Assistant preferences exceed 16 KiB")
    path.parent.mkdir(parents=True, exist_ok=True)
    # Do not follow a symlink placed at the destination.
    if path.is_symlink():
        raise ValueError("Assistant preferences path cannot be a symlink")
    name = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="wb", prefix=".assistant-", suffix=".tmp",
                dir=path.parent, delete=False) as file:
            name = Path(file.name)
            file.write(payload)
            file.flush()
            os.fsync(file.fileno())
        try:
            name.chmod(0o600)
        except OSError:
            pass
        os.replace(str(name), str(path))
    finally:
        if name is not None and name.exists():
            name.unlink()
    return path
