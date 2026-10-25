#!/usr/bin/env python3
"""Safely import *local, user-selected* standard Shimeji ZIP frame archives.

No downloaded ZIP, EXE, JAR or script is executed. The actual numbered PNG
frames are preserved byte-for-byte, with no painted, synthesized or repeated
filler frames. Not all unrelated Shimeji formats follow the 46-frame layout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
import zipfile

try:
    from .chibi_profiles import CHIBI_PROFILES, available_role_folder
    from .install_native_role import validate_native_role
    from .artist_visual_review import create_native_art_review
    from .install_nanopet_shimeji import GROUPS
except ImportError:
    from chibi_profiles import CHIBI_PROFILES, available_role_folder
    from install_native_role import validate_native_role
    from artist_visual_review import create_native_art_review
    from install_nanopet_shimeji import GROUPS

MAX_ENTRIES = 1200
MAX_UNCOMPRESSED = 64 * 1024 * 1024
MAX_SINGLE_PNG = 6 * 1024 * 1024
MAX_SIDE = 2048
PNG_SIG = b"\x89PNG\r\n\x1a\n"
FRAME_NAME = re.compile(r"(?:^|/)shime([1-9][0-9]?)_?\.png$", re.I)


def _png_size(raw):
    if len(raw) < 24 or not raw.startswith(PNG_SIG) or raw[12:16] != b"IHDR":
        raise ValueError("Invalid original Shimeji PNG image")
    width, height = struct.unpack(">II", raw[16:24])
    if not 1 <= width <= MAX_SIDE or not 1 <= height <= MAX_SIDE:
        raise ValueError("Unsafe Shimeji frame dimensions")
    return width, height


def inspect_shimeji_zip(source):
    """Return original image bytes only after ZIP and PNG safety checks."""
    source = Path(source).expanduser()
    if source.is_symlink() or not source.is_file():
        raise ValueError("Select a local regular Shimeji ZIP")
    images = {}
    with zipfile.ZipFile(source) as archive:
        members = archive.infolist()
        if len(members) > MAX_ENTRIES:
            raise ValueError("Archive contains too many members")
        total = sum(m.file_size for m in members)
        if total > MAX_UNCOMPRESSED:
            raise ValueError("Archive exceeds uncompressed size bound")
        for m in members:
            match = FRAME_NAME.search(m.filename.replace("\\", "/"))
            if not match:
                continue  # EXE/JAR/XML/scripts are never extracted or executed.
            index = int(match.group(1))
            if index > 46 or index in images:
                raise ValueError("Duplicate or out-of-range Shimeji frame index")
            if (m.file_size < 50 or m.file_size > MAX_SINGLE_PNG or
                    m.file_size / max(m.compress_size, 1) > 250):
                raise ValueError("Unsafe Shimeji PNG size/compression")
            raw = archive.read(m)
            if len(raw) != m.file_size:
                raise ValueError("ZIP PNG length mismatch")
            _png_size(raw)
            images[index] = raw
    if 1 not in images or sum(n in images for n in (2, 3)) < 2:
        raise ValueError("Not a compatible standard Shimeji archive (requires stand 1 and walk 2/3)")
    # A single sketch copied to multiple numbered files must not count as motion.
    if len({hashlib.sha256(images[n]).digest() for n in (1, 2, 3) if n in images}) < 2:
        raise ValueError("Walk frames are identical; no genuine motion to import")
    return images


def install_personal_shimeji_zip(source, output_root, *, profile, confirmed=False,
                                 verified_react_sha=None):
    if not confirmed:
        raise ValueError("Personal import requires explicit user confirmation")
    if profile not in CHIBI_PROFILES or not profile.startswith("genshin_"):
        raise ValueError("Select the exact Genshin identity; never infer from filename")
    if verified_react_sha is not None and (
            not isinstance(verified_react_sha, str) or
            re.fullmatch(r"[a-f0-9]{64}", verified_react_sha) is None):
        raise ValueError("Verified React-Shimeji module SHA-256 must be 64 lowercase hex characters")
    source = Path(source).expanduser()
    original = inspect_shimeji_zip(source)
    root = Path(output_root).expanduser()
    if root.is_symlink():
        raise ValueError("Refusing linked character root")
    root = root.resolve()
    destination_name = available_role_folder(
        root, "PersonalShimeji" + "".join(w.title() for w in profile[8:].split("_")))
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", destination_name):
        raise ValueError("Character folder name too long")
    destination = root / destination_name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Cannot replace a previously installed character")

    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix=".local-shimeji-") as temp:
        stage = Path(temp) / destination_name
        act_root = stage / "action"
        originals = stage / "source_frames"
        act_root.mkdir(parents=True)
        originals.mkdir()
        for num, raw in sorted(original.items()):
            (originals / f"shime{num}.png").write_bytes(raw)

        def action(images, direction=None):
            item = {"images": images, "act_num": 1, "frame_refresh": 0.17}
            if direction:
                item.update({"need_move": True, "direction": direction, "frame_move": 3.0})
            return item

        groups = {}
        for name, nums in GROUPS.items():
            found = [n for n in nums if n in original]
            if found:
                groups[name] = found
                for idx, n in enumerate(found):
                    (act_root / f"{name}_{idx}.png").write_bytes(original[n])
        act = {
            "default": action("stand"),
            "left_walk": action("walk", "left"),
            "right_walk": action("walk", "right"),
        }
        for key, group in (("drag", "drag"), ("fall", "fall"),
                           ("on_floor", "onfloor"), ("climb", "climb"),
                           ("rest", "sit"), ("crawl", "crawl"),
                           ("landing", "landing")):
            if group in groups:
                act[key] = action(group)

        width, height = _png_size(original[1])
        pet = {
            "width": width, "height": height, "scale": 1.0, "refresh": 5,
            "interact_speed": 0.02, "default": "default", "up": "default",
            "down": "default", "left": "left_walk", "right": "right_walk",
            "drag": "drag" if "drag" in act else "default",
            "fall": "fall" if "fall" in act else "default",
            "on_floor": "on_floor" if "on_floor" in act else "default",
            "patpat": "default",  # standard Shimeji does not define a real pat gesture
            "random_act": [
                {"name": "待机", "act_list": ["default"],
                 "act_prob": 1.0, "act_type": [2, 0]},
                {"name": "行走", "act_list": ["left_walk", "right_walk"],
                 "act_prob": 0.15, "act_type": [3, 1]},
            ],
        }
        for filename, obj in (("act_conf.json", act), ("pet_conf.json", pet)):
            (stage / filename).write_text(
                json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        validation = validate_native_role(stage)
        receipt = {
            "mode": "personal_local_only",
            "source_kind": "user_selected_shimeji_zip",
            "selected_profile": profile,
            "source_archive_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "all_original_frames_preserved": len(original),
            "mapped_original_frame_groups": sorted(groups),
            "source_upstream_identity_verified": False,
            "source_rights_verified": False,
            "likeness_manually_reviewed": False,
            "real_windows_qa_verified": False,
            "redistribution_allowed_by_tool": False,
            "validation": validation,
        }
        if verified_react_sha is not None:
            receipt.update({
                "source_kind": "pinned_react_shimeji_lfs_local_only",
                "source_module_sha256": verified_react_sha,
                "upstream_lfs_revision_verified": True,
                "original_png_atlas_frame_pixels_preserved": True,
                "source_author_likeness_qa_passed": False,
                "real_desktop_playback_qa_passed": False,
                "redistribution_allowed_by_tool": False,
            })
        # Attestation is committed with the role atomically: a failed write
        # must never leave a playable role with an incomplete source receipt.
        (stage / "PERSONAL_IMPORT.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        create_native_art_review(stage)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Concurrent character install; refusing overwrite")
        stage.rename(destination)
    return destination


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--profile", choices=sorted(k for k in CHIBI_PROFILES if k.startswith("genshin_")), required=True)
    p.add_argument("--role-root", type=Path, default=Path(__file__).resolve().parents[1]/"res"/"role")
    p.add_argument("--personal-use", action="store_true")
    args = p.parse_args(argv)
    print(install_personal_shimeji_zip(
        args.archive, args.role_root, profile=args.profile,
        confirmed=args.personal_use))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
