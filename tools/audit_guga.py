#!/usr/bin/env python3
"""Audit local Guga role animation and optionally a user-supplied WAV.

Does NOT download media and never labels work as a verified copy of a source.
Run from repository root: python tools/audit_guga.py --role "res/role/Guga"
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from DyberPet.assistant.character_fidelity import FidelityError, inspect_guga_role


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", required=True, type=Path,
                        help="Existing locally installed DyberPet role folder")
    parser.add_argument("--wav", type=Path,
                        help="Optional locally obtained PCM WAV for technical validation")
    parser.add_argument("--report", type=Path,
                        help="Optional destination for JSON audit report (never media)")
    args = parser.parse_args(argv)
    try:
        result = inspect_guga_role(args.role, args.wav)
    except (FidelityError, OSError, ValueError) as exc:
        parser.exit(1, "Guga audit blocked: " + str(exc) + "\n")
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        target = args.report.expanduser()
        if target.is_symlink():
            parser.exit(1, "Report destination must not be a symlink\n")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")
    else:
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
