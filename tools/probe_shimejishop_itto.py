#!/usr/bin/env python3
"""Independent, untrusted third-party Itto Shimeji ZIP probe (no promotion).

The publisher page credits Ookami and links an archive. ZIP content, original
artist attribution, exact Genshin identity and visual likeness require separate
verification; a working standard frame layout is NOT those approvals.

Downloads are bounded to the exact known URL, file bytes are SHA-256-hashed,
only numbered Shimeji PNGs are read, and no EXE/JAR/script is executed. No
third-party art is uploaded into GitHub or bundled with DyberPet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from .install_personal_shimeji_zip import (
        inspect_shimeji_zip, install_personal_shimeji_zip)
    from .install_native_role import validate_native_role
except ImportError:
    from install_personal_shimeji_zip import (
        inspect_shimeji_zip, install_personal_shimeji_zip)
    from install_native_role import validate_native_role

PROFILE = "genshin_arataki_itto"
PAGE = "https://shimejishop.com/free/arataki-itto-shimeji/"
ARCHIVE = "https://shimejishop.com/free/wp-content/uploads/2026/09/50036.zip"
MAX_DOWNLOAD = 32 * 1024 * 1024


def bounded_download(url=ARCHIVE):
    """Fetch only the named candidate over TLS, refusing other host redirects."""
    if url != ARCHIVE:
        raise ValueError("Unexpected source archive; this probe is Itto-only")
    with urlopen(Request(url, headers={
            "User-Agent": "DyberPet-original-frames-candidate/1"}), timeout=25) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname not in (
                "shimejishop.com", "www.shimejishop.com"):
            raise ValueError("Publisher archive redirected outside trusted host")
        payload = response.read(MAX_DOWNLOAD + 1)
    if len(payload) > MAX_DOWNLOAD:
        raise ValueError("Excessive community Shimeji download")
    return payload


def probe_itto(*, downloader=None):
    obtain = downloader if downloader is not None else bounded_download
    raw = obtain(ARCHIVE)
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX_DOWNLOAD:
        raise ValueError("Invalid or excessive publisher ZIP bytes")
    with tempfile.TemporaryDirectory(prefix="itto-third-party-qa-") as td:
        root = Path(td)
        downloaded = root / "candidate.zip"
        downloaded.write_bytes(raw)
        images = inspect_shimeji_zip(downloaded)
        installed = install_personal_shimeji_zip(
            downloaded, root / "installed", profile=PROFILE, confirmed=True)
        native = validate_native_role(installed)
        audit = json.loads(
            (installed / "ACTION_PIXEL_AUDIT.json").read_text(encoding="utf-8"))
        receipt = json.loads(
            (installed / "PERSONAL_IMPORT.json").read_text(encoding="utf-8"))
        if (len(images) < 12 or native["actions"] < 5 or
                receipt["selected_profile"] != PROFILE or
                receipt["source_archive_sha256"] != hashlib.sha256(raw).hexdigest() or
                receipt["all_original_frames_preserved"] != len(images) or
                not (installed / "ANIMATION_PREVIEW.png").is_file()):
            raise ValueError("Original Shimeji frames or native action quality gate failed")
        return {
            "scope": "candidate_archive_structure_only_not_fixed_source",
            "profile": PROFILE,
            "publisher_page": PAGE,
            "page_named_creator": "Ookami",
            "source_url": ARCHIVE,
            "archive_size": len(raw),
            "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "original_png_frames": len(images),
            "native_actions": native["actions"],
            "original_frame_structure_passed": audit["summary"]["animation_structure_passed"],
            "pixel_issue_categories": audit["summary"]["issue_categories"],
            "original_artist_identity_verified": False,
            "character_likeness_manually_verified": False,
            "archive_character_identity_verified": False,
            "physical_desktop_qa_verified": False,
            "rights_verified": False,
            "source_registry_promoted": False,
        }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.parse_args(argv)
    report = probe_itto()
    print("ITTO_ORIGINAL_ARCHIVE_CANDIDATE_PROBED " +
          json.dumps(report, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
