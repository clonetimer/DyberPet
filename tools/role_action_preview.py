"""Strict, read-only preview plan for DyberPet's real native action frames.

This is deliberately independent from Qt, disk writes or third-party installs.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

try:
    from .install_native_role import inspect_native_folder
except ImportError:
    from install_native_role import inspect_native_folder

PREVIEW_ORDER=("idle","left_walk","right_walk","wave","jump","run","wait",
               "review","failed","sleep","lookaround")
MAX_PREVIEW_FRAMES=120
MAX_FRAME_BYTES=8*1024*1024
MAX_PIXEL_SIDE=2048
PNG_SIG=b"\x89PNG\r\n\x1a\n"


def _png_dimensions(path):
    with path.open("rb") as f:
        data=f.read(24)
    if len(data)!=24 or not data.startswith(PNG_SIG) or data[12:16]!=b"IHDR":
        raise ValueError("Preview image is not a valid PNG header")
    w=int.from_bytes(data[16:20],"big")
    h=int.from_bytes(data[20:24],"big")
    if not (1<=w<=MAX_PIXEL_SIDE and 1<=h<=MAX_PIXEL_SIDE):
        raise ValueError("Preview PNG exceeds supported dimensions")
    return (w,h)


def action_preview_plan(role_dir):
    """Return bounded native action paths/intervals after integrity checks."""
    role=Path(role_dir).expanduser()
    inspect_native_folder(role)
    actions=json.loads((role/"act_conf.json").read_text(encoding="utf-8"))
    if not isinstance(actions,dict):
        raise ValueError("Invalid native action dictionary")
    keys=sorted(actions,key=lambda k: (PREVIEW_ORDER.index(k)
                if k in PREVIEW_ORDER else len(PREVIEW_ORDER),k))
    output=[]
    for name in keys:
        entry=actions[name]
        prefix=entry["images"]
        candidates=(role/"action").glob(prefix+"_*.png")
        valid=[]
        for p in candidates:
            m=re.fullmatch(re.escape(prefix)+r"_(\d+)\.png",p.name)
            if m:
                valid.append((int(m.group(1)),p))
        valid.sort(key=lambda x:x[0])
        if len(valid)>MAX_PREVIEW_FRAMES:
            raise ValueError("Action has too many frames for safe live preview")
        frames=[]
        for _,p in valid:
            if p.is_symlink() or not p.is_file() or p.stat().st_size>MAX_FRAME_BYTES:
                raise ValueError("Invalid or oversized frame in preview")
            _png_dimensions(p)
            frames.append(p)
        if not frames:
            raise ValueError("Action has no numbered PNGs: "+name)
        interval_ms=max(16,min(10000,round(float(entry.get("frame_refresh",0.5))*1000)))
        output.append({"name":name,"frames":frames,"interval_ms":interval_ms,
                       "frame_count":len(frames)})
    return {"folder":role.name,"actions":output,"total_frames":sum(
        x["frame_count"] for x in output),"read_only":True}
