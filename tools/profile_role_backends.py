#!/usr/bin/env python3
"""Read-only, process-isolated DyberPet native-vs-Python role audit profiler.

Example with a locally installed and legitimately acquired role:
    python tools/profile_role_backends.py --role res/role/Guga --character Guga

For reproducible CI, without third-party art:
    python tools/profile_role_backends.py --synthetic-frames 100 --rounds 5

Every backend is measured in a *fresh* Python subprocess; no file content,
file names, local paths, screenshots or individual audit findings are emitted.
This profiles resource *auditing*, NOT animation FPS, sound output, or the Qt UI.
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
import tempfile
import time
import tracemalloc


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fixture_frame(path: Path):
    header = bytearray(33)
    header[:8] = b"\x89PNG\r\n\x1a\n"
    header[12:16] = b"IHDR"
    header[16:20] = (192).to_bytes(4, "big")
    header[20:24] = (208).to_bytes(4, "big")
    header[24] = 8
    header[25] = 6
    path.write_bytes(header)


def _create_synthetic(root: Path, frames: int) -> Path:
    import json as _json
    role = root / "Guga"
    assets = role / "action"
    assets.mkdir(parents=True)
    (role / "pet_conf.json").write_text(
        _json.dumps({"width": 192, "height": 208}), encoding="utf-8")
    (role / "act_conf.json").write_text(_json.dumps({
        "default": {"images": "idle"},
        "happy": {"images": "idle"},
        "left_walk": {"images": "left"},
        "right_walk": {"images": "right"},
        "speak": {"images": "talk"},
    }), encoding="utf-8")
    for prefix in ("idle", "left", "right", "talk"):
        for n in range(frames):
            _fixture_frame(assets / f"{prefix}_{n:04d}.png")
    return role


def _worker(args):
    # Import *after* argument parsing to measure warm-up/module import
    # separately from the steady-state audited role latency.
    started = time.perf_counter()
    from DyberPet.assistant.native_bridge import backend_status
    from DyberPet.assistant.character_fidelity import inspect_character_role
    from DyberPet.assistant.character_profiles import resolve_profile
    import_elapsed_ms = (time.perf_counter() - started) * 1000

    backend = backend_status()
    requested = os.environ.get("DYBERPET_NATIVE_BACKEND", "python")
    if requested == "rust" and backend["active"] != "rust":
        print(json.dumps({"available": False, "backend": backend}, sort_keys=True))
        return 0
    role = Path(args.role)
    if (not role.is_dir() or role.is_symlink()
            or resolve_profile(args.character) is None):
        raise ValueError("Role is missing, linked, or has no supported fidelity profile")

    for _ in range(args.warmup):
        inspect_character_role(role, args.character)

    timings = []
    reports = []
    # Python memory tracking itself alters latency, so run it separately
    # *after* steady-state timings instead of during benchmark iterations.
    try:
        import psutil
        process = psutil.Process(os.getpid())
        rss_before = process.memory_info().rss
    except ImportError:
        process = None
        rss_before = None
    for _ in range(args.rounds):
        t = time.perf_counter()
        report = inspect_character_role(role, args.character)
        timings.append((time.perf_counter() - t) * 1000)
        reports.append(hashlib.sha256(json.dumps(
            report, sort_keys=True, ensure_ascii=True,
            separators=(",", ":")).encode("utf-8")).hexdigest())

    tracemalloc.start()
    try:
        inspect_character_role(role, args.character)
        _current, python_alloc_peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    rss_after = process.memory_info().rss if process is not None else None
    if len(set(reports)) != 1:
        raise RuntimeError("Role report changed during benchmark; re-run with stable assets")
    result = {
        "available": True,
        "backend": backend,
        "import_elapsed_ms": round(import_elapsed_ms, 3),
        "audit_median_ms": round(statistics.median(timings), 3),
        "audit_min_ms": round(min(timings), 3),
        "audit_max_ms": round(max(timings), 3),
        "python_alloc_peak_bytes": python_alloc_peak,
        "rss_before_bytes": rss_before,
        "rss_after_bytes": rss_after,
        "rss_note": "RSS snapshots, not peak RSS; requires optional psutil",
        "report_sha256": reports[0],
        "rounds": args.rounds,
    }
    print(json.dumps(result, sort_keys=True))
    return 0


def _run_process(role: Path, character: str, mode: str, rounds: int, warmup: int):
    command = [sys.executable, "-I", str(Path(__file__).resolve()),
               "--worker", "--role", str(role),
               "--character", character, "--rounds", str(rounds),
               "--warmup", str(warmup)]
    env = dict(os.environ)
    env["DYBERPET_NATIVE_BACKEND"] = mode
    before = time.perf_counter()
    result = subprocess.run(
        command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", timeout=90,
        check=False)
    wall_ms = (time.perf_counter() - before) * 1000
    if result.returncode:
        # Avoid printing the local path from tracebacks into shared CI logs.
        raise RuntimeError(
            f"{mode} profiling subprocess failed ({result.returncode}); "
            "run locally with --worker for diagnostic details")
    try:
        payload = json.loads(result.stdout.strip())
    except ValueError as exc:
        raise RuntimeError("Profiler subprocess did not return valid JSON") from exc
    payload["process_elapsed_ms"] = round(wall_ms, 3)
    return payload


def profile(role: Path, character: str, rounds: int = 5,
            warmup: int = 1, require_rust: bool = False):
    if not (1 <= rounds <= 20 and 0 <= warmup <= 5):
        raise ValueError("Rounds must be 1..20 and warmup must be 0..5")
    candidate = Path(role).expanduser()
    if candidate.is_symlink():
        raise ValueError("Role/action must be ordinary directories")
    role = candidate.resolve(strict=True)
    if not role.is_dir() or (role / "action").is_symlink():
        raise ValueError("Role/action must be ordinary directories")
    from DyberPet.assistant.character_profiles import resolve_profile
    profile_data = resolve_profile(character)
    if profile_data is None:
        raise ValueError("No registered fidelity profile for this character")

    values = {}
    for mode in ("python", "rust"):
        values[mode] = _run_process(role, character, mode, rounds, warmup)
    rust = values["rust"]
    if require_rust and not rust.get("available"):
        raise RuntimeError("Required Rust extension is unavailable or not active")
    parity = (values["python"]["report_sha256"] == rust["report_sha256"]
              if rust.get("available") else None)
    if parity is False:
        raise RuntimeError("Python/Rust reports differ; performance result rejected")
    return {
        "schema_version": 1,
        "scope": "role_audit_only_not_animation_or_voice",
        "role_profile": profile_data.key,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
        "host": sys.platform,
        "warmup": warmup,
        "rounds": rounds,
        "report_parity": parity,
        "no_role_asset_content_emitted": True,
        "backend_measurements": values,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--role", type=Path, help="Installed local role folder")
    parser.add_argument("--character", default="Guga",
                        help="Registered role name (Guga, Doro, Paimon, etc.)")
    parser.add_argument("--synthetic-frames", type=int,
                        help="Build disposable synthetic Guga fixture (1..200)")
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--warmup", type=int, default=1)
    parser.add_argument("--require-rust", action="store_true")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        if args.role is None:
            parser.error("--worker requires --role")
        return _worker(args)
    if bool(args.role) == (args.synthetic_frames is not None):
        parser.error("Select exactly one of --role or --synthetic-frames")
    if args.synthetic_frames is not None:
        if not 1 <= args.synthetic_frames <= 200:
            parser.error("--synthetic-frames must be between 1 and 200")
        with tempfile.TemporaryDirectory() as tmp:
            role = _create_synthetic(Path(tmp), args.synthetic_frames)
            result = profile(role, "Guga", args.rounds, args.warmup,
                             args.require_rust)
            result["fixture"] = "generated_33_byte_png_headers_not_real_art"
    else:
        result = profile(args.role, args.character, args.rounds,
                         args.warmup, args.require_rust)
        result["fixture"] = "user_provided_local_assets_no_content_export"
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
