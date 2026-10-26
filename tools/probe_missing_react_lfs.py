#!/usr/bin/env python3
"""Check two missing Genshin roles against real upstream Git LFS source bytes.

This is an *optional, non-publishing* discovery test. Downloading a pointer
does not count as a source. Only exact byte count + full SHA256 + successful
original PNG frame crop + native role install is printed as verified.
No TypeScript execution and no third-party artist sprite upload.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

try:
    from .react_shimeji_source_leads import CANDIDATES, REPOSITORY, REVISION
    from .install_pinned_react_shimeji import MAX_TS_BYTES, decode_pinned_frames, install_pinned_react_shimeji
    from .artist_animation_audit import audit_native_character
except ImportError:
    from react_shimeji_source_leads import CANDIDATES, REPOSITORY, REVISION
    from install_pinned_react_shimeji import MAX_TS_BYTES, decode_pinned_frames, install_pinned_react_shimeji
    from artist_animation_audit import audit_native_character

MISSING_PROFILES = ("genshin_amber", "genshin_fischl")
ALLOWED_HOSTS = frozenset(("media.githubusercontent.com", "raw.githubusercontent.com"))


def candidate_urls(profile):
    if profile not in MISSING_PROFILES:
        raise ValueError("Only two currently missing, exact-upstream profiles are permitted")
    slug = CANDIDATES[profile][0]
    relative = "packages/character-" + slug + "/index.ts"
    return (
        "https://media.githubusercontent.com/media/" + REPOSITORY + "/" + REVISION + "/" + relative,
        "https://raw.githubusercontent.com/" + REPOSITORY + "/" + REVISION + "/" + relative,
    )


def _bounded_fetch(url):
    endpoint = urlsplit(url)
    if endpoint.scheme != "https" or endpoint.hostname not in ALLOWED_HOSTS:
        raise ValueError("Untrusted GitHub LFS content origin")
    request = Request(url, headers={"User-Agent": "DyberPet-creator-art-validation/1"})
    with urlopen(request, timeout=25) as response:
        if urlsplit(response.geturl()).hostname not in ALLOWED_HOSTS:
            raise ValueError("Unexpected third-party redirect")
        return response.read(MAX_TS_BYTES + 1)


def fetch_matching_source(profile, *, fetch=_bounded_fetch):
    slug, expected_sha, expected_bytes, *_ = CANDIDATES[profile]
    failures = []
    for url in candidate_urls(profile):
        try:
            raw = fetch(url)
            if len(raw) > MAX_TS_BYTES:
                raise ValueError("Excessive LFS response")
            if raw.startswith(b"version https://git-lfs.github.com/spec/v1"):
                raise ValueError("Git LFS pointer, not original animation data")
            if len(raw) != expected_bytes or hashlib.sha256(raw).hexdigest() != expected_sha:
                raise ValueError("Full original byte count / SHA-256 mismatch")
            return raw, url
        except (OSError, ValueError, TimeoutError) as exc:
            failures.append({"host": urlsplit(url).hostname, "reason": str(exc)[:145]})
    raise ValueError("No real matching LFS bytes retrieved: " + json.dumps(failures))


def probe(profile, *, fetch=_bounded_fetch):
    raw, _verified_url = fetch_matching_source(profile, fetch=fetch)
    with tempfile.TemporaryDirectory(prefix="dyberpet-lfs-origin-") as td:
        root = Path(td)
        module = root / "actual-index.ts"
        module.write_bytes(raw)
        frames, sha = decode_pinned_frames(module, profile=profile)
        installed = install_pinned_react_shimeji(
            module, root / "personal-roles", profile=profile, confirmed=True)
        audit = audit_native_character(installed)
        receipt = json.loads((installed / "PERSONAL_IMPORT.json").read_text("utf-8"))
        if receipt["source_module_sha256"] != sha or receipt["selected_profile"] != profile:
            raise ValueError("Verified original frames mapped to wrong role")
        incomplete_motion = [
            {"action": item["action"], "issues": item["issues"]}
            for item in audit["actions"] if item["issues"]
        ]
        return {
            "profile": profile,
            "full_lfs_bytes_verified": len(raw),
            "source_sha256": sha,
            "distinct_source_frames": len(frames),
            "native_actions": audit["summary"]["native_actions"],
            "original_frames_inspected": audit["summary"]["original_frames_inspected"],
            "native_install_verified": True,
            "animation_structure_passed": audit["summary"]["animation_structure_passed"],
            "actions_needing_motion_review": incomplete_motion,
            "art_likeness_manually_verified": False,
            "voice_and_rights_verified": False,
        }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--profile", choices=MISSING_PROFILES)
    args = parser.parse_args(argv)
    profiles = MISSING_PROFILES if args.all or not args.profile else (args.profile,)
    outcomes = []
    for profile in profiles:
        try:
            item = probe(profile)
            print("REAL_LFS_SOURCE_BYTES_AND_NATIVE_INSTALL_VERIFIED " +
                  json.dumps(item, ensure_ascii=False), flush=True)
            outcomes.append({"profile": profile, "success": True})
        except (OSError, ValueError) as exc:
            print("REAL_LFS_CANDIDATE_NOT_VERIFIED " +
                  json.dumps({"profile": profile, "cause": str(exc)[:300]}), flush=True)
            outcomes.append({"profile": profile, "success": False})
    return 0 if all(item["success"] for item in outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
