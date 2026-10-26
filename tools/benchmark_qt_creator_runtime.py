#!/usr/bin/env python3
"""R7 offscreen Qt runtime probe using pinned, original creator sprites.

Does NOT measure physical monitor FPS, true desktop startup, or user-perceived
role switching. Benchmarks PySide6 QPixmap decode, the ACTUAL PetConfig
constructor, and an offscreen QLabel repaint loop in isolated subprocesses.
No user assets or screenshots leave the runner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.benchmark_creator_asset_backends import _validate_creator
from tools.install_artist_codex import SOURCES


def _worker(root: Path, kind: str, *, ticks: int):
    source = _validate_creator(root, kind)
    request = os.environ.get("DYBERPET_NATIVE_BACKEND", "python")
    from DyberPet.assistant.native_bridge import backend_status
    backend = backend_status()
    if backend["active"] != request:
        raise RuntimeError("Qt worker used wrong native backend (fallback forbidden)")
    start = time.perf_counter()
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication, QLabel
    from PySide6.QtGui import QImage, QPixmap
    from DyberPet import conf
    app = QApplication.instance() or QApplication([])
    app.processEvents()
    qt_setup_ms = (time.perf_counter() - start) * 1000
    # The native app reads this module variable; isolate it to the worker.
    conf.basedir = str(root.parent.parent)
    pics = {}
    frames = sorted((source / "action").glob("*.png"))
    if not 4 <= len(frames) <= 2400:
        raise RuntimeError("Unexpected number of original source PNG frames")
    begun = time.perf_counter()
    for file in frames:
        if file.is_symlink() or not file.is_file() or file.stat().st_size > 8*1024*1024:
            raise RuntimeError("Unsafe source frame during Qt benchmark")
        pix = QPixmap(str(file))
        if pix.isNull() or pix.width() > 4096 or pix.height() > 4096:
            raise RuntimeError("Qt cannot decode authentic source frame")
        pics[file.stem] = pix
    pixmap_decode_ms = (time.perf_counter() - begun) * 1000
    begun = time.perf_counter()
    pet = conf.PetConfig.init_config(source.name, pics)
    petconfig_ms = (time.perf_counter() - begun) * 1000
    if not pet.default or not pet.default.images:
        raise RuntimeError("Original creator role has no playable Qt idle animation")
    sequence = []
    for key in ("default", "left", "right"):
        action = getattr(pet, key, None)
        if action is not None:
            sequence.extend(action.images)
    if len(sequence) < 2:
        raise RuntimeError("Not enough creator frames to test Qt repaint")
    # Identical pixel digest makes a parity mismatch fatal. This is computed
    # OUTSIDE timing so Rust/Python receive the same isolated workload.
    fingerprint = hashlib.sha256()
    for frame in sequence:
        image = frame.toImage().convertToFormat(QImage.Format_RGBA8888)
        fingerprint.update(image.width().to_bytes(4, "big"))
        fingerprint.update(image.height().to_bytes(4, "big"))
        fingerprint.update(bytes(image.bits()))
    widget = QLabel()
    widget.resize(pet.default.images[0].size())
    widget.show()
    app.processEvents()
    begun = time.perf_counter()
    for index in range(ticks):
        widget.setPixmap(sequence[index % len(sequence)])
        widget.repaint()
        app.processEvents()
    qt_repaint_ms = (time.perf_counter() - begun) * 1000
    widget.close()
    app.processEvents()
    try:
        import psutil
        rss = psutil.Process().memory_info().rss
    except ImportError:
        rss = None
    return {
        "available": True,
        "backend": backend["active"],
        "scope": "offscreen_qt_decode_config_repaint_not_physical_fps",
        "frame_count": len(frames),
        "tick_count": ticks,
        "pixel_sha256": fingerprint.hexdigest(),
        "qt_setup_ms": round(qt_setup_ms, 3),
        "pixmap_decode_ms": round(pixmap_decode_ms, 3),
        "petconfig_ms": round(petconfig_ms, 3),
        "qt_repaint_ms": round(qt_repaint_ms, 3),
        "rss_snapshot_bytes": rss,
    }


def _run_worker(root: Path, kind: str, mode: str, ticks: int):
    env = dict(os.environ)
    env["DYBERPET_NATIVE_BACKEND"] = mode
    env["DYBERPET_REQUIRE_RUST"] = "1" if mode == "rust" else "0"
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    cmd = [sys.executable, "-I", str(Path(__file__).resolve()),
           "--worker", "--role-root", str(root), "--kind", kind,
           "--ticks", str(ticks)]
    started = time.perf_counter()
    result = subprocess.run(cmd, env=env, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=90,
                            check=False)
    if result.returncode:
        raise RuntimeError("Isolated Qt backend failed; inspect locally in --worker mode")
    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        raise RuntimeError("Isolated Qt probe did not return JSON") from exc
    payload["process_ms"] = round((time.perf_counter() - started)*1000, 3)
    return payload


def paired_qt(root: Path, kind: str, *, blocks=2, ticks=96, runner=_run_worker):
    if kind not in SOURCES or not 1 <= blocks <= 4 or not 8 <= ticks <= 512:
        raise ValueError("Unsupported role or R7 benchmark bounds")
    root = Path(root).expanduser()
    _validate_creator(root, kind)
    rows = {"python": [], "rust": []}
    observed_hash = None
    for block in range(blocks):
        order = ("python", "rust", "rust", "python") if block % 2 == 0 else (
            "rust", "python", "python", "rust")
        for mode in order:
            sample = runner(root, kind, mode, ticks)
            if (sample.get("available") is not True or
                    sample.get("backend") != mode):
                raise RuntimeError("R7 backend unavailable or silently fell back")
            digest = sample.get("pixel_sha256")
            if not isinstance(digest, str) or len(digest) != 64:
                raise RuntimeError("R7 Qt pixel fingerprint missing")
            if observed_hash is not None and digest != observed_hash:
                raise RuntimeError("Qt creator frame pixels differ between backends")
            observed_hash = digest
            rows[mode].append(sample)

    def describe(mode):
        samples = rows[mode]
        def median(key):
            nums = [x[key] for x in samples
                    if isinstance(x.get(key), (float,int))]
            return round(statistics.median(nums), 3) if nums else None
        return {"processes": len(samples),
                "qt_setup_median_ms": median("qt_setup_ms"),
                "pixmap_decode_median_ms": median("pixmap_decode_ms"),
                "petconfig_median_ms": median("petconfig_ms"),
                "qt_repaint_median_ms": median("qt_repaint_ms"),
                "process_median_ms": median("process_ms"),
                "rss_snapshot_median_bytes": median("rss_snapshot_bytes")}

    return {
        "schema_version": 1,
        "scope": "offscreen_qt_decode_config_repaint_not_physical_fps",
        "kind": kind,
        "blocks": blocks,
        "ticks_per_worker": ticks,
        "counterbalanced": "ABBA_BAAB",
        "qt_pixel_parity": True,
        "pixel_sha256": observed_hash,
        "no_original_art_exported": True,
        "not_a_physical_windows_test": True,
        "timing_not_a_speed_acceptance_gate": True,
        "backends": {"python": describe("python"), "rust": describe("rust")},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--role-root", required=True, type=Path)
    ap.add_argument("--kind", required=True, choices=tuple(SOURCES))
    ap.add_argument("--blocks", type=int, default=2)
    ap.add_argument("--ticks", type=int, default=96)
    ap.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.worker:
        output = _worker(args.role_root, args.kind, ticks=args.ticks)
    else:
        output = paired_qt(args.role_root, args.kind, blocks=args.blocks,
                           ticks=args.ticks)
    print(json.dumps(output, sort_keys=True, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
