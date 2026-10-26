#!/usr/bin/env python3
"""Read-only per-character original-art animation/interaction coverage ledger.

Demos are explicitly excluded. Neither structural frames nor action names
certify a character's art likeness or that an action is currently unlocked.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re

from PIL import Image, UnidentifiedImageError

from DyberPet.assistant.role_interactions import available_interactions

MAX_ACTION_CONFIG_BYTES = 512 * 1024
MAX_SPRITE_PIXELS = 4_000_000
MAX_SPRITE_SIDE = 4096


def _safe_installed_role(root, folder):
    # Never follow a received role name outside the selected installation root.
    # Whole-directory symlinks must be rejected, not just linked act_conf.json.
    if (not isinstance(folder, str) or not folder or len(folder) > 120 or
            folder in (".", "..") or
            any(part in folder for part in ("/", chr(92), chr(0)))):
        raise ValueError("Invalid installed role folder name")
    role = root / folder
    if role.is_symlink() or not role.is_dir():
        raise ValueError("Missing or linked installed role folder")
    return role


def _action_inventory(root, folder):
    """Only a safe installed first PNG frame can establish an action exists.

    A declared action in act_conf is NOT playable when its original files are
    missing or corrupted. This on-demand check decodes the first frame only:
    it does not prove full sequence completeness, unique animation, character
    identity or runtime unlock; those require deeper visual testing.
    """
    role = _safe_installed_role(root, folder)
    target = role / "act_conf.json"
    if (target.is_symlink() or not target.is_file() or
            target.stat().st_size > MAX_ACTION_CONFIG_BYTES):
        raise ValueError("Unsafe or missing action configuration")
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or len(data) > 128:
        raise ValueError("Action map must be a bounded JSON object")
    art = role / "action"
    if art.is_symlink() or not art.is_dir():
        raise ValueError("Role has no trusted action PNG directory")
    valid, unusable = [], []
    for name, entry in data.items():
        if not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_\u4e00-\u9fff-]{1,80}", name):
            unusable.append(str(name)[:80])
            continue
        prefix = entry.get("images") if isinstance(entry, dict) else None
        if not isinstance(prefix, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", prefix):
            unusable.append(name)
            continue
        original_frame = art / (prefix + "_0.png")
        if (original_frame.is_symlink() or not original_frame.is_file() or
                not 32 <= original_frame.stat().st_size <= 8 * 1024 * 1024):
            unusable.append(name)
            continue
        # An eight-byte PNG signature does not prove the sprite can decode:
        # reject forged headers, truncated IDAT streams and decompression bombs.
        try:
            with Image.open(original_frame) as image:
                if (image.format != "PNG" or image.width <= 0 or image.height <= 0 or
                        image.width > MAX_SPRITE_SIDE or image.height > MAX_SPRITE_SIDE or
                        image.width * image.height > MAX_SPRITE_PIXELS):
                    unusable.append(name)
                    continue
                image.load()
        except (OSError, ValueError, UnidentifiedImageError):
            unusable.append(name)
            continue
        valid.append(name)
    return valid, unusable


def _original_art_action_names(root, folder):
    valid, broken = _action_inventory(root, folder)
    if not valid:
        raise ValueError("No configured action has an installed, valid PNG first frame")
    return valid


def rank_installed_role_variants(role_root, folders):
    """Prioritize actually decodable and category-rich local artwork versions.

    This only selects a default for PREVIEW. It never activates a role, swaps
    a saved role, changes personal settings, or certifies sprite likeness.
    Unusable alternatives remain visible, with a reason for their placement.
    """
    root = Path(role_root).expanduser()
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Unsafe installed role root")
    if not isinstance(folders, (list, tuple)) or len(folders) > 40:
        raise ValueError("Expected at most 40 installed creator role folders")
    if any(not isinstance(x, str) or not x or len(x) > 120 or
           x in (".", "..") or "/" in x or chr(92) in x or chr(0) in x
           for x in folders):
        raise ValueError("Invalid installed role folder name")
    if len(set(folders)) != len(folders):
        raise ValueError("Repeated local creator-art folder")
    ranked = []
    for folder in folders:
        try:
            actions, broken = _action_inventory(root, folder)
            live = [x["id"] for x in available_interactions(actions)
                    if x["available"]]
            status = "first_frames_decodable" if actions else "no_playable_actions"
            ranked.append({
                "folder": folder, "status": status, "interaction_categories": live,
                "available_interaction_count": len(live),
                "action_name_count": len(actions),
                "broken_action_count": len(broken),
                "preview_only": True,
                "manual_appearance_review_required": True,
            })
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
            ranked.append({
                "folder": folder, "status": "invalid_installed_sprite",
                "interaction_categories": [], "available_interaction_count": 0,
                "action_name_count": 0, "broken_action_count": 0,
                "reason": str(exc)[:160], "preview_only": True,
                "manual_appearance_review_required": True,
            })
    return sorted(ranked, key=lambda x: (
        -int(x["status"] == "first_frames_decodable"),
        -x["available_interaction_count"], -x["action_name_count"],
        x["broken_action_count"], x["folder"].casefold()))


def interaction_coverage(role_root, *, genshin_snapshot=None, mascot_snapshot=None):
    root = Path(role_root).expanduser()
    if root.is_symlink():
        raise ValueError("Linked role directory refused")
    if genshin_snapshot is None:
        from tools.genshin_library import scan_genshin_library
        genshin = scan_genshin_library(root)
    else:
        genshin = genshin_snapshot
    if mascot_snapshot is None:
        from tools.mascot_library import scan_mascot_library
        mascots = scan_mascot_library(root)
    else:
        mascots = mascot_snapshot
    rows = []

    def record(profile, name, family, folders):
        actual_folders = [x["folder"] for x in folders]
        all_names = set()
        playable_folders = []
        variants = []
        errors = []
        for folder in actual_folders:
            try:
                names = _original_art_action_names(root, folder)
                all_names.update(names)
                playable_folders.append(folder)
                variant_actions = available_interactions(names)
                variants.append({
                    "folder": folder, "status": "has_decodable_first_frames",
                    "installed_action_names": sorted(names),
                    "available_category_ids": [a["id"] for a in variant_actions
                                               if a["available"]],
                    "requires_manual_visual_qa": True,
                })
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                reason = str(exc)[:160]
                errors.append({"folder": folder, "reason": reason})
                variants.append({
                    "folder": folder, "status": "unusable_config_or_first_frame",
                    "installed_action_names": [],
                    "available_category_ids": [],
                    "requires_manual_visual_qa": True, "error": reason,
                })
        interactions = available_interactions(sorted(all_names))
        playable_sets = [set(x["available_category_ids"]) for x in variants
                         if x["status"] == "has_decodable_first_frames"]
        common = (set.intersection(*playable_sets) if playable_sets else set())
        any_version = {x["id"] for x in interactions if x["available"]}
        ordered = [x["id"] for x in interactions]
        some_only = any_version - common
        rows.append({
            "id": profile, "name": name, "family": family,
            "imported_creator_role_count": len(actual_folders),
            "playable_creator_role_count": len(playable_folders),
            "playable_creator_role_folders": sorted(playable_folders),
            "creator_folders_with_broken_actions": len(actual_folders) - len(playable_folders),
            "original_creator_art_present": bool(playable_folders),
            "actual_action_names": sorted(all_names),
            "creator_role_variants": variants,
            "suggested_preview_variant": next((
                x["folder"] for x in sorted(
                    variants,
                    key=lambda v: (
                        -int(v["status"] == "has_decodable_first_frames"),
                        -len(v["available_category_ids"]),
                        -len(v["installed_action_names"]), v["folder"].casefold()))
                if x["status"] == "has_decodable_first_frames"), None),
            "suggestion_is_interaction_only_not_likeness": True,
            "action_categories_in_every_usable_version": [
                k for k in ordered if k in common],
            "action_categories_only_in_some_versions": [
                k for k in ordered if k in some_only],
            "largest_single_version_category_count": max(
                (len(s) for s in playable_sets), default=0),
            "action_categories_present_in_art": [x["id"] for x in interactions if x["available"]],
            "action_categories_missing_in_art": [x["id"] for x in interactions if not x["available"]],
            "runtime_unlock_qa_verified": False,
            "character_likeness_qa_verified": False,
            "per_role_interaction_qa_verified": False,
            "errors": errors,
        })

    for item in genshin["characters"]:
        personal = [x for x in item["installed_folders"] if not x.get("is_original_demo")]
        record(item["profile"], item["name"], "genshin", personal)
    for item in mascots["mascots"]:
        record("mascot_" + item["key"], item["display_name"], "mascot",
               item["imported_creator_art"])

    return {
        "scope": "local_read_only_original_art_only",
        "summary": {
            "template_total": len(rows),
            "roles_with_creator_art": sum(r["original_creator_art_present"] for r in rows),
            "roles_with_creator_folder_but_no_playable_actions": sum(
                bool(r["imported_creator_role_count"]) and
                not r["original_creator_art_present"] for r in rows),
            "broken_creator_asset_folder_count": sum(
                r["creator_folders_with_broken_actions"] for r in rows),
            "roles_with_at_least_one_interaction": sum(
                bool(r["action_categories_present_in_art"]) for r in rows),
            "roles_with_variant_dependent_actions": sum(
                len(r["creator_role_variants"]) > 1 and
                bool(r["action_categories_only_in_some_versions"]) for r in rows),
            "roles_where_union_exceeds_any_single_version": sum(
                len(r["action_categories_present_in_art"]) >
                r["largest_single_version_category_count"] for r in rows),
            "roles_missing_all_original_art_interactions": sum(
                not r["action_categories_present_in_art"] for r in rows),
            "roles_with_read_errors": sum(bool(r["errors"]) for r in rows),
            "human_likeness_approved": 0,
            "full_runtime_interaction_qa_approved": 0,
        },
        "characters": rows,
        "note": ("Original/demo characters NEVER count as creator-art coverage. "
                 "Categories in this report are a UNION of installed role variants; "
                 "each variant has a separate action list, so the union is NOT the "
                 "capability set of one selected desktop pet. "
                 "This report is a static asset action inventory, NOT proof of runtime "
                 "unlock, actual Qt playback, original identity, voice, or rights."),
    }



def inspect_selected_role_interactions(role_root, role_name, *,
                                       unlocked_actions=(), runtime_group_plan=None):
    """Inspect one active role without scanning all 125 character directories.

    A locally created receipt cannot prove official art provenance or likeness;
    imported and built-in demonstration assets are deliberately distinguished.
    """
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Unsafe installed role root")
    if (not isinstance(role_name, str) or not role_name or
            len(role_name) > 120 or role_name in (".", "..") or
            "/" in role_name or chr(92) in role_name or chr(0) in role_name):
        raise ValueError("Invalid role folder name")
    folder = root / role_name
    if folder.is_symlink():
        raise ValueError("Linked role folder refused")
    if not folder.is_dir():
        return {
            "role": role_name, "status": "not_installed",
            "on_disk_action_names": [], "configured_but_unplayable_actions": [],
            "runtime_action_group_mapping": {},
            "runtime_group_evidence_available": runtime_group_plan is not None,
            "installed_action_categories": [],
            "currently_unlocked_categories": [], "missing_categories": [
                x["id"] for x in available_interactions([])],
            "art_likeness_qa_passed": False, "physical_desktop_qa_passed": False,
        }
    for receipt in ("PERSONAL_IMPORT.json", "IMPORT_REPORT.json",
                    "BUILTIN_CHIBI_DEMO.json", "BUILTIN_MASCOT_DEMO.json"):
        if (folder / receipt).is_symlink():
            raise ValueError("Linked role receipt refused")
    demo = ((folder / "BUILTIN_CHIBI_DEMO.json").is_file() or
            (folder / "BUILTIN_MASCOT_DEMO.json").is_file())
    imported = ((folder / "PERSONAL_IMPORT.json").is_file() or
                (folder / "IMPORT_REPORT.json").is_file())
    status = ("builtin_demo_not_original_art" if demo else
              "imported_artist_claim_not_verified" if imported else
              "unverified_local_role")
    action_names, invalid = _action_inventory(root, role_name)
    on_disk = available_interactions(action_names)
    now_unlocked = set(x for x in unlocked_actions if isinstance(x, str))
    live = available_interactions(
        [name for name in action_names if name in now_unlocked])
    group_map = {}
    if runtime_group_plan is not None:
        if not isinstance(runtime_group_plan, list):
            raise ValueError("Invalid runtime action-group evidence")
        on_disk_categories = {x["id"] for x in on_disk if x["available"]}
        allowed_ids = {x["id"] for x in available_interactions([])}
        for item in runtime_group_plan:
            if not isinstance(item, dict) or not isinstance(item.get("id"), str):
                raise ValueError("Invalid runtime group entry")
            category, title = item["id"], item.get("action")
            if (category not in allowed_ids or category in group_map or
                    item.get("available") is not True or
                    not isinstance(title, str) or title not in now_unlocked or
                    category not in on_disk_categories):
                continue
            group_map[category] = title
        # Unlike legacy on-disk PNG hints, the active PetWidget dispatches
        # only installed+unlocked random-act GROUP NAMES. Never compare those
        # names directly with wave/jump image keys.
        live = [{"id": x["id"], "available": x["id"] in group_map}
                for x in available_interactions([])]
    return {
        "role": role_name,
        "status": status,
        "on_disk_action_names": sorted(action_names),
        "configured_but_unplayable_actions": sorted(invalid),
        "runtime_action_group_mapping": group_map,
        "runtime_group_evidence_available": runtime_group_plan is not None,
        "installed_action_categories": [x["id"] for x in on_disk if x["available"]],
        "currently_unlocked_categories": [x["id"] for x in live if x["available"]],
        "missing_categories": [x["id"] for x in on_disk if not x["available"]],
        "art_likeness_qa_passed": False,
        "physical_desktop_qa_passed": False,
        "note": ("Installed native action names and active PetWidget action-group "
                 "unlocks are distinct namespaces. Runtime group mapping, when supplied, "
                 "is used for playable categories; source art, real playback, "
                 "animation uniqueness and rights await visual review."),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1] / "res" / "role")
    ap.add_argument("--output", type=Path)
    args = ap.parse_args(argv)
    report = interaction_coverage(args.role_root)
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
