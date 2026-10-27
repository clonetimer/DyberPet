#!/usr/bin/env python3
"""Install artist SaylaMars's ORIGINAL Eula desktop pet privately, by SHA.

Never bundle or upload third-party sprites. No third-party executable/XML is
executed. Use a public publisher file link or a locally saved exact original
ZIP. Conversion preserves all 109 numbered PNG bytes and marks human QA pending.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from tools.probe_artist_eula_fanbox import (
    PROFILE, AUTHOR_POST, fetch_public_post, extract_public_eula_post,
    download_creator_zip, MAX_DOWNLOAD,
)
from tools.install_personal_shimeji_zip import (
    EULA_EXTENDED_SOURCE_SHA256, install_personal_shimeji_zip,
)

SOURCE_KEY = "eula_saylamars_original"
ARCHIVE_BYTES = 8400168


def _verified_original(*, archive=None, post_loader=None, downloader=None):
    if archive is not None:
        source = Path(archive).expanduser()
        if (source.is_symlink() or not source.is_file() or
                source.stat().st_size != ARCHIVE_BYTES):
            raise ValueError("Only the exact original Eula ZIP is allowed")
        raw = source.read_bytes()
    else:
        post = (fetch_public_post() if post_loader is None else post_loader())
        attachments = extract_public_eula_post(post)
        if len(attachments) != 1:
            raise ValueError("Original artist post must contain exactly one public ZIP")
        fetch = download_creator_zip if downloader is None else downloader
        raw = fetch(attachments[0]["url"])
    if not isinstance(raw, bytes) or len(raw) != ARCHIVE_BYTES:
        raise ValueError("Original Eula creator ZIP has unexpected byte length")
    if hashlib.sha256(raw).hexdigest() != EULA_EXTENDED_SOURCE_SHA256:
        raise ValueError("Original Eula ZIP SHA-256 mismatched; refusing installation")
    return raw


def install_pinned_eula_shimeji(kind, role_root, *, confirmed=False,
                                archive=None, post_loader=None, downloader=None):
    if kind != SOURCE_KEY:
        raise ValueError("Unknown or unverified Eula original creator key")
    if not confirmed:
        raise ValueError("Original creator material requires explicit personal consent")
    raw = _verified_original(
        archive=archive, post_loader=post_loader, downloader=downloader)
    # Ephemeral source ZIP; role frames installed only after complete native
    # verification and visual/animation audit by the existing atomic importer.
    with tempfile.TemporaryDirectory(prefix="eula-original-verified-") as tmp:
        source = Path(tmp) / "original-eula-creator.zip"
        source.write_bytes(raw)
        target = install_personal_shimeji_zip(
            source, role_root, profile=PROFILE, confirmed=True,
            extended_eula_source=True)
    receipt = json.loads(
        (target / "PERSONAL_IMPORT.json").read_text(encoding="utf-8"))
    if (receipt.get("source_archive_sha256") != EULA_EXTENDED_SOURCE_SHA256 or
            receipt.get("all_original_frames_preserved") != 109 or
            receipt.get("selected_profile") != PROFILE or
            not receipt.get("verified_extended_eula_author_source")):
        raise ValueError("Eula installed art did not pass pinned original receipt")
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=[SOURCE_KEY])
    parser.add_argument("--role-root", type=Path, default=(
        Path(__file__).resolve().parents[1] / "res" / "role"))
    parser.add_argument("--archive", type=Path,
                        help="Locally downloaded original archive with exact SHA")
    parser.add_argument("--accept-personal-use", action="store_true")
    args = parser.parse_args(argv)
    try:
        role = install_pinned_eula_shimeji(
            args.source, args.role_root, confirmed=args.accept_personal_use,
            archive=args.archive)
        print(json.dumps({
            "status": "installed_source_png_frames_not_human_approved",
            "role_folder": role.name, "profile": PROFILE,
            "author_post": AUTHOR_POST,
            "source_sha256": EULA_EXTENDED_SOURCE_SHA256,
            "visual_likeness_approved": False,
            "physical_desktop_qa_approved": False,
            "rights_verified": False,
        }, ensure_ascii=False))
    except (OSError, ValueError, TypeError) as error:
        # Signed publisher URLs and authentication values are never logged.
        parser.exit(2, "Pinned Eula creator import refused: " +
                    type(error).__name__ + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
