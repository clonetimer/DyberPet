"""Q版三视图 × 原生交互证据：不将二维左右动作冒充真实背视图。

Read-only; uses precisely the native role's original PNG frames. Three-view
manifest is optional; when absent, front/side are animation *candidates*,
back is strictly unavailable. Neither screenshots nor review claims are
exported or redistributed. No image generation/mirroring/warping is done.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath

try:
    from .role_action_preview import action_preview_plan, _png_dimensions
except ImportError:
    from role_action_preview import action_preview_plan, _png_dimensions

VIEW_NAMES = ("front", "side", "back")
INTERACTIONS = (
    ("default", "正面待机"),
    ("left", "向左移动"),
    ("right", "向右移动"),
    ("patpat", "摸头反馈"),
    ("drag", "拖拽反馈"),
    ("on_floor", "休息 / 落地"),
    ("fall", "下落"),
)
MANIFEST = "Q_CHIBI_3VIEW.json"
MAX_JSON_BYTES = 128 * 1024
MAX_FRAME_BYTES = 8 * 1024 * 1024


def _load_json(file):
    if file.is_symlink() or not file.is_file() or file.stat().st_size > MAX_JSON_BYTES:
        raise ValueError("Missing or unsafe Q版角色动作/三视图 JSON")
    data = json.loads(file.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Native role JSON must be an object")
    return data


def _bound(key, pet, actions):
    name = pet.get(key)
    if isinstance(name, str):
        return name if name in actions else None
    # Older source roles allow choices per interaction type.
    if key == "patpat" and isinstance(name, dict):
        return next((entry for entry in name.values()
                     if isinstance(entry, str) and entry in actions), None)
    return None


def _frame_from_declared(root, entry):
    if not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
        raise ValueError("Three-view source requires explicit PNG file paths")
    rel = PurePosixPath(entry["file"])
    if (rel.is_absolute() or len(rel.parts) != 2
            or any(p in (".", "..", "") for p in rel.parts)
            or rel.parts[0] not in ("action", "threeview")
            or rel.suffix.lower() != ".png"):
        raise ValueError("Unsafe or ambiguous three-view reference path")
    file = root.joinpath(*rel.parts)
    if (file.is_symlink() or not file.is_file() or
            file.stat().st_size > MAX_FRAME_BYTES
            or file.resolve().parent != (root / rel.parts[0]).resolve()
            and len(rel.parts) == 2):
        raise ValueError("Invalid referenced source PNG")
    _png_dimensions(file)
    expected = entry.get("sha256")
    if not isinstance(expected, str) or len(expected) != 64:
        raise ValueError("Three-view PNG SHA256 must be pinned")
    actual = hashlib.sha256(file.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError("Three-view original PNG changed; do not reuse review")
    return file, actual


def _confirmed_threeview(root):
    file = root / MANIFEST
    if not file.exists() and not file.is_symlink():
        return None
    data = _load_json(file)
    if (data.get("schema_version") != 1
            or not isinstance(data.get("source_url"), str)
            or not data["source_url"].startswith("https://")
            or not isinstance(data.get("artist"), str) or not data["artist"].strip()
            or not isinstance(data.get("variant"), str) or not data["variant"].strip()
            or not isinstance(data.get("views"), dict)
            or set(data["views"]) != set(VIEW_NAMES)):
        raise ValueError("Three-view requires one identified artist, variant and 3 original views")
    verified = {}
    for name in VIEW_NAMES:
        file, digest = _frame_from_declared(root, data["views"][name])
        verified[name] = {"file": file, "sha256": digest,
                          "evidence": "同源三视图候选，尚须人工核对原设",
                          "explicit": True}
    if len({v["sha256"] for v in verified.values()}) != 3:
        raise ValueError("Front, side and back may not be the same/mirrored file")
    return verified


def native_threeview_interactions(role_directory):
    """Inspect a role already packaged with the application (no downloads).

    Does not claim a 2D walk cycle shows a true orthographic side/back view.
    Returns real author PNG paths only, for visual comparison and interactions.
    """
    root = Path(role_directory).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Missing native character directory")
    animation = action_preview_plan(root)
    by_name = {x["name"]: x for x in animation["actions"]}
    pet = _load_json(root / "pet_conf.json")
    configured = _load_json(root / "act_conf.json")
    interactions = {}
    for key, label in INTERACTIONS:
        actual = _bound(key, pet, by_name)
        if actual is not None:
            interactions[key] = {"label": label, "action": actual,
                                 "frames": by_name[actual]["frames"],
                                 "interval_ms": by_name[actual]["interval_ms"]}
    front_name = _bound("default", pet, by_name)
    if not front_name:
        raise ValueError("Real default animation missing")
    front = by_name[front_name]["frames"][0]
    front_prefix = configured[front_name]["images"]
    side = None
    for direction in ("left", "right"):
        move = _bound(direction, pet, by_name)
        if move and configured[move]["images"] != front_prefix:
            side = by_name[move]["frames"][0]
            break
    views = {
        "front": {"file": front,
                  "evidence": "待机源帧（未确认是正交正面）",
                  "explicit": False},
        "side": {"file": side,
                 "evidence": ("左右移动源帧（未确认是正交侧面）" if side else
                              "缺少独立侧视/移动帧"),
                 "explicit": False},
        "back": {"file": None, "evidence": "缺少独立背面原画，不允许镜像或凭空补图",
                 "explicit": False},
    }
    explicitly_sourced = _confirmed_threeview(root)
    if explicitly_sourced:
        views = explicitly_sourced

    widths, heights = [], []
    for view in views.values():
        if view["file"] is not None:
            width, height = _png_dimensions(view["file"])
            view["dimensions"] = (width, height)
            widths.append(width)
            heights.append(height)
    # Also bound the interaction previews to the same image scale, including
    # dragging/petting poses that are taller than the still turnaround art.
    for entry in interactions.values():
        w, h = _png_dimensions(entry["frames"][0])
        widths.append(w)
        heights.append(h)
    if not widths:
        raise ValueError("No Q版三视图 source frames")
    return {
        "role": root.name,
        "views": views,
        "interactions": interactions,
        "actions": animation["actions"],
        "reference_dimensions": (max(widths), max(heights)),
        "source_threeview_complete": bool(explicitly_sourced),
        "threeview_human_approved": False,
        "visual_likeness_verified": False,
        "read_only": True,
        "warning": "同一造型的正交正/侧/背三视图必须人工对照；动作源帧不能替代缺失的背面。",
    }
