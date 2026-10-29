"""Read-only, strictly local Cubism model3.json inventory for one Doro preview.

No networking, modification, copying, conversion, screenshots or redistribution.
Passing this structural preflight NEVER asserts that artwork is Doro or approved.
"""
from __future__ import annotations

import json
from pathlib import Path, PurePosixPath

MAX_JSON_BYTES = 512 * 1024
MAX_RESOURCES = 200
MAX_ASSET_BYTES = 100 * 1024 * 1024


def _resource(root, relative):
    if not isinstance(relative, str) or "\\" in relative or "\x00" in relative:
        raise ValueError("Unsafe Cubism resource reference")
    rel = PurePosixPath(relative)
    if (not relative or rel.is_absolute() or len(rel.parts) > 8
            or any(p in ("", ".", "..") for p in rel.parts)
            or ":" in relative or relative.startswith("//")):
        raise ValueError("Cubism reference must stay below model directory")
    target = root.joinpath(*rel.parts)
    if (target.is_symlink() or not target.is_file()
            or target.stat().st_size > MAX_ASSET_BYTES
            or not target.resolve().is_relative_to(root.resolve())):
        raise ValueError("Missing/linked/oversized Cubism resource")
    return target


def inspect_local_live2d(model_json):
    """Validate model and every declared model asset, without opening art bytes."""
    model = Path(model_json).expanduser()
    if (model.is_symlink() or not model.is_file() or
            model.suffix.lower() != ".json" or
            not model.name.endswith(".model3.json") or
            model.stat().st_size > MAX_JSON_BYTES):
        raise ValueError("Select one actual local Cubism 3+ .model3.json")
    root = model.parent.resolve(strict=True)
    data = json.loads(model.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Cubism model configuration must be a JSON object")
    refs = data.get("FileReferences")
    if not isinstance(refs, dict):
        raise ValueError("No Cubism FileReferences found")
    assets = []
    moc = refs.get("Moc")
    if not isinstance(moc, str) or not moc.endswith(".moc3"):
        raise ValueError("Cubism moc3 file missing")
    assets.append(moc)
    textures = refs.get("Textures")
    if not isinstance(textures, list) or not textures:
        raise ValueError("Cubism texture list missing")
    if not all(isinstance(x, str) and x.lower().endswith(".png") for x in textures):
        raise ValueError("Invalid Cubism texture path")
    assets.extend(textures)
    for optional in ("Physics", "Pose", "UserData", "DisplayInfo"):
        if refs.get(optional) is not None:
            assets.append(refs[optional])
    expressions = refs.get("Expressions", [])
    motions = refs.get("Motions", {})
    if not isinstance(expressions, list) or not isinstance(motions, dict):
        raise ValueError("Invalid Cubism expressions or motions")
    expression_ids = []
    for row in expressions:
        if not isinstance(row, dict) or not isinstance(row.get("Name"), str):
            raise ValueError("Invalid Cubism expression item")
        expression_ids.append(row["Name"])
        assets.append(row.get("File"))
    motion_groups = {}
    for group, entries in motions.items():
        if not isinstance(group, str) or not isinstance(entries, list):
            raise ValueError("Invalid Cubism motion group")
        motion_groups[group] = len(entries)
        for row in entries:
            if not isinstance(row, dict):
                raise ValueError("Invalid Cubism motion")
            assets.append(row.get("File"))
            if row.get("Sound") is not None:
                assets.append(row["Sound"])
    if len(assets) > MAX_RESOURCES or len(set(assets)) != len(assets):
        raise ValueError("Excess or repeated references in model manifest")
    # The actual Dororong source used by MelanTech records its Idle.motion3
    # beside Doro.model3.json in a VTube Studio sidecar, not under Motions.
    # Only accept a same-directory sidecar pointing back to THIS model file.
    extra_motions = {}
    extra_expressions = {}
    vtube = root / (model.name.removesuffix(".model3.json") + ".vtube.json")
    if vtube.exists():
        if vtube.is_symlink() or not vtube.is_file() or vtube.stat().st_size > MAX_JSON_BYTES:
            raise ValueError("Invalid local VTube Studio idle metadata")
        vt = json.loads(vtube.read_text(encoding="utf-8"))
        if not isinstance(vt, dict) or not isinstance(vt.get("FileReferences"), dict):
            raise ValueError("Invalid local VTube Studio metadata")
        vr = vt["FileReferences"]
        if vr.get("Model") != model.name:
            raise ValueError("VTube Studio metadata refers to a different model")
        idle = vr.get("IdleAnimation")
        if idle:
            if not isinstance(idle, str) or not idle.endswith(".motion3.json"):
                raise ValueError("Invalid VTube Studio idle motion")
            _resource(root, idle)
            if "OwnerIdle" in motion_groups:
                raise ValueError("Reserved owner idle group already declared")
            extra_motions["OwnerIdle"] = [str((root / idle).resolve())]
            motion_groups["OwnerIdle"] = 1
            assets.append(idle)
        # Some author VTube Studio packages have additional EXP shortcuts
        # outside the core model3.json expression list. Load ONLY actual
        # same-folder files; missing shortcut files are not claimed as art.
        hotkeys = vt.get("Hotkeys", [])
        if not isinstance(hotkeys, list) or len(hotkeys) > 128:
            raise ValueError("Invalid local VTube Studio hotkey metadata")
        for entry in hotkeys:
            if not isinstance(entry, dict):
                raise ValueError("Invalid VTube Studio hotkey")
            if entry.get("Action") != "ToggleExpression":
                continue
            name, file = entry.get("Name"), entry.get("File")
            if (not isinstance(name, str) or not (1 <= len(name) <= 80)
                    or not isinstance(file, str)
                    or not file.lower().endswith(".exp3.json")):
                raise ValueError("Invalid VTube Studio expression shortcut")
            # Do not use the raw global keyboard shortcut, or create a
            # Windows-wide hook. Expose local expression via existing UI.
            if name in expression_ids or name in extra_expressions:
                continue
            if entry.get("Folder") not in ("", None):
                continue  # other folders aren't inside this model's owner tree
            # A referenced VTubeStudio shortcut can be optional/uninstalled.
            # Validate the path *even when absent* before checking existence.
            rel = PurePosixPath(file)
            if (rel.is_absolute() or ":" in file or "\\\\" in file
                    or "\x00" in file or len(rel.parts) != 1
                    or file in (".", "..")):
                raise ValueError("Unsafe VTube Studio expression shortcut")
            candidate = root / file
            if not candidate.exists():
                continue
            _resource(root, file)
            extra_expressions[name] = str(candidate.resolve())
            expression_ids.append(name)
            assets.append(file)
            if len(extra_expressions) > 32 or len(assets) > MAX_RESOURCES:
                raise ValueError("Too many local VTube Studio expressions")
    for item in assets:
        _resource(root, item)
    # Only report hit areas actually declared by the selected source model.
    # In the verified Dororong version these are HitAreaFace and HitAreaLegBack.
    raw_areas = data.get("HitAreas", [])
    if not isinstance(raw_areas, list) or len(raw_areas) > 64:
        raise ValueError("Invalid Cubism hit-area inventory")
    hit_areas = {}
    for row in raw_areas:
        if not isinstance(row, dict):
            raise ValueError("Invalid Cubism hit-area entry")
        name, drawable = row.get("Name"), row.get("Id")
        if (not isinstance(name, str) or not isinstance(drawable, str)
                or not (1 <= len(name) <= 80) or not (1 <= len(drawable) <= 80)
                or name in hit_areas):
            raise ValueError("Invalid/duplicate Cubism hit-area name or id")
        hit_areas[name] = drawable
    return {
        "model_json": str(model.resolve()),
        "model_type": "Cubism 3+",
        "resource_files_checked": len(assets),
        "expressions": expression_ids,
        "extra_expressions": extra_expressions,
        "hit_areas": hit_areas,
        "motion_groups": motion_groups,
        "extra_motions": extra_motions,
        "is_user_approved_doro_likeness": False,
        "independent_orthographic_threeview_complete": False,
        "redistribution_rights_verified": False,
        "model_asset_copied": False,
        "note": "Local structural read-only validation; no art identity/rights guarantees.",
    }
