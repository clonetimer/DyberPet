#!/usr/bin/env python3
"""Small *indicative* Python/Rust comparison, not a release performance claim.

Run after maturin wheel installation:
  python tools/benchmark_rust_core.py --rounds 5 --frames 2000

Prints cold-safe median timings and hashes on synthetic, local data only.
File system cache and PyO3 boundary overhead can make Python faster here.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time
from pathlib import Path

from DyberPet.assistant.character_fidelity import png_metadata
from DyberPet.assistant.native_bridge import backend_status, sha256_file


def benchmark(frames: int, rounds: int, hash_mb: int) -> dict:
    if not (10 <= frames <= 100000 and 1 <= rounds <= 20 and 1 <= hash_mb <= 32):
        raise ValueError("Out-of-bounds benchmark request")
    with tempfile.TemporaryDirectory() as temp:
        frame = Path(temp) / "original-synthetic.png"
        header = bytearray(33)
        header[:8] = b"\x89PNG\r\n\x1a\n"
        header[12:16] = b"IHDR"
        header[16:20] = (192).to_bytes(4, "big")
        header[20:24] = (208).to_bytes(4, "big")
        header[24:26] = bytes((8, 6))
        frame.write_bytes(header)
        blob = Path(temp) / "original-synthetic.wav"
        blob.write_bytes(bytes(range(256)) * (4096 * hash_mb))
        results = {}
        initial = os.environ.get("DYBERPET_NATIVE_BACKEND")
        try:
            for mode in ("python", "rust"):
                os.environ["DYBERPET_NATIVE_BACKEND"] = mode
                if mode == "rust" and backend_status()["active"] != "rust":
                    results[mode] = {"available": False}
                    continue
                png_results, hash_results = [], []
                for _ in range(rounds):
                    start = time.perf_counter()
                    for _i in range(frames):
                        png_metadata(frame)
                    png_results.append(time.perf_counter() - start)
                    start = time.perf_counter()
                    checksum = sha256_file(blob)
                    hash_results.append(time.perf_counter() - start)
                results[mode] = {
                    "available": True,
                    "png_count": frames,
                    "png_median_s": round(statistics.median(png_results), 6),
                    "hash_size_mb": hash_mb,
                    "hash_median_s": round(statistics.median(hash_results), 6),
                    "sha256": checksum,
                }
        finally:
            if initial is None:
                os.environ.pop("DYBERPET_NATIVE_BACKEND", None)
            else:
                os.environ["DYBERPET_NATIVE_BACKEND"] = initial
        if results["rust"].get("available") and (
            results["python"]["sha256"] != results["rust"]["sha256"]
        ):
            raise RuntimeError("Native/Python hashing mismatch")
        return {
            "benchmark_type": "synthetic_local_indicative_only",
            "passes": rounds,
            "backends": results,
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=2000)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--hash-mb", type=int, default=4)
    args = parser.parse_args()
    print(json.dumps(
        benchmark(args.frames, args.rounds, args.hash_mb), indent=2))


if __name__ == "__main__":
    main()
