#!/usr/bin/env python3
"""Import a personally downloaded Codex Pet ZIP without running vendor code.

Only the selected pet.json and its original spritesheet are read. Frame pixels
are preserved by the existing native converter; no fake actions are invented.
Artwork rights and likeness require independent review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import stat
import tempfile
import zipfile

try:
    from .chibi_profiles import CHIBI_PROFILES, available_role_folder, get_profile
    from .import_codex_pet import convert, read_atlas
    from .install_native_role import validate_native_role
except ImportError:
    from chibi_profiles import CHIBI_PROFILES, available_role_folder, get_profile
    from import_codex_pet import convert, read_atlas
    from install_native_role import validate_native_role

MAX_ARCHIVE = 30 * 1024 * 1024
MAX_EXPANDED = 35 * 1024 * 1024
MAX_ENTRIES = 128
MAX_JSON = 64 * 1024
MAX_SHEET = 12 * 1024 * 1024


def inspect_codex_zip(source):
    """Read source bytes only; reject dangerous paths and duplicate packages."""
    path = Path(source).expanduser()
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_ARCHIVE:
        raise ValueError("Choose a regular Codex ZIP under the size limit")
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > MAX_ENTRIES:
            raise ValueError("Too many ZIP members")
        if sum(m.file_size for m in members) > MAX_EXPANDED:
            raise ValueError("Expanded ZIP too large")
        files = {}
        for info in members:
            name = info.filename.replace("\\", "/")
            parts = PurePosixPath(name).parts
            if (name.startswith("/") or ".." in parts or
                    any(p in ("", ".") for p in parts) or ":" in name):
                raise ValueError("Unsafe ZIP member path")
            if stat.S_IFMT(info.external_attr >> 16) == stat.S_IFLNK:
                raise ValueError("ZIP symbolic link refused")
            if info.is_dir():
                continue
            leaf = parts[-1]
            if leaf not in ("pet.json", "spritesheet.webp", "spritesheet.png"):
                continue  # Never extract scripts, executables or other payloads.
            if leaf in files:
                raise ValueError("Ambiguous duplicate Codex pet package")
            bound = MAX_JSON if leaf == "pet.json" else MAX_SHEET
            if (not 0 < info.file_size <= bound or
                    info.file_size / max(info.compress_size, 1) > 250):
                raise ValueError("Invalid ZIP member size or ratio")
            files[leaf] = (parts[:-1], archive.read(info))
        if "pet.json" not in files:
            raise ValueError("Missing Codex pet.json")
        raw = files["pet.json"][1]
        try:
            manifest = json.loads(raw.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid UTF-8 Codex manifest") from exc
        if not isinstance(manifest, dict) or not isinstance(manifest.get("id"), str):
            raise ValueError("Invalid Codex manifest identity")
        sheet_name = manifest.get("spritesheetPath")
        if sheet_name not in ("spritesheet.webp", "spritesheet.png"):
            raise ValueError("Unsafe or unsupported Codex sprite path")
        if sheet_name not in files or files[sheet_name][0] != files["pet.json"][0]:
            raise ValueError("Codex spritesheet missing from manifest directory")
        sheet = files[sheet_name][1]
        from io import BytesIO
        # Verify actual decodable atlas dimensions, not the extension alone.
        with tempfile.TemporaryDirectory(prefix="codex-zip-inspect-") as td:
            atlas_path = Path(td) / sheet_name
            atlas_path.write_bytes(sheet)
            _, version = read_atlas(atlas_path, manifest)
        hasher = hashlib.sha256()
        with path.open("rb") as archive_file:
            while True:
                chunk = archive_file.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
        digest = hasher.hexdigest()
        return {"manifest": manifest, "manifest_bytes": raw, "sheet": sheet,
                "sheet_name": sheet_name, "version": version,
                "package_sha256": digest}


def install_personal_codex_zip(source, output_root, *, profile, confirmed=False):
    if not confirmed:
        raise ValueError("Explicit confirmation required for a personal creator ZIP")
    if profile not in CHIBI_PROFILES or not profile.startswith("genshin_"):
        raise ValueError("Choose the exact Genshin character; no filename-based identity guessing")
    source_data = inspect_codex_zip(source)
    root = Path(output_root).expanduser()
    if root.is_symlink():
        raise ValueError("Linked role root refused")
    root = root.resolve()
    name = available_role_folder(root, "PersonalCodex" +
                                 "".join(part.title() for part in profile[8:].split("_")))
    destination = root / name
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Refuse to overwrite an existing character")
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".personal-codex-source-") as tmp:
        folder = Path(tmp)
        (folder / "pet.json").write_bytes(source_data["manifest_bytes"])
        (folder / source_data["sheet_name"]).write_bytes(source_data["sheet"])
        installed = None
        try:
            installed = convert(
                folder, root, folder=name, profile=profile,
                name=get_profile(profile)["name"],
                author="External creator (not verified by importer)",
                license_name="Personal local use; rights not independently verified",
                preserve_source_frames=True,
            )
            checked = validate_native_role(installed)
            (installed / "PERSONAL_IMPORT.json").write_text(json.dumps({
                "mode": "personal_local_only",
                "source_kind": "user_selected_codex_zip",
                "source_archive_sha256": source_data["package_sha256"],
                "source_pet_id": source_data["manifest"]["id"],
                "selected_profile": profile,
                "source_spritesheet_sha256": hashlib.sha256(source_data["sheet"]).hexdigest(),
                "atlas_version": source_data["version"],
                "source_original_frames_preserved": True,
                "source_creator_identity_verified": False,
                "source_rights_verified": False,
                "likeness_manually_reviewed": False,
                "real_windows_qa_verified": False,
                "redistribution_allowed_by_tool": False,
                "validation": checked,
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return installed
        except Exception:
            if (installed is not None and installed == destination and
                    installed.is_dir() and not installed.is_symlink()):
                import shutil
                shutil.rmtree(installed)
            raise


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--profile", choices=sorted(k for k in CHIBI_PROFILES
                                             if k.startswith("genshin_")), required=True)
    p.add_argument("--role-root", type=Path,
                   default=Path(__file__).resolve().parents[1] / "res" / "role")
    p.add_argument("--personal-use", action="store_true")
    a = p.parse_args(argv)
    print(install_personal_codex_zip(
        a.archive, a.role_root, profile=a.profile, confirmed=a.personal_use))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
