#!/usr/bin/env python3
"""Check a real installed DyberPet role against a specific character dossier.

Does NOT fetch game art, synthesize a copyrighted voice or assign a visual
similarity score without the actual reference images and human review.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from DyberPet.assistant.character_profiles import PROFILES
from DyberPet.assistant.character_fidelity import (
    FidelityError, inspect_character_role,
)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--character", required=True,
                        help="Installed character name, e.g. Doro, 派蒙, 阿丽莎")
    parser.add_argument("--role", type=Path, required=True,
                        help="Existing installed role directory containing pet_conf.json")
    parser.add_argument("--wav", type=Path,
                        help="Optional locally permitted PCM WAV signature sample")
    parser.add_argument("--report", type=Path,
                        help="Save audit JSON; no third-party art is copied")
    args = parser.parse_args(argv)
    try:
        audit = inspect_character_role(args.role, args.character, args.wav)
        payload = json.dumps(audit, ensure_ascii=False, indent=2) + "\n"
        if args.report:
            target = args.report.expanduser()
            if target.is_symlink():
                raise FidelityError("Report destination cannot be a symbolic link")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(payload, encoding="utf-8")
        else:
            if hasattr(sys.stdout, "reconfigure"):
                sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            print(payload, end="")
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(1, "Character audit blocked: " + str(exc) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
