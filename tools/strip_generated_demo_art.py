#!/usr/bin/env python3
"""Remove only recognizably generated low-fidelity chibis from a disposable build.

Run AFTER the frozen binary's 125-demo CI smoke, BEFORE publishing its personal
archive. Never run on a user's installed role library or downloaded artist art.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil


MARKERS = {
    "BUILTIN_CHIBI_DEMO.json": "DyberPet-first-party-abstract-chibi-v1",
    "BUILTIN_MASCOT_DEMO.json": "DyberPet-first-party-mascot-chibi-v1",
}


def inspect_generated_art(root):
    root = Path(root)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Expected a real staged res/role directory")
    found = []
    for folder in root.iterdir():
        if folder.is_symlink():
            raise ValueError("Symlinked role entries are not safe package inputs")
        if not folder.is_dir():
            continue
        for marker, generator in MARKERS.items():
            receipt = folder / marker
            if not receipt.exists() and not receipt.is_symlink():
                continue
            if receipt.is_symlink() or receipt.stat().st_size > 64 * 1024:
                raise ValueError("Invalid generated-art receipt")
            record = json.loads(receipt.read_text(encoding="utf-8"))
            if not isinstance(record, dict) or record.get("generator") != generator:
                raise ValueError("Ambiguous generated-art marker: " + folder.name)
            if marker == "BUILTIN_CHIBI_DEMO.json":
                if not (folder.name.startswith("DemoG_") and
                        record.get("official_character_art") is False and
                        record.get("original_illustration") is True):
                    raise ValueError("Unexpected first-party demo identity")
            elif not (folder.name in ("DemoMascotDoro", "DemoMascotGuga") and
                      record.get("external_artist_sprite_included") is False and
                      record.get("original_geometry") is True):
                raise ValueError("Unexpected mascot demo identity")
            found.append(folder)
            break
    return sorted(found, key=lambda item: item.name)


def remove_generated_art(root, *, expected=125, verify_only=False):
    """Verify precise first-party origin before removing disposable build roles."""
    found = inspect_generated_art(root)
    if verify_only:
        if found:
            raise ValueError("Personal candidate still contains generated placeholders")
        return {"remaining_low_fidelity_demos": 0}
    if len(found) != expected:
        raise ValueError(f"Refusing incomplete stripping: {len(found)} != {expected}")
    for folder in found:
        shutil.rmtree(folder)
    if inspect_generated_art(root):
        raise ValueError("Some generated demo art remains in personal build")
    return {"removed_low_fidelity_demos": len(found),
            "remaining_low_fidelity_demos": 0}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-root", type=Path, required=True)
    parser.add_argument("--expected", type=int, default=125)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(remove_generated_art(args.role_root,
                                           expected=args.expected,
                                           verify_only=args.verify_only)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
