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
    except ImportError:
        return None


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
