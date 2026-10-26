#!/usr/bin/env python3
"""Read-only frame-by-frame QA ledger for an installed creator-art DyberPet role.

A complete file and distinct frame can still depict the WRONG character.
This ledger deliberately never approves likeness, rights, voice, or motion
semantics; it only measures structural evidence and exposes review blockers.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError

MAX_CONF_BYTES = 256 * 1024
MAX_FRAME_BYTES = 8 * 1024 * 1024
MAX_ACTIONS = 128
MAX_FRAMES_PER_ACTION = 200
MAX_TOTAL_FRAMES = 1800
MAX_SIDE = 4096
MAX_PIXELS = 4_000_000

MOVEMENT_NAMES = frozenset((
    "left_walk", "right_walk", "walk", "run", "jump", "climb",
    "crawl", "drag", "fall", "landing", "bounce",
))


def _read_config(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_CONF_BYTES:
        raise ValueError("Missing or unsafe role action configuration")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Role config must be a JSON object")
    return value


def _frames_for_action(role, prefix):
    if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", prefix):
        raise ValueError("Unsupported or unsafe action frame prefix")
    folder = role / "action"
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Missing or linked animation directory")
    matched = []
    for path in folder.glob(prefix + "_*.png"):
        match = re.fullmatch(re.escape(prefix) + r"_(\d+)\.png", path.name)
        if match:
            if (path.is_symlink() or not path.is_file() or
                    not 32 <= path.stat().st_size <= MAX_FRAME_BYTES):
                raise ValueError("Unsafe or oversized installed sprite")
            matched.append((int(match.group(1)), path))
    matched.sort(key=lambda pair: pair[0])
    if len(matched) > MAX_FRAMES_PER_ACTION:
        raise ValueError("Too many frames in one action")
    if [idx for idx, _ in matched] != list(range(len(matched))):
        raise ValueError("Frames missing or non-zero-indexed in " + prefix)
    return [path for _num, path in matched]


def audit_native_character(role_folder):
    """Inspect installed source sprites exactly, without modifying role files."""
    role = Path(role_folder).expanduser()
    if role.is_symlink() or not role.is_dir():
        raise ValueError("Role folder is missing or linked")
    pet = _read_config(role / "pet_conf.json")
    actions = _read_config(role / "act_conf.json")
    if not actions or len(actions) > MAX_ACTIONS:
        raise ValueError("Unsupported number of original actions")
    seen = {}
    records = []
    total = 0
    for action_name, config in sorted(actions.items()):
        if not isinstance(action_name, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", action_name):
            raise ValueError("Unsafe action identifier")
        if not isinstance(config, dict):
            raise ValueError("Action definition is not an object")
        prefix = config.get("images")
        if prefix not in seen:
            seen[prefix] = _frames_for_action(role, prefix)
        files = seen[prefix]
        if not files:
            raise ValueError("Action has no source frames: " + action_name)
        total += len(files)
        if total > MAX_TOTAL_FRAMES:
            raise ValueError("Too many installed source frames")
        pixel_hashes = []
        dimensions = set()
        invisible_count = 0
        for frame_file in files:
            try:
                with Image.open(frame_file) as image:
                    if (image.width <= 0 or image.height <= 0 or
                            image.width > MAX_SIDE or image.height > MAX_SIDE or
                            image.width * image.height > MAX_PIXELS):
                        raise ValueError("Excessive original frame dimensions")
                    image.load()
                    if image.format != "PNG":
                        raise ValueError("Animation must contain actual PNG images")
                    pixels = image.convert("RGBA")
                    dimensions.add(pixels.size)
                    if pixels.getchannel("A").getbbox() is None:
                        invisible_count += 1
                    pixel_hashes.append(hashlib.sha256(pixels.tobytes()).hexdigest())
            except (OSError, UnidentifiedImageError) as exc:
                raise ValueError("Unreadable original frame: " + frame_file.name) from exc
        unique_frames = len(set(pixel_hashes))
        movement = (bool(config.get("need_move")) or
                    action_name.casefold() in MOVEMENT_NAMES)
        issues = []
        if invisible_count:
            issues.append("fully_transparent_frames")
        if len(dimensions) != 1:
            issues.append("inconsistent_frame_dimensions")
        if movement and unique_frames < 2:
            issues.append("movement_has_no_distinct_frames")
        if len(files) > 1 and unique_frames == 1:
            issues.append("all_frames_visually_identical")
        records.append({
            "action": action_name, "frame_prefix": prefix,
            "original_file_count": len(files),
            "pixel_unique_frame_count": unique_frames,
            "same_pixel_duplicate_count": len(files) - unique_frames,
            "transparent_frames": invisible_count,
            "sizes": [list(x) for x in sorted(dimensions)],
            "movement_action": movement,
            "issues": issues,
        })
    if pet.get("default") not in actions:
        raise ValueError("Missing usable default action")
    all_issues = sorted(set(issue for row in records for issue in row["issues"]))
    is_demo = ((role / "BUILTIN_CHIBI_DEMO.json").exists() or
               (role / "BUILTIN_MASCOT_DEMO.json").exists())
    imported = ((role / "PERSONAL_IMPORT.json").exists() or
                (role / "IMPORT_REPORT.json").exists())
    return {
        "scope": "installed_source_pixel_structure_only",
        "folder": role.name,
        "source_status": ("builtin_demo_not_original_art" if is_demo else
                          "import_receipt_present_not_likeness_proof" if imported else
                          "unverified_local_role"),
        "summary": {
            "native_actions": len(records),
            "original_frames_inspected": total,
            "actions_with_pixel_issues": sum(bool(x["issues"]) for x in records),
            "issue_categories": all_issues,
            "animation_structure_passed": not bool(all_issues),
            "character_visual_likeness_verified": False,
            "action_semantics_manually_verified": False,
            "voice_fidelity_verified": False,
            "rights_verified": False,
        },
        "actions": records,
        "note": ("Distinct sprite pixels and complete frame indices cannot establish "
                 "character identity, visual fidelity, natural motion or rights. "
                 "A human must review all original frames at actual screen size."),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role_folder", type=Path)
    parser.add_argument("--output", type=Path,
                        help="Optional JSON output; by default prints a read-only report")
    args = parser.parse_args(argv)
    result = json.dumps(audit_native_character(args.role_folder),
                        ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
