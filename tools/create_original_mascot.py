#!/usr/bin/env python3
"""Generate a genuinely animated, original chibi desktop role from vector shapes.

No game model, scraped image, downloaded art, character voice or network call.
The PNG frames are generated locally in a staging folder and never overwrite
an existing role. Both CLI and the GUI call the same function.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = ImageDraw = None

if __package__:
    from .chibi_profiles import available_role_folder, make_bubble_config
    from .chibi_preview import create_contact_sheet
    from .import_codex_pet import build_configs, make_info_images
    from .install_native_role import validate_native_role
else:
    from chibi_profiles import available_role_folder, make_bubble_config
    from chibi_preview import create_contact_sheet
    from import_codex_pet import build_configs, make_info_images
    from install_native_role import validate_native_role

CELL = (192, 208)
UPSCALE = 3
ACTIONS = {
    "idle": 8, "left_walk": 6, "right_walk": 6,
    "wave": 8, "jump": 6, "wait": 6, "review": 6,
}
NAME = "星芽"
FOLDER = "StarSprout"


def _render_frame(state: str, index: int, total: int):
    """Original soft-shaded sprout mascot; every action has meaningful poses."""
    if Image is None:
        raise ImportError("Pillow required to draw original character")
    t = 2.0 * math.pi * index / total
    walking = state in ("left_walk", "right_walk")
    running = walking
    bob = round(2 * math.sin(t)) if state == "idle" else 0
    leap = max(0, round(29 * math.sin(math.pi * index / (total - 1)))) if state == "jump" else 0
    walk = round(7 * math.sin(t)) if walking else 0
    hand = round(18 * (1 + math.sin(t))) if state == "wave" else 0
    head_tilt = round(2 * math.sin(t)) if state == "review" else 0
    # Coordinates below are native 192x208; supersample for non-jagged edges.
    S = UPSCALE
    img = Image.new("RGBA", (CELL[0] * S, CELL[1] * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    def ellipse(box, fill, outline=None, width=1):
        d.ellipse(tuple(round(x * S) for x in box), fill=fill,
                  outline=outline, width=width * S)
    def poly(points, fill, outline=None):
        d.polygon([(round(x * S), round(y * S)) for x, y in points],
                  fill=fill)
        if outline:
            d.line([(round(x * S), round(y * S)) for x, y in points + [points[0]]],
                   fill=outline, width=2 * S, joint="curve")
    def curve(points, fill, width=2):
        d.line([(round(x * S), round(y * S)) for x, y in points],
               fill=fill, width=width * S, joint="curve")
    y = bob - leap
    x = 3 * math.sin(t) if walking else 0
    # Shadow is part of the original local sprite, not a game asset.
    if state != "jump":
        ellipse((63, 177, 131, 183), (93, 126, 145, 48))
    else:
        ellipse((73, 178, 121, 182), (93, 126, 145, 32))
    # Two rounded shoes, walking gait and airborne knees.
    step = walk if walking else 0
    ellipse((72 + x - step, 159 + y, 91 + x - step, 177 + y),
            (46, 83, 111, 255), (36, 64, 87, 255), 2)
    ellipse((104 + x + step, 159 + y, 124 + x + step, 177 + y),
            (46, 83, 111, 255), (36, 64, 87, 255), 2)
    # Scarf and rounded seed-like body.
    ellipse((60 + x, 107 + y, 133 + x, 164 + y),
            (74, 174, 165, 255), (34, 109, 117, 255), 2)
    ellipse((76 + x, 116 + y, 116 + x, 153 + y),
            (134, 226, 200, 255))
    poly([(62+x, 115+y), (94+x, 139+y), (128+x, 116+y),
          (120+x, 132+y), (97+x, 149+y), (74+x, 132+y)],
         (239, 174, 102, 255), (174, 99, 72, 255))
    # Left hand; raised right hand waves in an authored eight-frame cycle.
    ellipse((51+x, 116+y, 70+x, 133+y), (64, 166, 151, 255),
            (37, 105, 108, 255), 2)
    if state == "wave":
        ellipse((125+x, 122+y-hand, 144+x, 141+y-hand),
                (64, 166, 151, 255), (37, 105, 108, 255), 2)
    else:
        ellipse((125+x, 118+y, 142+x, 136+y),
                (64, 166, 151, 255), (37, 105, 108, 255), 2)
    # Oversized head and side cheeks are deliberately Q-proportioned.
    hx = x + head_tilt
    ellipse((50+hx, 56+y, 141+hx, 134+y),
            (115, 218, 203, 255), (32, 112, 122, 255), 2)
    ellipse((60+hx, 66+y, 133+hx, 126+y),
            (181, 247, 222, 255))
    # Two leaves and a curved stem make a recognisable original silhouette.
    curve([(95+hx, 61+y), (95+hx, 43+y), (100+hx, 36+y)],
          (40, 120, 91, 255), 3)
    ellipse((86+hx, 24+y, 102+hx, 45+y),
            (79, 173, 105, 255), (45, 126, 90, 255), 2)
    ellipse((98+hx, 28+y, 123+hx, 41+y),
            (103, 190, 117, 255), (45, 126, 90, 255), 2)
    # Unique per-frame expressions. Neither mouth nor eyes are external art.
    blink = state == "wait" or (state == "idle" and index == total - 1)
    if blink:
        curve([(71+hx, 93+y), (82+hx, 94+y)], (37, 78, 96, 255), 2)
        curve([(107+hx, 94+y), (118+hx, 93+y)], (37, 78, 96, 255), 2)
    else:
        ellipse((71+hx, 85+y, 83+hx, 102+y), (33, 75, 95, 255))
        ellipse((107+hx, 85+y, 119+hx, 102+y), (33, 75, 95, 255))
        ellipse((74+hx, 88+y, 78+hx, 92+y), (255, 255, 255, 255))
        ellipse((110+hx, 88+y, 114+hx, 92+y), (255, 255, 255, 255))
    ellipse((61+hx, 104+y, 73+hx, 110+y), (248, 155, 158, 170))
    ellipse((118+hx, 104+y, 130+hx, 110+y), (248, 155, 158, 170))
    if state == "jump" or state == "wave":
        ellipse((94+hx, 105+y, 100+hx, 113+y), (144, 75, 90, 255))
    else:
        curve([(92+hx, 107+y), (97+hx, 110+y), (102+hx, 107+y)],
              (111, 81, 96, 255), 2)
    # An actual page for the "review" action, rather than a copied idle.
    if state == "review":
        poly([(117+x, 127+y), (143+x, 122+y), (149+x, 148+y),
              (123+x, 153+y)], (252, 244, 221, 255), (126, 147, 139, 255))
        curve([(125+x, 136+y), (142+x, 132+y)],
              (107, 141, 159, 255), 2)
        curve([(128+x, 143+y), (144+x, 140+y)],
              (107, 141, 159, 255), 2)
    frame = img.resize(CELL, Image.Resampling.LANCZOS)
    return frame.transpose(Image.Transpose.FLIP_LEFT_RIGHT) if state == "left_walk" else frame


def create_original_mascot(output_root: Path, *, folder: str | None = None) -> Path:
    """Atomically create a playable local role, never overwriting other roles."""
    if Image is None:
        raise ImportError("Pillow is required: python -m pip install Pillow")
    output_root = Path(output_root).expanduser().resolve()
    explicit = folder is not None
    if explicit and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,39}", folder):
        raise ValueError("Role folder must be a safe ASCII name")
    role_folder = folder if explicit else available_role_folder(output_root, FOLDER)
    destination = output_root / role_folder
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("Existing character will not be overwritten: " + role_folder)
    output_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output_root, prefix=".original-role-") as td:
        staged = Path(td) / role_folder
        (staged / "action").mkdir(parents=True)
        (staged / "info").mkdir()
        frames = {}
        for state, count in ACTIONS.items():
            images = [_render_frame(state, i, count) for i in range(count)]
            frames[state] = images
            for i, art in enumerate(images):
                art.save(staged / "action" / f"{state}_{i}.png")
        act, pet, info = build_configs(set(ACTIONS), 1, NAME, "DyberPet original illustration")
        pet["scale"] = 0.84
        info["intro"] = "完全程序绘制的原创 Q 版桌宠；不含第三方角色资产或配音。"
        info["tages"] = {"原创 Q版": "#A7DFD2"}
        (staged / "pet_conf.json").write_text(
            json.dumps(pet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staged / "act_conf.json").write_text(
            json.dumps(act, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        make_info_images(frames["idle"][0], staged / "info", style="chibi")
        (staged / "info" / "info.json").write_text(
            json.dumps(info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (staged / "note").mkdir()
        (staged / "note" / "bubble_conf.json").write_text(
            json.dumps(make_bubble_config("chibi"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        preview = create_contact_sheet(frames, staged / "ANIMATION_PREVIEW.png")
        report = {
            "generated_from": "DyberPet first-party mathematical drawing code",
            "character": NAME, "third_party_art": False,
            "third_party_voice": False, "automated_runtime_qa": False,
            "manual_windows_qa_required": True,
            "per_action_frames": dict(ACTIONS), "preview": preview,
        }
        (staged / "ORIGINAL_GENERATION.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        validate_native_role(staged)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError("Character name became occupied during build")
        staged.rename(destination)
    return destination


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path,
                        default=Path("data") / "original_chibi_demo")
    parser.add_argument("--folder", help="Optional safe non-overwriting role folder")
    args = parser.parse_args(argv)
    try:
        output = create_original_mascot(args.output_root, folder=args.folder)
        print(json.dumps({"role": str(output), "generated": True,
                          "requires_manual_qa": True}, ensure_ascii=False))
        return 0
    except (OSError, ValueError, ImportError) as exc:
        parser.exit(1, "Original character generation blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
