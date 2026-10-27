#!/usr/bin/env python3
"""Convert a local Codex Pets V1/V2 sprite atlas to a DyberPet role MOD.

Artwork must be supplied by the user; this tool does not fetch or redistribute
third-party assets. Requires Pillow (python -m pip install Pillow).
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tempfile
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    Image = None  # Pillow is optional until a local Codex atlas is imported.

if __package__:
    from .chibi_layout import normalize_grounded_frames, suggested_scale, quality_metrics
    from .chibi_profiles import CHIBI_PROFILES, get_profile, make_bubble_config
    from .chibi_preview import create_contact_sheet
else:
    from chibi_layout import normalize_grounded_frames, suggested_scale, quality_metrics
    from chibi_profiles import CHIBI_PROFILES, get_profile, make_bubble_config
    from chibi_preview import create_contact_sheet

CELL = (192, 208)
COLUMNS = 8
# name, row, maximum frame count, refresh seconds
STATES = (
    ("idle", 0, 6, 0.18),
    ("right_walk", 1, 8, 0.12),
    ("left_walk", 2, 8, 0.12),
    ("wave", 3, 4, 0.18),
    ("jump", 4, 5, 0.16),
    ("failed", 5, 8, 0.17),
    ("wait", 6, 6, 0.18),
    ("run", 7, 6, 0.14),
    ("review", 8, 6, 0.18),
)
PRESETS = {
    "guga": {"name": "咕嘎", "folder": "Guga", "author": "CIRCUS",
             "license": "Unverified; obtain creator permission before redistribution"},
    "doro": {"name": "Doro", "folder": "Doro", "author": "legeling",
             "license": "CC BY-NC 4.0 (specific doro--lingxiaotian artwork); underlying IP rights separate"},
}


def json_text(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def resolve_source(path: Path) -> tuple[Path, dict]:
    """Accept image file or a local Codex Pets directory with optional manifest."""
    path = path.expanduser().resolve()
    if path.is_file():
        if path.suffix.lower() not in (".webp", ".png"):
            raise ValueError("Source image must be .webp or .png")
        return path, {}
    if not path.is_dir():
        raise ValueError(f"Input not found: {path}")
    manifest_path = path / "pet.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    relative = manifest.get("spritesheetPath", "spritesheet.webp")
    if not isinstance(relative, str) or not relative:
        raise ValueError("Invalid spritesheetPath")
    atlas = (path / relative).resolve()
    if not atlas.is_relative_to(path) or not atlas.is_file():
        raise ValueError("Atlas is missing or outside the supplied folder")
    if atlas.suffix.lower() not in (".webp", ".png"):
        raise ValueError("Sprite atlas must be .webp or .png")
    return atlas, manifest


def read_atlas(atlas: Path, manifest: dict) -> tuple[Image.Image, int]:
    if Image is None:
        raise ImportError("This feature requires Pillow. Install with: py -m pip install Pillow")
    with Image.open(atlas) as original:
        size = original.size
        if size == (1536, 1872):
            version = 1
        elif size == (1536, 2288):
            version = 2
        else:
            raise ValueError(f"Unsupported atlas {size}; expected V1 1536x1872 or V2 1536x2288")
        declared = manifest.get("spriteVersionNumber")
        if declared is not None and declared != version:
            raise ValueError(f"Manifest says V{declared}, image dimensions indicate V{version}")
        return original.convert("RGBA"), version


def extract_frames(atlas: Image.Image, row: int, maximum: int) -> list[Image.Image]:
    frames = []
    for index in range(maximum):
        left = (index % COLUMNS) * CELL[0]
        top = (row + index // COLUMNS) * CELL[1]
        frame = atlas.crop((left, top, left + CELL[0], top + CELL[1]))
        if frame.getchannel("A").getbbox() is not None:
            frames.append(frame)
    return frames


def build_configs(available: set[str], version: int, name: str,
                  author: str) -> tuple[dict, dict, dict]:
    if "idle" not in available:
        raise ValueError("Required idle row contains no visible frames")

    def use(state: str) -> str:
        return state if state in available else "idle"

    act_conf = {}
    for state, _, _, refresh in STATES:
        if state not in available:
            continue
        action = {"images": state, "act_num": 1, "frame_refresh": refresh}
        if state in ("left_walk", "right_walk"):
            action.update({"need_move": True,
                           "direction": "left" if state == "left_walk" else "right",
                           "frame_move": 4.0})
        act_conf[state] = action
    if "lookaround" in available:
        act_conf["lookaround"] = {"images": "lookaround", "act_num": 1, "frame_refresh": 0.13}

    groups = [("站立", ["idle"], 1.0, [2, 0])]
    if "left_walk" in available or "right_walk" in available:
        walking = [a for a in ("left_walk", "right_walk") if a in available]
        groups.append(("左右散步" if len(walking) == 2 else "散步",
                       walking, 0.24, [3, 0]))
    for title, act, weight, state in (
        ("打招呼", "wave", 0.18, [2, 0]),
        ("蹦一蹦", "jump", 0.10, [3, 0]),
        ("休息", "wait", 0.12, [1, 0]),
        ("认真观察", "review", 0.07, [2, 0]),
        ("左顾右盼", "lookaround", 0.08, [2, 0]),
    ):
        if act in available:
            groups.append((title, [act], weight, state))
    random_act = [
        {"name": title, "act_list": refs, "act_prob": weight, "act_type": state}
        for title, refs, weight, state in groups
    ]
    random_act.append({
        "name": "onfloor", "act_list": [use("jump")],
        "act_prob": 0, "act_type": [0, 10000]
    })
    pet_conf = {
        "width": CELL[0], "height": CELL[1], "scale": 0.65, "interact_speed": 0.02,
        "default": "idle", "up": "idle", "down": "idle",
        "left": use("left_walk"), "right": use("right_walk"),
        "drag": use("jump"), "prefall": use("jump"),
        "fall": use("jump"), "on_floor": use("jump"),
        "focus": use("review"),
        "patpat": "idle",  # No author-defined pat action in Codex V1/V2; do not mislabel waving.
        "random_act": random_act,
    }
    info = {
        "coverImages": ["cover.png"], "pfp": "pfp.png", "petName": name,
        "tages": {"Codex图集转换": "#B9D7EA", "V" + str(version): "#D6D6F0"},
        "intro": f"由用户提供的 Codex Pets V{version} 图集转换，请遵守素材许可。",
        "author": {"name": author, "infos": "来源标注不构成再分发授权。"},
    }
    return act_conf, pet_conf, info


def make_personality_bubbles(preset: str | None) -> dict:
    """Original, text-only pet reactions. No third-party voice or dialogue assets."""
    lines = {
        "guga": {
            "pat_random_1": "咕嘎！听见你啦！",
            "pat_random_2": "今天也一起开心玩耍吧！",
            "pat_random_3": "咕嘎咕嘎~",
            "pat_frequent": "哎呀，戳得太快啦！",
            "feed_done": "好耶，收到了！",
            "pat_focus": "现在是专心时间，咕嘎会安静陪着你。",
        },
        "doro": {
            "pat_random_1": "Doro！",
            "pat_random_2": "Doro正在观察你的桌面。",
            "pat_random_3": "发现一颗小心心。",
            "pat_frequent": "Doro被戳晕了！",
            "feed_done": "Doro很满意！",
            "pat_focus": "Doro正在安静陪你工作。",
        },
    }.get(preset or "", {})
    return {key: {"icon": None, "message": message,
                  "start_audio": None, "end_audio": None}
            for key, message in lines.items()}


def make_info_images(idle: "Image.Image", info_directory: Path,
                     *, style: str = "classic") -> None:
    """Generate a real avatar and cover without modifying the source animation."""
    bbox = idle.getchannel("A").getbbox()
    if bbox is None:
        raise ValueError("Idle frame is transparent")
    portrait = idle.crop(bbox)
    # Q-style character head is typically prominent; give avatar extra room
    # for the face without ever altering the full-body animation sprites.
    if style == "chibi" and portrait.height >= 80:
        portrait = portrait.crop((0, 0, portrait.width,
                                  round(portrait.height * 0.87)))
    portrait.thumbnail((128, 128), Image.Resampling.LANCZOS)
    avatar = Image.new("RGBA", (160, 160), (0, 0, 0, 0))
    avatar.alpha_composite(portrait, ((160 - portrait.width) // 2,
                                      (160 - portrait.height) // 2))
    avatar.save(info_directory / "pfp.png")

    cover = Image.new("RGBA", (300, 169), (242, 244, 249, 255))
    cover.alpha_composite(portrait, ((300 - portrait.width) // 2,
                                     (169 - portrait.height) // 2))
    cover.convert("RGB").save(info_directory / "cover.png")


def convert(source: Path, dest_root: Path, *, preset: str | None = None,
            folder: str | None = None, name: str | None = None,
            author: str | None = None, license_name: str | None = None,
            source_url: str | None = None, style: str = "classic",
            profile: str | None = None,
            preserve_source_frames: bool = False) -> Path:
    """Preserve exact artist frame pixels for pinned sources, including layout.

    Ordinary user-selected chibi normalization stays available. Preserving a
    creator's art must not suppress persona/franchise metadata or dialogue.
    """
    if style not in ("classic", "chibi"):
        raise ValueError("Unknown style: " + str(style))
    profile_info = get_profile(profile)
    if preserve_source_frames:
        style = "classic"
    elif profile_info is not None:
        style = "chibi"
    atlas_path, manifest = resolve_source(source)
    preset_data = PRESETS.get(preset or "", {})
    requested_folder = folder
    folder = folder or preset_data.get("folder") or re.sub(
        r"[^A-Za-z0-9_-]+", "_", str(manifest.get("id", "CodexPet"))
    )
    if requested_folder is None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", folder):
        folder = "ChibiPet"
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", folder):
        raise ValueError("Output folder: ASCII letters/digits/_/-, begins with a letter, max 40")
    name = name or (profile_info or {}).get("name") or preset_data.get("name") or manifest.get("displayName") or folder
    # Character identities do not establish art attribution. Restrict the legacy
    # artist defaults to the precise source IDs they were originally based on.
    credit_ids = {
        "guga": frozenset(("guga--circus",)),
        "doro": frozenset(("doro--lingxiaotian", "doro--godxxy1229")),
    }
    source_matches = manifest.get("id") in credit_ids.get(preset, ())
    author = author or (preset_data.get("author") if source_matches else None) or "Unspecified"
    license_name = license_name or (preset_data.get("license") if source_matches else None) or "Unverified; do not redistribute"
    dest_root = dest_root.expanduser().resolve()
    output = dest_root / folder
    if output.exists():
        raise FileExistsError(f"Role already exists, refusing to overwrite: {output}")

    atlas, version = read_atlas(atlas_path, manifest)
    frames = {state: extract_frames(atlas, row, count) for state, row, count, _ in STATES}
    if version == 2:
        frames["lookaround"] = extract_frames(atlas, 9, 16)
    available = {state for state, items in frames.items() if items}
    warnings = []
    shifts = {}
    if style == "chibi" and "idle" in available:
        if (profile_info or {}).get("ground_mode") == "floating":
            warnings.append("Floating profile: grounded baseline correction intentionally skipped")
        else:
            frames, shifts, issues = normalize_grounded_frames(frames)
            warnings.extend(issues)
    for state, row, maximum, _ in STATES:
        populated = [i for i in range(maximum)
                     if atlas.crop((i * CELL[0], row * CELL[1],
                                    (i + 1) * CELL[0], (row + 1) * CELL[1]))
                     .getchannel("A").getbbox() is not None]
        if populated and populated != list(range(len(populated))):
            warnings.append(f"{state}: transparent gaps between animation frames")
    if version == 2 and len(frames["lookaround"]) < 16:
        warnings.append("V2: some of the sixteen look-direction frames are empty")
    act_conf, pet_conf, info = build_configs(available, version, str(name), str(author))
    if style == "chibi":
        target_height = (profile_info or {}).get("target_height", 116)
        actual_scale, scale_clamped = suggested_scale(frames["idle"], target_height)
        pet_conf["scale"] = actual_scale
        if scale_clamped:
            warnings.append("Chibi display scale clamped; check actual size in desktop GUI")
        info["tages"]["Q版"] = "#F5C2D1"
    if profile_info is not None:
        info["tages"][profile_info["franchise"]] = "#C7E3D1"
        info["intro"] = (
            (f"{profile_info['name']}的创作者原始桌宠动画；已保留原画帧布局。"
             if preserve_source_frames else
             f"{profile_info['name']}的Q版桌宠配置模板；图像由用户自行提供。")
            + "不代表该作品官方授权。"
        )

    dest_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".dyberpet-import-", dir=dest_root) as tmp:
        working = Path(tmp) / folder
        action = working / "action"
        action.mkdir(parents=True)
        for state in sorted(available):
            for idx, frame in enumerate(frames[state]):
                frame.save(action / f"{state}_{idx}.png", "PNG")
        # Verify ALL exported frames against the original decoded atlas cells,
        # not just the idle thumbnail. This protects artist pose proportions,
        # per-frame alignment and transparency from implicit transformations.
        if preserve_source_frames:
            for state, _, _, _ in STATES:
                for idx, raw in enumerate(extract_frames(
                        atlas, next(row for name, row, _, _ in STATES
                                    if name == state),
                        next(count for name, _, count, _ in STATES
                             if name == state))):
                    with Image.open(action / f"{state}_{idx}.png") as written:
                        saved = written.convert("RGBA")
                    if saved.size != raw.size or saved.tobytes() != raw.tobytes():
                        raise ValueError("Exported source pixels were changed: " + state)
            if version == 2:
                for idx, raw in enumerate(extract_frames(atlas, 9, 16)):
                    with Image.open(action / f"lookaround_{idx}.png") as written:
                        saved = written.convert("RGBA")
                    if saved.size != raw.size or saved.tobytes() != raw.tobytes():
                        raise ValueError("Exported V2 source pixels were changed")
        (working / "pet_conf.json").write_text(json_text(pet_conf), encoding="utf-8")
        (working / "act_conf.json").write_text(json_text(act_conf), encoding="utf-8")
        preview = create_contact_sheet(frames, working / "ANIMATION_PREVIEW.png")
        (working / "info").mkdir()
        make_info_images(frames["idle"][0], working / "info", style=style)
        (working / "info" / "info.json").write_text(json_text(info), encoding="utf-8")
        bubble_config = make_bubble_config(profile) if profile_info is not None else make_personality_bubbles(preset)
        if bubble_config:
            (working / "note").mkdir()
            (working / "note" / "bubble_conf.json").write_text(
                json_text(bubble_config), encoding="utf-8")
        (working / "IMPORT_REPORT.json").write_text(
            json_text({"format": f"Codex Pets V{version}", "style": style,
                       "profile": profile,
                       "preserve_source_frames": bool(preserve_source_frames),
                       "source_pixel_integrity_verified": bool(preserve_source_frames),
                       "mascot_preset": preset if source_matches else None,
                       "source_manifest_id": manifest.get("id"),
                       "mascot_identity_confirmed_by_filename": False,
                       "official_character_art_verified": False,
                       "recommended_scale": pet_conf["scale"],
                       "warnings": warnings,
                       "aligned_frames_per_action": shifts,
                       "geometry": quality_metrics(frames),
                       "preview": preview,
                       "frame_counts": {k: len(v) for k, v in frames.items()},
                       "actions": sorted(act_conf)}), encoding="utf-8")
        provenance = (
            f"Character: {name}\nAuthor/credit: {author}\n"
            f"Artwork license (user/preset): {license_name}\n"
            f"Original URL: {source_url or 'Not supplied'}\n"
            f"Input: {atlas_path.name}\nFormat: Codex Pets V{version}\n"
            f"Chibi configuration: {profile or 'none'}\n"
            f"Source manifest ID: {manifest.get('id', 'not supplied')}\n\n"
            "Conversion does not confer rights to original characters, drawings,"
            " voices or trademarks. Verify permission before publishing.\n"
        )
        (working / "ASSET_SOURCE.txt").write_text(provenance, encoding="utf-8")
        shutil.move(str(working), str(output))
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Local pet folder or spritesheet.webp/.png")
    parser.add_argument("--preset", choices=sorted(PRESETS))
    parser.add_argument("--output-root", type=Path,
                        default=Path(__file__).resolve().parents[1] / "res" / "role")
    parser.add_argument("--folder", help="ASCII folder for new character")
    parser.add_argument("--name", help="Display name")
    parser.add_argument("--author", help="Original asset author")
    parser.add_argument("--license", dest="license_name", help="Verified asset license")
    parser.add_argument("--source-url", help="Original asset URL for attribution")
    parser.add_argument("--style", choices=("classic", "chibi"), default="classic",
                        help="Chibi style enables conservative foot alignment and auto scaling")
    parser.add_argument("--profile", choices=sorted(CHIBI_PROFILES),
                        help="Optional Q-style character template (does not include artwork)")
    args = parser.parse_args()
    try:
        output = convert(
            args.source, args.output_root, preset=args.preset,
            folder=args.folder, name=args.name, author=args.author,
            license_name=args.license_name, source_url=args.source_url,
            style=args.style, profile=args.profile
        )
    except (ValueError, FileNotFoundError, FileExistsError, OSError, ImportError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")
    print(f"Imported DyberPet role: {output}")
    print("Restart DyberPet, then choose the character in 系统 → 角色管理.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
