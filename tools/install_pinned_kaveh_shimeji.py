#!/usr/bin/env python3
"""Opt-in Kaveh creator Shimeji alternative; no art redistributed or auto-approved."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from tools.chibi_profiles import available_role_folder
from tools.install_personal_shimeji_zip import install_personal_shimeji_zip
from tools.creator_motion_quality import analyze_creator_actions
from tools.probe_shimejishop_kaveh import (
    ARCHIVE, PUBLISHER_PAGE, ARTIST_CREDIT, PROFILE, bounded_download)

SOURCE_KEY = "kaveh_ilewdha"
ARCHIVE_SIZE = 990054
ARCHIVE_SHA256 = "86b14aff32b1eeec87800c632817a21b22779a654d876d79a854fb14da4669c9"


def verified_zip(*, archive=None, downloader=None):
    if archive is None:
        payload = (bounded_download if downloader is None else downloader)(ARCHIVE)
    else:
        path = Path(archive).expanduser()
        if (path.is_symlink() or not path.is_file()
                or path.stat().st_size != ARCHIVE_SIZE):
            raise ValueError("Select the original bounded Kaveh ZIP")
        payload = path.read_bytes()
    if not isinstance(payload, bytes) or len(payload) != ARCHIVE_SIZE:
        raise ValueError("Kaveh ZIP original byte length differs")
    if hashlib.sha256(payload).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("Kaveh ZIP original SHA-256 mismatch")
    return payload


def install_pinned_kaveh_shimeji(key, output_root, *, confirmed=False,
                                archive=None, downloader=None):
    if key != SOURCE_KEY:
        raise ValueError("Only the fixed Kaveh identity is allowed")
    if not confirmed:
        raise ValueError("Explicit creator-source consent required")
    raw = verified_zip(archive=archive, downloader=downloader)
    root = Path(output_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Unsafe role root")
    root = root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=root, prefix=".kaveh-pinned-") as temp:
        work = Path(temp)
        source = work / "verified.zip"
        source.write_bytes(raw)
        built = install_personal_shimeji_zip(
            source, work / "roles", profile=PROFILE, confirmed=True)
        evidence = analyze_creator_actions(built.parent, built.name)
        receipt_path = built / "PERSONAL_IMPORT.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if (receipt.get("selected_profile") != PROFILE or
                receipt.get("source_archive_sha256") != ARCHIVE_SHA256 or
                receipt.get("all_original_frames_preserved") != 46):
            raise ValueError("Native Kaveh source receipt mismatch")
        receipt.update({
            "source_kind": "sha256_pinned_kaveh_alternative",
            "source_url": ARCHIVE, "publisher_page": PUBLISHER_PAGE,
            "publisher_credited_artist": ARTIST_CREDIT,
            "verified_source_zip_sha256": ARCHIVE_SHA256,
            "verified_source_zip_bytes": ARCHIVE_SIZE,
            "weak_original_motion_actions": [
                item["action"] for item in evidence["actions"]
                if item["risk_indicators"]],
            "complete_motion_quality_verified": False,
            "original_game_likeness_verified": False,
            "creator_rights_verified": False,
            "real_desktop_playback_verified": False,
            "redistribution_allowed_by_tool": False,
        })
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        destination = root / available_role_folder(root, "SourceKavehIlewdha")
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Existing Kaveh art cannot be replaced")
        built.rename(destination)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", choices=(SOURCE_KEY,))
    parser.add_argument("--role-root", type=Path,
                        default=Path(__file__).resolve().parents[1]/"res"/"role")
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--accept-personal-use", action="store_true")
    a = parser.parse_args(argv)
    try:
        folder = install_pinned_kaveh_shimeji(
            a.source, a.role_root, confirmed=a.accept_personal_use,
            archive=a.archive)
        print(json.dumps({
            "installed_folder": folder.name, "source_sha256": ARCHIVE_SHA256,
            "source_identity": PROFILE, "visual_review_passed": False,
            "motion_review_passed": False, "rights_review_passed": False,
        }, ensure_ascii=False))
        return 0
    except (ValueError, OSError) as exc:
        parser.exit(2, "Kaveh source rejected: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
