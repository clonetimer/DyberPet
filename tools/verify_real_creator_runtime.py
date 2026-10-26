#!/usr/bin/env python3
"""Live source-byte-to-desktop-action-group verification; no art redistribution.

Downloads TWO real publisher ZIPs with registry-pinned full-archive SHA-256,
converts them in a disposable temp directory, confirms decoded original sprite
frames, and tests that native motion keys map to *PetWidget menu group names*.
Neither this test nor the publisher's SHA certifies original-game appearance.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from tools.install_pinned_codexpetdb import (
    get_verified_package, install_pinned_codexpetdb)
from tools.install_native_role import validate_native_role
from DyberPet.assistant.native_groups import runtime_group_interactions


def validate_real_creator(key, root):
    zipped = root / (key + ".zip")
    data, record = get_verified_package(key)
    zipped.write_bytes(data)
    installed = install_pinned_codexpetdb(
        key, root / "roles", confirmed=True, archive=zipped)
    pet = json.loads((installed / "pet_conf.json").read_text("utf-8"))
    native = json.loads((installed / "act_conf.json").read_text("utf-8"))
    receipt = json.loads((installed / "PERSONAL_IMPORT.json").read_text("utf-8"))
    audit = json.loads((installed / "ACTION_PIXEL_AUDIT.json").read_text("utf-8"))
    checked = validate_native_role(installed)
    if (receipt.get("selected_profile") != record["profile"] or
            receipt.get("source_zip_sha256_verified") != record["sha256"] or
            checked["images"] < 30 or checked["actions"] < 5 or
            not audit["summary"]["animation_structure_passed"]):
        raise ValueError("Original provider ZIP or fully decoded native sprite QA failed")
    groups = pet.get("random_act", [])
    if not isinstance(groups, list):
        raise ValueError("Native pet missing random action groups")
    # This is a test-only hypothetical FV=unlocked state; never write game
    # settings or override a real user's affection-level action locks.
    all_unlocked = {
        group["name"]: {"act_type": "random_act", "unlocked": True}
        for group in groups if isinstance(group, dict) and
        isinstance(group.get("name"), str)}
    ready = runtime_group_interactions(all_unlocked, groups, native.keys())
    mappings = {x["id"]: x["action"] for x in ready if x["available"]}
    if (mappings.get("greet") != "打招呼" or
            mappings.get("walk") not in ("左右散步", "散步") or
            mappings.get("jump") != "蹦一蹦"):
        raise ValueError("Real sprite actions cannot execute through native PetWidget groups")
    if any(value in native for value in mappings.values()):
        raise ValueError("Dispatched an image key rather than a real menu action group")
    locked = runtime_group_interactions(
        {name: {**entry, "unlocked": False}
         for name, entry in all_unlocked.items()}, groups, native.keys())
    if any(x["available"] for x in locked):
        raise ValueError("Affection-locked groups appeared as playable")
    missing_wave = runtime_group_interactions(
        all_unlocked, groups, set(native) - {"wave"})
    if any(x["id"] == "greet" and x["available"] for x in missing_wave):
        raise ValueError("A missing real wave was erroneously represented as playable")
    record_out = {
        "profile": record["profile"],
        "source": record["slug"],
        "sha256": record["sha256"],
        "native_actions": checked["actions"],
        "original_frames": audit["summary"]["original_frames_inspected"],
        "runtime_group_commands": mappings,
        "real_sprites_to_group_mapping_passed": True,
        "visual_likeness_manually_reviewed": False,
        "physical_desktop_playback_qa_passed": False,
        "sound_verified": False,
    }
    print("PINNED_CREATOR_RUNTIME_GROUP_PASS " +
          json.dumps(record_out, ensure_ascii=False, sort_keys=True),
          flush=True)
    return record_out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", choices=("yanfei", "emilie", "both"),
                   default="both")
    args = p.parse_args(argv)
    keys = ("yanfei", "emilie") if args.source == "both" else (args.source,)
    with tempfile.TemporaryDirectory(prefix="artist-to-runtime-") as td:
        for key in keys:
            validate_real_creator(key, Path(td))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
