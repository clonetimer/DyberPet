#!/usr/bin/env python3
"""Two self-contained *original* mascot demos for offline DyberPet packages.

Guga-style: a turquoise penguin-hoodie walker with pronounced waddle.
Doro-style: a pink-tufted white quadruped with independent four-leg gait.
These are NOT sprites, voices or faithful reproductions of the creators' pets.
Users can import their own genuine Codex/artist releases separately.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

try:
    from .generate_builtin_chibi_demos import ACTIONS, CELL
    from .import_codex_pet import build_configs, make_info_images
    from .chibi_profiles import make_bubble_config
    from .install_native_role import validate_native_role
except ImportError:
    from generate_builtin_chibi_demos import ACTIONS, CELL
    from import_codex_pet import build_configs, make_info_images
    from chibi_profiles import make_bubble_config
    from install_native_role import validate_native_role

MASCOTS = {
    "guga": {
        "folder": "DemoMascotGuga",
        "name": "〔演示〕咕嘎风企鹅",
        "description": "原创企鹅连帽风 Q 版人物：左右摇摆走路、挥手、跳跃和眨眼。并非 CIRCUS 创作的咕嘎原始素材。",
    },
    "doro": {
        "folder": "DemoMascotDoro",
        "name": "〔演示〕Doro风四足团子",
        "description": "原创白色四足小团子和粉色毛发的组合：独立四肢步态、甩尾及夸张表情。并非 Doro／桃乐丝的原始二创素材。",
    },
}


def _guga(action: str, i: int, count: int):
    t = 2 * math.pi * i / count
    walks = action in ("left_walk", "right_walk")
    direction = -1 if action == "left_walk" else 1
    # Combine sine and cosine so six walk frames remain visually distinct.
    shift = round(5 * math.sin(t) + 3 * math.cos(t)) * direction if walks else 0
    steps = round(8 * math.sin(t)) if walks else 0
    tilt = round(4 * math.sin(t)) if walks or action == "wave" else 0
    hop = round(28 * math.sin(math.pi*i/max(1,count-1))) if action == "jump" else 0
    wave = round(25*(1+math.sin(t))/2) if action == "wave" else 0
    bob = round(2*math.sin(t)) if action == "idle" else 0
    y = bob - hop
    im=Image.new("RGBA",CELL,(0,0,0,0)); d=ImageDraw.Draw(im)
    def ell(box, fill, line=None, w=2):
        d.ellipse(tuple(round(v) for v in box), fill=fill,outline=line,width=w)
    shadow=(70,89,114,38)
    ell((58,187,143,193),shadow)
    # Original teal penguin-hoodie. No traced external image.
    ell((72+shift-steps,160+y,98+shift-steps,185+y),
        (237,151,86,255),(151,99,73,255))
    ell((103+shift+steps,160+y,131+shift+steps,185+y),
        (237,151,86,255),(151,99,73,255))
    ell((56+shift,89+y,146+shift,172+y),
        (47,142,163,255),(28,85,117,255),3)
    ell((69+shift,112+y,132+shift,163+y),
        (251,248,230,255))
    # Arms are stubby flippers; raised flipper on greet.
    ell((46+shift,117+y,70+shift,146+y),
        (40,125,155,255),(20,85,113,255))
    ell((135+shift,115+y-wave,155+shift,144+y-wave),
        (40,125,155,255),(20,85,113,255))
    # Oversized hood with separate penguin eyes and tiny beak.
    ell((41+shift+tilt,48+y,155+shift+tilt,142+y),
        (40,140,168,255),(27,82,118,255),3)
    ell((57+shift+tilt,66+y,138+shift+tilt,134+y),
        (251,231,207,255))
    ell((62+shift+tilt,27+y,82+shift+tilt,64+y),
        (45,143,165,255),(21,86,114,255))
    ell((116+shift+tilt,27+y,136+shift+tilt,64+y),
        (45,143,165,255),(21,86,114,255))
    ell((76+shift+tilt,58+y,90+shift+tilt,71+y),
        (13,38,71,255))
    ell((111+shift+tilt,58+y,125+shift+tilt,71+y),
        (13,38,71,255))
    d.polygon([(98+shift+tilt,67+y),(89+shift+tilt,74+y),
               (105+shift+tilt,79+y)],fill=(248,183,107,255))
    blink = action == "wait" or (action == "idle" and i==count-1)
    if blink:
        d.line((74+shift+tilt,106+y,88+shift+tilt,106+y),
               fill=(64,67,91,255),width=3)
        d.line((110+shift+tilt,106+y,125+shift+tilt,106+y),
               fill=(64,67,91,255),width=3)
    else:
        ell((77+shift+tilt,95+y,89+shift+tilt,112+y),
            (54,62,89,255))
        ell((110+shift+tilt,95+y,122+shift+tilt,112+y),
            (54,62,89,255))
    if action in ("wave","jump"):
        ell((95+shift+tilt,118+y,103+shift+tilt,124+y),
            (159,90,105,255))
    else:
        d.arc((93+shift+tilt,116+y,105+shift+tilt,125+y),
              0,180,fill=(147,96,93,255),width=2)
    if action == "review":
        d.rounded_rectangle((121+shift,133+y,155+shift,161+y),
                            3,fill=(253,239,218,255))
        d.line((127+shift,142+y,148+shift,142+y),
               fill=(76,108,131,255),width=2)
    return im


def _doro(action: str, i: int, count: int):
    t=2*math.pi*i/count
    walking=action in ("right_walk","left_walk")
    direction=-1 if action == "left_walk" else 1
    stride=round(10*math.sin(t)) if walking else 0
    stride2=round(10*math.sin(t+math.pi)) if walking else 0
    dx=round(5*math.cos(t))*direction if walking else 0
    jump=round(32*math.sin(math.pi*i/max(1,count-1))) if action=="jump" else 0
    sway=round(4*math.sin(t)) if action in ("wave","idle") else 0
    y= -jump + (round(2*math.sin(t)) if action=="idle" else 0)
    im=Image.new("RGBA",CELL,(0,0,0,0));d=ImageDraw.Draw(im)
    def ell(box, color, outline=None, w=2):
        d.ellipse(tuple(round(v) for v in box),fill=color,outline=outline,width=w)
    white=(246,247,249,255)
    outline=(140,143,175,255)
    pink=(240,158,194,255)
    ell((48,184,149,192),(116,94,132,37))
    # Four independently animated paws are placed BEHIND the horizontal torso.
    # This is specifically NOT the upright humanoid Genshin renderer.
    ell((60+dx+stride,138+y,83+dx+stride,178+y),white,outline,2)
    ell((87+dx+stride2,143+y,108+dx+stride2,180+y),white,outline,2)
    ell((112+dx+stride2,138+y,137+dx+stride2,178+y),white,outline,2)
    ell((134+dx+stride,143+y,153+dx+stride,181+y),white,outline,2)
    # Curly tail with visible wave frames.
    tw=round(9*math.sin(t))
    d.arc((132+dx,107+y+tw,176+dx,156+y+tw),265,90,
          fill=(218,216,230,255),width=7)
    # Pear-shaped four-legged body, large front head.
    ell((53+dx,103+y,153+dx,164+y),white,outline,3)
    ell((36+dx,71+y+sway,133+dx,143+y+sway),white,outline,3)
    # Original bright-pink mop tuft, no traced Dorothy/Dororong sprites.
    d.polygon([(45+dx,85+y+sway),(45+dx,51+y),
               (66+dx,60+y),(73+dx,33+y),
               (91+dx,53+y),(110+dx,38+y),
               (122+dx,79+y)],fill=pink)
    ell((47+dx,63+y,111+dx,91+y),pink)
    # Two floppy pink hair tips on each side.
    ell((25+dx,83+y+sway,51+dx,117+y+sway),pink)
    ell((115+dx,84+y+sway,140+dx,120+y+sway),pink)
    # Famous-like wide-eyed visual language is redrawn as basic geometry.
    eye=(91,60,130,255)
    blink=action=="wait" or (action=="idle" and i==count-1)
    if blink:
        d.arc((52+dx,96+y,80+dx,112+y),5,160,fill=eye,width=3)
        d.arc((91+dx,96+y,121+dx,112+y),5,160,fill=eye,width=3)
    else:
        ell((55+dx,92+y,75+dx,116+y),eye)
        ell((98+dx,92+y,118+dx,116+y),eye)
        ell((60+dx,96+y,64+dx,102+y),(250,250,255,255))
        ell((102+dx,96+y,106+dx,102+y),(250,250,255,255))
    if action in ("wave","jump"):
        ell((82+dx,119+y,95+dx,130+y),(165,113,152,255))
    else:
        d.arc((78+dx,117+y,99+dx,130+y),5,175,
              fill=(166,125,156,255),width=2)
    # In wave action one front paw lifts while all four remain distinctly visible.
    if action=="wave":
        lift=round(21*(1+math.sin(t))/2)
        ell((59+dx,142+y-lift,84+dx,170+y-lift),white,outline,2)
    if action=="review":
        ell((121+dx,133+y,156+dx,170+y),
            (255,230,168,255))
        d.line((129+dx,148+y,145+dx,148+y),
               fill=(172,124,106,255),width=2)
    if action=="left_walk":
        return im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return im


def generate_mascot_demos(root: Path, keys=None):
    """Write only missing mascot demos to user-writable or package role root."""
    root=Path(root).expanduser().resolve()
    selected=sorted(set(MASCOTS if keys is None else keys))
    if not set(selected)<=set(MASCOTS):
        raise ValueError("Supported mascots are guga and doro")
    root.mkdir(parents=True,exist_ok=True)
    new,kept=[],[]
    for key in selected:
        meta=MASCOTS[key]
        dest=root/meta["folder"]
        if dest.exists() or dest.is_symlink():
            kept.append(meta["folder"])
            continue
        with tempfile.TemporaryDirectory(dir=root,prefix=".mascot-demo-") as td:
            folder=Path(td)/meta["folder"]
            (folder/"action").mkdir(parents=True)
            (folder/"info").mkdir()
            rendered={}
            for action,n in ACTIONS.items():
                rendered[action]=[]
                for idx in range(n):
                    image=(_guga if key=="guga" else _doro)(action,idx,n)
                    image.save(folder/"action"/f"{action}_{idx}.png")
                    rendered[action].append(image)
            actions,pet,info=build_configs(set(ACTIONS),1,meta["name"],
                                          "DyberPet original geometric illustration")
            pet["scale"]=0.82
            info["intro"]=meta["description"]+" 个人可另行导入作者原素材，不包括角色原声。"
            info["tages"]={"原创演示":"#9CD0E1","非原设素材":"#D8BDD2"}
            for file,data in (("act_conf.json",actions),("pet_conf.json",pet)):
                (folder/file).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n",
                                         encoding="utf-8")
            make_info_images(rendered["idle"][0],folder/"info",style="chibi")
            (folder/"info"/"info.json").write_text(
                json.dumps(info,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            (folder/"note").mkdir()
            (folder/"note"/"bubble_conf.json").write_text(
                json.dumps(make_bubble_config("chibi"),ensure_ascii=False,indent=2)+"\n",
                encoding="utf-8")
            (folder/"BUILTIN_MASCOT_DEMO.json").write_text(
                json.dumps({
                    "generator":"DyberPet-first-party-mascot-chibi-v1",
                    "mascot":key,
                    "external_artist_sprite_included":False,
                    "faithful_original_art_verified":False,
                    "game_voice_included":False,
                    "author_rights_verified":False,
                    "original_geometry":True,
                    "visible_four_leg_walk":key=="doro",
                    "animation_actions":dict(ACTIONS),
                },ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            validation=validate_native_role(folder)
            if validation["actions"]!=len(ACTIONS) or validation["images"]!=sum(ACTIONS.values()):
                raise ValueError("Generated mascot has incomplete animation")
            if dest.exists() or dest.is_symlink():
                kept.append(meta["folder"])
                continue
            folder.rename(dest)
        new.append(meta["folder"])
    return {
        "mascots":list(selected),"created":len(new),
        "preserved_existing":len(kept),
        "frames_per_mascot":sum(ACTIONS.values()),
        "original_art_only":True,
        "actual_character_likeness_verified":False,
    }


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output-root",type=Path,default=Path("res/role"))
    ap.add_argument("--only",choices=sorted(MASCOTS))
    args=ap.parse_args(argv)
    print(json.dumps(generate_mascot_demos(
        args.output_root,[args.only] if args.only else None),ensure_ascii=False))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
