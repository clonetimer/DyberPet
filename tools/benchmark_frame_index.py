#!/usr/bin/env python3
"""Compare full role-asset audit throughput, not just one synthetic PNG read.

This uses only freshly generated, structurally valid IHDR fixtures. Timing on
ephemeral CI is indicative and MUST NOT become an automatic speed gate.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from DyberPet.assistant.character_fidelity import inspect_character_role
from DyberPet.assistant.native_bridge import backend_status


def _frame(path: Path):
    blob = bytearray(33)
    blob[:8] = b"\x89PNG\r\n\x1a\n"
    blob[12:16] = b"IHDR"
    blob[16:20] = (192).to_bytes(4, "big")
    blob[20:24] = (208).to_bytes(4, "big")
    blob[24] = 8
    blob[25] = 6
    path.write_bytes(blob)


def benchmark(frames: int = 100, rounds: int = 5) -> dict:
    if not (1 <= frames <= 500 and 1 <= rounds <= 20):
        raise ValueError("Frame counts must be 1..500 and rounds 1..20")
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp) / "Guga"
        action = root / "action"
        action.mkdir(parents=True)
        (root / "pet_conf.json").write_text(
            json.dumps({"width": 192, "height": 208}), encoding="utf-8")
        (root / "act_conf.json").write_text(
            json.dumps({
                "default": {"images": "idle"},
                "happy": {"images": "idle"},
                "left_walk": {"images": "left"},
                "right_walk": {"images": "right"},
            }), encoding="utf-8")
        for prefix in ("idle", "left", "right"):
            for i in range(frames):
                _frame(action / f"{prefix}_{i:04d}.png")
        before = os.environ.get("DYBERPET_NATIVE_BACKEND")
        result = {"kind": "synthetic_role_audit_not_user_performance",
                  "number_of_files": frames * 3,
                  "checked_per_prefix": min(frames, 100),
                  "rounds": rounds, "backends": {}}
        reports = {}
        try:
            for mode in ("python", "rust"):
                os.environ["DYBERPET_NATIVE_BACKEND"] = mode
                if mode == "rust" and backend_status()["active"] != "rust":
                    result["backends"][mode] = {"available": False}
                    continue
                durations = []
                for _ in range(rounds):
                    start = time.perf_counter()
                    report = inspect_character_role(root, "Guga")
                    durations.append(time.perf_counter() - start)
                reports[mode] = report
                result["backends"][mode] = {
                    "available": True,
                    "median_ms": round(statistics.median(durations) * 1000, 3),
                    "min_ms": round(min(durations) * 1000, 3),
                }
        finally:
            if before is None:
                os.environ.pop("DYBERPET_NATIVE_BACKEND", None)
            else:
                os.environ["DYBERPET_NATIVE_BACKEND"] = before
        if len(reports) == 2 and reports["python"] != reports["rust"]:
            raise RuntimeError("Role audit report mismatch between backends")
        result["report_parity"] = len(reports) == 2
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=5)
    args = parser.parse_args()
    print(json.dumps(benchmark(args.frames, args.rounds), indent=2))


if __name__ == "__main__":
    main()
