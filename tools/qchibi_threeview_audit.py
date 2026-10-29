#!/usr/bin/env python3
"""Read-only Q-chibi three-view evidence gate for already installed native roles.

A packaged role is not a completed three-view character. A pinned manifest
proves file provenance/integrity only; human review of identity, proportions
and artistic faithfulness is always separate. No source art is generated,
changed, mirrored, downloaded or copied by this tool.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageOps

try:
    from .qchibi_native_threeview import MANIFEST, VIEW_NAMES, _confirmed_threeview
    from .qchibi_pose_geometry import _visible
except ImportError:
    from qchibi_native_threeview import MANIFEST, VIEW_NAMES, _confirmed_threeview
    from qchibi_pose_geometry import _visible

MAX_ROLES = 512


def _visible_pixels(path):
    """Crop transparent canvas padding, without modifying original PNGs."""
    with Image.open(path) as src:
        image = src.convert("RGBA")
        image.load()
    bbox = image.getchannel("A").getbbox()
    if bbox is None:
        return None
    return image.crop(bbox)


def _independence_warnings(views):
    pixels = {key: _visible_pixels(views[key]["file"]) for key in VIEW_NAMES}
    problems = []
    for key, image in pixels.items():
        if image is None:
            problems.append(key + ":empty_visible_reference")
    for i, a in enumerate(VIEW_NAMES):
        for b in VIEW_NAMES[i + 1:]:
            left, right = pixels[a], pixels[b]
            if left is None or right is None or left.size != right.size:
                continue
            if left.tobytes() == right.tobytes():
                problems.append(a + "_" + b + ":identical_visible_pixels")
            elif ImageOps.mirror(left).tobytes() == right.tobytes():
                problems.append(a + "_" + b + ":exact_horizontal_mirror")
    heights = [_visible(v["file"])["bbox"] for v in views.values()]
    if all(heights):
        lengths = [box[3] - box[1] for box in heights]
        if max(lengths) / max(1, min(lengths)) > 1.65:
            problems.append("views:inconsistent_visible_height")
    return problems


def audit_role(folder):
    """Inspect a real on-disk role; no implicit success from its directory."""
    role = Path(folder)
    row = {
        "role": role.name,
        "status": "missing_threeview_manifest",
        "source_threeview_complete": False,
        "ready_for_manual_art_review": False,
        "threeview_human_approved": False,
        "character_likeness_verified": False,
        "read_only": True,
        "issues": [],
        "views": {},
    }
    if role.is_symlink() or not role.is_dir():
        row.update(status="invalid_role", issues=["unsafe_role_directory"])
        return row
    for name in ("pet_conf.json", "act_conf.json"):
        file = role / name
        if file.is_symlink() or not file.is_file():
            row.update(status="invalid_role", issues=["missing_or_linked_" + name])
            return row
    manifest = role / MANIFEST
    if not manifest.exists() and not manifest.is_symlink():
        row["issues"] = ["independent_front_side_back_source_not_declared"]
        return row
    try:
        declared = _confirmed_threeview(role)
        if declared is None:
            raise ValueError("No three-view evidence")
        metadata = json.loads(manifest.read_text(encoding="utf-8"))
        row["source"] = {
            "artist": metadata["artist"],
            "variant": metadata["variant"],
            "url": metadata["source_url"],
        }
        for name in VIEW_NAMES:
            file = declared[name]["file"]
            row["views"][name] = {
                "file": file.relative_to(role).as_posix(),
                "sha256": declared[name]["sha256"],
                "dimensions": list(_visible(file)["size"]),
            }
        issues = _independence_warnings(declared)
        row["issues"] = issues
        if issues:
            row["status"] = "threeview_requires_source_correction"
        else:
            row["status"] = "threeview_source_candidate_manual_review_required"
            row["source_threeview_complete"] = True
            row["ready_for_manual_art_review"] = True
    except (ValueError, OSError, KeyError, TypeError, json.JSONDecodeError) as exc:
        row["status"] = "invalid_threeview_evidence"
        row["issues"] = [str(exc)[:240]]
    return row


def audit_role_root(role_root):
    root = Path(role_root)
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Role root must be a real installed directory")
    roles = []
    for folder in sorted(root.iterdir(), key=lambda p: p.name.casefold()):
        if folder.is_symlink():
            roles.append(audit_role(folder))
        elif folder.is_dir() and (
            (folder / "pet_conf.json").exists() or
            (folder / "act_conf.json").exists()
        ):
            roles.append(audit_role(folder))
        if len(roles) > MAX_ROLES:
            raise ValueError("Role directory exceeds bounded audit limit")
    counts = {
        "installed_role_folders": len(roles),
        "source_threeview_candidates": sum(
            x["source_threeview_complete"] for x in roles),
        "missing_source_threeviews": sum(
            x["status"] == "missing_threeview_manifest" for x in roles),
        "invalid_or_suspicious_evidence": sum(
            x["status"] in ("invalid_role", "invalid_threeview_evidence",
                            "threeview_requires_source_correction") for x in roles),
        "human_approved": 0,
    }
    return {
        "schema_version": 1,
        "scope": "packaged_local_resources_only",
        "summary": counts,
        "roles": roles,
        "policy": [
            "Native animation frames are not automatically orthographic views.",
            "Identical and exact horizontally mirrored views are rejected as independent references.",
            "Manifest hashes prove file integrity, not source identity or original-character likeness.",
            "An absent back view is missing; no reflection or substitute artwork is generated.",
            "Approval is always pending an actual artist/user visual review.",
        ],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-root", type=Path, required=True)
    parser.add_argument("--out", type=Path, help="Optional JSON report location")
    parser.add_argument("--fail-on-invalid", action="store_true",
                        help="Block packaging on malformed or copied three-view evidence; not on missing views")
    args = parser.parse_args(argv)
    report = audit_role_root(args.role_root)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(payload, encoding="utf-8")
    else:
        print(payload, end="")
    rejected = [role for role in report["roles"]
                if role["status"] in ("invalid_role", "invalid_threeview_evidence",
                                     "threeview_requires_source_correction")]
    if args.fail_on_invalid and rejected:
        for role in rejected[:12]:
            print("BLOCKED_QCHIBI_ROLE=" +
                  json.dumps({"role": role["role"], "status": role["status"],
                              "issues": role["issues"]}, ensure_ascii=False))
        if len(rejected) > 12:
            print("BLOCKED_QCHIBI_REMAINING=" + str(len(rejected) - 12))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
