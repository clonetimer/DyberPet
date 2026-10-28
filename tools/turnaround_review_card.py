"""Create a LOCAL visual evidence card for a Q-chibi three-view reference.

The contact sheet is not a rights grant or automatic likeness judgement. It is
generated only inside the caller's workspace and contains copies of source art,
so it must NOT be committed or distributed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

try:
    from .turnaround_gate import VIEWS, capture, TurnaroundError
except ImportError:
    from turnaround_gate import VIEWS, capture, TurnaroundError


CARD_WIDTH = 1050
CARD_HEIGHT = 560
PANEL_WIDTH = 314
TOP = 95
BOTTOM = 488


def _check_unchanged(sheet):
    if not isinstance(sheet, dict) or not sheet.get("views"):
        raise TurnaroundError("Attach front, side and back before producing review card")
    try:
        fresh = capture(
            *(sheet["views"][name]["path"] for name in VIEWS),
            reference_url=sheet["reference_url"], artist=sheet["artist"],
            variant=sheet["variant"])
        if fresh["views"] != sheet["views"]:
            raise TurnaroundError("Three-view source changed; reattach and re-review")
    except (KeyError, TypeError) as exc:
        raise TurnaroundError("Incomplete three-view source record") from exc
    return fresh


def render_review_card(candidate_id, sheet, output_dir):
    """Return path and hash for a non-public front/side/back contact sheet.

    Keep the *same scale* across three source images rather than stretching
    each to fill the panel; cropping differences become visible to a reviewer.
    """
    if not re.fullmatch(r"[a-z][a-z0-9_]{2,47}", candidate_id):
        raise TurnaroundError("Invalid candidate ID")
    fresh = _check_unchanged(sheet)
    identity = json.dumps(
        {"source": sheet["reference_url"], "artist": sheet["artist"],
         "variant": sheet["variant"],
         "sha256": [fresh["views"][v]["sha256"] for v in VIEWS]},
        ensure_ascii=False, sort_keys=True).encode("utf-8")
    ref_key = hashlib.sha256(identity).hexdigest()[:16]
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    out = output_dir / f"{candidate_id}-{ref_key}.png"
    if out.exists() or out.is_symlink():
        raise FileExistsError("Review card already exists; do not overwrite evidence: " + str(out))

    opened = []
    try:
        for name in VIEWS:
            with Image.open(fresh["views"][name]["path"]) as img:
                opened.append(ImageOps.exif_transpose(img).convert("RGBA"))
        # Same size factor for all views, with no silent distortion or trimming.
        scale = min(
            (PANEL_WIDTH - 36) / max(im.width for im in opened),
            (BOTTOM - TOP - 30) / max(im.height for im in opened),
            1.0,
        )
        canvas = Image.new("RGB", (CARD_WIDTH, CARD_HEIGHT), "#f5f6f9")
        draw = ImageDraw.Draw(canvas)
        draw.text((38, 18), "Q-CHIBI | THREE-VIEW HUMAN REVIEW", fill="#131c2d")
        draw.text((38, 44), "Candidate: " + candidate_id + "  |  Reference: " + ref_key,
                  fill="#334155")
        for i, (name, src) in enumerate(zip(VIEWS, opened)):
            left = 37 + i * 338
            draw.rounded_rectangle(
                (left, TOP - 8, left + PANEL_WIDTH, BOTTOM + 8),
                radius=10, fill="#ffffff", outline="#cbd5e1", width=2)
            draw.text((left + 12, TOP + 3), name.upper(), fill="#172554")
            # Checkerboard gives a visible reference for transparent edges.
            for y in range(TOP + 40, BOTTOM - 11, 20):
                for x in range(left + 12, left + PANEL_WIDTH - 10, 20):
                    if ((x - left) // 20 + (y - TOP) // 20) % 2 == 0:
                        draw.rectangle((x, y, x + 19, y + 19), fill="#edf0f4")
            w = max(1, round(src.width * scale))
            h = max(1, round(src.height * scale))
            resized = src.resize((w, h), Image.Resampling.LANCZOS)
            x = left + (PANEL_WIDTH - w) // 2
            y = BOTTOM - 12 - h
            canvas.paste(resized, (x, y), resized)
            draw.line((left + 8, BOTTOM - 10, left + PANEL_WIDTH - 8, BOTTOM - 10),
                      fill="#0f766e", width=2)
            draw.text((left + 12, BOTTOM + 14),
                      f"{src.width}x{src.height}  sha256:{fresh['views'][name]['sha256'][:12]}",
                      fill="#475569")
        draw.text((38, 541), "LOCAL ONLY | Verify original identity, costume, silhouette, alignment.",
                  fill="#9f1239")
        canvas.save(out, format="PNG")
    finally:
        for im in opened:
            im.close()
    return {
        "candidate": candidate_id,
        "review_card": str(out),
        "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
        "source_sha256": {v: fresh["views"][v]["sha256"] for v in VIEWS},
        "status": "awaiting human visual review",
    }
