#!/usr/bin/env python3
"""R6 paired, counterbalanced audit benchmark for locally installed creator art.

The script NEVER downloads a role, modifies assets, starts Qt, or publishes art.
Use a pinned-source installer separately to create an ephemeral source role.
Each run launches a NEW process for each backend in ABBA / BAAB order.
Parity is required across ALL processes before any timing can be reported.
Audit time is not animation FPS, latency, or end-to-end application startup.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.install_artist_codex import REVISION, REPO, SOURCES
from tools.profile_role_backends import _run_process


def _validate_creator(root: Path, kind: str):
    if kind not in SOURCES:
        raise ValueError("Unknown reviewed artist source")
    source_id, _name, _profile, _manifest, _atlas = SOURCES[kind]
    role = root / ("SourceCodex" + "".join(part.title() for part in kind.split("_")))
    if root.is_symlink() or role.is_symlink() or (role / "action").is_symlink():
        raise ValueError("Refusing linked creator art or action directory")
    if not role.is_dir() or not (role / "action").is_dir():
        raise ValueError("Install the reviewed original creator role before benchmarking")
    receipt = role / "PERSONAL_IMPORT.json"
    conversion = role / "IMPORT_REPORT.json"
    if any(p.is_symlink() or not p.is_file() or p.stat().st_size > 32768
           for p in (receipt, conversion)):
        raise ValueError("Missing or oversized original-source receipts")
    try:
        provenance = json.loads(receipt.read_text(encoding="utf-8"))
        geometry = json.loads(conversion.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError) as exc:
        raise ValueError("Invalid creator-source metadata") from exc
    if (provenance.get("source_repository") != REPO or
            provenance.get("source_commit") != REVISION or
            provenance.get("source_id") != source_id or
            provenance.get("selected_profile") != SOURCES[kind][2] or
            geometry.get("preserve_source_frames") is not True or
            geometry.get("source_pixel_integrity_verified") is not True or
            geometry.get("aligned_frames_per_action") != {}):
        raise ValueError("Artwork was not installed through pinned pixel-preserving source")
    return role


def paired_creator_audit(root: Path, kind: str, *, blocks=2, rounds=3,
                         warmup=1, require_rust=True, runner=_run_process):
    if not (1 <= blocks <= 4 and 1 <= rounds <= 10 and 0 <= warmup <= 5):
        raise ValueError("Blocks 1..4, rounds 1..10 and warmup 0..5 required")
    # Reject unsupported profiles before even touching their local data.
    profile_names = {"nahida": "Nahida", "paimon": "Paimon",
                     "furina": "Furina", "klee": "Klee"}
    if kind not in profile_names:
        raise ValueError("The source has no supported character audit profile")
    role = _validate_creator(Path(root).expanduser(), kind)
    from DyberPet.assistant.character_profiles import resolve_profile
    name = profile_names[kind]
    if resolve_profile(name) is None:
        raise ValueError("No supported fidelity profile for source")
    records = {"python": [], "rust": []}
    hashes = []
    for block in range(blocks):
        # ABBA / BAAB order compensates for shared file cache and thermal drift.
        order = ("python", "rust", "rust", "python") if block % 2 == 0 else (
            "rust", "python", "python", "rust")
        for mode in order:
            row = runner(role, name, mode, rounds, warmup)
            if not row.get("available"):
                if mode == "rust" and not require_rust:
                    return {
                        "schema_version": 1,
                        "scope": "creator_role_audit_only_not_animation_fps",
                        "source": "pinned_creator_atlas_local_only",
                        "character": kind,
                        "rust_available": False,
                        "report_parity": None,
                        "measured_speedup": None,
                        "no_role_asset_content_emitted": True,
                    }
                raise RuntimeError("Native backend unavailable; cannot claim paired benchmark")
            if row.get("backend", {}).get("active") != mode:
                raise RuntimeError("Measured worker did not activate requested backend")
            digest = row.get("report_sha256")
            if (not isinstance(digest, str) or len(digest) != 64 or
                    any(c not in "0123456789abcdef" for c in digest)):
                raise RuntimeError("Worker did not return a valid report fingerprint")
            hashes.append(digest)
            records[mode].append(row)
            if len(set(hashes)) != 1:
                raise RuntimeError("Python/Rust role reports differ or changed during test")

    def summarize(mode):
        samples = records[mode]
        def metric(key):
            values = [r[key] for r in samples if isinstance(r.get(key), (int, float))]
            return round(statistics.median(values), 3) if values else None
        return {"processes": len(samples),
                "audit_median_ms": metric("audit_median_ms"),
                "process_elapsed_median_ms": metric("process_elapsed_ms"),
                "import_elapsed_median_ms": metric("import_elapsed_ms"),
                "rss_after_median_bytes": metric("rss_after_bytes"),
                "python_alloc_peak_median_bytes": metric("python_alloc_peak_bytes")}

    python = summarize("python")
    rust = summarize("rust")
    speedup = (round(python["audit_median_ms"] / rust["audit_median_ms"], 3)
               if rust["audit_median_ms"] and python["audit_median_ms"] is not None
               else None)
    return {
        "schema_version": 1,
        "scope": "creator_role_audit_only_not_animation_fps",
        "source": "pinned_creator_atlas_local_only",
        "character": kind,
        "counterbalanced_order": "ABBA_BAAB",
        "blocks": blocks,
        "worker_rounds": rounds,
        "report_parity": True,
        "report_sha256": hashes[0],
        "measured_speedup": speedup,
        "speedup_note": "Ratio of audit medians (Python/Rust); >1 means Rust faster. Never a GUI FPS claim.",
        "memory_note": "RSS snapshots and Python allocations are not whole-process memory peaks.",
        "no_role_asset_content_emitted": True,
        "backends": {"python": python, "rust": rust},
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role-root", type=Path, required=True)
    parser.add_argument("--kind", choices=tuple(SOURCES), required=True)
    parser.add_argument("--blocks", type=int, default=2)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--allow-missing-rust", action="store_true")
    args = parser.parse_args(argv)
    result = paired_creator_audit(
        args.role_root, args.kind, blocks=args.blocks,
        rounds=args.rounds, warmup=args.warmup,
        require_rust=not args.allow_missing_rust)
    print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
