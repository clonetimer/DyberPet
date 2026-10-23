"""Authenticity audit of a locally installed Guga character, without art copying.

Checks *engineering readiness*, never infers artistic fidelity or copyright
permission from a file name, a video URL, or a playable WAV. The reviewer must
compare specific authorized material manually.
"""
from __future__ import annotations

import json
import re
import struct
import wave
from pathlib import Path

REFERENCE_PAGES = {
    "character_background": "https://knowyourmeme.com/memes/gugu-gaga-penguin",
    "desktop_pet_demo": "https://www.bilibili.com/video/BV1MGLN6eEuh/",
    "desktop_pet_v02": "https://www.bilibili.com/video/BV1UJoEBrE9J",
}
EXPECTED_ACTION_GROUPS = {
    "idle": ("default", "idle", "stand"),
    "left_walk": ("left_walk", "walk_left"),
    "right_walk": ("right_walk", "walk_right"),
    "sleep": ("sleep", "fall_asleep"),
    "interact": ("patpat", "wave", "happy", "jump", "touch", "angry"),
    "speak": ("speak", "talk", "talking", "mouth", "speaking"),
}
PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class FidelityError(ValueError):
    pass


def png_metadata(path: Path):
    """Read actual PNG IHDR only: full transparency requires manual preview."""
    with path.open("rb") as stream:
        header = stream.read(33)
    if len(header) != 33 or header[:8] != PNG_SIGNATURE:
        raise FidelityError("Invalid PNG image: " + path.name)
    if header[12:16] != b"IHDR":
        raise FidelityError("PNG IHDR missing: " + path.name)
    w, h, bit_depth, kind = struct.unpack(">IIBB", header[16:26])
    if not (0 < w <= 8192 and 0 < h <= 8192):
        raise FidelityError("Invalid PNG dimensions: " + path.name)
    # Truecolor+alpha = 6; grayscale+alpha = 4; indexed PNG may have tRNS.
    return {"width": w, "height": h, "bit_depth": bit_depth,
            "color_type": kind, "rgba_compatible": kind in (4, 6)}


def inspect_wav(path: str | Path):
    path = Path(path).expanduser()
    if not path.is_file() or path.is_symlink():
        raise FidelityError("Select a local regular WAV file")
    if path.suffix.lower() != ".wav" or path.stat().st_size > 5 * 1024 * 1024:
        raise FidelityError("Only WAV audio up to 5 MiB is supported")
    try:
        with wave.open(str(path), "rb") as audio:
            sample_rate = audio.getframerate()
            channels = audio.getnchannels()
            width = audio.getsampwidth()
            frames = audio.getnframes()
            compression = audio.getcomptype()
    except (wave.Error, OSError, EOFError) as exc:
        raise FidelityError("Invalid or unsupported WAV file") from exc
    duration = frames / sample_rate if sample_rate else 0
    if (compression != "NONE" or width != 2 or channels not in (1, 2)
            or sample_rate not in (16000, 22050, 24000, 32000, 44100, 48000)
            or not 0.1 <= duration <= 15):
        raise FidelityError(
            "WAV must be PCM16 mono/stereo, 16–48 kHz and 0.1–15 seconds")
    return {"sample_rate": sample_rate, "channels": channels,
            "seconds": round(duration, 3), "frames": frames,
            "encoding": "PCM16"}


def inspect_guga_role(role_dir: str | Path, voice_path=None) -> dict:
    role = Path(role_dir).expanduser()
    if not role.is_dir() or role.is_symlink():
        raise FidelityError("Role folder is missing or is a symbolic link")
    act_file = role / "act_conf.json"
    pet_file = role / "pet_conf.json"
    if not act_file.is_file() or not pet_file.is_file():
        raise FidelityError("Missing DyberPet native pet_conf.json or act_conf.json")
    try:
        actions = json.loads(act_file.read_text(encoding="utf-8"))
        pet = json.loads(pet_file.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise FidelityError("Invalid role configuration JSON") from exc
    if not isinstance(actions, dict) or not isinstance(pet, dict):
        raise FidelityError("Role config must contain JSON objects")
    action_files = role / "action"
    coverage = {}
    wrong_size, invalid_images, frame_counts = [], [], {}
    for name, spec in actions.items():
        if not isinstance(spec, dict) or not isinstance(spec.get("images"), str):
            continue
        prefix = spec["images"]
        if not re.fullmatch(r"[\w-]{1,100}", prefix):
            continue
        frames = sorted(action_files.glob(prefix + "_*.png")) if action_files.is_dir() else []
        frames = [frame for frame in frames if frame.is_file() and not frame.is_symlink()
                  and re.fullmatch(re.escape(prefix) + r"_\d+\.png", frame.name)]
        frame_counts[name] = len(frames)
        for frame in frames[:100]:
            try:
                metadata = png_metadata(frame)
                if (metadata["width"], metadata["height"]) != (
                        pet.get("width"), pet.get("height")):
                    wrong_size.append(frame.name)
            except FidelityError:
                invalid_images.append(frame.name)
    for group, aliases in EXPECTED_ACTION_GROUPS.items():
        found = [name for name in aliases if frame_counts.get(name, 0) > 0]
        coverage[group] = {"available": bool(found), "matched_actions": found}
    voice = None
    if voice_path is not None:
        voice = inspect_wav(voice_path)
    problems = []
    if not coverage["idle"]["available"]:
        problems.append("No playable idle/default animation")
    if not coverage["left_walk"]["available"] or not coverage["right_walk"]["available"]:
        problems.append("Missing left/right movement animations")
    if not coverage["speak"]["available"]:
        problems.append("No dedicated speaking/mouth animation; cannot claim lip sync")
    if wrong_size:
        problems.append("Some frame dimensions differ from pet_conf width/height")
    if invalid_images:
        problems.append("Some PNG frames are invalid")
    if voice is None:
        problems.append("No licensed local Guga sample supplied")
    return {
        "schema_version": 1,
        "target": "guga_penguin_fan_derivative",
        "role_name": role.name,
        "reference_pages": REFERENCE_PAGES,
        "action_coverage": coverage,
        "frame_count_by_action": frame_counts,
        "image_size_mismatches": sorted(set(wrong_size)),
        "invalid_images": sorted(set(invalid_images)),
        "sample_audio": voice,
        "manual_review_required": {
            "shape": "Compare to specific creator/version; penguin hood, silhouette, "
                     "eyes, expression and proportion, do not infer from file names",
            "motion": "Review standing, waddling, reacting, sleep and mouth animation",
            "signature_audio": "Compare authorized recording by ear; inspect attribution",
            "chat_voice": "A separate TTS/synth voice review is needed; pyttsx3 is generic",
            "rights": "Confirm use and redistribution rights per actual work and audio",
        },
        "issues": problems,
        "authenticity_status": "not_verified",
        "not_verified_reason":
            "Metadata and frame counts cannot prove resemblance or permissions",
    }
