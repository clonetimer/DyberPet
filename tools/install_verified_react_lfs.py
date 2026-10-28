#!/usr/bin/env python3
"""Install only independently verified original React-Shimeji LFS sprites.

The old native-import tool required users to download the actual .ts module.
This wrapper retrieves byte-for-byte pinned modules in the cloud / user machine
and passes them to the existing safe literal-data decoder. Source code is NEVER
executed. Personal-use consent and creator licensing remain the user's choice.
"""
from __future__ import annotations

import hashlib
from pathlib import Path
import tempfile

try:
    from .react_shimeji_source_leads import verified_lfs_sources
    from .probe_missing_react_lfs import fetch_matching_source
    from .install_pinned_react_shimeji import install_pinned_react_shimeji
except ImportError:
    from tools.react_shimeji_source_leads import verified_lfs_sources
    from tools.probe_missing_react_lfs import fetch_matching_source
    from tools.install_pinned_react_shimeji import install_pinned_react_shimeji

ALLOWED = {"amber": "genshin_amber", "fischl": "genshin_fischl",
           "neuvillette": "genshin_neuvillette", "wriothesley": "genshin_wriothesley"}


def install_verified_react_lfs(key, role_root, *, confirmed=False,
                               fetch=fetch_matching_source,
                               native_import=install_pinned_react_shimeji):
    """Acquire exact pinned LFS bytes, import original PNGs without replacement."""
    if not confirmed:
        raise ValueError("Explicit personal-use source consent required")
    profile = ALLOWED.get(key)
    if profile is None:
        raise ValueError("Only four independently source-verified React-Shimeji roles can be auto-installed")
    registered = verified_lfs_sources()
    trusted = registered.get(profile)
    if trusted is None or trusted["profile"] != profile:
        raise ValueError("Missing independently verified LFS source attestation")
    root = Path(role_root).expanduser()
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError("Unsafe or linked destination")
    raw, verified_url = fetch(profile)
    if (not isinstance(raw, bytes) or len(raw) != trusted["verified_bytes"] or
            hashlib.sha256(raw).hexdigest() != trusted["sha256"]):
        raise ValueError("LFS source does not match registered full-byte SHA-256")
    # Source URL is returned for audit only. We do not execute JavaScript,
    # include npm dependencies, follow untrusted redirects or invent PNGs.
    if not verified_url.startswith((
        "https://media.githubusercontent.com/media/",
        "https://raw.githubusercontent.com/")):
        raise ValueError("Source URL not permitted")
    with tempfile.TemporaryDirectory(prefix="dyberpet-react-lfs-") as tmp:
        verified_module = Path(tmp) / "verified-index.ts"
        verified_module.write_bytes(raw)
        imported = native_import(verified_module, root, profile=profile,
                                 confirmed=True)
    installed = Path(imported)
    if installed.is_symlink() or not installed.is_dir():
        raise ValueError("Native React-Shimeji installer gave invalid destination")
    receipt = installed / "PERSONAL_IMPORT.json"
    if receipt.is_symlink() or not receipt.is_file():
        raise ValueError("Native import did not write original source receipt")
    return {
        "profile": profile, "folder": installed.name,
        "full_lfs_sha256_verified": True,
        "source_bytes": len(raw),
        "original_art_installed_structurally": True,
        "human_likeness_verified": False,
        "voice_included": False,
        "license_for_redistribution_verified": False,
    }
