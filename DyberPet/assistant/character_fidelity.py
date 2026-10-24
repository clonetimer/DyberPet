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
from .character_profiles import resolve_profile, PROFILES, CharacterProfile
from .character_motion import style_for
from .mini_motion import MiniHover

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


def inspect_character_role(role_dir: str | Path, character_name: str,
                           voice_path=None) -> dict:
    """Check technical completeness; never claim likeness or original voice."""
    profile = resolve_profile(character_name)
    if profile is None:
        raise FidelityError("No registered character fidelity profile: " + str(character_name))
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
        problems.append("No licensed local character sample supplied")
    if profile.key == "doro":
        # An action label alone is not a real 4-legged gait.
        for group in ("left_walk", "right_walk"):
            aliases = EXPECTED_ACTION_GROUPS[group]
            number = max((frame_counts.get(key, 0) for key in aliases), default=0)
            if number < 4:
                problems.append(
                    "Doro " + group +
                    " needs at least 4 native sprite frames for a gait preview; "
                    "frame count still cannot prove 4-legged motion")
    if profile.key == "paimon":
        idle_frames = max(
            (frame_counts.get(key, 0) for key in EXPECTED_ACTION_GROUPS["idle"]),
            default=0)
        if idle_frames < 2:
            problems.append(
                "Paimon needs at least 2 native idle frames for visual float animation; "
                "runtime hover alone is not a complete floating character")
    motion = style_for(character_name)
    return {
        "schema_version": 1,
        "target": ("guga_penguin_fan_derivative" if profile.key == "guga"
                   else profile.key + "_character"),
        "profile_key": profile.key,
        "profile_title": profile.title,
        "role_name": role.name,
        "reference_pages": (
            REFERENCE_PAGES if profile.key == "guga"
            else {"primary_" + str(i+1): ref for i, ref in enumerate(profile.references)}),
        "expected_visual_checks": list(profile.visual_checks),
        "expected_motion_checks": list(profile.motion_checks),
        "expected_tone_checks": list(profile.tone_checks),
        "expected_audio_checks": list(profile.audio_checks),
        "origin": profile.origin,
        "variant_note": profile.variant_note,
        "floating": profile.floating,
        "runtime_motion_policy": {
            "kind": motion.kind,
            "horizontal_multiplier": motion.horizontal_multiplier,
            "hover_lift_px_at_scale_1": motion.hover_lift,
            "bob_amplitude_px_at_scale_1": motion.bob_amplitude,
            "note": "Native window-motion heuristic only; not original authored animation",
        },
        "action_coverage": coverage,
        "frame_count_by_action": frame_counts,
        "image_size_mismatches": sorted(set(wrong_size)),
        "invalid_images": sorted(set(invalid_images)),
        "sample_audio": voice,
        "manual_review_required": {
            "shape": "Compare creator/version and: " + "; ".join(profile.visual_checks),
            "motion": "Review: " + "; ".join(profile.motion_checks),
            "signature_audio": "; ".join(profile.audio_checks),
            "chat_voice": "Generic pyttsx3 voice is NOT the character's original voice",
            "tone": "; ".join(profile.tone_checks),
            "rights": "Confirm rights separately for image, motion, audio, derivative and release",
        },
        "issues": problems,
        "authenticity_status": "not_verified",
        "not_verified_reason":
            "Metadata and frame counts cannot prove resemblance or permissions",
    }


def inspect_mini_character_role(role_dir: str | Path,
                                character_name: str, voice_path=None) -> dict:
    """Audit a genuine res/pet mini-role and its authoritative follow flags."""
    result = inspect_character_role(role_dir, character_name, voice_path)
    role = Path(role_dir).expanduser()
    try:
        conf = json.loads((role / "pet_conf.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise FidelityError("Mini-pet configuration is missing or invalid") from exc
    if not isinstance(conf, dict):
        raise FidelityError("Mini-pet configuration must be an object")
    follow_x, follow_y = conf.get("follow_main_x", True), conf.get("follow_main_y", False)
    if type(follow_x) is not bool or type(follow_y) is not bool:
        raise FidelityError("Mini-pet follow flags must be booleans")
    control = MiniHover.for_pet(character_name, is_subpet=True,
                                follows_main_y=follow_y, enabled=True)
    result["runtime"] = "SubPet"
    result["mini_follow"] = {
        "follow_main_x": follow_x, "follow_main_y": follow_y,
        "optional_hover_supported": control.enabled,
        "reason": ("Native X/Y follow has priority; extra hover disabled"
                   if follow_y else
                   "Optional hover applies to a floor-following Paimon mini-pet"
                   if control.enabled else
                   "No character-specific mini-hover configured"),
    }
    if control.enabled and result["frame_count_by_action"].get(
            conf.get("default", ""), 0) < 2:
        result["issues"].append(
            "Paimon mini-pet can move its window but still lacks a confirmed"
            " multi-frame floating idle animation")
    return result


def inspect_guga_role(role_dir: str | Path, voice_path=None) -> dict:
    """Backward-compatible Guga-specific entry for existing UI and tests."""
    return inspect_character_role(role_dir, "guga", voice_path)
