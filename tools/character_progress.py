#!/usr/bin/env python3
"""Read-only, evidence-based cross-family character readiness report.

A working original demonstration skin must never be conflated with licensed
or creator-faithful art, voiced personas, physical desktop QA or permissions.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

try:
    from .genshin_library import scan_genshin_library
    from .mascot_library import scan_mascot_library
except ImportError:
    from genshin_library import scan_genshin_library
    from mascot_library import scan_mascot_library


def character_progress(role_root):
    """Return a detached, JSON-compatible capability ledger; no file writes."""
    genshin = scan_genshin_library(role_root)
    mascots = scan_mascot_library(role_root)
    entries = []
    for item in genshin["characters"]:
        folders = item["installed_folders"]
        demos = [f for f in folders if f["is_original_demo"]]
        personal = [f for f in folders if not f["is_original_demo"]]
        entries.append({
            "id": item["profile"], "name": item["name"], "family": "genshin",
            "template_available": True,
            "native_original_demo": bool(demos),
            "personal_art_structurally_installed": bool(personal),
            "native_preview_ready": bool(folders),
            "demo_actions": max((x["actions"] for x in demos), default=0),
            "demo_frames": max((x["frames"] for x in demos), default=0),
            "creator_art_and_likeness_verified": False,
            "character_voice_verified": False,
            "physical_desktop_qa_verified": False,
        })
    for item in mascots["mascots"]:
        demos = item["original_demos"]
        personal = item["imported_creator_art"]
        entries.append({
            "id": "mascot_" + item["key"], "name": item["display_name"],
            "family": "mascot",
            "template_available": True,
            "native_original_demo": bool(demos),
            "personal_art_structurally_installed": bool(personal),
            "native_preview_ready": bool(demos or personal),
            "demo_actions": max((x["actions"] for x in demos), default=0),
            "demo_frames": max((x["frames"] for x in demos), default=0),
            "creator_art_and_likeness_verified": False,
            "character_voice_verified": False,
            "physical_desktop_qa_verified": False,
        })
    return {
        "scope": "local_only_read_only",
        "summary": {
            "template_total": len(entries),
            "genshin_templates": len(genshin["characters"]),
            "mascot_templates": len(mascots["mascots"]),
            "original_demo_ready": sum(x["native_original_demo"] for x in entries),
            "personal_art_structurally_installed": sum(
                x["personal_art_structurally_installed"] for x in entries),
            "native_preview_ready": sum(x["native_preview_ready"] for x in entries),
            "missing_native_animation": sum(
                not x["native_preview_ready"] for x in entries),
            "genshin_demo_actions": sorted(set(
                x["demo_actions"] for x in entries
                if x["family"] == "genshin" and x["native_original_demo"])),
            "mascot_demo_actions": sorted(set(
                x["demo_actions"] for x in entries
                if x["family"] == "mascot" and x["native_original_demo"])),
            "physical_qa_completed": 0,
            "voice_fidelity_qa_completed": 0,
            "art_likeness_qa_completed": 0,
            "invalid_local_folders": (
                genshin["summary"]["invalid_folder_count"] +
                mascots["summary"]["invalid_count"]),
        },
        "characters": entries,
        "notes": [
            "Native PNG playback is different from distinctive character animations.",
            "Original procedural Q demos are not original game/creator artwork.",
            "Structural import receipts do not verify source licensing or likeness.",
            "No voice fidelity or long-running physical desktop acceptance is claimed.",
        ],
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", type=Path,
                    default=Path(__file__).resolve().parents[1] / "res" / "role")
    args = ap.parse_args(argv)
    print(json.dumps(character_progress(args.role_root), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
