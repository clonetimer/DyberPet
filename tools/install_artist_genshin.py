"""Opt-in installation of existing artist-drawn Genshin desktop pet sprites.

Downloads an immutable upstream GitHub source ZIP into temporary storage,
extracts only one named role and retains its original animation PNGs and
configuration. Does not produce replacement/generated character artwork.
"""
from __future__ import annotations

import argparse
import hashlib
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
    from .artist_visual_review import create_native_art_review
    from .artist_motion_audit import write_motion_evidence
except ImportError:
    from install_native_role import validate_native_role
    from artist_visual_review import create_native_art_review
    from artist_motion_audit import write_motion_evidence

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

# Exact Git blob IDs at pinned upstream commit, checked against the raw
# original bytes *before* any required legacy configuration compatibility fix.
# These bind display identity to genuine artist-provided default PNG artwork.
# A structural-valid-but-swapped role can no longer install under another name.
SOURCE_IDENTITY = {
    "nahida": {
        "pet_conf.json": "c35730bfef960b692ede3909e4d79dc45e6641a7",
        "act_conf.json": "f5d6d3b8c1e4a5659ac3f995d12e40d23bff2146",
        "action/hx_0.png": "9d6893fd9304ef7c8d011b0cac0e807e188c0a0d",
    },
    "xiao": {
        "pet_conf.json": "ed9f64fae6a011a3bb249d10bdb0a1452d00ca0d",
        "act_conf.json": "e1f467b16eb38de114b166738269e1585ba22b3a",
        "action/stand_0.png": "111112768a305901213c54cf8efbbe68c934fc01",
    },
    "wanderer": {
        "pet_conf.json": "a204e9495fad1c42130b401813681b616817caae",
        "act_conf.json": "f40d19d250dfb136f881f9241210f0b627a948b9",
        "action/stand_0.png": "4467a4c6c41abcb41d61294292ad6b5231400b1c",
    },
}


def _git_blob_sha(path):
    raw = Path(path).read_bytes()
    if len(raw) > MAX_SINGLE:
        raise ValueError("Source identity anchor exceeds file size limit")
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def verify_artist_role_identity(folder, kind, *, identities=None):
    """Bind character identity to 3 immutable upstream bytestrings.

    Verifies *source authenticity*, not perceived character likeness, outfit,
    rights, voice, or manual visual acceptance.
    """
    expected = SOURCE_IDENTITY if identities is None else identities
    if kind not in expected or kind not in ROLES:
        raise ValueError("Unknown source identity")
    root = Path(folder)
    verified = []
    for rel, sha in expected[kind].items():
        file = root / rel
        if not file.is_file() or file.is_symlink():
            raise ValueError("Missing authentic source asset: " + rel)
        actual = _git_blob_sha(file)
        if actual != sha:
            raise ValueError("Character artwork/config identity mismatch: " + rel)
        verified.append(rel)
    return verified



def _prune_missing_optional_actions(folder):
    """Repair an upstream legacy configuration with missing *optional* sprites.

    Only action references to absent original PNGs are removed; no frames,
    artwork, proportions or image pixels are generated or modified. Current
    artist config is preserved in a separate source metadata file.
    """
    pet_file = folder / "pet_conf.json"
    act_file = folder / "act_conf.json"
    pet = json.loads(pet_file.read_text(encoding="utf-8"))
    actions = json.loads(act_file.read_text(encoding="utf-8"))
    missing = sorted(name for name, cfg in actions.items()
                     if not list((folder / "action").glob(str(cfg.get("images", "")) + "_*.png")))
    if not missing:
        return []
    for core in ("default", "drag", "fall"):
        if pet.get(core) in missing:
            raise ValueError("Upstream core action is missing artist sprites: " + core)
    (folder / "UPSTREAM_ACT_CONF.json").write_text(
        json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "UPSTREAM_PET_CONF.json").write_text(
        json.dumps(pet, ensure_ascii=False, indent=2), encoding="utf-8")
    for key in missing:
        del actions[key]
    for field in ("up", "down", "left", "right", "prefall", "on_floor", "focus"):
        if pet.get(field) in missing:
            pet[field] = pet["default"]
    if isinstance(pet.get("patpat"), str) and pet["patpat"] in missing:
        pet["patpat"] = pet["default"]
    if isinstance(pet.get("patpat"), dict):
        pet["patpat"] = {key: (pet["default"] if act in missing else act)
                         for key, act in pet["patpat"].items()}
    pet["random_act"] = [entry for entry in pet.get("random_act", [])
                         if all(act in actions for act in entry.get("act_list", []))]
    pet["accessory_act"] = [entry for entry in pet.get("accessory_act", [])
                            if all(act in actions for act in
                                   entry.get("act_list", []) + entry.get("acc_list", []))]
    pet_file.write_text(json.dumps(pet, ensure_ascii=False, indent=2), encoding="utf-8")
    act_file.write_text(json.dumps(actions, ensure_ascii=False, indent=2), encoding="utf-8")
    return missing


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
            verified_source_files = verify_artist_role_identity(staged, kind)
            # Some author-released older configurations list effects whose
            # sprites were never published (e.g. Wanderer). Keep genuine art
            # intact and drop only missing, nonessential action references.
            excluded = _prune_missing_optional_actions(staged)
            status = validate_native_role(staged)
            visual_review = create_native_art_review(staged)
            motion_review = write_motion_evidence(staged)
            (staged / "PERSONAL_IMPORT.json").write_text(
                json.dumps({"selected_profile": profile,
                            "display_name": original,
                            "source_repository": REPOSITORY,
                            "source_commit": REVISION,
                            "source_kind": "artist_original_animation",
                            "source_identity_anchors_verified": verified_source_files,
                            "visual_review": visual_review,
                            "motion_evidence_file": "ANIMATION_MOTION_QA.json",
                            "motion_warning_count": len(motion_review["warnings"]),
                            "animation_quality_automatically_approved": False,
                            "source_rights_verified": False,
                            "likeness_manually_reviewed": False,
                            "voice_verified": False,
                            "installed_for_personal_use": True,
                            "absent_upstream_actions": excluded},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            if destination.exists() or destination.is_symlink():
                raise FileExistsError("Source role folder was created concurrently")
            staged.rename(destination)
    return {"folder": destination.name, "profile": profile,
            "actions": status["actions"], "frames": status["images"],
            "source": SOURCE_URL + original, "uses_original_author_frames": True,
            "source_identity_verified": True,
            "visual_review": visual_review["visual_review_file"],
            "motion_evidence": "ANIMATION_MOTION_QA.json",
            "motion_warnings": len(motion_review["warnings"]),
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
