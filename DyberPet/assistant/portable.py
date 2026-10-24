"""Path and resource checks for the Windows portable EXE.

DyberPet's legacy Windows UI expects res/ and writable data/ adjacent to the
executable. Never change the working directory when running from source.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


REQUIRED_RESOURCES = (
    "res/language/language.json",
    "res/role/sys/sys_conf.json",
    "res/icons/icon.png",
    "res/items",
    "res/pet",
)



def resource_root(source_module=None, *, frozen=None, executable=None):
    """Absolute res/ parent for source and PyInstaller --onedir on any OS.

    Source module lives under DyberPet/*.py; frozen module __file__ can
    reference the bundled tree rather than the writable onedir root.
    """
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return Path(executable or sys.executable).resolve().parent
    if source_module is None:
        raise ValueError("Source resource root requires the importing module path")
    return Path(source_module).resolve().parent.parent


def initialize_portable_directory(frozen=None, executable=None):
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if not frozen:
        return None
    executable = Path(executable or sys.executable).resolve()
    root = executable.parent
    os.chdir(root)
    return root


def inspect_assets(root):
    root = Path(root)
    missing = [p for p in REQUIRED_RESOURCES if not (root / p).exists()]
    return {"root": str(root), "ok": not missing, "missing": missing}
