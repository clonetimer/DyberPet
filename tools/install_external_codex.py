#!/usr/bin/env python3
"""Opt-in import of independent artists' Git-pinned Codex Pets.

Downloads only the selected exact pet.json and spritesheet.webp to ephemeral
space, preserves the artist's atlas cells, and installs into a new DyberPet role.
Source hash integrity is not visual fidelity or redistribution authorization.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import tempfile

try:
    from .chibi_profiles import CHIBI_PROFILES
    from .install_artist_codex import _download_pinned
    from .import_codex_pet import convert
    from .install_native_role import validate_native_role
    from .artist_visual_review import create_native_art_review
except ImportError:
    from chibi_profiles import CHIBI_PROFILES
    from install_artist_codex import _download_pinned
    from import_codex_pet import convert
    from install_native_role import validate_native_role
    from artist_visual_review import create_native_art_review

REGISTRY = Path(__file__).with_name("external_codex_art_sources.json")


def source_manifest(path=REGISTRY):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("schema") != 1 or len(data.get("sources", {})) != 7:
        raise ValueError("Unknown pinned external artist registry")
    for kind, rec in data["sources"].items():
        if not re.fullmatch(r"[a-z][a-z_]{1,39}", kind):
            raise ValueError("Invalid artist choice name")
        if not re.fullmatch(r"[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+", rec.get("repository", "")):
            raise ValueError("Unrecognized creator GitHub repository name")
        if not re.fullmatch(r"[0-9a-f]{40}", rec.get("revision", "")):
            raise ValueError("External creator version must be immutable")
        if not re.fullmatch(r"[A-Za-z0-9_/-]+", rec.get("directory", "")):
            raise ValueError("Unsafe external creator path")
        if rec.get("directory", "").startswith("/") or ".." in rec["directory"].split("/"):
            raise ValueError("Unsafe source directory")
        if rec.get("profile") not in CHIBI_PROFILES or not rec["profile"].startswith("genshin_"):
            raise ValueError("Creator source character is outside the roster")
        for label in ("pet", "sprites"):
            spec = rec.get(label, {})
            if type(spec.get("size")) is not int or not 100 <= spec["size"] <= 5*1024*1024:
                raise ValueError("Bad creator source byte size")
            if not re.fullmatch(r"[0-9a-f]{40}", str(spec.get("sha", ""))):
                raise ValueError("Bad immutable Git blob ID")
    return data


def install_external_codex(kind, output_root, *, confirmed=False, downloader=_download_pinned,
                           manifest=None):
    if not confirmed:
        raise ValueError("Please confirm personal-only creator artwork download")
    sources = source_manifest() if manifest is None else manifest
    if kind not in sources["sources"]:
        raise ValueError("Unregistered creator character")
    item = sources["sources"][kind]
    root = Path(output_root).expanduser()
    if root.is_symlink():
        raise ValueError("Refuse linked role directory")
    root = root.resolve()
    folder = "SourceExternal" + "".join(x.title() for x in kind.split("_"))
    if (root/folder).exists() or (root/folder).is_symlink():
        raise FileExistsError("Cannot overwrite existing artist-created character")
    root.mkdir(parents=True, exist_ok=True)
    source_url = "https://raw.githubusercontent.com/{}/{}/{}/".format(
        item["repository"], item["revision"], item["directory"])
    with tempfile.TemporaryDirectory(prefix=".external-codex-", dir=root) as tmp:
        local = Path(tmp) / "original"
        local.mkdir()
        for filename, spec in (("pet.json", item["pet"]),
                               ("spritesheet.webp", item["sprites"])):
            raw = downloader(source_url+filename, (spec["size"], spec["sha"]))
            (local / filename).write_bytes(raw)
        metadata = json.loads((local/"pet.json").read_text(encoding="utf-8"))
        if (metadata.get("id") != item["manifest_id"]
                or metadata.get("spritesheetPath") != "spritesheet.webp"):
            raise ValueError("Wrong artist, role, or atlas structure in pinned source")
        imported = convert(
            local, root, folder=folder, profile=item["profile"],
            name=item["name"], style="classic", preserve_source_frames=True,
            source_url=("https://github.com/{}/tree/{}/{}".format(
                item["repository"], item["revision"], item["directory"])),
            license_name="Creator work; local personal use only; rights not reviewed")
        report = validate_native_role(imported)
        visual = create_native_art_review(imported)
        (imported/"PERSONAL_IMPORT.json").write_text(json.dumps({
            "selected_profile": item["profile"],
            "display_name": item["name"],
            "source_id": item["manifest_id"],
            "source_repository": item["repository"],
            "source_commit": item["revision"],
            "source_path": item["directory"],
            "source_kind": "independent_creator_codex_atlas",
            "source_rights_verified": False,
            "likeness_manually_reviewed": False,
            "real_windows_qa_verified": False,
            "redistribution_allowed_by_tool": False,
            "source_pixel_integrity_verified": True,
            "validation": report,
        }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return {
        "folder": folder, "profile": item["profile"],
        "actions": report["actions"], "frames": report["images"],
        "artist_source_pixels_preserved": True,
        "likeness_manually_reviewed": False,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("role", choices=tuple(source_manifest()["sources"]))
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1]/"res"/"role")
    ap.add_argument("--accept-personal-use", action="store_true")
    args = ap.parse_args(argv)
    try:
        result = install_external_codex(args.role, args.role_root,
                                        confirmed=args.accept_personal_use)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, OSError) as exc:
        ap.exit(1, "Independent artist import blocked: "+str(exc)+"\n")


if __name__ == "__main__":
    raise SystemExit(main())
