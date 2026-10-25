#!/usr/bin/env python3
"""Verify and import a personally downloaded, pinned React-Shimeji LFS module.

This tool parses literal JSON values from the upstream generated TS module; it
NEVER imports, evaluates, transpiles, or executes TypeScript / JavaScript.
Original PNG sprite pixels are cropped into numbered Shimeji frames before
the existing personal-only, never-overwrite native DyberPet installer runs.
"""
from __future__ import annotations

import argparse
import base64
import binascii
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re
import tempfile
import zipfile

from PIL import Image

try:
    from .react_shimeji_source_leads import CANDIDATES
    from .install_personal_shimeji_zip import install_personal_shimeji_zip
except ImportError:
    from react_shimeji_source_leads import CANDIDATES
    from install_personal_shimeji_zip import install_personal_shimeji_zip

MAX_TS_BYTES = 6 * 1024 * 1024
MAX_PNG_BYTES = 15 * 1024 * 1024
MAX_ATLAS_PIXELS = 8_000_000
MAX_CROPS = 200
FRAME = re.compile(r"(?:^|/)shime([1-9][0-9]?)\.png$", re.I)
FIELD = re.compile(r"^\s*(id|spritesheet|sprites|actions|behaviors):\s*", re.M)


def _parse_only_literal_source(raw, *, expected_id):
    if len(raw) > MAX_TS_BYTES:
        raise ValueError("React-Shimeji TypeScript exceeds safe input bound")
    try:
        source = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("Expected UTF-8 source module") from exc
    if source.startswith("version https://git-lfs.github.com/spec/v1"):
        raise ValueError("This is only a Git LFS pointer; download the real source file")
    if "export const character = {" not in source:
        raise ValueError("Not a generated React-Shimeji character module")
    decoder = json.JSONDecoder()
    values = {}
    for match in FIELD.finditer(source):
        key = match.group(1)
        if key in values:
            raise ValueError("Duplicate character module field: " + key)
        try:
            value, _ = decoder.raw_decode(source[match.end():])
        except json.JSONDecodeError as exc:
            raise ValueError("Malformed literal React-Shimeji data field") from exc
        values[key] = value
    if set(("id", "spritesheet", "sprites", "actions", "behaviors")) - values.keys():
        raise ValueError("Incomplete generated React-Shimeji sprite module")
    if values["id"] != expected_id:
        raise ValueError("Downloaded character ID does not match chosen Genshin profile")
    if not isinstance(values["actions"], str) or not isinstance(values["behaviors"], str):
        raise ValueError("Expected character action strings, not executable code")
    if not isinstance(values["sprites"], dict) or len(values["sprites"]) > MAX_CROPS:
        raise ValueError("Unsafe or missing sprite atlas index")
    return values


def decode_pinned_frames(ts_path, *, profile):
    if profile not in CANDIDATES:
        raise ValueError("Only explicitly pinned profile IDs are supported")
    slug, expected_sha, expected_bytes, *_ = CANDIDATES[profile]
    source = Path(ts_path).expanduser()
    if source.is_symlink() or not source.is_file() or source.stat().st_size > MAX_TS_BYTES:
        raise ValueError("Choose a regular bounded downloaded .ts module")
    raw = source.read_bytes()
    if len(raw) != expected_bytes:
        raise ValueError("Pinned React-Shimeji LFS byte count mismatch")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha:
        raise ValueError("Pinned React-Shimeji LFS SHA-256 mismatch")
    data = _parse_only_literal_source(raw, expected_id=slug)
    image_uri = data["spritesheet"]
    prefix = "data:image/png;base64,"
    if not isinstance(image_uri, str) or not image_uri.startswith(prefix):
        raise ValueError("Only original embedded PNG atlas data URIs are accepted")
    try:
        original_png = base64.b64decode(image_uri[len(prefix):], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("Bad PNG base64 data") from exc
    if len(original_png) > MAX_PNG_BYTES or not original_png.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("Atlas is not a bounded PNG")
    with Image.open(BytesIO(original_png)) as atlas:
        atlas.load()
        if atlas.format != "PNG" or atlas.width * atlas.height > MAX_ATLAS_PIXELS:
            raise ValueError("Unacceptable original PNG atlas size")
        frames = {}
        for key, rect in data["sprites"].items():
            if not isinstance(key, str):
                continue
            found = FRAME.search(key.replace("\\", "/"))
            if not found:
                continue
            n = int(found.group(1))
            if n > 46 or n in frames:
                raise ValueError("Duplicate or out-of-range numbered Shimeji frame")
            if not isinstance(rect, dict):
                raise ValueError("Invalid sprite frame coordinates")
            values = [rect.get(t) for t in ("x", "y", "width", "height")]
            if any(type(v) is not int for v in values):
                raise ValueError("Non-integer atlas rectangle")
            x, y, w, h = values
            if not (0 <= x and 0 <= y and 0 < w <= 2048 and 0 < h <= 2048
                    and x + w <= atlas.width and y + h <= atlas.height):
                raise ValueError("Frame rectangle outside of original art atlas")
            out = BytesIO()
            atlas.crop((x, y, x + w, y + h)).save(out, format="PNG")
            frames[n] = out.getvalue()
    if 38 not in frames or len(set(hashlib.sha256(frames[n]).digest()
                                    for n in (1, 2, 3) if n in frames)) < 2:
        raise ValueError("Source lacks distinct Shimeji walk frames and standard idle 38")
    return frames, digest


def install_pinned_react_shimeji(ts_path, role_root, *, profile, confirmed=False):
    if not confirmed:
        raise ValueError("Explicit private local user confirmation required")
    frames, digest = decode_pinned_frames(ts_path, profile=profile)
    with tempfile.TemporaryDirectory(prefix="react-shimeji-frames-") as temp:
        archive = Path(temp) / "numbered-original-sprites.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as writer:
            for num, png in sorted(frames.items()):
                writer.writestr("Shimeji/img/shime%d.png" % num, png)
        installed = install_personal_shimeji_zip(
            archive, role_root, profile=profile, confirmed=True)
    # Provenance is the complete TS module (LFS OID), not the temporary ZIP.
    receipt_path = installed / "PERSONAL_IMPORT.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt.update({
        "source_kind": "pinned_react_shimeji_lfs_local_only",
        "source_module_sha256": digest,
        "upstream_lfs_revision_verified": True,
        "original_png_atlas_frame_pixels_preserved": True,
        "source_author_likeness_qa_passed": False,
        "real_desktop_playback_qa_passed": False,
        "redistribution_allowed_by_tool": False,
    })
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return installed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--module", type=Path, required=True,
                        help="Locally downloaded actual LFS TypeScript module (not pointer)")
    parser.add_argument("--profile", choices=sorted(CANDIDATES), required=True)
    parser.add_argument("--role-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "res" / "role")
    parser.add_argument("--personal-use", action="store_true")
    args = parser.parse_args(argv)
    print(install_pinned_react_shimeji(
        args.module, args.role_root, profile=args.profile, confirmed=args.personal_use))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
