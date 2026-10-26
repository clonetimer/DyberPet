"""R5 lossless-visible-pixel original-sprite canvas stabilization.

Some authentic artist Shimeji sequences vary PNG canvas dimensions between
frames, causing desktop size/origin jumps. This transform NEVER stretches,
repaints, duplicates, or invents any character pixels. It pads with transparent
pixels on a single fixed canvas, centered horizontally / bottom aligned for
feet. Every byte of every original PNG and source receipt is preserved
alongside the derived DISPLAY frames for inspection.

A stabilized result is still a candidate; it is not human-approved Q likeness.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

from tools.artist_animation_audit import (
    _read_config, _frames_for_action, audit_native_character,
    MAX_PIXELS, MAX_TOTAL_FRAMES,
)
from tools.character_interaction_coverage import _safe_installed_role

MAX_TOTAL_SOURCE_BYTES = 512 * 1024 * 1024
DERIVED_ROLE_NAMES = {
    "SourceShimejiAyaka": "SourceCanvasR5Ayaka",
    "SourceShimejiVenti": "SourceCanvasR5Venti",
}


def create_lossless_canvas_candidate(role_root, folder, *, output_folder=None):
    root = Path(role_root).expanduser()
    original = _safe_installed_role(root, folder)
    new_name = output_folder or DERIVED_ROLE_NAMES.get(folder)
    if new_name is None or new_name not in DERIVED_ROLE_NAMES.values():
        raise ValueError("Only two independently probed original Shimeji sources allowed")
    if DERIVED_ROLE_NAMES.get(folder) != new_name:
        raise ValueError("Derived variant must preserve exact original source identity")
    target = root / new_name
    if target.exists() or target.is_symlink():
        raise ValueError("Never replace an existing creator role")
    pet = _read_config(original / "pet_conf.json")
    config = _read_config(original / "act_conf.json")
    if not config or pet.get("default") not in config:
        raise ValueError("Source lacks native original-action defaults")
    receipts = original / "PERSONAL_IMPORT.json"
    if receipts.is_symlink() or not receipts.is_file():
        raise ValueError("Missing original author provenance and identity")
    receipt = json.loads(receipts.read_text(encoding="utf-8"))
    target_profile = {"SourceShimejiAyaka": "genshin_ayaka",
                      "SourceShimejiVenti": "genshin_venti"}[folder]
    if receipt.get("selected_profile") != target_profile:
        raise ValueError("Source portrait does not match requested game character")
    unique_frames = {}
    for action in config.values():
        if not isinstance(action, dict):
            raise ValueError("Malformed author animation groups")
        paths = _frames_for_action(original, action.get("images"))
        if not paths:
            raise ValueError("Author action lacks frames")
        for p in paths:
            unique_frames[p.name] = p
    if not unique_frames or len(unique_frames) > MAX_TOTAL_FRAMES:
        raise ValueError("Source contains too many native original frames")
    width = height = source_bytes = 0
    for source in unique_frames.values():
        source_bytes += source.stat().st_size
        if source_bytes > MAX_TOTAL_SOURCE_BYTES:
            raise ValueError("Original author sprites exceed safe memory budget")
        with Image.open(source) as img:
            if img.format != "PNG" or img.width <= 0 or img.height <= 0:
                raise ValueError("Unsupported original author image")
            img.load()
            width = max(width, img.width)
            height = max(height, img.height)
    if width * height > MAX_PIXELS or width > 4096 or height > 4096:
        raise ValueError("Original artwork requires excessive canvas dimensions")

    # Build beside source in a stage directory. Never mutate or rename the
    # author's original art; only a new derived role is written.
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(prefix=".r5-canvas-", dir=str(root)) as tmp:
        stage = Path(tmp) / new_name
        action_out = stage / "action"
        backup = stage / "source_original"
        action_out.mkdir(parents=True)
        (backup / "action").mkdir(parents=True)
        trace = {}
        for name, source in sorted(unique_frames.items()):
            raw = source.read_bytes()
            (backup / "action" / name).write_bytes(raw)
            with Image.open(source) as img:
                rgba = img.convert("RGBA")
                x, y = (width - rgba.width) // 2, height - rgba.height
                padded = Image.new("RGBA", (width, height), (0, 0, 0, 0))
                padded.paste(rgba, (x, y))
                # This exact pixel check proves the transformation added
                # transparent canvas only, with NO stretched character pixels.
                if padded.crop((x, y, x+rgba.width, y+rgba.height)).tobytes() != rgba.tobytes():
                    raise ValueError("Original painter pixels would change")
                padded.save(action_out / name, format="PNG")
                trace[name] = {
                    "original_png_sha256": hashlib.sha256(raw).hexdigest(),
                    "original_dimensions": [rgba.width, rgba.height],
                    "derived_dimensions": [width, height],
                    "transparent_padding_left": x,
                    "transparent_padding_above": y,
                    "visible_pixels_unchanged": True,
                }
        for original_config in ("pet_conf.json", "act_conf.json", "PERSONAL_IMPORT.json"):
            shutil.copy2(original / original_config, backup / original_config)
        pet["width"], pet["height"] = width, height
        (stage / "pet_conf.json").write_text(
            json.dumps(pet, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        (stage / "act_conf.json").write_text(
            json.dumps(config, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        derivative = dict(receipt)
        derivative.update({
            "derived_canvas_only": True,
            "derived_from_source_role": folder,
            "original_author_images_preserved_under": "source_original/action",
            "visual_content_pixels_unchanged": True,
            "original_likeness_human_approved": False,
            "motion_semantics_human_approved": False,
            "rights_for_derived_distribution_verified": False,
        })
        (stage / "PERSONAL_IMPORT.json").write_text(
            json.dumps(derivative, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        (stage / "ORIGINAL_CANVAS_PADDING_R5.json").write_text(
            json.dumps({
                "schema": 1, "profile": target_profile,
                "scope": "transparent_canvas_only_source_pixels_unchanged",
                "original_role": folder,
                "derived_role": new_name,
                "canvas": [width, height],
                "frames": trace,
                "human_q_likeness_approved": False,
                "author_rights_verified": False,
            }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        audit = audit_native_character(stage)
        if not audit["summary"]["animation_structure_passed"]:
            raise ValueError("Transparent-only candidate still fails native action QA: " +
                             ",".join(audit["summary"]["issue_categories"]))
        if target.exists() or target.is_symlink():
            raise ValueError("A creator source variant was installed concurrently")
        stage.rename(target)
    return {
        "profile": target_profile,
        "folder": new_name,
        "derived_canvas_dimensions": [width, height],
        "source_png_count_preserved": len(trace),
        "only_transparent_canvas_added": True,
        "full_native_png_structure_passed": True,
        "q_likeness_manually_verified": False,
        "source_original_bytes_preserved": True,
    }
