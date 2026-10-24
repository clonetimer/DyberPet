"""Local contact sheet of REAL DyberPet artist PNG frames.

Never re-draws a character, downloads references, or marks likeness approved.
Picks frames from the native pet_conf/act_conf action graph, not arbitrary PNGs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, UnidentifiedImageError

ACTIONS = ("default", "left", "right", "patpat", "drag", "fall", "on_floor")
MAX_FRAME_BYTES = 8 * 1024 * 1024
MAX_PIXELS_SIDE = 4096
MAX_ROWS = 7


def _read_json(path):
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 256 * 1024:
        raise ValueError("Invalid native role configuration")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Invalid native role configuration object")
    return value


def _sample_frames(folder, prefix):
    if not isinstance(prefix, str) or not re.fullmatch(r"[\w-]{1,80}", prefix):
        raise ValueError("Invalid native sprite prefix")
    root = folder / "action"
    files = []
    for p in root.glob(prefix + "_*.png"):
        match = re.fullmatch(re.escape(prefix) + r"_(\d+)\.png", p.name)
        if match:
            if p.is_symlink() or not p.is_file() or p.stat().st_size > MAX_FRAME_BYTES:
                raise ValueError("Unsafe native sprite frame")
            files.append((int(match.group(1)), p))
    files.sort(key=lambda item: item[0])
    if not files:
        return []
    selected = sorted(set((0, len(files)//2, len(files)-1)))
    return [files[i][1] for i in selected]


def create_native_art_review(folder, *, output=None):
    """Build review-only thumbnails from unchanged artist frames; no approval."""
    role = Path(folder)
    if role.is_symlink() or not role.is_dir():
        raise ValueError("Invalid native role folder")
    pet = _read_json(role / "pet_conf.json")
    actions = _read_json(role / "act_conf.json")
    rows = []
    seen = set()
    for entry in ACTIONS:
        name = pet.get(entry)
        if not isinstance(name, str) or name in seen:
            continue
        config = actions.get(name)
        if not isinstance(config, dict):
            continue
        selected = _sample_frames(role, config.get("images"))
        if selected:
            rows.append((entry, selected))
            seen.add(name)
        if len(rows) >= MAX_ROWS:
            break
    if not rows or rows[0][0] != "default":
        raise ValueError("Native role must have authentic idle frames")
    width = 760
    row_h = 158
    sheet = Image.new("RGB", (width, 48 + row_h * len(rows)), "#f8fafc")
    draw = ImageDraw.Draw(sheet)
    draw.text((14, 12), "Original source sprites | Visual review pending", fill="#26364c")
    for idx, (label, frames) in enumerate(rows):
        y = 48 + row_h*idx
        draw.rectangle((0,y,width-1,y+row_h-1),outline="#cdd5df")
        draw.text((12,y+65),label,fill="#334155")
        for i, source in enumerate(frames):
            try:
                with Image.open(source) as orig:
                    if orig.width > MAX_PIXELS_SIDE or orig.height > MAX_PIXELS_SIDE:
                        raise ValueError("Original sprite dimensions exceed preview limits")
                    orig.load()
                    frame = orig.convert("RGBA")
            except (OSError, UnidentifiedImageError) as exc:
                raise ValueError("Unrenderable original sprite: " + source.name) from exc
            frame.thumbnail((185,142), Image.Resampling.LANCZOS)
            tile = Image.new("RGBA", (185,142), "#f8fafc")
            tile.alpha_composite(frame, ((185-frame.width)//2,(142-frame.height)//2))
            sheet.paste(tile.convert("RGB"),(125+208*i,y+8))
    out = Path(output) if output is not None else role / "ANIMATION_PREVIEW.png"
    if out.resolve().parent != role.resolve():
        raise ValueError("Preview file must stay in installed role directory")
    sheet.save(out,"PNG",optimize=True)
    return {"source_frames_unmodified":True,"likeness_manually_reviewed":False,
            "visual_review_file":out.name,"visual_review_actions":[k for k,_ in rows]}
