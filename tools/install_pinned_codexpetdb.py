#!/usr/bin/env python3
"""Opt-in personal install from four SHA-pinned CodexPetDB ZIP listings.

A public download page is only a *lead*. The actual compressed ZIP must pass
its advertised SHA-256 and the package's pet.json/atlas must be validated
before any native role is installed. No third-party program is executed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from .chibi_profiles import CHIBI_PROFILES, available_role_folder
    from .install_personal_codex_zip import (
        inspect_codex_zip, install_personal_codex_zip)
    from .artist_animation_audit import audit_native_character
except ImportError:
    from chibi_profiles import CHIBI_PROFILES, available_role_folder
    from install_personal_codex_zip import inspect_codex_zip, install_personal_codex_zip
    from artist_animation_audit import audit_native_character

REGISTRY = Path(__file__).with_name("codexpetdb_pinned_zip_leads.json")
SOURCE_HOST = "cdn.codexpetdb.com"
MAX_ARCHIVE_BYTES = 3 * 1024 * 1024


def listed_packages(path=REGISTRY):
    listing = json.loads(Path(path).read_text(encoding="utf-8"))
    entries = listing.get("sources")
    if listing.get("schema") != 1 or listing.get("provider") != "CodexPetDB":
        raise ValueError("Unknown pinned creator package registry")
    if not isinstance(entries, dict) or len(entries) != 4:
        raise ValueError("Pinned package registry requires exactly four checked listings")
    seen_profiles = set()
    for key, item in entries.items():
        if not re.fullmatch(r"[a-z_]{3,32}", key):
            raise ValueError("Unsafe creator source key")
        if not isinstance(item, dict):
            raise ValueError("Broken creator package registry")
        profile = item.get("profile")
        if profile not in CHIBI_PROFILES or not profile.startswith("genshin_"):
            raise ValueError("Unknown registered Genshin identity")
        if profile in seen_profiles:
            raise ValueError("Two download sources conflict for one role")
        seen_profiles.add(profile)
        if item.get("slug") != "gi-" + key.replace("_", "-"):
            raise ValueError("Package slug does not match pinned character identity")
        if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
                            str(item.get("revision", ""))):
            raise ValueError("Revision identifier is not a pinned UUID")
        if not re.fullmatch(r"[a-f0-9]{64}", str(item.get("sha256", ""))):
            raise ValueError("Package SHA-256 must be pinned")
        if not (type(item.get("max_bytes")) is int and
                0 < item["max_bytes"] <= MAX_ARCHIVE_BYTES):
            raise ValueError("Unsafe compressed package size bound")
        if item.get("listing_url") != "https://codexpetdb.com/en/pets/" + item["slug"] + "/download":
            raise ValueError("Package landing page is not from allowlisted origin")
    return listing


def fixed_archive_url(record):
    return ("https://" + SOURCE_HOST + "/revisions/" + record["revision"] +
            "/" + record["slug"] + ".zip")


def _download_bytes(url, max_bytes):
    if (urlsplit(url).scheme != "https" or
            urlsplit(url).hostname != SOURCE_HOST):
        raise ValueError("Unknown CDN download origin")
    request = Request(url, headers={"User-Agent": "DyberPet-personal-creator-art/1"})
    with urlopen(request, timeout=30) as response:
        if urlsplit(response.geturl()).hostname != SOURCE_HOST:
            raise ValueError("Unexpected cross-domain CDN redirect")
        return response.read(max_bytes + 1)


def get_verified_package(key, *, archive=None, downloader=_download_bytes,
                         manifest=None):
    listing = listed_packages() if manifest is None else manifest
    if key not in listing["sources"]:
        raise ValueError("Unregistered Genshin art package")
    record = listing["sources"][key]
    if archive is None:
        payload = downloader(fixed_archive_url(record), record["max_bytes"])
    else:
        path = Path(archive).expanduser()
        if path.is_symlink() or not path.is_file() or path.stat().st_size > record["max_bytes"]:
            raise ValueError("Select a bounded regular downloaded ZIP archive")
        payload = path.read_bytes()
    if len(payload) > record["max_bytes"]:
        raise ValueError("Creator ZIP is larger than pinned source limit")
    if hashlib.sha256(payload).hexdigest() != record["sha256"]:
        raise ValueError("Creator archive SHA-256 mismatch; source not installed")
    return payload, record


def install_pinned_codexpetdb(key, role_root, *, confirmed=False,
                             archive=None, downloader=_download_bytes,
                             manifest=None):
    if not confirmed:
        raise ValueError("Confirm personal opt-in before retrieving creator artwork")
    payload, record = get_verified_package(
        key, archive=archive, downloader=downloader, manifest=manifest)
    root = Path(role_root).expanduser()
    if root.is_symlink():
        raise ValueError("Linked installation folder refused")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".codexpetdb-verified-", dir=root) as td:
        staging = Path(td)
        zipped = staging / (record["slug"] + ".zip")
        zipped.write_bytes(payload)
        inspected = inspect_codex_zip(zipped)
        if inspected["manifest"]["id"] != record["slug"]:
            raise ValueError("ZIP pet.json.id does not match requested Genshin role")
        if inspected["manifest"].get("spritesheetPath") != inspected["sheet_name"]:
            raise ValueError("Wrong image type or untrusted spritesheet path")
        workspace = staging / "staged-roles"
        created = install_personal_codex_zip(
            zipped, workspace, profile=record["profile"], confirmed=True)
        receipt = created / "PERSONAL_IMPORT.json"
        info = json.loads(receipt.read_text(encoding="utf-8"))
        info.update({
            "source_kind": "codexpetdb_sha256_pinned_personal_art",
            "source_site": record["listing_url"],
            "source_zip_sha256_verified": record["sha256"],
            "source_zip_revision": record["revision"],
            "source_zip_id": record["slug"],
            "character_original_likeness_qa_passed": False,
            "source_rights_verified": False,
            "redistribution_allowed_by_tool": False,
        })
        receipt.write_text(json.dumps(info, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
        audit = audit_native_character(created)
        (created / "ACTION_PIXEL_AUDIT.json").write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        final_name = available_role_folder(
            root, "SourcePetDb" + "".join(p.title() for p in key.split("_")))
        target = root / final_name
        if target.exists() or target.is_symlink():
            raise FileExistsError("Refusing to replace an existing artist character")
        created.rename(target)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=sorted(listed_packages()["sources"]))
    parser.add_argument("--archive", type=Path,
                        help="Optional manually downloaded ZIP; never execute its files")
    parser.add_argument("--role-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "res" / "role")
    parser.add_argument("--accept-personal-use", action="store_true")
    parser.add_argument("--verify-only", action="store_true",
                        help="Check actual provider ZIP hash, ID and sprite atlas; do not install")
    a = parser.parse_args(argv)
    if a.verify_only:
        payload, record = get_verified_package(a.source, archive=a.archive)
        with tempfile.TemporaryDirectory(prefix="petdb-verify-only-") as temp:
            path = Path(temp) / "source.zip"
            path.write_bytes(payload)
            inspected = inspect_codex_zip(path)
            if inspected["manifest"]["id"] != record["slug"]:
                raise ValueError("Verified source has the wrong persona id")
        print(json.dumps({
            "source": a.source, "status": "verified_compressed_bytes_and_atlas",
            "sha256": record["sha256"], "byte_length": len(payload),
            "source_package_id": record["slug"],
            "character_art_likeness_verified": False,
            "role_installed": False,
        }, ensure_ascii=False))
    else:
        print(install_pinned_codexpetdb(
            a.source, a.role_root, confirmed=a.accept_personal_use,
            archive=a.archive))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
