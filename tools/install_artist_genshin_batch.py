#!/usr/bin/env python3
"""One-download, opt-in batch installer for pinned artist native roles.

Only author-published native DyberPet folders from a fixed Git commit. The
download is locally consumed, not republished. Each role still gets its
original author-pinned hash verification and separate visual-preview receipt.
Missing or weak artwork is never replaced by generated placeholder sprites.
"""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from urllib.request import Request, urlopen

try:
    from .install_artist_genshin import (
        ARCHIVE_URL, MAX_DOWNLOAD, ROLES, install_artist_genshin,
    )
except ImportError:
    from install_artist_genshin import (
        ARCHIVE_URL, MAX_DOWNLOAD, ROLES, install_artist_genshin,
    )


# Keep R39's "all" stable: it always means the 3 human Genshin roles.
# Companion mascots are independent original source roles, not human slots.
CORE_ROLES = ("nahida", "xiao", "wanderer")
COMPANION_ROLES = ("arana", "scara_cat", "fungus", "xiao_bird")


def parse_roles(raw):
    """Choose pinned author character sets; never auto-fill template slots."""
    raw = str(raw or "").strip().lower()
    if raw == "all":
        return CORE_ROLES
    if raw == "companions":
        return COMPANION_ROLES
    if raw == "all-seven":
        return CORE_ROLES + COMPANION_ROLES
    keys = tuple(x.strip() for x in raw.split(","))
    if not keys or any(not x or x not in ROLES for x in keys):
        raise ValueError("Select all or known artist-backed roles: " + ", ".join(ROLES))
    if len(keys) != len(set(keys)):
        raise ValueError("Duplicated source role in batch")
    return keys


def _download_archive(destination, opener):
    req = Request(ARCHIVE_URL, headers={"User-Agent": "DyberPet-personal-art/1"})
    with opener(req, timeout=60) as response, destination.open("xb") as output:
        total = 0
        while True:
            data = response.read(1024 * 1024)
            if not data:
                break
            total += len(data)
            if total > MAX_DOWNLOAD:
                raise ValueError("Pinned upstream archive exceeds download limit")
            output.write(data)
    return total


def install_artist_genshin_batch(roles, output_root, *, confirmed=False,
                                 opener=urlopen):
    """Prepare all genuine roles in isolation; publish only if all pass.

    This is a private-install path. No existing role folder is overwritten.
    A failed role or unexpectedly changed source leaves no partially installed
    roles, even if the final copy fails halfway through.
    """
    if not confirmed:
        raise ValueError("Explicit personal-source download consent required")
    keys = parse_roles(roles) if isinstance(roles, str) else tuple(roles)
    if not keys or len(keys) != len(set(keys)) or any(k not in ROLES for k in keys):
        raise ValueError("Unknown or duplicated artist-backed character selection")
    rawroot = Path(output_root).expanduser()
    if rawroot.is_symlink():
        raise ValueError("Symlinked role root not allowed")
    root = rawroot.resolve()
    if root.exists() and not root.is_dir():
        raise ValueError("Role root must be a directory")
    names = ["SourceGenshin" + k.title() for k in keys]
    for name in names:
        target = root / name
        if target.exists() or target.is_symlink():
            raise FileExistsError("Role already installed: " + name)

    root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".artist-batch-", dir=root.parent) as td:
        tmp = Path(td)
        archive_file = tmp / "upstream.zip"
        downloaded = _download_archive(archive_file, opener)

        def cached_opener(request, timeout=60):
            if request.full_url != ARCHIVE_URL:
                raise ValueError("Unexpected remote source in cached artist installer")
            return archive_file.open("rb")

        staging = tmp / "roles"
        staged = []
        for key in keys:
            # Reuse single-role identity hashing, original-PNG preflight,
            # missing-optional-sprite repairs and visual review receipt.
            result = install_artist_genshin(
                key, staging, confirmed=True, opener=cached_opener)
            staged.append(result)

        # Source is fully verified, then commit each role into destination.
        # Reserve every destination directory with atomic mkdir(exist_ok=False),
        # not rename (which could replace an empty pre-existing directory).
        root.mkdir(parents=True, exist_ok=True)
        reserved = []
        try:
            for name in names:
                target = root / name
                target.mkdir(exist_ok=False)
                reserved.append(target)
            for item in staged:
                source = staging / item["folder"]
                dest = root / item["folder"]
                shutil.copytree(source, dest, dirs_exist_ok=True,
                                symlinks=False)
        except Exception:
            for folder in reversed(reserved):
                shutil.rmtree(folder)
            raise

    return {
        "installed_count": len(staged),
        "archive_download_count": 1,
        "archive_download_bytes": downloaded,
        "source_identity_verified": True,
        "likeness_manually_reviewed": False,
        "art_rights_verified": False,
        "roles": staged,
        "only_for_personal_use": True,
    }


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--roles", default="all",
                   help="all (original 3), companions (4 mascots), all-seven, or comma-separated IDs")
    p.add_argument("--role-root", default="res/role")
    p.add_argument("--accept-personal-use", action="store_true")
    a = p.parse_args(argv)
    result = install_artist_genshin_batch(
        a.roles, a.role_root, confirmed=a.accept_personal_use)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
