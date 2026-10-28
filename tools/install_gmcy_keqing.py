#!/usr/bin/env python3
"""Opt-in native DyberPet import of ORIGINAL Keqing creator's 92 PNG frames.

The upstream author identifies resources/pet_1 as 原神 刻晴 in README and
cfg_diaona.py. We pin the upstream commit AND every Git blob SHA/size. Neither
the author's arbitrary Python code nor any executable in the ZIP is run.
Original 6 action groups are preserved without inventing walk, fall or pat art.
Art is downloaded to a private machine only after explicit confirmation.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import stat
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
import zipfile

from PIL import Image

try:
    from .chibi_profiles import CHIBI_PROFILES, available_role_folder
    from .install_native_role import validate_native_role
    from .artist_visual_review import create_native_art_review
    from .artist_animation_audit import audit_native_character
except ImportError:
    from tools.chibi_profiles import CHIBI_PROFILES, available_role_folder
    from tools.install_native_role import validate_native_role
    from tools.artist_visual_review import create_native_art_review
    from tools.artist_animation_audit import audit_native_character

SOURCE_KEY = "keqing_92"
MANIFEST = Path(__file__).with_name("gmcy_keqing_92_source.json")
MAX_DOWNLOAD_BYTES = 105 * 1024 * 1024
MAX_UNCOMPRESSED = 90 * 1024 * 1024
MAX_ENTRIES = 400
MAX_FRAME_PIXELS = 4_000_000
MAX_FRAME_SIDE = 4096
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def source_manifest():
    obj = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (obj.get("schema") != 1 or
            obj.get("repository") != "GMCY2020/DesktopPet-Simple" or
            obj.get("commit") != "1b7d73a940ae4df84a283399f25a80fe2c571595" or
            obj.get("source_profile") != "genshin_keqing" or
            obj.get("source_directory") != "resources/pet_1" or
            obj.get("original_frame_count") != 92 or
            len(obj.get("files", [])) != 92 or
            len(obj.get("original_action_groups", [])) != 6):
        raise ValueError("Unrecognized pinned Keqing creator source")
    if "genshin_keqing" not in CHIBI_PROFILES:
        raise ValueError("Keqing missing from exact 123-roster")
    found = {}
    for item in obj["files"]:
        n, size, sha = item.get("num"), item.get("bytes"), item.get("git_blob_sha1")
        if (type(n) is not int or type(size) is not int or
                not 1 <= n <= 92 or not 50 <= size <= 8*1024*1024 or
                not isinstance(sha, str) or
                not re.fullmatch("[0-9a-f]{40}", sha) or n in found):
            raise ValueError("Invalid Keqing original PNG identity or duplicate")
        found[n] = item
    if set(found) != set(range(1,93)) or sum(x["bytes"] for x in found.values()) != obj["original_image_bytes"]:
        raise ValueError("Incomplete pinned Keqing frame inventory")
    flattened = []
    for i, group in enumerate(obj["original_action_groups"], 1):
        if group.get("name") != f"author_motion_{i:02d}" or not isinstance(group.get("frames"), list):
            raise ValueError("Unrecognized Keqing authored action group")
        flattened.extend(group["frames"])
    if sorted(flattened) != list(range(1, 93)):
        raise ValueError("Author action groups do not partition exact original frames")
    return obj


def _git_blob_sha(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def source_zip_url(manifest=None):
    obj = source_manifest() if manifest is None else manifest
    return ("https://codeload.github.com/" + obj["repository"] +
            "/zip/" + obj["commit"])


def download_original_archive(*, opener=urlopen):
    """Fetch ZIP from one immutable GitHub commit, respecting size & redirects."""
    url = source_zip_url()
    req = Request(url, headers={"User-Agent": "DyberPet-original-Keqing92-import/1"})
    with opener(req, timeout=55) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname != "codeload.github.com":
            raise ValueError("Unexpected original-source ZIP redirect")
        raw = response.read(MAX_DOWNLOAD_BYTES + 1)
    if len(raw) > MAX_DOWNLOAD_BYTES or not raw.startswith(b"PK\x03\x04"):
        raise ValueError("Keqing source archive exceeds safe size or is not ZIP")
    return raw


def verify_original_frames(archive_bytes, *, manifest=None):
    """Pin all 92 PNG Git blobs, ignoring (never executing) all other files."""
    src = source_manifest() if manifest is None else manifest
    if (not isinstance(archive_bytes, bytes) or
            len(archive_bytes) > MAX_DOWNLOAD_BYTES):
        raise ValueError("Unexpected original source archive data")
    prefix = "DesktopPet-Simple-" + src["commit"] + "/" + src["source_directory"] + "/"
    entries = {}
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as z:
        members = z.infolist()
        if len(members) > MAX_ENTRIES or sum(x.file_size for x in members) > MAX_UNCOMPRESSED:
            raise ValueError("Unexpected or expanded creator archive")
        for member in members:
            path = member.filename
            match = re.fullmatch(re.escape(prefix) + r"shime([1-9]\d{0,2})\.png", path)
            if not match:
                continue
            number = int(match.group(1))
            if number in entries or not 1 <= number <= 92:
                raise ValueError("Ambiguous numbered Keqing sprite")
            if (member.is_dir() or stat.S_IFMT(member.external_attr >> 16)
                    not in (0, stat.S_IFREG) or
                    member.file_size > 8*1024*1024 or
                    member.file_size / max(member.compress_size,1) > 400):
                raise ValueError("Unsafe Keqing ZIP frame")
            entries[number] = member
        if set(entries) != set(range(1, 93)):
            raise ValueError("Keqing author archive lacks 92 original frames")
        pinned = {f["num"]:f for f in src["files"]}
        verified = {}
        for n in sorted(entries):
            item = entries[n]
            if item.file_size != pinned[n]["bytes"]:
                raise ValueError("Keqing frame byte-count mismatch: " + str(n))
            raw = z.read(item)
            if _git_blob_sha(raw) != pinned[n]["git_blob_sha1"]:
                raise ValueError("Keqing original Git blob identity mismatch: " + str(n))
            if not raw.startswith(PNG_MAGIC):
                raise ValueError("Keqing frame is not original PNG: " + str(n))
            with Image.open(io.BytesIO(raw)) as img:
                if (img.format != "PNG" or not 1 <= img.width <= MAX_FRAME_SIDE or
                        not 1 <= img.height <= MAX_FRAME_SIDE or
                        img.width * img.height > MAX_FRAME_PIXELS):
                    raise ValueError("Unsafe original PNG dimensions")
                img.verify()
            verified[n] = raw
    return verified


def install_gmcy_keqing(key, output_root, *, confirmed=False,
                       archive_bytes=None, downloader=download_original_archive):
    """Atomic new-role-only install; never overwrite a creator or user's art."""
    if key != SOURCE_KEY:
        raise ValueError("Wrong original Genshin character source")
    if not confirmed:
        raise ValueError("Explicit personal-use consent required")
    src = source_manifest()
    raw = downloader() if archive_bytes is None else archive_bytes
    frames = verify_original_frames(raw, manifest=src)
    output_root = Path(output_root).expanduser()
    if output_root.is_symlink() or (output_root.exists() and not output_root.is_dir()):
        raise ValueError("Unsafe role destination")
    root = output_root.resolve()
    folder = available_role_folder(root, "SourceGmcyKeqing")
    target = root / folder
    if target.exists() or target.is_symlink():
        raise FileExistsError("Author original role cannot overwrite an existing character")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root, prefix=".author-keqing92-") as tmp:
        stage = Path(tmp) / folder
        action_path = stage / "action"
        action_path.mkdir(parents=True)
        acts = {}
        for i, group in enumerate(src["original_action_groups"]):
            action_name = "default" if i == 0 else group["name"]
            prefix = group["name"]
            # Original frames are written byte-for-byte, exactly once each.
            for index, n in enumerate(group["frames"]):
                (action_path / f"{prefix}_{index}.png").write_bytes(frames[n])
            acts[action_name] = {"images": prefix, "act_num": 1, "frame_refresh": 0.27}
        # Original upstream lists 9 independent groups but does not label
        # them fall/walk/pat; do not invent character-specific gestures.
        pet = {
            "width": 800, "height": 820, "scale": 0.65,
            "refresh": 5, "interact_speed": 0.02,
            "default": "default", "up": "default", "down": "default",
            "left": "default", "right": "default", "drag": "default",
            "fall": "default", "on_floor": "default", "patpat": "default",
            "random_act": [
                {"name": "原作者动作 " + str(i+1),
                 "act_list": ["default" if i == 0 else group["name"]],
                 "act_prob": 0.1, "act_type": [2,0]}
                for i,group in enumerate(src["original_action_groups"])
            ]
        }
        for name, obj in (("pet_conf.json", pet), ("act_conf.json", acts)):
            (stage / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+"\n",
                                      encoding="utf-8")
        info = stage / "info"
        info.mkdir()
        (info / "info.json").write_text(json.dumps({
            "petName": "刻晴", "display_name_zh": "刻晴",
            "notes": "GMCY 原作者 92 帧；动作语义和原设视觉待人工验收"
        }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        validation = validate_native_role(stage)
        receipt = {
            "mode": "personal_local_only",
            "source_kind": "sha1_git_blob_pinned_gmcy_keqing92",
            "selected_profile": "genshin_keqing",
            "display_name_zh": "刻晴",
            "upstream_repo": src["repository"],
            "upstream_commit": src["commit"],
            "original_author": src["source_author"],
            "all_original_frames_preserved": 92,
            "original_action_groups_preserved": 6,
            "sha1_blob_sha_verified_for_every_frame": True,
            "original_png_frame_bytes_preserved": True,
            "motion_semantics_manually_reviewed": False,
            "likeness_manually_reviewed": False,
            "source_rights_verified": False,
            "redistribution_allowed_by_tool": False,
            "real_windows_qa_verified": False,
            "validation": validation,
        }
        (stage / "PERSONAL_IMPORT.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2)+"\n",
            encoding="utf-8")
        create_native_art_review(stage)
        audit = audit_native_character(stage)
        (stage / "ACTION_PIXEL_AUDIT.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2)+"\n",
            encoding="utf-8")
        if target.exists() or target.is_symlink():
            raise FileExistsError("Concurrent original-art install collision")
        stage.rename(target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-root", type=Path, default=Path(__file__).resolve().parents[1] / "res/role")
    parser.add_argument("--archive", type=Path,
                        help="Optional offline ZIP downloaded from immutable upstream commit")
    parser.add_argument("--personal-use", action="store_true")
    args = parser.parse_args(argv)
    raw = args.archive.read_bytes() if args.archive else None
    print(install_gmcy_keqing(SOURCE_KEY, args.role_root,
                             confirmed=args.personal_use, archive_bytes=raw))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
