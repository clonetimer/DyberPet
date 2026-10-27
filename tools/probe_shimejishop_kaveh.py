#!/usr/bin/env python3
"""R18: inspect an independently credited Kaveh Shimeji ZIP, never republish it.

This is a candidate *alternative* to an existing SHA-pinned Kaveh CodexPetDB
source, not a new Genshin identity. The publisher's author credit is a lead,
not proof of original artist approval or copyright/license conditions.

Only the immutable named URL may be requested. Reject other-domain redirects;
inspect bounded ZIP and PNG files, never execute binaries, and leave artist
images in a disposable local directory only. A structural pass is not likeness.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import BadZipFile

from tools.install_personal_shimeji_zip import (
    inspect_shimeji_zip, install_personal_shimeji_zip)
from tools.install_native_role import validate_native_role
from tools.creator_motion_quality import analyze_creator_actions

PROFILE = "genshin_kaveh"
PUBLISHER_PAGE = "https://shimejishop.com/free/kaveh-shimeji/"
ARTIST_CREDIT = "ilewdha"
ARCHIVE = "https://shimejishop.com/free/wp-content/uploads/2025/09/628.zip"
MAX_DOWNLOAD = 32 * 1024 * 1024
ALLOWED_HOSTS = {"shimejishop.com", "www.shimejishop.com"}


def bounded_download(url=ARCHIVE, *, opener=urlopen):
    if url != ARCHIVE:
        raise ValueError("Unexpected third-party Kaveh archive URL")
    request = Request(url, headers={
        "User-Agent": "DyberPet-isolated-creator-candidate-audit/1"})
    with opener(request, timeout=25) as response:
        final = urlsplit(response.geturl())
        if final.scheme != "https" or final.hostname not in ALLOWED_HOSTS:
            raise ValueError("Publisher redirected outside ShimejiShop HTTPS")
        raw = response.read(MAX_DOWNLOAD + 1)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_DOWNLOAD:
        raise ValueError("Missing or excessive original creator archive")
    return raw


def probe_kaveh(*, downloader=None):
    obtain = downloader if downloader is not None else bounded_download
    raw = obtain(ARCHIVE)
    if not isinstance(raw, bytes) or not 0 < len(raw) <= MAX_DOWNLOAD:
        raise ValueError("Invalid Kaveh candidate archive content")
    with tempfile.TemporaryDirectory(prefix="dyberpet-kaveh-candidate-") as tmp:
        workspace = Path(tmp)
        zip_path = workspace / "candidate.zip"
        zip_path.write_bytes(raw)
        try:
            frames = inspect_shimeji_zip(zip_path)
        except BadZipFile as exc:
            raise ValueError("Candidate is not a valid Shimeji ZIP") from exc
        role = install_personal_shimeji_zip(
            zip_path, workspace / "private-native",
            profile=PROFILE, confirmed=True)
        native = validate_native_role(role)
        motion = analyze_creator_actions(role.parent, role.name)
        source_receipt = json.loads(
            (role / "PERSONAL_IMPORT.json").read_text(encoding="utf-8"))
        audit = json.loads(
            (role / "ACTION_PIXEL_AUDIT.json").read_text(encoding="utf-8"))
        if (len(frames) < 12 or native["actions"] < 5 or
                source_receipt["selected_profile"] != PROFILE or
                source_receipt["all_original_frames_preserved"] != len(frames) or
                source_receipt["source_archive_sha256"] !=
                hashlib.sha256(raw).hexdigest()):
            raise ValueError("Candidate ZIP failed real native frame checks")
        walks = [x for x in motion["actions"] if x["action"] in
                 ("left_walk", "right_walk")]
        walk_evidence = (
            len(walks) == 2 and
            all(x["frame_count"] >= 2 and x["unique_visible_poses"] >= 2
                and not x["risk_indicators"] for x in walks)
        )
        return {
            "scope": "independent_kaveh_original_art_candidate_NOT_SOURCE_PROMOTION",
            "profile": PROFILE,
            "existing_kaveh_fixed_source": True,
            "new_distinct_genshin_identity_count": 0,
            "publisher_page": PUBLISHER_PAGE,
            "publisher_credited_artist": ARTIST_CREDIT,
            "source_url": ARCHIVE,
            "archive_size": len(raw),
            "archive_sha256": hashlib.sha256(raw).hexdigest(),
            "original_png_frames": len(frames),
            "native_actions": native["actions"],
            "pixel_action_structure_passed": audit["summary"]["animation_structure_passed"],
            "pixel_issue_categories": audit["summary"]["issue_categories"],
            "movement_actions": [{
                "name": a["action"],
                "frames": a["frame_count"],
                "distinct_poses": a["unique_visible_poses"],
                "risks": a["risk_indicators"],
            } for a in motion["actions"] if a["movement_expected"]],
            "walk_pose_evidence_passed": walk_evidence,
            "source_registry_promoted": False,
            "artist_original_identity_verified": False,
            "official_genshin_likeness_verified": False,
            "artist_rights_verified": False,
            "physical_desktop_playback_verified": False,
            "source_art_uploaded": False,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        report = probe_kaveh()
        print("KAVEH_THIRD_PARTY_ART_CANDIDATE " +
              json.dumps(report, ensure_ascii=False, sort_keys=True), flush=True)
        # The probe distinguishes structural availability from motion suitability.
        # Fail the *non-gating* job if even basic walk poses are not distinct.
        return 0 if report["walk_pose_evidence_passed"] else 1
    except (OSError, ValueError, TimeoutError) as error:
        print("KAVEH_CANDIDATE_NOT_VERIFIED " +
              json.dumps({"error_type": type(error).__name__,
                          "error": str(error)[:220]}), flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
