#!/usr/bin/env python3
"""Build 123 distinct, first-party *demo* Q sprites without external assets.

Not authentic Genshin character artwork, a licensed sprite collection or
speech synthesis. Each role is a usable, labelled procedurally drawn stand-in
with native DyberPet configs and animated poses, replaceable by personal art.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from .chibi_profiles import CHIBI_PROFILES, make_bubble_config
    from .genshin_roster import GENSHIN_ROSTER
    from .import_codex_pet import build_configs, make_info_images
    from .install_native_role import validate_native_role
except ImportError:
    from chibi_profiles import CHIBI_PROFILES, make_bubble_config
    from genshin_roster import GENSHIN_ROSTER
    from import_codex_pet import build_configs, make_info_images
    from install_native_role import validate_native_role

VERSION = 1
CELL = (192, 208)
ACTIONS = {
    "idle": 8, "left_walk": 6, "right_walk": 6,
    "wave": 8, "jump": 6, "wait": 6, "review": 6,
}
# Keep ACTIONS stable for the separate mascot generator's original base poses.
# Genshin demos have three more truly rendered generic animation sequences.
DEMO_ACTIONS = {**ACTIONS, "run": 8, "failed": 6, "lookaround": 6}
ELEMENT_COLORS = {
    "火": (226, 103, 81), "水": (91, 160, 224),
    "风": (91, 191, 157), "雷": (157, 110, 214),
    "草": (105, 175, 108), "冰": (130, 201, 215),
    "岩": (196, 154, 99), "多元素": (157, 157, 191),
}
HAIR_COLORS = {
    "金": (232, 185, 96), "白": (231, 230, 224),
    "银": (199, 207, 218), "蓝": (76, 126, 183),
    "紫": (154, 116, 177), "绿": (100, 173, 131),
    "粉": (224, 150, 177), "红": (190, 99, 103),
    "黑": (83, 94, 115), "棕": (155, 120, 95),
}
ROLE_PREFIX = "DemoG_"


def _rgb(base, factor=1.0):
    return tuple(max(0, min(255, round(v * factor))) for v in base) + (255,)


def folder_name(profile):
    if not re.fullmatch(r"genshin_[a-z0-9_]+", profile):
        raise ValueError("Invalid Genshin profile ID")
    tail = profile[len("genshin_"):]
    # Native role and GUI directories are limited to 40 ASCII characters.
    name = ROLE_PREFIX + tail
    if len(name) > 40:
        name = ROLE_PREFIX + tail[:19] + "_" + hashlib.sha256(
            profile.encode("utf-8")).hexdigest()[:8]
    return name


def _palette(profile):
    record = GENSHIN_ROSTER.get(profile.removeprefix("genshin_"), {})
    visual = " ".join(str(v) for v in record.get("visual_checks", []))
    digest = hashlib.sha256(profile.encode("utf-8")).digest()
    element = "多元素"
    # Most curated profiles have no structured element: use a varied abstract
    # palette, never invent a canonical game element.
    for candidate in ELEMENT_COLORS:
        if candidate + "元素" in visual:
            element = candidate
            break
    if element == "多元素":
        element = list(ELEMENT_COLORS)[digest[1] % (len(ELEMENT_COLORS) - 1)]
    hair = next((rgb for word, rgb in HAIR_COLORS.items() if word in visual),
                list(HAIR_COLORS.values())[digest[0] % len(HAIR_COLORS)])
    return record, visual, digest, ELEMENT_COLORS[element], hair


def _render(profile, action, index, total):
    record, visual, salt, outfit, hair = _palette(profile)
    t = 2 * math.pi * index / total
    walking = action in ("left_walk", "right_walk", "run")
    sx = ((6 * math.sin(t) + 3 * math.cos(t))
          if action == "run" else
          (5 if action == "right_walk" else -5) * math.sin(t)
          if walking else
          5 * math.sin(t) + 3 * math.cos(t)
          if action == "lookaround" else 0)
    step = round((12 if action == "run" else 7) * math.sin(t)) if walking else 0
    bob = round(3 * math.sin(t)) if action in ("idle", "wait", "review") else 0
    jump = round(25 * max(0, math.sin(math.pi * index / max(1,total-1)))) if action == "jump" else 0
    hand = round(23 * (1 + math.sin(t)) / 2) if action == "wave" else (round(8 * math.cos(t)) if action == "run" else 0)
    y = bob - jump
    x = round(sx)
    # All shapes are code-drawn; they are not copies of game art.
    im = Image.new("RGBA", CELL, (0,0,0,0))
    draw = ImageDraw.Draw(im)
    def e(bounds, color, outline=None, width=2):
        draw.ellipse(tuple(round(v) for v in bounds), fill=color,
                     outline=outline, width=width if outline else 1)
    def poly(points, color):
        draw.polygon([(round(px),round(py)) for px,py in points],fill=color)
    dark = _rgb(outfit, 0.54)
    mid = _rgb(outfit, 0.88)
    light = _rgb(outfit, 1.23)
    hair_light = _rgb(hair, 1.16)
    skin = (247, 214 - salt[4] % 13, 191 - salt[5] % 12, 255)
    e((64,183,134,188),(88,106,121,43))
    # Individually shaded boots, a short tunic and a geometric cloak.
    e((68+x-step,163+y,89+x-step,185+y),dark)
    e((105+x+step,163+y,126+x+step,185+y),dark)
    poly([(68+x,114+y),(123+x,114+y),(131+x,162+y),
          (61+x,162+y)],mid)
    poly([(61+x,120+y),(49+x,161+y),(67+x,166+y),(82+x,122+y)],
         _rgb(outfit,0.68))
    poly([(114+x,121+y),(145+x,166+y),(124+x,162+y)],dark)
    poly([(84+x,119+y),(108+x,119+y),(116+x,153+y),
          (76+x,153+y)],light)
    # Little chest jewel changes shape and hue by stable hash.
    accent = (241, 201 + salt[6] % 30, 116 + salt[7] % 40, 255)
    poly([(96+x,128+y),(102+x,134+y),(96+x,143+y),(90+x,134+y)],accent)
    e((48+x,121+y,66+x,141+y),skin,dark)
    e((126+x,120+y-hand,146+x,140+y-hand),skin,dark)
    # Hair behind head: length, ponytail placement and head accessories vary.
    length = 6 + (salt[8] % 4)*7
    e((53+x,63+y,140+x,128+y+length),hair,dark)
    hair_style = salt[9] % 5
    if hair_style == 0:
        e((40+x,84+y,63+x,136+y),hair,dark)
        e((131+x,84+y,154+x,136+y),hair,dark)
    elif hair_style == 1:
        e((46+x,67+y,67+x,115+y),hair,dark)
        e((123+x,70+y,146+x,119+y),hair,dark)
    elif hair_style == 2:
        e((41+x,98+y,67+x,149+y),hair,dark)
    elif hair_style == 3:
        poly([(130+x,84+y),(158+x,65+y),(149+x,141+y)],hair)
    else:
        e((50+x,90+y,143+x,122+y),hair,dark)
    # Rounded face, very large chibi eyes and a simple mouth.
    e((58+x,71+y,135+x,136+y),skin,_rgb(hair,0.70))
    poly([(61+x,75+y),(68+x,60+y),(103+x,70+y),
          (119+x,61+y),(134+x,84+y),(121+x,88+y),
          (103+x,79+y),(79+x,85+y)],hair_light)
    blink = action=="wait" or (action=="idle" and index==total-1)
    ink=(47,56,78,255)
    if blink:
        draw.arc((70+x,99+y,84+x,105+y),0,180,fill=ink,width=2)
        draw.arc((106+x,99+y,120+x,105+y),0,180,fill=ink,width=2)
    else:
        e((72+x,95+y,84+x,109+y),ink)
        e((106+x,95+y,118+x,109+y),ink)
        e((75+x,97+y,78+x,100+y),(255,255,255,255))
        e((109+x,97+y,112+x,100+y),(255,255,255,255))
    e((64+x,112+y,77+x,118+y),(255,143,155,90))
    e((115+x,112+y,128+x,118+y),(255,143,155,90))
    if action in ("jump","wave"):
        e((95+x,113+y,101+x,121+y),(157,88,105,255))
    else:
        draw.arc((90+x,111+y,105+x,121+y),0,180,fill=(137,83,102,255),width=2)
    # A distinctive first-party accessory determined by the profile hash,
    # never directly traced from external artwork.
    hat_style = salt[10] % 5
    if "猫耳" in visual or hat_style==0:
        poly([(62+x,73+y),(57+x,43+y),(84+x,64+y)],hair)
        poly([(112+x,64+y),(137+x,43+y),(131+x,79+y)],hair)
    elif "帽" in visual or hat_style==1:
        e((45+x,59+y,146+x,80+y),dark)
        e((65+x,39+y,129+x,75+y),mid)
    elif "角" in visual or hat_style==2:
        poly([(66+x,73+y),(60+x,36+y),(80+x,64+y)],accent)
        poly([(112+x,65+y),(132+x,36+y),(127+x,78+y)],accent)
    elif hat_style==3:
        e((79+x,46+y,112+x,70+y),accent)
    else:
        draw.arc((65+x,44+y,129+x,70+y),178,355,fill=accent,width=4)
    if action=="review":
        poly([(122+x,128+y),(145+x,122+y),(150+x,154+y),
              (122+x,159+y)],(255,241,218,255))
        draw.line((128+x,137+y,143+x,134+y),fill=ink,width=2)
        draw.line((128+x,145+y,144+x,142+y),fill=ink,width=2)
    # Real first-party poses rather than JSON-only aliases to idle.
    if action == "failed":
        # A 6-frame collapse -> tumble -> return. This is a visual cartoon
        # sequence and is not evidence of a complete physics fall recovery.
        angles = (0, 20, 58, 77, 31, 0)
        im = im.rotate(angles[index % len(angles)], Image.Resampling.BICUBIC,
                       expand=False, fillcolor=(0, 0, 0, 0))
        marks = ImageDraw.Draw(im)
        if index in (2, 3, 4):
            marks.arc((135, 29, 169, 57), 192, 315,
                      fill=(239, 177, 89, 240), width=3)
        return im
    if action == "run":
        marks = ImageDraw.Draw(im)
        for n in range(3):
            ymark = 134 + n * 13 + round(4 * math.sin(t))
            marks.line((13, ymark, 43, ymark - 2),
                       fill=(136, 165, 175, 210), width=3)
    elif action == "lookaround":
        marks = ImageDraw.Draw(im)
        angle = 185 + index * 16
        marks.arc((71, 26, 129, 54), angle, angle + 49,
                  fill=(242, 194, 109, 220), width=3)
    return im


def generate_demo_roles(root, profiles=None):
    """Generate only missing demos atomically; never overwrite installed roles."""
    root = Path(root).expanduser().resolve()
    all_ids = sorted(k for k in CHIBI_PROFILES if k.startswith("genshin_"))
    if len(all_ids) != 123:
        raise ValueError("Expected dated 7.1 roster of 123 templates; got " + str(len(all_ids)))
    keys = all_ids if profiles is None else sorted(set(profiles))
    if not set(keys).issubset(all_ids):
        raise ValueError("Only Genshin profile IDs are supported")
    if len({folder_name(k) for k in keys}) != len(keys):
        raise ValueError("Generated demo folder IDs collide")
    root.mkdir(parents=True,exist_ok=True)
    created, already_present = [], []
    for key in keys:
        name = CHIBI_PROFILES[key]["name"]
        folder = folder_name(key)
        target = root / folder
        if target.exists() or target.is_symlink():
            # Never overwrite users' customized or modified characters.
            already_present.append(folder)
            continue
        with tempfile.TemporaryDirectory(prefix=".builtin-demo-",dir=root) as td:
            staged=Path(td) / folder
            (staged/"action").mkdir(parents=True)
            (staged/"info").mkdir()
            frames={}
            for action,n in DEMO_ACTIONS.items():
                frames[action]=[]
                for i in range(n):
                    frame=_render(key,action,i,n)
                    frame.save(staged/"action"/f"{action}_{i}.png",optimize=False,
                               compress_level=3)
                    frames[action].append(frame)
            config,pet,info=build_configs(set(DEMO_ACTIONS),1,"〔演示〕"+name,
                                         "DyberPet first-party drawing code")
            pet["scale"]=0.84
            # Native actions, not extra independent UI logic.
            pet["fall"] = "failed"
            pet["on_floor"] = "jump"
            pet["random_act"].append({
                "name": "原创演示小跑", "act_list": ["run"],
                "act_prob": 0.05, "act_type": [3, 0],
            })
            info["intro"]=("原创几何风格 Q 版演示形象，仅与人物配置关联；"
                           "不是原神官方角色美术、模型、立绘或配音。"
                           "可通过导入本地美术替换。")
            info["tages"]={"原创演示": "#87B5CD", "非官方人物美术":"#DDD1F0"}
            (staged/"pet_conf.json").write_text(
                json.dumps(pet,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            (staged/"act_conf.json").write_text(
                json.dumps(config,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            make_info_images(frames["idle"][0],staged/"info",style="chibi")
            (staged/"info"/"info.json").write_text(
                json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            (staged/"note").mkdir()
            (staged/"note"/"bubble_conf.json").write_text(
                json.dumps(make_bubble_config(key),ensure_ascii=False,indent=2)+"\n",
                encoding="utf-8")
            receipt={
                "generator":"DyberPet-first-party-abstract-chibi-v1",
                "profile":key,"name":name,
                "original_illustration":True,
                "official_character_art":False,"character_likeness_verified":False,
                "game_voice_included":False,"actual_character_rights_verified":False,
                "needs_real_desktop_qa":True,"per_action_frames":dict(DEMO_ACTIONS),
            }
            (staged/"BUILTIN_CHIBI_DEMO.json").write_text(
                json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",
                encoding="utf-8")
            validate_native_role(staged)
            if target.exists() or target.is_symlink():
                already_present.append(folder)
                continue
            staged.rename(target)
        created.append(folder)
    return {
        "profile_count":len(all_ids),
        "selected":len(keys),"created":len(created),
        "existing_preserved":len(already_present),
        "official_game_art_included":False,
        "rendered_frames_per_profile":sum(DEMO_ACTIONS.values()),
        "generated_dirs":created,
    }


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-root",type=Path,default=Path("res/role"))
    ap.add_argument("--only",help="Comma-separated Genshin template IDs for selective test")
    args=ap.parse_args(argv)
    chosen=args.only.split(",") if args.only else None
    report=generate_demo_roles(args.output_root,chosen)
    print(json.dumps(report,ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
