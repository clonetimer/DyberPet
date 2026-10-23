#!/usr/bin/env python3
"""Import locally supplied transparent GIF/APNG/PNG-sequence animations as a DyberPet chibi role.

No artwork is downloaded, generated, or redistributed. Requires Pillow.
This accepts a folder with idle.gif, idle.png, idle_0.png, etc.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path
from statistics import median

try:
    from PIL import Image
except ImportError:
    Image = None

if __package__:
    from .chibi_layout import normalize_grounded_frames, quality_metrics, suggested_scale
    from .chibi_profiles import CHIBI_PROFILES, get_profile, make_bubble_config
    from .chibi_preview import create_contact_sheet
    from .import_codex_pet import build_configs, json_text, make_info_images
else:
    from chibi_layout import normalize_grounded_frames, quality_metrics, suggested_scale
    from chibi_profiles import CHIBI_PROFILES, get_profile, make_bubble_config
    from chibi_preview import create_contact_sheet
    from import_codex_pet import build_configs, json_text, make_info_images

# First matches are canonical; aliases are permitted for user convenience.
ALIASES = {
    "idle": ("idle", "stand", "standing", "breath"),
    "left_walk": ("left_walk", "walk_left", "left", "run_left"),
    "right_walk": ("right_walk", "walk_right", "right", "run_right"),
    "wave": ("wave", "waving", "patpat", "greet"),
    "jump": ("jump", "jumping"),
    "wait": ("wait", "waiting", "rest"),
    "failed": ("failed", "sad"),
    "run": ("run", "running"),
    "review": ("review", "focus", "working"),
    "sleep": ("sleep", "sleeping"),
}
ALLOWED = {".png", ".gif", ".webp"}
MAX_SOURCE_PIXELS = 4096 * 4096
MAX_FRAMES_PER_ACTION = 120
CELL = (192, 208)


def resolve_animations(folder: Path) -> tuple[dict, list]:
    folder = folder.expanduser().resolve()
    if not folder.is_dir():
        raise ValueError("Please select an animation folder")
    found, warnings = {}, []
    for action, options in ALIASES.items():
        chosen = None
        for alias in options:
            paths = [folder / (alias + ext) for ext in (".gif", ".png", ".webp")]
            single = next((p for p in paths if p.is_file()), None)
            if single:
                chosen = [single]
                break
            # Sort by numerical suffix, not lexicographic ("_10" after "_9").
            candidates = []
            for p in folder.iterdir():
                match = re.fullmatch(rf"{re.escape(alias)}_(\d+)\.(png|gif|webp)",
                                     p.name, re.IGNORECASE)
                if p.is_file() and match:
                    candidates.append((int(match.group(1)), p))
            if candidates:
                candidates.sort(key=lambda item: item[0])
                indexes = [v[0] for v in candidates]
                if indexes != list(range(indexes[0], indexes[-1] + 1)):
                    warnings.append(f"{action}: gaps in numbered source images")
                chosen = [p for _, p in candidates]
                break
        if chosen:
            found[action] = chosen
    if "idle" not in found:
        raise ValueError("No idle animation found: provide idle.gif, idle.png or idle_0.png")
    return found, warnings


def load_sources(paths: list[Path]) -> tuple[list, list]:
    """Extract composited Pillow frames; duration ms is preserved in a side channel."""
    if Image is None:
        raise ImportError("Pillow is required: py -m pip install Pillow")
    frames, delays = [], []
    for path in paths:
        with Image.open(path) as anim:
            if anim.width * anim.height > MAX_SOURCE_PIXELS:
                raise ValueError(f"Source image too large: {path.name}")
            for i in range(getattr(anim, "n_frames", 1)):
                if len(frames) >= MAX_FRAMES_PER_ACTION:
                    raise ValueError(f"Too many frames (>{MAX_FRAMES_PER_ACTION}) in {path.name}")
                anim.seek(i)
                frame = anim.convert("RGBA")
                frames.append(frame.copy())
                ms = anim.info.get("duration", 170)
                try:
                    duration = int(ms) if ms is not None else 170
                except (TypeError, ValueError, OverflowError):
                    duration = 170
                delays.append(max(40, min(2000, duration)))
    return frames, delays


def frame_to_canvas(frame, scale):
    width, height = frame.size
    w = max(1, round(width * scale))
    h = max(1, round(height * scale))
    resized = frame.resize((w, h), Image.Resampling.LANCZOS)
    result = Image.new("RGBA", CELL, (0, 0, 0, 0))
    result.alpha_composite(resized, ((CELL[0] - w) // 2, CELL[1] - h))
    return result


def prepare_animation_frames(sources: dict):
    raw, delays, warnings = {}, {}, []
    all_sizes = []
    for action, paths in sources.items():
        frames, times = load_sources(paths)
        if frames and not any(f.getchannel("A").getbbox() for f in frames):
            warnings.append(f"{action}: all source frames are fully transparent")
            continue
        # Opaque corner pixels usually indicate a non-transparent background.
        if any(f.getpixel((0, 0))[3] == 255 and
               f.getpixel((f.width-1, f.height-1))[3] == 255 for f in frames):
            warnings.append(f"{action}: one or more frames may have an opaque background")
        raw[action] = frames
        delays[action] = times
        all_sizes.extend(f.size for f in frames)
    if "idle" not in raw:
        raise ValueError("Idle animation has no visible image data")
    max_w = max(w for w, _ in all_sizes)
    max_h = max(h for _, h in all_sizes)
    scale = min(CELL[0] / max_w, CELL[1] / max_h)
    converted = {
        name: [frame_to_canvas(frame, scale) for frame in frames]
        for name, frames in raw.items()
    }
    if len(set(all_sizes)) > 1:
        warnings.append("Animation canvases have differing sizes; review action transitions")
    return converted, delays, warnings


def convert_animation_folder(source: Path, output_root: Path, *,
                             folder: str | None = None, name: str | None = None,
                             profile: str | None = None, style: str = "chibi",
                             author: str | None = None, license_name: str | None = None,
                             source_url: str | None = None) -> Path:
    if style not in ("classic", "chibi"):
        raise ValueError("style must be classic or chibi")
    profile_info = get_profile(profile)
    if profile_info:
        style = "chibi"
    source = source.expanduser().resolve()
    sources, warnings = resolve_animations(source)
    raw_frames, delays, more_warnings = prepare_animation_frames(sources)
    warnings.extend(more_warnings)
    folder = folder or re.sub(r"[^A-Za-z0-9_-]+", "_", source.name)
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", folder):
        raise ValueError("Output folder must start with ASCII letter, max 40 characters")
    name = name or (profile_info or {}).get("name") or source.name
    output_root = output_root.expanduser().resolve()
    target = output_root / folder
    if target.exists():
        raise FileExistsError(f"Role already exists: {target}")
    shifted = {}
    if style == "chibi":
        if (profile_info or {}).get("ground_mode") == "floating":
            warnings.append("Floating profile: kept original vertical alignment")
        else:
            raw_frames, shifted, notes = normalize_grounded_frames(raw_frames)
            warnings.extend(notes)
    states = set(raw_frames)
    act_conf, pet_conf, info = build_configs(states, 1, str(name), str(author or "Unspecified"))
    if "sleep" in states:
        act_conf["sleep"] = {
            "images": "sleep", "act_num": 1,
            "frame_refresh": max(0.04, round(median(delays["sleep"]) / 1000, 3))
        }
        pet_conf["random_act"].append({
            "name": "睡觉", "act_list": ["sleep"], "act_prob": 0.09,
            "act_type": [1, 0]
        })
    for state, sequence in delays.items():
        if state in act_conf:
            act_conf[state]["frame_refresh"] = max(
                0.04, round(median(sequence) / 1000, 3)
            )
        if len(set(sequence)) > 1:
            warnings.append(f"{state}: variable source frame timing approximated by median")
    if style == "chibi":
        scale, clamped = suggested_scale(
            raw_frames["idle"], (profile_info or {}).get("target_height", 116)
        )
        pet_conf["scale"] = scale
        info["tages"]["Q版"] = "#F5C2D1"
        if clamped:
            warnings.append("Display scale clamped; check real desktop size")
    if profile_info:
        info["tages"][profile_info["franchise"]] = "#C7E3D1"
        info["intro"] = f"{name}的Q版桌宠配置；美术由使用者提供，不代表官方授权。"
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root, prefix=".dyberpet-frames-") as temp:
        staged = Path(temp) / folder
        (staged / "action").mkdir(parents=True)
        (staged / "info").mkdir()
        for state, images in raw_frames.items():
            for i, frame in enumerate(images):
                frame.save(staged / "action" / f"{state}_{i}.png")
        preview = create_contact_sheet(raw_frames, staged / "ANIMATION_PREVIEW.png")
        (staged / "pet_conf.json").write_text(json_text(pet_conf), encoding="utf-8")
        (staged / "act_conf.json").write_text(json_text(act_conf), encoding="utf-8")
        make_info_images(raw_frames["idle"][0], staged / "info", style=style)
        (staged / "info" / "info.json").write_text(json_text(info), encoding="utf-8")
        bubbles = make_bubble_config(profile)
        if bubbles:
            (staged / "note").mkdir()
            (staged / "note" / "bubble_conf.json").write_text(json_text(bubbles),
                                                             encoding="utf-8")
        report = {
            "format": "Local GIF/APNG/PNG animations",
            "profile": profile, "style": style, "warnings": warnings,
            "recommended_scale": pet_conf["scale"],
            "frame_counts": {k: len(v) for k, v in raw_frames.items()},
            "geometry": quality_metrics(raw_frames),
            "preview": preview,
            "aligned_frames_per_action": shifted,
            "source_files": {key: [p.name for p in value]
                             for key, value in sources.items()},
        }
        (staged / "IMPORT_REPORT.json").write_text(json_text(report), encoding="utf-8")
        provenance = (f"Character: {name}\nArt author: {author or 'Not supplied'}\n"
                      f"Art license: {license_name or 'Unverified; do not redistribute'}\n"
                      f"Source URL: {source_url or 'Not supplied'}\n"
                      f"Original local files: {', '.join(sorted(p.name for paths in sources.values() for p in paths))}\n"
                      "No redistribution permission is inferred from a profile name.\n")
        (staged / "ASSET_SOURCE.txt").write_text(provenance, encoding="utf-8")
        shutil.move(str(staged), str(target))
    return target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "res" / "role")
    parser.add_argument("--profile", choices=sorted(CHIBI_PROFILES))
    parser.add_argument("--style", choices=("classic", "chibi"), default="chibi")
    parser.add_argument("--folder")
    parser.add_argument("--name")
    parser.add_argument("--author")
    parser.add_argument("--license", dest="license_name")
    parser.add_argument("--source-url")
    args = parser.parse_args()
    try:
        target = convert_animation_folder(
            args.source, args.output_root, folder=args.folder, name=args.name,
            profile=args.profile, style=args.style, author=args.author,
            license_name=args.license_name, source_url=args.source_url,
        )
    except (ValueError, OSError, ImportError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print("Imported:", target)
    print("Restart DyberPet and open 系统 → 角色管理")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
