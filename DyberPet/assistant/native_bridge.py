"""Optional Rust/PyO3 accelerator boundary, disabled by default.

No Rust module is required to use the existing Python desktop pet. Opt-in is
per process: DYBERPET_NATIVE_BACKEND=rust. Missing Rust wheels use the original
Python implementation; exceptions from an *installed* Rust extension propagate
instead of silently weakening integrity validation.

Nothing here changes file-operation or authorization policies.
"""
from __future__ import annotations

import hashlib
import importlib
import os
from pathlib import Path
from typing import Any


def _rust_module():
    if os.environ.get("DYBERPET_NATIVE_BACKEND", "python").lower() != "rust":
        return None
    try:
        return importlib.import_module("dyberpet_native")
    except ModuleNotFoundError as exc:
        # A wheel missing altogether is safe to fall back from. If a module
        # exists but a transitive dependency is broken, preserve the error:
        # silently choosing Python would disguise a defective Rust install.
        if exc.name == "dyberpet_native":
            return None
        raise


def backend_status() -> dict:
    requested = os.environ.get("DYBERPET_NATIVE_BACKEND", "python").lower()
    module = _rust_module()
    return {
        "requested": requested,
        "active": "rust" if module is not None else "python",
        "rust_available": module is not None,
        "fallback": requested == "rust" and module is None,
        "version": module.engine_version() if module is not None else None,
    }


def native_png_metadata(path: str | Path) -> dict[str, Any] | None:
    """Return native PNG IHDR metadata, or None to request Python baseline."""
    engine = _rust_module()
    if engine is None:
        return None
    return engine.png_metadata(str(Path(path)))


def native_batch_png_headers(paths) -> list | None:
    """Read a bounded group of PNG IHDRs in one native call.

    Returns tuples (width, height, depth, color_type), or None entries for
    invalid PNGs. A returned None *for the whole call* means use the original
    Python validation implementation. Native I/O exceptions are propagated.
    """
    engine = _rust_module()
    if engine is None:
        return None
    paths = [str(Path(path)) for path in paths]
    if len(paths) > 10_000:
        raise ValueError("Batch exceeds 10000 PNG paths")
    return engine.batch_png_headers(paths)


def sha256_file(path: str | Path) -> str:
    """Hash a file; exact Python output and errors by default."""
    engine = _rust_module()
    if engine is not None:
        return engine.sha256_file(str(Path(path)))
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
