#!/usr/bin/env python3
"""Install opt-in, immutable public creator Shimeji frames as native DyberPet roles.

Original transparent PNG bytes are preserved. No line-art replacement, synthetic
pose generation, upscaling or source-asset redistribution. Source presence does
not constitute a likeness judgment or a redistribution license.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import tempfile
from urllib.request import Request, urlopen

try:
    from .install_native_role import validate_native_role
    from .chibi_profiles import CHIBI_PROFILES
except ImportError:
    from install_native_role import validate_native_role
    from chibi_profiles import CHIBI_PROFILES

MANIFEST = Path(__file__).with_name("artist_shimeji_sources.json")
MAX_PNG_BYTES = 1024 * 1024
MAX_ROLE_BYTES = 16 * 1024 * 1024
PNG_HEADER = bytes.fromhex("89504e470d0a1a0a")
_FILE = re.compile(r"(?:climb|drag|fall|walk)[1-9][0-9]*\.png|id[12]_1\.png|sp[1-9][0-9]*_[1-9][0-9]*\.png")


def source_manifest(path=MANIFEST):
    record = json.loads(Path(path).read_text(encoding="utf-8"))
    if record.get("schema") != 1 or record.get("repository") != "AkshitIreddy/AI-Desktop-Pet":
        raise ValueError("Unrecognized source registry")
    if not re.fullmatch(r"[a-f0-9]{40}", str(record.get("revision", ""))):
        raise ValueError("Source revision must be pinned")
    if len(record.get("roles", {})) != 8:
        raise ValueError("Expected 8 independently identifiable creator sprite sets")
    for key, item in record["roles"].items():
        if not re.fullmatch(r"[a-z]+", key) or item["profile"] not in CHIBI_PROFILES:
            raise ValueError("Invalid creator role identity")
        files = item.get("files", {})
        if not files or len(files) > 48:
            raise ValueError("Invalid pinned sprite count")
        for filename, spec in files.items():
            if not _FILE.fullmatch(filename):
                raise ValueError("Invalid sprite filename")
            if not isinstance(spec.get("size"), int) or not 20 <= spec["size"] <= MAX_PNG_BYTES:
                raise ValueError("Invalid sprite size")
            if not re.fullmatch(r"[a-f0-9]{40}", str(spec.get("sha", ""))):
                raise ValueError("Invalid Git blob anchor")
        if not {"id1_1.png", "walk1.png", "drag1.png", "fall1.png"} <= files.keys():
            raise ValueError("Artist animation is missing a required original pose")
    return record


def _download_png(url, spec, opener=urlopen):
    req = Request(url, headers={"User-Agent": "DyberPet-personal-shimeji/1"})
    with opener(req, timeout=30) as stream:
        raw = stream.read(MAX_PNG_BYTES + 1)
    if len(raw) != spec["size"]:
        raise ValueError("Creator artwork size differs from pinned file")
    anchor = hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()
    if anchor != spec["sha"]:
        raise ValueError("Creator artwork Git-blob digest mismatch")
    if not raw.startswith(PNG_HEADER) or raw[12:16] != b"IHDR":
        raise ValueError("Source sprite is not a PNG")
    width, height = struct.unpack(">II", raw[16:24])
    if not (8 <= width <= 2048 and 8 <= height <= 2048 and width * height <= 1024 * 1024):
        raise ValueError("Unsafe source PNG dimensions")
    return raw


def _source_actions(files):
    def natural(prefix):
        return sorted((name for name in files if re.fullmatch(prefix, name)),
                      key=lambda name: [int(n) for n in re.findall(r"[0-9]+", name)])
    return {
        "stand": natural(r"id[12]_1\.png"),
        "walk": natural(r"walk[1-9][0-9]*\.png"),
        "drag": natural(r"drag[1-9][0-9]*\.png"),
        "fall": natural(r"fall[1-9][0-9]*\.png"),
        "special": natural(r"sp1_[1-9][0-9]*\.png"),
        "climb": natural(r"climb[1-9][0-9]*\.png"),
    }


def install_artist_shimeji(kind, output_root, *, confirmed=False,
                           downloader=_download_png, manifest=None):
    if not confirmed:
        raise ValueError("Choose and consent to personal local artist-source download")
    manifest = source_manifest() if manifest is None else manifest
    if kind not in manifest["roles"]:
        raise ValueError("Unknown creator sprite character")
    root = Path(output_root).expanduser()
    if root.is_symlink():
        raise ValueError("Symbolic-link role root is not supported")
    root = root.resolve()
    item = manifest["roles"][kind]
    folder = "SourceShimeji" + kind.title()
    target = root / folder
    if target.exists() or target.is_symlink():
        raise FileExistsError("Creator art already installed; never overwrite user data")
    root.mkdir(parents=True, exist_ok=True)
    groups = _source_actions(item["files"])
    if not all(groups[x] for x in ("stand", "walk", "drag", "fall")):
        raise ValueError("Missing required creator animation group")
    if sum(v["size"] for v in item["files"].values()) > MAX_ROLE_BYTES:
        raise ValueError("Artist sprite bundle exceeds 16 MiB")
    source_root = ("https://raw.githubusercontent.com/"
                   + manifest["repository"] + "/" + manifest["revision"]
                   + "/public/assets/" + kind + "/")
    with tempfile.TemporaryDirectory(prefix=".creator-shimeji-", dir=root) as tmp:
        stage = Path(tmp) / folder
        action = stage / "action"
        action.mkdir(parents=True)
        shape = None
        for group, source_names in groups.items():
            for index, filename in enumerate(source_names):
                spec = item["files"][filename]
                raw = downloader(source_root + filename, spec)
                if group == "stand" and index == 0:
                    shape = struct.unpack(">II", raw[16:24])
                (action / f"{group}_{index}.png").write_bytes(raw)
        acts = {}
        for key, prefix in (("default", "stand"), ("left_walk", "walk"),
                            ("right_walk", "walk"), ("drag", "drag"),
                            ("fall", "fall"), ("on_floor", "stand"),
                            ("patpat", "special"), ("climb", "climb")):
            if not groups[prefix]:
                continue
            config = {"images": prefix, "act_num": 1, "frame_refresh": 0.16}
            if key in ("left_walk", "right_walk"):
                config.update({"need_move": True,
                               "direction": "left" if key == "left_walk" else "right"})
            acts[key] = config
        if shape is None:
            raise ValueError("The author did not supply an idle image")
        pet = {
            "width": shape[0], "height": shape[1], "scale": 1.0,
            "refresh": 5, "interact_speed": 0.02,
            "default": "default", "drag": "drag", "fall": "fall",
            "up": "default", "down": "default",
            "left": "left_walk", "right": "right_walk",
            "on_floor": "on_floor",
            "random_act": [
                {"name": "待机", "act_list": ["default"], "act_prob": 1,
                 "act_type": [2, 0]},
                {"name": "行走", "act_list": ["left_walk", "right_walk", "default"],
                 "act_prob": 0.2, "act_type": [3, 1]}
            ],
        }
        if "patpat" in acts:
            pet["patpat"] = "patpat"
        (stage / "pet_conf.json").write_text(
            json.dumps(pet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (stage / "act_conf.json").write_text(
            json.dumps(acts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        checked = validate_native_role(stage)
        (stage / "PERSONAL_IMPORT.json").write_text(json.dumps({
            "display_name": item["name"], "selected_profile": item["profile"],
            "source_repository": manifest["repository"],
            "source_commit": manifest["revision"],
            "source_asset_path": "public/assets/" + kind,
            "source_kind": "creator_shimeji_frames",
            "source_author_credit": "@uuteki (as credited by upstream repository)",
            "verified_exact_source_frame_bytes": True,
            "source_rights_verified": False,
            "likeness_manually_reviewed": False,
            "real_windows_qa_verified": False,
            "redistribution_allowed_by_tool": False,
            "original_pixel_frames": sum(map(len, groups.values())),
            "validation": checked,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if target.exists() or target.is_symlink():
            raise FileExistsError("Target installed concurrently; no overwrite")
        stage.rename(target)
    return {"folder": folder, "profile": item["profile"],
            "actions": checked["actions"], "frames": checked["images"],
            "original_artist_pixels_preserved": True,
            "likeness_manually_reviewed": False, "rights_verified": False}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("role", choices=tuple(source_manifest()["roles"]))
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1] / "res" / "role")
    ap.add_argument("--accept-personal-use", action="store_true")
    args = ap.parse_args(argv)
    try:
        value = install_artist_shimeji(args.role, args.role_root,
                                      confirmed=args.accept_personal_use)
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        ap.exit(1, "Shimeji artist install blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
