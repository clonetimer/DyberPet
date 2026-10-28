"""Check a *built* Personal65 portable ZIP before uploading it.

This validates launchers, backend metadata, installer entry points, 123-role
inventory consistency, and absence of accidentally embedded creator art.
It does NOT certify licensing, visual likeness, voice, or desktop playback.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile

_REQUIRED = {
    "DyberPet.exe", "DyberPet-Role-Installer.exe", "Run-DyberPet.cmd",
    "Install-Available-Roles.cmd", "Install-Available-Roles.ps1",
    "Install-Guga-Doro.cmd", "Install-Guga-Doro.ps1",
    "Retry-Failed-Roles.cmd", "Retry-Failed-Roles.ps1",
    "Make-My-Offline-DyberPet.cmd", "Make-Personal65-Offline.ps1",
    "PERSONAL65_BUILD_INFO.json", "PERSONAL65_INSTALL.md",
    "Install-Whale-Pet.cmd", "Install-Whale-Pet.ps1", "WHALE_PERSONAL_GUIDE.md",
}
_DEMO_MARKERS = {"builtin_chibi_demo.json", "builtin_mascot_demo.json"}
_MAX_ENTRIES = 50000
_MAX_TOTAL_UNCOMPRESSED = 3 * 1024**3


def verify_portable_zip(archive: str | Path, backend: str) -> dict:
    """Return a release audit receipt; reject a structurally invalid package."""
    if backend not in ("python", "rust"):
        raise ValueError("Expected backend must be python or rust")
    file = Path(archive)
    with zipfile.ZipFile(file, "r") as zf:
        members = zf.infolist()
        if len(members) > _MAX_ENTRIES:
            raise ValueError("Portable ZIP contains too many entries")
        files = {}
        folded_names = set()
        uncompressed = 0
        for entry in members:
            name = entry.filename.replace("\\", "/")
            path = PurePosixPath(name)
            if (not name or name.startswith("/") or name.startswith("//")
                    or path.is_absolute() or ".." in path.parts
                    or (path.parts and ":" in path.parts[0])):
                raise ValueError("Unsafe portable ZIP entry path")
            key = name.casefold().rstrip("/")
            if key in folded_names:
                raise ValueError("Duplicate case-insensitive ZIP entry: " + name)
            folded_names.add(key)
            if entry.is_dir():
                continue
            uncompressed += entry.file_size
            if uncompressed > _MAX_TOTAL_UNCOMPRESSED:
                raise ValueError("Portable ZIP exceeds size limit")
            parts = tuple(p.casefold() for p in path.parts)
            if (name.casefold().startswith("imageio_ffmpeg/binaries/")
                    or name.casefold().endswith("ffmpeg-win-x86_64-v7.1.exe")):
                raise ValueError("Optimized Windows bundle must not prebundle whale FFmpeg")
            if name.casefold().endswith((".pyc", ".pyo")):
                raise ValueError("Unexpected bytecode cache in portable ZIP")
            if parts and parts[0] == "data":
                raise ValueError("Private user data directory embedded in portable ZIP")
            if len(parts) >= 3 and parts[:2] == ("res", "role"):
                if parts[2].startswith("source"):
                    raise ValueError("Creator Source* artwork embedded in hosted package")
                if parts[-1] in _DEMO_MARKERS:
                    raise ValueError("QA-only placeholder art marker in final ZIP")
                if parts[-1] in ("creator_source_receipt.json", "artist_source_receipt.json"):
                    raise ValueError("Creator artwork provenance receipt in final hosted ZIP")
            files[name] = entry

        missing = _REQUIRED - set(files)
        if missing:
            raise ValueError("Missing required portable files: " + ", ".join(sorted(missing)))
        metadata = json.loads(zf.read("PERSONAL65_BUILD_INFO.json").decode("utf-8-sig"))
        total = metadata.get("character_templates")
        covered = metadata.get("pinned_source_characters")
        missing_count = metadata.get("missing_source_characters")
        if (type(total) is not int or total != 123 or
                type(covered) is not int or not (66 <= covered <= total) or
                type(missing_count) is not int or missing_count != total - covered):
            raise ValueError("Frozen 123-character source counts inconsistent")
        if metadata.get("variant") != backend:
            raise ValueError("Frozen backend metadata differs from package variant")
        if metadata.get("prebundled_third_party_art") is not False:
            raise ValueError("Package claims to include third-party artwork")
        if metadata.get("release_is_prerelease") is not True:
            raise ValueError("Personal ZIP must not claim Stable release")
        launcher = zf.read("Run-DyberPet.cmd").decode("utf-8-sig").casefold()
        if "dyberpet_native_backend=" + backend not in launcher:
            raise ValueError("Launcher does not activate the requested backend")
        if backend == "rust" and "dyberpet_require_rust=1" not in launcher:
            raise ValueError("Rust package lacks fail-closed native backend requirement")
        if zf.testzip() is not None:
            raise ValueError("Portable ZIP entry CRC verification failed")
    digest = hashlib.sha256()
    with file.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    sha = digest.hexdigest()
    return {
        "archive": file.name, "sha256": sha, "backend": backend,
        "files_checked": len(files), "character_templates": total,
        "pinned_source_characters": covered,
        "missing_source_characters": missing_count,
        "creator_art_prebundled": False,
        "real_windows_desktop_qa_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--backend", choices=("python", "rust"), required=True)
    args = parser.parse_args()
    print(json.dumps(verify_portable_zip(args.archive, args.backend), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
