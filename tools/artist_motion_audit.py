"""Read-only evidence about actual native author animation frames.

This identifies mechanically static or suspicious frame sequences; it DOES NOT
judge likeness, style, artistic quality, authenticity or redistribution rights.
No images are redrawn or sent anywhere. Only native action bindings are read.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, UnidentifiedImageError

ACTIONS = ("default", "left", "right", "patpat", "drag", "fall", "on_floor", "focus")
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_DIM = 4096
MAX_SAMPLES = 9
MAX_JSON_BYTES = 256 * 1024


def _config(role, name):
    src = role / name
    if src.is_symlink() or not src.is_file() or src.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Invalid native role JSON")
    value = json.loads(src.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Role config must be a dictionary")
    return value


def _frames(role, prefix):
    if not isinstance(prefix, str) or not re.fullmatch(r"[\w-]{1,80}", prefix):
        raise ValueError("Unsafe animation prefix")
    folder = role / "action"
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError("Invalid action directory")
    found = []
    for file in folder.glob(prefix + "_*.png"):
        match = re.fullmatch(re.escape(prefix) + r"_(\d+)\.png", file.name)
        if not match:
            continue
        if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("Unsafe action frame")
        found.append((int(match.group(1)), file))
    return [file for _, file in sorted(found)]


def _sample_paths(paths):
    if len(paths) <= MAX_SAMPLES:
        return paths
    positions = sorted({i * (len(paths) - 1) // (MAX_SAMPLES - 1)
                        for i in range(MAX_SAMPLES)})
    return [paths[i] for i in positions]


def _frame_features(path):
    try:
        with Image.open(path) as img:
            if (img.format != "PNG" or min(img.size) < 1 or
                    max(img.size) > MAX_DIM):
                raise ValueError("Unsafe original PNG geometry")
            rgba = img.convert("RGBA")
            rgba.load()
            alpha = rgba.getchannel("A")
            bounds = alpha.getbbox()
            visible = bounds is not None
            edge = (visible and
                    (bounds[0] == 0 or bounds[1] == 0 or
                     bounds[2] == rgba.width or bounds[3] == rgba.height))
            identity = hashlib.sha256(rgba.tobytes()).hexdigest()
            return {"hash": identity, "blank": not visible,
                    "edge_touch": bool(edge), "size": list(rgba.size)}
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Invalid source image: " + path.name) from exc


def audit_native_motion(folder):
    """Inspect bound actions, sampling at most nine real PNG frames per action.

    A visually distinct frame is not necessarily a good or recognizable walk;
    artist likeness and temporal coherence still need human review.
    """
    role = Path(folder).expanduser()
    if role.is_symlink() or not role.is_dir():
        raise ValueError("Unsafe native role folder")
    pet = _config(role, "pet_conf.json")
    actions = _config(role, "act_conf.json")
    reports = {}
    warnings = []
    for key in ACTIONS:
        binding = pet.get(key)
        if key == "patpat" and isinstance(binding, dict):
            binding = next((x for x in binding.values()
                            if isinstance(x, str) and x in actions), None)
        if not isinstance(binding, str) or binding not in actions:
            continue
        action = actions[binding]
        if not isinstance(action, dict):
            raise ValueError("Invalid native action descriptor")
        paths = _frames(role, action.get("images"))
        if not paths:
            warnings.append(key + ": no visible source PNG actions")
            continue
        picked = _sample_paths(paths)
        sample = [_frame_features(path) for path in picked]
        hashes = [a["hash"] for a in sample]
        unique = len(set(hashes))
        blanks = sum(x["blank"] for x in sample)
        edges = sum(x["edge_touch"] for x in sample)
        reports[key] = {
            "bound_action": binding,
            "frames_in_source": len(paths),
            "sampled_frames": len(sample),
            "visually_distinct_samples": unique,
            "identical_neighbor_pairs": sum(a == b for a, b in zip(hashes, hashes[1:])),
            "blank_samples": blanks,
            "edge_touch_samples": edges,
            "sampled_sizes": sorted({tuple(x["size"]) for x in sample}),
        }
        # Unchanging frames may be intentional for idle or holding a pose.
        if key in ("left", "right") and unique <= 1:
            warnings.append(key + ": sampled walk has no visual pose changes")
        if blanks:
            warnings.append(key + ": sampled transparent/empty frames")
        if edges:
            warnings.append(key + ": source may touch viewport boundary; verify crop manually")
    if "default" not in reports:
        raise ValueError("Real artist source requires default animation PNGs")
    for key in ("left", "right"):
        if key in reports and reports[key]["bound_action"] == reports["default"]["bound_action"]:
            warnings.append(key + ": walk reuses idle animation binding")
    if "left" in reports and "right" in reports:
        if reports["left"]["bound_action"] == reports["right"]["bound_action"]:
            warnings.append("left/right: both movement directions bind same animation")
    return {
        "schema_version": 1,
        "role_folder": role.name,
        "analyzed_actions": len(reports),
        "actions": reports,
        "manual_visual_review_pending": True,
        "animation_quality_automatically_approved": False,
        "source_art_pixels_modified": False,
        "rights_or_identity_certified": False,
        "warnings": sorted(set(warnings)),
        "note": "Static frame evidence only; character identity, artistic fidelity, actual four-foot gait and Windows playback require human QA.",
    }


def write_motion_evidence(folder):
    """Write a new local receipt only, never edit artist art or author config."""
    role = Path(folder).resolve()
    report = audit_native_motion(role)
    output = role / "ANIMATION_MOTION_QA.json"
    if output.exists() or output.is_symlink():
        raise FileExistsError("Existing motion QA receipt; refusing to replace")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--role", required=True, type=Path)
    p.add_argument("--write", action="store_true",
                   help="Write ANIMATION_MOTION_QA.json beside role; default is read-only")
    args = p.parse_args(argv)
    result = write_motion_evidence(args.role) if args.write else audit_native_motion(args.role)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
