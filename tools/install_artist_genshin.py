"""Opt-in installation of existing artist-drawn Genshin desktop pet sprites.

Downloads an immutable upstream GitHub source ZIP into temporary storage,
extracts only one named role and retains its original animation PNGs and
configuration. Does not produce replacement/generated character artwork.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import tempfile
from urllib.request import Request, urlopen
from zipfile import ZipFile, BadZipFile

try:
    from .install_native_role import validate_native_role
except ImportError:
    from install_native_role import validate_native_role

REPOSITORY = "ChaozhongLiu/DyberPet_GenshinImpact"
REVISION = "0789950b81802cc51ebeeecfc24be16aaee16e74"
SOURCE_URL = "https://github.com/" + REPOSITORY + "/tree/" + REVISION + "/res/role/"
ARCHIVE_URL = "https://codeload.github.com/" + REPOSITORY + "/zip/" + REVISION
ROLES = {
    "nahida": ("纳西妲", "genshin_nahida", "纳西妲"),
    "xiao": ("魈", "genshin_xiao", "魈"),
    "wanderer": ("流浪者", "genshin_wanderer", "流浪者"),
}
MAX_DOWNLOAD = 600 * 1024 * 1024
MAX_SINGLE = 64 * 1024 * 1024
MAX_ROLE = 180 * 1024 * 1024
MAX_FILES = 5000
SAFE_EXTENSIONS = {".png", ".json", ".wav"}
ROOT_PREFIX = "DyberPet_GenshinImpact-" + REVISION + "/res/role/"


def install_artist_genshin(kind, output_root, *, confirmed=False, opener=urlopen):
    """Return folder name; fail without modifying existing roles."""
    if not confirmed:
        raise ValueError("Explicit personal download consent required")
    if kind not in ROLES:
        raise ValueError("Unknown reviewed original-art role")
    original, profile, _label = ROLES[kind]
    rawroot = Path(output_root).expanduser()
    if rawroot.is_symlink():
        raise ValueError("Do not install into a symbolic-link role root")
    root = rawroot.resolve()
    # Stable readable folder names, never overwrite imported/source/demo art.
    destination = root / ("SourceGenshin" + kind.title())
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("This source character has already been installed")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".artist-source-", dir=root) as tmp:
        archive_path = Path(tmp) / "upstream.zip"
        request = Request(ARCHIVE_URL, headers={"User-Agent": "DyberPet-personal-art/1"})
        with opener(request, timeout=60) as response, archive_path.open("wb") as output:
            received = 0
            while True:
                data = response.read(1024 * 1024)
                if not data:
                    break
                received += len(data)
                if received > MAX_DOWNLOAD:
                    raise ValueError("Upstream source ZIP exceeds download size limit")
                output.write(data)
        try:
            zipfile = ZipFile(archive_path)
        except BadZipFile as exc:
            raise ValueError("Upstream download is not a valid ZIP") from exc
        with zipfile as archive:
            prefix = ROOT_PREFIX + original + "/"
            items = []
            total = 0
            for info in archive.infolist():
                if not info.filename.startswith(prefix) or info.is_dir():
                    continue
                relative = info.filename[len(prefix):]
                parts = PurePosixPath(relative).parts
                if (not relative or relative.startswith(("/", "\\")) or
                    "\\" in relative or len(parts) > 4 or
                    any(part in ("", ".", "..") or part.startswith(".") for part in parts) or
                    PurePosixPath(relative).suffix.lower() not in SAFE_EXTENSIONS or
                    stat.S_ISLNK(info.external_attr >> 16)):
                    raise ValueError("Unsafe or unsupported upstream role member")
                if info.file_size > MAX_SINGLE:
                    raise ValueError("Upstream member exceeds file size cap")
                total += info.file_size
                if total > MAX_ROLE or len(items) >= MAX_FILES:
                    raise ValueError("Upstream role exceeds installation limits")
                items.append((info, parts))
            names = {"/".join(parts) for _, parts in items}
            if not {"pet_conf.json", "act_conf.json"}.issubset(names) or not any(
                    name.startswith("action/") and name.endswith(".png") for name in names):
                raise ValueError("Source is missing native DyberPet role data")
            staged = Path(tmp) / "staged"
            staged.mkdir()
            for info, parts in items:
                target = staged.joinpath(*parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as reader, target.open("xb") as writer:
                    shutil.copyfileobj(reader, writer, 1024 * 1024)
            # This validates original configuration and its genuine image frames.
            status = validate_native_role(staged)
            (staged / "PERSONAL_IMPORT.json").write_text(
                json.dumps({"selected_profile": profile,
                            "source_repository": REPOSITORY,
                            "source_commit": REVISION,
                            "source_kind": "artist_original_animation",
                            "source_rights_verified": False,
                            "likeness_manually_reviewed": False,
                            "voice_verified": False,
                            "installed_for_personal_use": True},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            if destination.exists() or destination.is_symlink():
                raise FileExistsError("Source role folder was created concurrently")
            staged.rename(destination)
    return {"folder": destination.name, "profile": profile,
            "actions": status["actions"], "frames": status["images"],
            "source": SOURCE_URL + original, "uses_original_author_frames": True,
            "likeness_manually_reviewed": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=tuple(ROLES))
    parser.add_argument("--role-root", default="res/role")
    parser.add_argument("--accept-personal-use", action="store_true")
    args = parser.parse_args(argv)
    result = install_artist_genshin(args.role, args.role_root,
                                    confirmed=args.accept_personal_use)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
