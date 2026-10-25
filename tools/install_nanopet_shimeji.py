#!/usr/bin/env python3
"""Opt-in local installation of original artist-made Genshin Shimeji frames.

The pinned upstream is a community archive. All 45/46 original PNG bytes
survive unaltered; only a subset of poses are assigned to DyberPet actions.
Never infer artist publication rights or high-fidelity visual QA from checksum.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import struct
import tempfile

try:
    from .chibi_profiles import CHIBI_PROFILES
    from .install_artist_shimeji import _download_png, MAX_PNG_BYTES
    from .install_native_role import validate_native_role
    from .artist_visual_review import create_native_art_review
except ImportError:
    from chibi_profiles import CHIBI_PROFILES
    from install_artist_shimeji import _download_png, MAX_PNG_BYTES
    from install_native_role import validate_native_role
    from artist_visual_review import create_native_art_review

REGISTRY = Path(__file__).with_name("nanopet_shimeji_sources.json")
GROUPS = {
    "stand": (38,),
    "stand_alt": (11,),
    "walk": (1, 2, 3),
    "drag": (5, 6, 7, 8, 9, 10),
    "fall": (4,),
    "onfloor": (18, 19, 20, 21),
    "climb": (12, 13, 14),
    "pat": (31, 32, 33),
}
MAX_ROLE_BYTES = 14 * 1024 * 1024


def source_manifest(path=REGISTRY):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != 1 or data.get("repository") != "Poseima/nano-pet":
        raise ValueError("Invalid Genshin Shimeji archive source")
    if not re.fullmatch(r"[a-f0-9]{40}", str(data.get("revision", ""))):
        raise ValueError("Source is not an immutable Git commit")
    if data.get("asset_root") != "NanoPetAssets/genshin-impact":
        raise ValueError("Unrecognized Genshin source directory")
    if len(data.get("roles", {})) != 17:
        raise ValueError("Expected 17 named artist sprite source entries")
    if "genshin-impact-xiao-catboy-by-uuteki" not in data.get("excluded", []):
        raise ValueError("Noncanon alternate must remain excluded")
    for kind, row in data["roles"].items():
        if not re.fullmatch(r"[a-z]+(?:-[a-z]+)*(?:-by-[a-z0-9-]+)", kind):
            raise ValueError("Invalid Genshin artist-source key: " + kind)
        if row.get("profile") not in CHIBI_PROFILES:
            raise ValueError("Shimeji character is not in Genshin roster")
        if row.get("upstream_dir") != "genshin-impact-" + kind:
            raise ValueError("Shimeji source directory differs from pinned identity")
        if row.get("artist") != kind.split("-by-")[-1]:
            raise ValueError("Shimeji artist metadata does not match its directory")
        frames = row.get("files")
        if not isinstance(frames, dict) or len(frames) not in (45, 46):
            raise ValueError("Incomplete upstream artist Shimeji frames")
        ids = set()
        for filename, spec in frames.items():
            match = re.fullmatch(r"shime([1-9][0-9]*)_?\.png", filename)
            if match is None:
                raise ValueError("Invalid upstream PNG file")
            index = int(match.group(1))
            if index < 1 or index > 46 or index in ids:
                raise ValueError("Out-of-range or ambiguous Shimeji frame")
            ids.add(index)
            if (type(spec.get("size")) is not int
                    or not 50 < spec["size"] <= MAX_PNG_BYTES
                    or not re.fullmatch(r"[a-f0-9]{40}", str(spec.get("sha", "")))):
                raise ValueError("Invalid pinned art size or blob digest")
        required = {n for indices in GROUPS.values() for n in indices}
        if not required.issubset(ids):
            raise ValueError("Creator source missing required distinct original poses")
        if sum(v["size"] for v in frames.values()) > MAX_ROLE_BYTES:
            raise ValueError("Artist PNGs exceed installed role size limit")
    return data


def install_nanopet_shimeji(kind, output_root, *, confirmed=False, downloader=_download_png,
                            manifest=None):
    if not confirmed:
        raise ValueError("Explicit user consent required for personal author-art download")
    record = source_manifest() if manifest is None else manifest
    if kind not in record["roles"]:
        raise ValueError("Unknown or excluded creator character source")
    item = record["roles"][kind]
    root = Path(output_root).expanduser()
    if root.is_symlink():
        raise ValueError("Refusing symbolic-link role root")
    root = root.resolve()
    folder = "SourceNano" + "".join(w.title() for w in kind.replace("-by-", "-").split("-"))
    destination = root / folder
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Original artist role already installed; cannot overwrite")
    root.mkdir(parents=True, exist_ok=True)
    prefix = ("https://raw.githubusercontent.com/" + record["repository"] + "/"
              + record["revision"] + "/" + record["asset_root"] + "/"
              + item["upstream_dir"] + "/img/")
    by_index = {int(re.fullmatch(r"shime([1-9][0-9]*)_?\.png", f).group(1)): f
                for f in item["files"]}
    with tempfile.TemporaryDirectory(prefix=".nanopet-artist-", dir=root) as temp:
        stage = Path(temp) / folder
        actions_dir = stage / "action"
        originals_dir = stage / "source_frames"
        actions_dir.mkdir(parents=True)
        originals_dir.mkdir(parents=True)
        source_data = {}
        for index, filename in sorted(by_index.items()):
            raw = downloader(prefix + filename, item["files"][filename])
            source_data[index] = raw
            (originals_dir / filename).write_bytes(raw)
        acts = {}
        for group, indexes in GROUPS.items():
            for dest_index, source_index in enumerate(indexes):
                (actions_dir / f"{group}_{dest_index}.png").write_bytes(source_data[source_index])
        def action(images, moving=None):
            result = {"images": images, "act_num": 1, "frame_refresh": 0.17}
            if moving:
                result.update(need_move=True, direction=moving)
            return result
        acts.update({
            "default": action("stand"),
            "left_walk": action("walk", "left"),
            "right_walk": action("walk", "right"),
            "drag": action("drag"),
            "fall": action("fall"),
            "on_floor": action("onfloor"),
            "climb": action("climb"),
            "patpat": action("pat"),
            "stand_alt": action("stand_alt"),
        })
        dims = struct.unpack(">II", source_data[38][16:24])
        pet = {
            "width": dims[0], "height": dims[1], "scale": 1.0, "refresh": 5,
            "interact_speed": 0.02, "default": "default",
            "up": "default", "down": "default",
            "left": "left_walk", "right": "right_walk",
            "drag": "drag", "fall": "fall", "on_floor": "on_floor",
            "patpat": "patpat",
            "random_act": [
                {"name": "待机", "act_list": ["default"], "act_prob": 1.0, "act_type": [2, 0]},
                {"name": "行走", "act_list": ["left_walk", "right_walk", "default"],
                 "act_prob": 0.1, "act_type": [3, 1]},
            ],
        }
        (stage / "act_conf.json").write_text(
            json.dumps(acts, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        (stage / "pet_conf.json").write_text(
            json.dumps(pet, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        checked = validate_native_role(stage)
        (stage / "PERSONAL_IMPORT.json").write_text(json.dumps({
            "selected_profile": item["profile"], "display_name": item["name"],
            "artist": item["artist"], "source_repository": record["repository"],
            "source_commit": record["revision"],
            "source_asset_path": record["asset_root"] + "/" + item["upstream_dir"] + "/img",
            "source_kind": "artist_shimeji_png_archive",
            "verified_exact_source_frame_bytes": True,
            "all_original_frames_preserved": len(source_data),
            "mapped_original_frame_groups": list(GROUPS),
            "source_rights_verified": False,
            "likeness_manually_reviewed": False,
            "physical_windows_qa_verified": False,
            "redistribution_allowed_by_tool": False,
            "validation": checked,
        }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        visual = create_native_art_review(stage)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Source role was concurrently installed; no overwrite")
        stage.rename(destination)
    return {"profile": item["profile"], "folder": destination.name,
            "source_original_frames": len(source_data),
            "actions": checked["actions"], "frames": checked["images"],
            "original_source_pixels_preserved": True,
            "likeness_manually_reviewed": False}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("role", choices=tuple(source_manifest()["roles"]))
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1] / "res" / "role")
    ap.add_argument("--accept-personal-use", action="store_true")
    args = ap.parse_args(argv)
    try:
        print(json.dumps(install_nanopet_shimeji(
            args.role, args.role_root, confirmed=args.accept_personal_use),
            ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as exc:
        ap.exit(1, "Original NanoPet Shimeji import blocked: "+str(exc)+"\n")


if __name__ == "__main__":
    raise SystemExit(main())
