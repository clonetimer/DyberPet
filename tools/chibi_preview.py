"""Create a local-only visual QA contact sheet from the imported character frames.

The sheet belongs to the same private role directory as the user's artwork.
It is not copied into the source repository or uploaded anywhere.
"""
from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = ImageDraw = ImageFont = None

STATES = (
    "idle", "left_walk", "right_walk", "wave", "jump",
    "wait", "sleep", "review", "failed", "lookaround", "run",
)


def create_contact_sheet(frames: dict, output: Path) -> dict:
    if Image is None:
        raise ImportError("Pillow required for role preview")
    scale = 0.5
    width = 1024
    header = 34
    row_height = 124
    active = [(k, frames[k]) for k in STATES if frames.get(k)]
    if not active:
        raise ValueError("No visible actions available for preview")
    sheet = Image.new("RGB", (width, header + row_height * len(active)), "#f8fafc")
    draw = ImageDraw.Draw(sheet)
    draw.text((16, 10), "DyberPet local character preview (not an official asset)", fill="#253247")
    for row_index, (name, images) in enumerate(active):
        y = header + row_index * row_height
        draw.rectangle((0, y, width, y + row_height), outline="#d6dce7", width=1)
        draw.text((12, y + 52), name, fill="#344054")
        for i, frame in enumerate(images[:8]):
            thumb = frame.convert("RGBA")
            thumb.thumbnail((96, 104), Image.Resampling.LANCZOS)
            x = 118 + 113 * i + (96 - thumb.width) // 2
            pad = (104 - thumb.height) // 2
            tile = Image.new("RGBA", thumb.size, "#f8fafc")
            tile.alpha_composite(thumb)
            sheet.paste(tile.convert("RGB"), (x, y + 10 + pad))
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, "PNG", optimize=True)
    return {"preview_rows": [name for name, _ in active],
            "preview_path": output.name,
            "preview_size": list(sheet.size)}
